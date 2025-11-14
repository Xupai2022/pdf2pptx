"""
Table Detector - Detects table structures in PDF pages
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import fitz

logger = logging.getLogger(__name__)


class TableDetector:
    """
    Detects table structures in PDF pages by analyzing grid patterns of shapes.
    Tables are identified by regular rows and columns of rectangles.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Table Detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        # Table cells should be well-aligned (within 3px tolerance)
        self.alignment_tolerance = config.get('table_alignment_tolerance', 3.0)
        # Minimum number of rows/cols to consider as table
        self.min_table_rows = config.get('min_table_rows', 2)
        self.min_table_cols = config.get('min_table_cols', 2)
        
    def detect_tables(self, shapes: List[Dict[str, Any]], page: fitz.Page, 
                      text_elements: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Detect table regions in a page by analyzing shape grid patterns.
        
        Supports两种表格检测模式：
        1. 矩形单元格表格（Rectangle-based tables）：每个cell是完整矩形
        2. 线框式表格（Line-based tables）：使用线条绘制边框的表格
        
        Args:
            shapes: List of shape elements from parser
            page: PyMuPDF page object
            text_elements: List of text elements (optional, for cell content mapping)
            
        Returns:
            List of table region dictionaries with bbox, rows, cols info
        """
        if len(shapes) < self.min_table_rows * self.min_table_cols:
            return []
        
        tables = []
        
        # MODE 1: Rectangle-based table detection (existing logic)
        # Find rectangular shapes that could be table cells
        cell_candidates = self._filter_table_cell_candidates(shapes)
        
        if len(cell_candidates) >= self.min_table_rows * self.min_table_cols:
            # Detect grid structures from rectangles
            rect_tables = self._detect_grid_structures(cell_candidates, page)
            tables.extend(rect_tables)
            logger.info(f"Rectangle-based detection found {len(rect_tables)} table(s)")
        
        # MODE 2: Line-based table detection (new logic)
        # Detect tables constructed from line segments
        line_tables = self._detect_line_based_tables(shapes, page)
        if line_tables:
            logger.info(f"Line-based detection found {len(line_tables)} table(s)")
            tables.extend(line_tables)
        
        # Remove overlapping tables (prefer rectangle-based over line-based)
        tables = self._remove_overlapping_tables(tables)
        
        # Populate cell contents if text_elements provided
        if text_elements:
            for table in tables:
                self._populate_table_cells(table, text_elements)
        
        for table in tables:
            logger.info(f"Detected table region: bbox={table['bbox']}, "
                       f"{table['rows']}x{table['cols']} cells")
        
        return tables
    
    def _filter_shapes_outside_charts(self, shapes: List[Dict[str, Any]], 
                                       chart_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out shapes that overlap significantly with chart regions.
        
        This prevents chart elements (pie slices, bar segments, legend boxes, lines)
        from being mistakenly identified as table cells.
        
        CRITICAL: For lines, use CENTER POINT overlap check instead of area overlap
        because lines have very small area but can span across regions.
        
        Args:
            shapes: List of shape elements
            chart_regions: List of chart region dictionaries with 'bbox' key
            
        Returns:
            Filtered list of shapes outside chart regions
        """
        if not chart_regions:
            return shapes
        
        filtered = []
        
        for shape in shapes:
            shape_bbox = (shape['x'], shape['y'], shape['x2'], shape['y2'])
            shape_type = shape.get('shape_type', 'rectangle')
            
            # Calculate shape center point
            shape_center_x = (shape_bbox[0] + shape_bbox[2]) / 2
            shape_center_y = (shape_bbox[1] + shape_bbox[3]) / 2
            
            # Check if shape overlaps significantly with any chart
            is_in_chart = False
            for chart in chart_regions:
                chart_bbox = chart.get('bbox')
                if not chart_bbox:
                    continue
                
                # CRITICAL: Different strategies for lines vs rectangles
                # Lines: Check if center point is in chart region
                # Rectangles: Check if > 50% area overlaps with chart
                
                if shape_type == 'line':
                    # For lines, check if center point is within chart bbox
                    if (chart_bbox[0] <= shape_center_x <= chart_bbox[2] and
                        chart_bbox[1] <= shape_center_y <= chart_bbox[3]):
                        is_in_chart = True
                        logger.debug(f"Filtered line in chart: center=({shape_center_x:.1f}, {shape_center_y:.1f}) in chart bbox={chart_bbox}")
                        break
                else:
                    # For rectangles, check area overlap
                    overlap_x = max(0, min(shape_bbox[2], chart_bbox[2]) - max(shape_bbox[0], chart_bbox[0]))
                    overlap_y = max(0, min(shape_bbox[3], chart_bbox[3]) - max(shape_bbox[1], chart_bbox[1]))
                    overlap_area = overlap_x * overlap_y
                    
                    # Calculate shape area
                    shape_area = (shape_bbox[2] - shape_bbox[0]) * (shape_bbox[3] - shape_bbox[1])
                    
                    # If > 50% of shape overlaps with chart, exclude it
                    if shape_area > 0 and overlap_area > shape_area * 0.5:
                        is_in_chart = True
                        logger.debug(f"Filtered shape in chart: bbox={shape_bbox}, overlap={overlap_area:.1f}/{shape_area:.1f}")
                        break
            
            if not is_in_chart:
                filtered.append(shape)
        
        return filtered
    
    def _filter_table_cell_candidates(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter shapes that could be table cells.
        
        Table cells are typically:
        - Rectangles (not lines or curves)
        - Similar sizes (not too large)
        - Have defined borders or fills
        
        CRITICAL IMPROVEMENT: Filter out both page backgrounds and table backgrounds
        by detecting rectangles that are significantly larger than typical cells.
        
        CRITICAL FIX: Filter out decorative lines and bars that look like table cells
        but are not part of real tables. Real table cells have balanced dimensions.
        
        Args:
            shapes: List of shape elements
            
        Returns:
            Filtered list of potential table cells
        """
        candidates = []
        
        # First pass: collect all shapes with basic size filtering
        for shape in shapes:
            # Must be a rectangle with reasonable size
            width = shape.get('width', 0)
            height = shape.get('height', 0)
            
            # CRITICAL FIX: Filter out very thin rectangles (lines/bars)
            # Real table cells have BOTH width and height >= 10pt
            # This filters:
            # - Vertical lines (width < 10pt)
            # - Horizontal lines (height < 10pt)  
            # - Decorative bars like page 16's 149.8x15.8pt and 120.8x18.0pt rectangles
            if width < 10 or height < 10:
                continue
            
            # CRITICAL FIX: Filter out extremely narrow decorative bars
            # Challenge: Both decorative bars and real table cells can have high aspect ratios!
            # - Decorative bars: 149.8pt x 15.8pt (9.5:1), 120.8pt x 18.0pt (6.7:1)
            # - Real table cells: 172.0pt x 21.5pt (8:1), 421.3pt x 21.5pt (19.6:1)
            # 
            # SOLUTION: Use stricter criteria for small/thin shapes, more lenient for larger shapes
            # - If height < 20pt AND aspect_ratio > 6:1 → likely decorative bar
            # - If height >= 20pt → allow higher ratios (table cells can be wide)
            # 
            # This filters out page 16's decorative bars (15.8pt, 18.0pt height)
            # while keeping page 8's table cells (21.5pt height)
            aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 100
            
            # STRICT filtering for very thin shapes (height < 20pt)
            if height < 20 and aspect_ratio > 6:
                logger.debug(f"Filtered thin decorative bar: {width:.1f}x{height:.1f}pt (height<20pt, aspect ratio {aspect_ratio:.1f}:1 > 6:1)")
                continue
            
            # LENIENT filtering for normal-height shapes (height >= 20pt)
            # Only filter extremely wide bars (> 25:1) to catch title/section bars
            if height >= 20 and aspect_ratio > 25:
                logger.debug(f"Filtered wide decorative bar: {width:.1f}x{height:.1f}pt (aspect ratio {aspect_ratio:.1f}:1 > 25:1)")
                continue
            
            # Has stroke or fill (visible cell)
            has_stroke = shape.get('stroke_color') is not None
            has_fill = shape.get('fill_color') is not None
            
            if has_stroke or has_fill:
                candidates.append(shape)
        
        if not candidates:
            return []
        
        # Second pass: Filter out background rectangles using statistical analysis
        # STRATEGY: Calculate median cell height, filter out cells that are
        # significantly larger than the median (likely backgrounds)
        
        heights = [c['height'] for c in candidates]
        widths = [c['width'] for c in candidates]
        
        # Sort heights to find median and percentiles
        sorted_heights = sorted(heights)
        sorted_widths = sorted(widths)
        
        # Calculate 75th percentile height (typical max cell height)
        idx_75 = int(len(sorted_heights) * 0.75)
        height_75th = sorted_heights[idx_75] if sorted_heights else 50
        
        # Calculate 75th percentile width
        idx_75_w = int(len(sorted_widths) * 0.75)
        width_75th = sorted_widths[idx_75_w] if sorted_widths else 200
        
        # CRITICAL THRESHOLD: Background rectangles are typically much larger than typical cells
        # IMPORTANT: Use AREA-BASED filtering instead of height/width separately
        # Reason: Merged cells can be tall (e.g., 154.8pt) but narrow (64.5pt)
        #         while table backgrounds are both tall (154.8pt) AND wide (657.8pt)
        # Strategy: Filter by area = width * height
        
        # Calculate typical cell area (75th percentile)
        areas = [c['width'] * c['height'] for c in candidates]
        sorted_areas = sorted(areas)
        idx_75_area = int(len(sorted_areas) * 0.75)
        area_75th = sorted_areas[idx_75_area] if sorted_areas else 1000
        
        # CRITICAL: Background rectangles have area > 10x typical cell area
        # Examples:
        # - Typical cell: 172pt × 21.5pt = 3,698 sq.pt
        # - Merged cell (first column): 64.5pt × 154.8pt = 9,985 sq.pt (2.7x)
        # - Table background: 657.8pt × 154.8pt = 101,827 sq.pt (27.5x)
        # - Page background: 675pt × 3482pt = 2,350,350 sq.pt (635x)
        background_area_threshold = area_75th * 10
        
        logger.debug(f"Cell area 75th percentile: {area_75th:.0f} sq.pt, "
                    f"background threshold: {background_area_threshold:.0f} sq.pt")
        logger.debug(f"Cell height 75th: {height_75th:.1f}pt, width 75th: {width_75th:.1f}pt")
        
        # Filter out background rectangles by area
        filtered_candidates = []
        for shape in candidates:
            height = shape['height']
            width = shape['width']
            area = width * height
            
            # Filter by area
            if area > background_area_threshold:
                logger.debug(f"Filtered out large background: {width:.1f}x{height:.1f}pt "
                           f"(area: {area:.0f} sq.pt > threshold: {background_area_threshold:.0f} sq.pt)")
                continue
            
            filtered_candidates.append(shape)
        
        logger.info(f"Filtered {len(candidates)} -> {len(filtered_candidates)} cell candidates "
                   f"(removed {len(candidates) - len(filtered_candidates)} backgrounds)")
        
        return filtered_candidates
    
    def _detect_line_based_tables(self, shapes: List[Dict[str, Any]], 
                                  page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Detect tables constructed from line segments (line-based tables).
        
        这种表格由水平线和垂直线构成网格框架，矩形仅作为单元格背景填充。
        常见于报表类PDF，如第5页的行业化季报表格。
        
        检测策略：
        1. 提取所有线条shapes（line type）
        2. 按方向分类为水平线（行分隔线）和垂直线（列分隔线）
        3. 检测线条是否形成规则网格（对齐且等间距）
        4. 从线条交点构建虚拟单元格
        5. 与矩形背景关联，提取单元格样式
        
        Args:
            shapes: List of all shape elements (including lines and rectangles)
            page: PyMuPDF page object
            
        Returns:
            List of detected line-based table dictionaries
        """
        # Step 1: Extract and classify lines
        h_lines = []  # Horizontal lines (row separators)
        v_lines = []  # Vertical lines (column separators)
        rectangles = []  # Cell backgrounds
        
        for shape in shapes:
            shape_type = shape.get('shape_type', 'rectangle')
            width = shape.get('width', 0)
            height = shape.get('height', 0)
            
            if shape_type == 'line':
                # Classify by orientation
                if width > height:
                    # Horizontal line
                    h_lines.append(shape)
                else:
                    # Vertical line
                    v_lines.append(shape)
            elif shape_type == 'rectangle' and width > 10 and height > 10:
                # Potential cell background
                rectangles.append(shape)
        
        # Need minimum lines to form a grid
        if len(h_lines) < 2 or len(v_lines) < 2:
            logger.debug(f"Insufficient lines for line-based table: {len(h_lines)} h-lines, {len(v_lines)} v-lines")
            return []
        
        logger.debug(f"Line-based detection: {len(h_lines)} h-lines, {len(v_lines)} v-lines, {len(rectangles)} rects")
        
        # Step 2: Group lines by position (detect alignment)
        h_line_groups = self._group_lines_by_position(h_lines, axis='y')
        v_line_groups = self._group_lines_by_position(v_lines, axis='x')
        
        if len(h_line_groups) < 2 or len(v_line_groups) < 2:
            logger.debug(f"Insufficient line groups: {len(h_line_groups)} h-groups, {len(v_line_groups)} v-groups")
            return []
        
        # Step 3: Validate grid pattern (lines should be regularly spaced)
        if not self._validate_line_grid_pattern(h_line_groups, v_line_groups):
            logger.debug("Line pattern does not form a valid table grid")
            return []
        
        # Step 4: Build table grid from line intersections
        table = self._build_table_from_lines(h_line_groups, v_line_groups, rectangles, page)
        
        if table:
            # CRITICAL VALIDATION: Check if table columns form a compact group
            # Reject tables where columns are scattered across disconnected regions
            # Example: Page 27 has left chart (X=132-435) + right table (X=462-920)
            # These should NOT be merged into one table
            
            cells = table.get('cells', [])
            if cells:
                # Get all unique column X positions
                col_x_positions = sorted(set(c['x'] for c in cells))
                
                # Calculate gaps between consecutive columns
                if len(col_x_positions) >= 2:
                    gaps = [col_x_positions[i+1] - col_x_positions[i] 
                           for i in range(len(col_x_positions) - 1)]
                    
                    # If there's a gap > 20pt between columns, it's likely two separate regions
                    # CRITICAL: This threshold should be smaller than typical column spacing
                    # but larger than typical cell borders (which are < 5pt)
                    max_gap = max(gaps) if gaps else 0
                    median_gap = sorted(gaps)[len(gaps)//2] if gaps else 0
                    
                    # Reject if max gap is > 3x median gap AND > 20pt (indicates discontinuity)
                    if max_gap > 20 and (median_gap == 0 or max_gap > median_gap * 3):
                        logger.info(f"Rejected line-based table: columns have large gap "
                                   f"(max_gap={max_gap:.1f}pt, median={median_gap:.1f}pt), "
                                   f"likely spans disconnected regions")
                        return []
            
            logger.info(f"Detected line-based table: {table['rows']}x{table['cols']} grid")
            return [table]
        
        return []
    
    def _group_lines_by_position(self, lines: List[Dict[str, Any]], axis: str) -> Dict[float, List[Dict[str, Any]]]:
        """
        Group lines by their position (Y for horizontal lines, X for vertical lines).
        
        Args:
            lines: List of line shapes
            axis: 'x' for vertical lines, 'y' for horizontal lines
            
        Returns:
            Dictionary mapping position to list of lines at that position
        """
        groups = {}
        tolerance = self.alignment_tolerance
        
        for line in lines:
            if axis == 'y':
                # Horizontal lines: group by Y coordinate (use midpoint)
                pos = (line['y'] + line['y2']) / 2
            else:
                # Vertical lines: group by X coordinate (use midpoint)
                pos = (line['x'] + line['x2']) / 2
            
            # Round to tolerance
            pos_key = round(pos / tolerance) * tolerance
            
            if pos_key not in groups:
                groups[pos_key] = []
            groups[pos_key].append(line)
        
        return groups
    
    def _validate_line_grid_pattern(self, h_line_groups: Dict, v_line_groups: Dict) -> bool:
        """
        Validate that lines form a regular grid pattern (not random lines).
        
        检查条件：
        1. 每个位置的线条应该跨越相似的范围（长度一致性）
        2. 线条之间的间距应该相对规则（不能间距过大或过小）
        3. 至少形成2x2的网格
        
        Args:
            h_line_groups: Horizontal line groups by Y position
            v_line_groups: Vertical line groups by X position
            
        Returns:
            True if lines form a valid table grid
        """
        # Check minimum grid size
        if len(h_line_groups) < 2 or len(v_line_groups) < 2:
            return False
        
        # Check if lines span across sufficient range
        # Horizontal lines should span multiple columns
        h_spans = []
        for pos, lines_at_pos in h_line_groups.items():
            for line in lines_at_pos:
                span = line['width']
                h_spans.append(span)
        
        # Vertical lines should span multiple rows
        v_spans = []
        for pos, lines_at_pos in v_line_groups.items():
            for line in lines_at_pos:
                span = line['height']
                v_spans.append(span)
        
        # Lines should have reasonable spans (> 20pt to cross at least one cell)
        avg_h_span = sum(h_spans) / len(h_spans) if h_spans else 0
        avg_v_span = sum(v_spans) / len(v_spans) if v_spans else 0
        
        if avg_h_span < 20 or avg_v_span < 20:
            logger.debug(f"Line spans too small: h_span={avg_h_span:.1f}, v_span={avg_v_span:.1f}")
            return False
        
        # Check spacing regularity (spacing should not vary wildly)
        sorted_h_positions = sorted(h_line_groups.keys())
        sorted_v_positions = sorted(v_line_groups.keys())
        
        # Calculate row heights (spacing between horizontal lines)
        row_heights = [sorted_h_positions[i+1] - sorted_h_positions[i] 
                      for i in range(len(sorted_h_positions) - 1)]
        
        # Calculate column widths (spacing between vertical lines)
        col_widths = [sorted_v_positions[i+1] - sorted_v_positions[i] 
                     for i in range(len(sorted_v_positions) - 1)]
        
        # Row heights should be reasonable (10pt - 150pt per row)
        if any(h < 10 or h > 150 for h in row_heights):
            logger.debug(f"Irregular row heights: {row_heights}")
            return False
        
        # Column widths should be reasonable (20pt - 600pt per column)
        if any(w < 20 or w > 600 for w in col_widths):
            logger.debug(f"Irregular column widths: {col_widths}")
            return False
        
        logger.debug(f"Valid line grid: {len(sorted_h_positions)} rows, {len(sorted_v_positions)} cols")
        return True
    
    def _build_table_from_lines(self, h_line_groups: Dict, v_line_groups: Dict,
                                rectangles: List[Dict[str, Any]], 
                                page: fitz.Page) -> Optional[Dict[str, Any]]:
        """
        Build table structure from line intersections.
        
        将线条的交点转换为单元格边界，创建虚拟单元格grid。
        
        CRITICAL FIX: Check for horizontally separated regions before building table
        Example: Page 27 has left chart (X=132-435) + right table (X=462-920)
        These should NOT be merged into one table
        
        Args:
            h_line_groups: Horizontal line groups (row separators)
            v_line_groups: Vertical line groups (column separators)
            rectangles: Rectangle shapes (cell backgrounds)
            page: PyMuPDF page object
            
        Returns:
            Table dictionary or None
        """
        # Get sorted positions
        row_positions = sorted(h_line_groups.keys())
        col_positions = sorted(v_line_groups.keys())
        
        # CRITICAL CHECK: Detect horizontal gaps in column positions
        # If there's a large gap (> 50pt) between columns, it indicates
        # two separate regions that should NOT be merged into one table
        if len(col_positions) >= 2:
            gaps = [col_positions[i+1] - col_positions[i] 
                   for i in range(len(col_positions) - 1)]
            max_gap = max(gaps) if gaps else 0
            
            # If max gap > 50pt, reject this table (likely spans disconnected regions)
            if max_gap > 50:
                logger.info(f"Rejected line-based table: columns have large gap "
                           f"(max_gap={max_gap:.1f}pt), likely spans disconnected regions "
                           f"(e.g., chart + table)")
                return None
        
        # Build cell grid
        cells = []
        rows = len(row_positions) - 1
        cols = len(col_positions) - 1
        
        for i in range(rows):
            for j in range(cols):
                # Cell boundaries
                y_top = row_positions[i]
                y_bottom = row_positions[i + 1]
                x_left = col_positions[j]
                x_right = col_positions[j + 1]
                
                # Create cell
                cell = {
                    'x': x_left,
                    'y': y_top,
                    'x2': x_right,
                    'y2': y_bottom,
                    'width': x_right - x_left,
                    'height': y_bottom - y_top,
                    'pdf_index': i * cols + j  # Sequential index
                }
                
                # Try to find matching rectangle background
                for rect in rectangles:
                    # Check if rectangle overlaps with this cell (within tolerance)
                    tolerance = 5.0
                    x_overlap = (abs(rect['x'] - x_left) < tolerance and 
                                abs(rect['x2'] - x_right) < tolerance)
                    y_overlap = (abs(rect['y'] - y_top) < tolerance and 
                                abs(rect['y2'] - y_bottom) < tolerance)
                    
                    if x_overlap and y_overlap:
                        # This rectangle is the background for this cell
                        cell['fill_color'] = rect.get('fill_color')
                        cell['stroke_color'] = rect.get('stroke_color')
                        cell['stroke_width'] = rect.get('stroke_width', 0.5)
                        break
                
                # If no background found, use default styling
                if 'fill_color' not in cell:
                    cell['fill_color'] = None  # No fill
                    cell['stroke_color'] = '#000000'  # Black border
                    cell['stroke_width'] = 0.5
                
                cells.append(cell)
        
        # Calculate table bounding box
        bbox = (
            col_positions[0],
            row_positions[0],
            col_positions[-1],
            row_positions[-1]
        )
        
        table = {
            'bbox': bbox,
            'rows': rows,
            'cols': cols,
            'cells': cells,
            'type': 'table',
            'detection_mode': 'line-based'  # Mark as line-based for debugging
        }
        
        return table
    
    def _detect_grid_structures(self, cells: List[Dict[str, Any]], 
                               page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Detect grid structures (tables) from cell candidates.
        
        CRITICAL FIX: Start detection from rows with most columns to handle sparse columns.
        Example: If header row has 3 columns but data rows have 2 columns (sparse first column),
        we should detect from header row to capture all columns.
        
        CRITICAL ENHANCEMENT: Detect horizontally separated tables on the same page.
        Example: Page 10 has TWO side-by-side tables that share same Y coordinates
        but have a horizontal gap (>50pt) between them.
        
        A grid is identified by:
        - Regular rows (cells with aligned Y positions)
        - Regular columns (cells with aligned X positions)
        - Multiple rows and columns forming a grid pattern
        
        Args:
            cells: List of potential table cells
            page: PyMuPDF page object
            
        Returns:
            List of detected table dictionaries
        """
        if not cells:
            return []
        
        # CRITICAL: Split horizontally separated tables BEFORE grouping by Y
        # Example: Page 10 has left table (X=37-473) and right table (X=481-920)
        # with 7.9pt gap between them. They share Y coordinates but are separate tables.
        table_groups = self._split_horizontally_separated_tables(cells)
        
        logger.debug(f"Split {len(cells)} cells into {len(table_groups)} horizontal table group(s)")
        
        # Process each horizontal table group independently
        all_tables = []
        
        for group_idx, table_cells in enumerate(table_groups):
            logger.debug(f"Processing horizontal table group {group_idx + 1} with {len(table_cells)} cells")
            
            # Group cells by rows (similar Y positions)
            rows = self._group_by_y_position(table_cells)
            
            if len(rows) < self.min_table_rows:
                logger.debug(f"Group {group_idx + 1}: Insufficient rows ({len(rows)} < {self.min_table_rows})")
                continue
        
            # For each row group, check if they form a grid
            tables = []
            
            # CRITICAL FIX: Sort rows by column count (descending) to prioritize rows with most columns
            # This ensures we start from header/footer rows that have all columns (including sparse ones)
            row_indices_by_col_count = sorted(
                range(len(rows)),
                key=lambda i: len(rows[i]),
                reverse=True  # Start with rows having most columns
            )
            
            # Try to build tables starting from rows with most columns
            # This handles sparse columns where some columns only appear in header/footer
            for i in row_indices_by_col_count:
                table = self._try_build_table_from_row(rows, i, page)
                if table:
                    tables.append(table)
            
            # Remove overlapping tables (keep the larger one)
            tables = self._remove_overlapping_tables(tables)
            
            all_tables.extend(tables)
        
        return all_tables
    
    def _split_horizontally_separated_tables(self, cells: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Split cells into horizontally separated table groups.
        
        Problem: Page 10 has TWO tables side-by-side:
        - Left table: X=37.4-473.0 (暴露面风险资产排名TOP5)
        - Right table: X=481.0-920.2 (未闭环风险端口TOP5)
        - Gap: 7.9pt between them
        
        They share the same Y coordinates (Y=189, 216, etc.) but are separate tables.
        Current code merges them into one 6-column table, which is incorrect.
        
        Strategy:
        1. Group cells by Y position (rows)
        2. For each row, detect horizontal gaps between cells
        3. If consistent gaps exist across multiple rows, split into table groups
        4. A gap >50pt (configurable) indicates separate tables
        
        Args:
            cells: List of all cell candidates
            
        Returns:
            List of cell groups, each group is a horizontally separate table
        """
        if not cells:
            return []
        
        # Configuration
        min_gap_threshold = 50.0  # Minimum gap to consider tables as separate (pt)
        min_gap_consistency = 0.6  # At least 60% of rows must have the gap
        
        # Step 1: Group cells by Y position (rows)
        tolerance = self.alignment_tolerance
        rows_dict = {}
        
        for cell in cells:
            y = round(cell['y'] / tolerance) * tolerance
            if y not in rows_dict:
                rows_dict[y] = []
            rows_dict[y].append(cell)
        
        if len(rows_dict) < 2:
            # Single row or empty - no splitting needed
            return [cells]
        
        # Step 2: Analyze horizontal gaps AND column clustering
        # Strategy: Detect gaps between NON-MERGED cells (cells with reasonable width)
        # Merged cells (like table titles) can span multiple columns and hide the real gaps
        from collections import defaultdict
        gap_positions = defaultdict(int)  # gap_center -> count of rows with this gap
        
        # Also collect column X positions to detect clustering
        # CRITICAL FIX: Collect from ALL cells initially, but will filter later
        all_col_x = []
        
        for y_key, row_cells in rows_dict.items():
            # Sort cells by X position
            sorted_cells = sorted(row_cells, key=lambda c: c['x'])
            
            # Filter out merged cells (width > 300pt typically indicates merged cells)
            # Keep cells with reasonable width for gap detection
            # IMPORTANT: 230pt columns are still valid (e.g., "风险端口列举" column in Page 10)
            # Only filter extremely wide cells (> 300pt) that span across multiple logical columns
            normal_cells = [c for c in sorted_cells if c.get('width', 0) < 300]
            
            # Collect column X positions from normal cells for gap detection
            for cell in normal_cells:
                all_col_x.append(cell['x'])
            
            # Find gaps between consecutive NORMAL cells
            for i in range(len(normal_cells) - 1):
                cell1_x2 = normal_cells[i]['x2']
                cell2_x = normal_cells[i + 1]['x']
                gap = cell2_x - cell1_x2
                
                # Check if gap is significant
                if gap > min_gap_threshold:
                    # Record gap center position (rounded to 10pt for tolerance)
                    gap_center = round((cell1_x2 + cell2_x) / 2 / 10) * 10
                    gap_positions[gap_center] += 1
                    
                    logger.debug(f"Row Y={y_key:.1f}: Found gap {gap:.1f}pt at X={gap_center:.1f} "
                               f"(between X2={cell1_x2:.1f} and X={cell2_x:.1f})")
        
        # Step 3: Find consistent gap positions (appear in >60% of rows)
        num_rows = len(rows_dict)
        consistent_gaps = []
        
        for gap_center, count in gap_positions.items():
            if count >= num_rows * min_gap_consistency:
                consistent_gaps.append(gap_center)
                logger.info(f"Detected consistent horizontal gap at X≈{gap_center:.1f} "
                           f"(appears in {count}/{num_rows} rows = {count*100/num_rows:.0f}%)")
        
        # Step 3.5: If no gaps found by gap detection, try column clustering
        # This handles cases where merged cells hide the gaps
        # Example: Page 10 has X=[37, 170, 242] (left table) and X=[481, 553, 625] (right table)
        # The X positions clearly form two clusters with a large gap in between
        #
        # CRITICAL: Use strict criteria to avoid false positives:
        # 1. Gap must be MUCH larger than typical column spacing (>= 200pt)
        # 2. Gap must be >> 2x the second-largest gap (to detect true cluster separation)
        # 3. Must have at least 4 columns (2 per potential table)
        if not consistent_gaps and len(all_col_x) >= 4:
            # CRITICAL FIX: Calculate gaps between column RIGHT EDGES and next column LEFT EDGES
            # NOT between column X positions (which gives wrong results)
            # 
            # Problem Example (Page 12):
            # - Column X positions: [31, 71, 307, 414, 480]
            # - Column widths: [40.8pt, 235.4pt, 107.5pt, 65.6pt, 216.6pt]
            # - OLD gap calculation (X to X): [40, 236, 107, 66] -> largest=236pt (WRONG!)
            # - NEW gap calculation (right edge to left edge):
            #   * Col 0 right edge: 31+40.8=71.8, Col 1 left edge: 71 -> gap=0 (no separation)
            #   * Col 1 right edge: 71+235.4=306.4, Col 2 left edge: 307 -> gap=0.6pt (no separation)
            #   * This correctly identifies it as ONE table, not TWO separate tables
            #
            # Strategy: Build a mapping of X position -> cell width for accurate gap calculation
            col_x_to_width = {}
            for cell in cells:
                cell_x = cell['x']
                cell_width = cell.get('width', 0)
                # Keep track of maximum width for each X position (handles overlapping cells)
                if cell_x not in col_x_to_width:
                    col_x_to_width[cell_x] = cell_width
                else:
                    col_x_to_width[cell_x] = max(col_x_to_width[cell_x], cell_width)
            
            # Sort column X positions
            sorted_col_x = sorted(set(all_col_x))
            
            # Find all gaps between consecutive columns
            # HYBRID STRATEGY: Consider both actual gap and column widths
            # - Actual gap = right edge of col i to left edge of col i+1
            # - Visual separation indicator = actual gap + (wide column bonus if col i is wide)
            # 
            # Rationale:
            # - Page 12: Col 0 (40.8pt wide) at X=31, Col 1 at X=71 -> small gap, same table
            # - Page 10: Col 2 (230.4pt wide) at X=242.6, Col 3 at X=481 -> 7.9pt gap but visually separated
            #
            # Solution: Add a "wide column bonus" to the gap if previous column is wide (>150pt)
            # This captures the visual separation even when actual gap is small
            gaps = []
            for i in range(len(sorted_col_x) - 1):
                col_x = sorted_col_x[i]
                next_col_x = sorted_col_x[i + 1]
                
                # Get column width (if available)
                col_width = col_x_to_width.get(col_x, 0)
                col_right_edge = col_x + col_width
                
                # Actual gap = distance from right edge to next column's left edge
                actual_gap = next_col_x - col_right_edge
                
                # CRITICAL: For wide columns (>150pt), add visual separation bonus
                # This helps detect side-by-side tables where the gap is small but columns are wide
                # Bonus = min(col_width - 150, 200) to cap the bonus at 200pt
                visual_gap = actual_gap
                if col_width > 150:
                    wide_col_bonus = min(col_width - 150, 200)
                    visual_gap += wide_col_bonus
                    logger.debug(f"Wide column bonus: col_width={col_width:.1f}pt > 150pt, "
                               f"adding {wide_col_bonus:.1f}pt bonus (actual_gap={actual_gap:.1f}pt, "
                               f"visual_gap={visual_gap:.1f}pt)")
                
                # Only consider non-negative gaps
                if actual_gap >= 0:
                    gap_center = (col_right_edge + next_col_x) / 2
                    gaps.append((visual_gap, gap_center))
                    logger.info(f"Column gap: X={col_x:.1f} (width={col_width:.1f}, right={col_right_edge:.1f}) "
                               f"to next X={next_col_x:.1f}, actual_gap={actual_gap:.1f}pt, "
                               f"visual_gap={visual_gap:.1f}pt")
            
            # Sort gaps by size (descending)
            gaps.sort(reverse=True)
            
            # CRITICAL FIX: Handle case where no valid gaps found (all columns overlap or touch)
            if not gaps:
                logger.debug("Column clustering: No valid gaps found (all columns touch or overlap)")
                # No gaps means single contiguous table
                return [cells]
            
            largest_gap, largest_gap_pos = gaps[0]
            
            # IMPROVED STRATEGY: Calculate typical column spacing (median of smaller gaps)
            # Exclude the largest gap (potential table separator) when calculating typical spacing
            smaller_gaps = [g[0] for g in gaps[1:]]  # Skip largest gap
            if smaller_gaps:
                smaller_gaps.sort()
                median_gap = smaller_gaps[len(smaller_gaps) // 2]
            else:
                median_gap = 0
            
            # STRICT CRITERIA for table separation (using visual gaps):
            # Strategy 1: Absolute threshold - gap >= 80pt (visual gap, including wide column bonus)
            # Strategy 2: Relative threshold - gap >= 2x median gap
            # 
            # Examples with NEW visual gap calculation:
            # - Page 12: Col 0 (40.8pt) gap to Col 1 = 0pt, no bonus -> visual_gap=0pt (no split) ✓
            # - Page 10: Col 2 (230.4pt) gap to Col 3 = 7.9pt + 80.4pt bonus -> visual_gap=88.3pt (split) ✓
            # - Page 7: Normal column gaps, no wide columns -> use relative ratio check
            #
            # IMPORTANT: Lowered absolute threshold from 200pt to 80pt to catch side-by-side tables
            # where visual separation comes from wide column bonus rather than actual spacing
            min_gap_threshold = 80  # pt - visual gap threshold
            min_ratio = 2.5  # Relative threshold (slightly higher since we lowered absolute threshold)
            
            if (largest_gap >= min_gap_threshold and 
                (median_gap == 0 or largest_gap >= median_gap * min_ratio)):
                consistent_gaps.append(largest_gap_pos)
                ratio_str = f"{largest_gap/median_gap:.1f}" if median_gap > 0 else 'inf'
                logger.info(f"Detected horizontal split via column clustering: "
                           f"largest gap {largest_gap:.1f}pt (median gap: {median_gap:.1f}pt, "
                           f"ratio: {ratio_str}x) "
                           f"at X≈{largest_gap_pos:.1f} "
                           f"(column positions: {[f'{x:.0f}' for x in sorted_col_x]})")
            else:
                ratio_str = f"{largest_gap/median_gap:.1f}" if median_gap > 0 else 'inf'
                logger.debug(f"Column clustering: No clear split (largest gap={largest_gap:.1f}pt, "
                            f"median gap={median_gap:.1f}pt, "
                            f"ratio={ratio_str}x < {min_ratio}x or gap < 200pt)")
        
        # Step 4: Split cells into groups based on consistent gaps
        if not consistent_gaps:
            # No consistent gaps - all cells belong to one table
            logger.debug("No consistent horizontal gaps detected, treating as single table")
            return [cells]
        
        # Sort gaps by X position
        consistent_gaps.sort()
        
        # Define horizontal regions based on gaps
        # Regions: [0, gap1), [gap1, gap2), ..., [gapN, ∞)
        regions = []
        prev_gap = 0
        
        for gap_pos in consistent_gaps:
            regions.append((prev_gap, gap_pos))
            prev_gap = gap_pos
        
        # Last region
        regions.append((prev_gap, float('inf')))
        
        logger.debug(f"Defined {len(regions)} horizontal regions: {regions}")
        
        # Assign each cell to a region based on its X position
        table_groups = [[] for _ in range(len(regions))]
        
        for cell in cells:
            cell_center_x = (cell['x'] + cell['x2']) / 2
            
            # Find which region this cell belongs to
            for region_idx, (x_min, x_max) in enumerate(regions):
                if x_min <= cell_center_x < x_max:
                    table_groups[region_idx].append(cell)
                    break
        
        # Filter out empty groups and groups with too few cells
        filtered_groups = [group for group in table_groups if len(group) >= self.min_table_rows * self.min_table_cols]
        
        logger.info(f"Split {len(cells)} cells into {len(filtered_groups)} horizontal table group(s) "
                   f"(filtered from {len(table_groups)} regions)")
        
        return filtered_groups if filtered_groups else [cells]
    
    def _group_by_y_position(self, cells: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Group cells by their Y position (rows).
        
        CRITICAL: For overlapping cells at the same position, keep only the one
        with the highest pdf_index (last drawn = visible on top).
        This fixes color issues where white background is drawn before colored foreground.
        
        CRITICAL FIX: Merge rows that only contain vertical-span cell tops
        Example: If row Y=36 has only one tall cell (154pt high), and row Y=39 has other cells,
        merge them into a single logical row (Y=39) with the tall cell included.
        
        Args:
            cells: List of cells
            
        Returns:
            List of cell groups (rows), sorted by Y position
        """
        rows = {}
        
        for cell in cells:
            y = round(cell['y'] / self.alignment_tolerance) * self.alignment_tolerance
            if y not in rows:
                rows[y] = []
            rows[y].append(cell)
        
        # CRITICAL: Deduplicate overlapping cells in each row
        # For cells at the same position, keep the one with highest pdf_index (drawn last)
        for y in rows:
            before_count = len(rows[y])
            deduplicated = self._deduplicate_overlapping_cells(rows[y])
            rows[y] = deduplicated
            if len(deduplicated) != before_count:
                logger.debug(f"Row Y={y:.1f}: Deduplicated {before_count} cells to {len(deduplicated)} cells")
        
        # Sort rows by Y position
        sorted_y_keys = sorted(rows.keys())
        
        # CRITICAL FIX: Merge single-cell rows (vertical-span tops) into next row
        # ENHANCED STRATEGY: 
        # 1. If a row has only 1-2 cells with at least one tall cell (height > 50pt)
        # 2. AND the next row (within 10pt vertical distance) has cells at DIFFERENT X positions
        # 3. Then merge the tall cell(s) into the next row to form a complete logical row
        # This handles cases like Page 9 where:
        # - Row Y=36 has: [X=39.2 (657.8pt wide table bg), X=39.2 (64.5pt first column)]
        # - Row Y=39 has: [X=103.7 (second column), X=275.7 (third column)]
        # - Expected result: Merge X=39.2 (64.5pt) from Y=36 into Y=39 row
        
        merged_rows = {}
        skip_rows = set()  # Rows to skip (already processed or merged)
        
        for i, y_key in enumerate(sorted_y_keys):
            if y_key in skip_rows:
                continue
                
            row_cells = rows[y_key]
            
            # Check if this is a sparse row with tall cells (likely vertical merge)
            # Find cells with height > 50pt and width < 200pt (not table background)
            tall_narrow_cells = [c for c in row_cells if c['height'] > 50 and c['width'] < 200]
            
            # If we have 1-2 tall cells and a next row exists
            if 1 <= len(tall_narrow_cells) <= 2 and i + 1 < len(sorted_y_keys):
                next_y_key = sorted_y_keys[i + 1]
                next_row_cells = rows[next_y_key]
                
                # Check if next row is close (< 10pt) and has cells at different X positions
                if abs(next_y_key - y_key) < 10 and len(next_row_cells) >= 1:
                    # Get X positions of tall cells and next row cells
                    tall_cell_x_positions = {round(c['x'] / 5) * 5 for c in tall_narrow_cells}
                    next_row_x_positions = {round(c['x'] / 5) * 5 for c in next_row_cells}
                    
                    # If X positions don't significantly overlap, merge
                    # (meaning tall cells are in different columns from next row)
                    overlap_count = len(tall_cell_x_positions & next_row_x_positions)
                    
                    if overlap_count == 0:
                        # No overlap - definitely merge
                        x_pos_str = ', '.join([f"{c['x']:.1f}" for c in tall_narrow_cells])
                        logger.debug(f"Merging {len(tall_narrow_cells)} tall cell(s) from Y={y_key:.1f} "
                                    f"(X positions: [{x_pos_str}]) "
                                    f"into next row Y={next_y_key:.1f}")
                        
                        # Merge tall cells into next row
                        merged_row = next_row_cells + tall_narrow_cells
                        merged_rows[next_y_key] = merged_row
                        skip_rows.add(y_key)  # Skip current row since it's merged
                        skip_rows.add(next_y_key)  # CRITICAL: Also skip next row to prevent overwriting
                        
                        logger.debug(f"After merge: row Y={next_y_key:.1f} now has {len(merged_row)} cells")
                        continue
            
            # Normal row, add as-is (only if not already merged into another row)
            if y_key not in skip_rows:
                merged_rows[y_key] = row_cells
        
        # Log cells in each merged row for debugging
        for y in sorted(merged_rows.keys()):
            row_cells = merged_rows[y]
            x_positions = sorted([c['x'] for c in row_cells])
            widths = {c['x']: c.get('width', 0) for c in row_cells}
            logger.debug(f"Row Y={y:.1f} has {len(row_cells)} cells at X positions: {[f'{x:.1f}({widths[x]:.1f}pt)' for x in x_positions[:5]]}")
        
        # Convert to list, sorted by Y position
        sorted_rows = [merged_rows[y] for y in sorted(merged_rows.keys())]
        
        return sorted_rows
    
    def _deduplicate_overlapping_cells(self, cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove overlapping cells, keeping the one with highest pdf_index (drawn last).
        
        In PDF, elements drawn later appear on top. For table cells with multiple
        overlapping rectangles (e.g., white background + colored foreground),
        we must keep the last-drawn (highest pdf_index) to get the visible color.
        
        Args:
            cells: List of cells in a row
            
        Returns:
            Deduplicated list of cells
        """
        if not cells:
            return cells
        
        # Group cells by position (x, y, width, height)
        from collections import defaultdict
        tolerance = 1.0  # 1pt tolerance for position matching
        
        position_groups = defaultdict(list)
        for cell in cells:
            # CRITICAL FIX: Group by position (x, y) only, NOT by width/height
            # Cells at the same position may have different widths:
            # Example: X=39.2 may have both a narrow border (width=0.5pt) and wide cell (width=64.5pt)
            # We want to merge them and keep the wider one
            pos_key = (
                round(cell['x'] / tolerance),
                round(cell['y'] / tolerance)
            )
            position_groups[pos_key].append(cell)
        
        # For each position, MERGE properties from overlapping cells
        # CRITICAL FIX: Instead of discarding cells, merge their properties
        # PDF table cells often have multiple overlapping rectangles:
        # - One with fill_color (background)
        # - One with stroke_color and stroke_width (border)
        # - Narrow border lines (width < 5pt)
        # We need to keep BOTH properties by merging them
        # CRITICAL: Prioritize WIDER cells over narrow border lines
        deduplicated = []
        for pos_key, group in position_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Multiple cells at same position - MERGE their properties
                # CRITICAL: Select best cell avoiding both narrow borders AND oversized backgrounds
                # Example: X=39.2 may have:
                # - 657.8pt background (too wide - full table width)
                # - 64.5pt cell (good - actual column width)
                # - 0.5pt border (too narrow)
                # Strategy: Select cell with width in reasonable range (5pt - 300pt)
                
                reasonable_cells = [c for c in group if 5.0 <= c.get('width', 0) <= 300]
                if reasonable_cells:
                    # Select widest among reasonable cells
                    merged_cell = max(reasonable_cells, key=lambda c: c.get('width', 0) * c.get('height', 0)).copy()
                    logger.debug(f"Merging {len(group)} cells at position {pos_key}, "
                               f"selected best reasonable cell: {merged_cell.get('width')}x{merged_cell.get('height')}pt")
                else:
                    # Fallback: select widest (even if unreasonable)
                    merged_cell = max(group, key=lambda c: c.get('width', 0) * c.get('height', 0)).copy()
                    logger.debug(f"Merging {len(group)} cells at position {pos_key}, "
                               f"no reasonable cells, selected widest: {merged_cell.get('width')}x{merged_cell.get('height')}pt")
                
                # Merge properties from all cells in the group
                # CRITICAL FIX: Prioritize non-white colors in PDF drawing order
                # PDF often draws white background first, then colored foreground on top
                # Strategy: Prefer colors drawn later (higher pdf_index) and non-white colors
                
                # Collect all fill colors with their pdf_index
                fill_colors_with_index = []
                for cell in group:
                    if cell.get('fill_color'):
                        fill_colors_with_index.append((cell['fill_color'], cell.get('pdf_index', 0)))
                
                # Sort by pdf_index (descending) to get colors drawn last
                fill_colors_with_index.sort(key=lambda x: x[1], reverse=True)
                
                # Select the best fill color:
                # 1. First try to find non-white color with highest pdf_index
                # 2. If all are white, use white
                best_fill_color = None
                for color, idx in fill_colors_with_index:
                    if color != '#FFFFFF':
                        best_fill_color = color
                        logger.debug(f"Selected non-white fill color: {color} (pdf_index={idx})")
                        break
                
                if not best_fill_color and fill_colors_with_index:
                    # All colors are white, use the one with highest pdf_index
                    best_fill_color = fill_colors_with_index[0][0]
                    logger.debug(f"All white, selected: {best_fill_color} (pdf_index={fill_colors_with_index[0][1]})")
                
                merged_cell['fill_color'] = best_fill_color
                
                # Merge stroke properties (keep if any cell has stroke)
                for cell in group:
                    if cell.get('stroke_color') and not merged_cell.get('stroke_color'):
                        merged_cell['stroke_color'] = cell['stroke_color']
                        merged_cell['stroke_width'] = cell.get('stroke_width', 0.5)
                    
                    # Keep the highest pdf_index
                    merged_cell['pdf_index'] = max(merged_cell.get('pdf_index', 0), 
                                                   cell.get('pdf_index', 0))
                
                deduplicated.append(merged_cell)
                
                logger.debug(f"Merged {len(group)} overlapping cells at position {pos_key}, "
                           f"result: fill={merged_cell.get('fill_color')}, "
                           f"stroke={merged_cell.get('stroke_color')}, "
                           f"width={merged_cell.get('stroke_width')}")
        
        return deduplicated
    
    def _try_build_table_from_row(self, rows: List[List[Dict[str, Any]]], 
                                  start_idx: int, page: fitz.Page) -> Optional[Dict[str, Any]]:
        """
        Try to build a table starting from a specific row.
        
        CRITICAL FIX: Support sparse columns (columns that only appear in some rows)
        Example: First column may only appear in header row and last row
        
        Args:
            rows: List of row groups
            start_idx: Starting row index
            page: PyMuPDF page object
            
        Returns:
            Table dictionary or None if not a valid table
        """
        # IMPROVED ALGORITHM: Collect column positions from ALL potential table rows
        # instead of just the first row. This handles sparse columns correctly.
        
        # Step 1: Identify all potential table rows by checking column overlap
        first_row = rows[start_idx]
        first_row_col_positions = sorted([round(cell['x'] / self.alignment_tolerance) * 
                                         self.alignment_tolerance for cell in first_row])
        
        if len(first_row_col_positions) < self.min_table_cols:
            return None
        
        # CRITICAL FIX: Collect consecutive rows both forwards AND backwards
        # This handles sparse columns where header/footer have more columns than data rows
        table_rows = [first_row]
        
        # Collect rows forwards (after start_idx)
        for i in range(start_idx + 1, len(rows)):
            row = rows[i]
            row_col_positions = sorted([round(cell['x'] / self.alignment_tolerance) * 
                                       self.alignment_tolerance for cell in row])
            
            # Check if columns roughly match
            match_result = self._columns_match(first_row_col_positions, row_col_positions)
            logger.debug(f"Forward row {i}: cols={row_col_positions} vs reference={first_row_col_positions}, match={match_result}")
            if match_result:
                table_rows.append(row)
            else:
                break
        
        # CRITICAL: Also collect rows backwards (before start_idx)
        # This handles cases where we start from a footer row with all columns
        for i in range(start_idx - 1, -1, -1):
            row = rows[i]
            row_col_positions = sorted([round(cell['x'] / self.alignment_tolerance) * 
                                       self.alignment_tolerance for cell in row])
            
            # Check if columns roughly match
            match_result = self._columns_match(first_row_col_positions, row_col_positions)
            logger.debug(f"Backward row {i}: cols={row_col_positions} vs reference={first_row_col_positions}, match={match_result}")
            if match_result:
                table_rows.insert(0, row)  # Insert at beginning to maintain order
            else:
                break
        
        # Valid table needs minimum rows
        if len(table_rows) < self.min_table_rows:
            return None
        
        # Step 2: Collect ALL unique column positions from all rows
        # This handles sparse columns (e.g., first column only in header/footer)
        all_col_positions = set()
        for row in table_rows:
            for cell in row:
                col_x = round(cell['x'] / self.alignment_tolerance) * self.alignment_tolerance
                all_col_positions.add(col_x)
        
        # Sort column positions
        col_positions = sorted(all_col_positions)
        
        logger.debug(f"Detected {len(col_positions)} unique columns from {len(table_rows)} rows: "
                    f"{[f'{x:.1f}' for x in col_positions]}")
        
        # Calculate bounding box
        all_cells = [cell for row in table_rows for cell in row]
        bbox = self._calculate_table_bbox(all_cells)
        
        # Calculate area to determine if this is a reasonable table
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        page_area = page.rect.width * page.rect.height
        
        # Table should not be too large (> 60% of page) - likely not a compact table
        if area > page_area * 0.6:
            return None
        
        # CRITICAL FIX: Validate this is a real table with grid structure
        # Non-tables (like decorative card layouts) may have aligned rectangles 
        # but lack the cross-pattern of rows and columns that defines a table
        if not self._validate_grid_structure(table_rows, col_positions):
            logger.debug(f"Rejected potential table: lacks clear grid structure "
                        f"({len(table_rows)} rows x {len(col_positions)} cols)")
            return None
        
        table = {
            'bbox': bbox,
            'rows': len(table_rows),
            'cols': len(col_positions),  # Use actual column count from all rows
            'cells': all_cells,
            'type': 'table'
        }
        
        return table
    
    def _validate_grid_structure(self, table_rows: List[List[Dict[str, Any]]], 
                                 col_positions: List[float]) -> bool:
        """
        Validate that the detected cells form a true table grid structure.
        
        Real tables have:
        1. Multiple cells per row (not just single column layouts)
        2. Multiple rows with consistent column positions
        3. Grid intersection pattern (cells meet at cross-points)
        
        This prevents false positives like:
        - Single-column card layouts (威胁管理/资产管理 sections)
        - Decorative aligned rectangles without grid structure
        
        Args:
            table_rows: List of rows, each row is a list of cell dictionaries
            col_positions: List of column X positions
            
        Returns:
            True if this is a valid table grid, False otherwise
        """
        num_rows = len(table_rows)
        num_cols = len(col_positions)
        
        # Rule 1: Must have at least 2 rows and 2 columns
        if num_rows < 2 or num_cols < 2:
            logger.debug(f"Grid validation failed: insufficient dimensions ({num_rows}x{num_cols})")
            return False
        
        # Rule 2: Check row consistency - most rows should have multiple cells
        # Single-column layouts (like威胁管理 cards) have only 1 cell per row
        # 
        # ENHANCED STRATEGY: Detect and handle merged header rows intelligently
        # Many tables have:
        # - Row 1: Merged header (1 cell spanning all columns)
        # - Rows 2-N: Data rows with multiple cells per row
        # 
        # This is a VALID table structure, not a false positive.
        # 
        # IMPROVED LOGIC:
        # 1. Count rows with multiple cells (>= 2 cells)
        # 2. For small tables (2-3 rows), allow ONE single-cell row at the top (merged header)
        # 3. For larger tables, require at least 50% of rows to have multiple cells
        
        rows_with_multiple_cells = 0
        single_cell_rows = []
        
        for row_idx, row in enumerate(table_rows):
            # Count cells with width > 5pt (exclude border lines)
            real_cells = [c for c in row if c.get('width', 0) > 5]
            if len(real_cells) >= 2:
                rows_with_multiple_cells += 1
            elif len(real_cells) == 1:
                single_cell_rows.append(row_idx)
        
        multi_cell_ratio = rows_with_multiple_cells / num_rows
        
        # CRITICAL FIX: Allow merged header row in small tables
        # For 2-3 row tables:
        # - If there's only ONE single-cell row AND it's the FIRST row (index 0)
        # - AND all other rows have multiple cells
        # - Then it's a valid table with merged header
        # 
        # Example: season_report_del.pdf page 9 table:
        # - Row 0 (Y=153): 1 cell (merged header)
        # - Row 1 (Y=186): 5 cells (data)
        # - Row 2 (Y=225): 5 cells (data)
        # This should be ACCEPTED as valid table (3x5)
        
        is_merged_header_table = False
        if num_rows <= 3:
            # Check if pattern matches merged header: single-cell first row + multi-cell other rows
            if len(single_cell_rows) == 1 and single_cell_rows[0] == 0:
                # First row is single cell (merged header), check if other rows are multi-cell
                if rows_with_multiple_cells == num_rows - 1:
                    # ADDITIONAL VALIDATION: Check if the "merged header" row has reasonable height
                    # Real table headers: typically 20-80pt high, max ~120pt
                    # Decorative layouts (like pie chart backgrounds): often > 200pt
                    first_row = table_rows[0]
                    first_row_heights = [c.get('height', 0) for c in first_row if c.get('width', 0) > 5]
                    
                    if first_row_heights:
                        max_header_height = max(first_row_heights)
                        avg_header_height = sum(first_row_heights) / len(first_row_heights)
                        
                        logger.debug(f"Potential merged header row: avg height={avg_header_height:.1f}pt, "
                                   f"max height={max_header_height:.1f}pt")
                        
                        # CRITICAL THRESHOLD: Real table headers rarely exceed 120pt
                        # If "header" > 150pt, it's likely a decorative background (pie chart, card, etc.)
                        if max_header_height > 150:
                            logger.debug(f"Rejected merged header table: header too tall "
                                       f"(max={max_header_height:.1f}pt > 150pt), likely decorative element")
                            return False
                    
                    is_merged_header_table = True
                    logger.debug(f"Detected merged header table: row 0 is merged header, "
                               f"rows 1-{num_rows-1} have multiple cells")
        
        # Determine minimum required ratio based on table size and structure
        if is_merged_header_table:
            # For merged header tables, allow lower ratio (we already validated structure)
            # At least 50% of rows should have multiple cells (the data rows)
            min_ratio = 0.5
        elif num_rows <= 3:
            # For small tables without merged header, require 80% (stricter)
            # This prevents card-like layouts from being mistaken for tables
            min_ratio = 0.8
        else:
            # For larger tables, 50% is sufficient
            min_ratio = 0.5
        
        if multi_cell_ratio < min_ratio:
            logger.debug(f"Grid validation failed: insufficient multi-cell rows "
                        f"({rows_with_multiple_cells}/{num_rows} = {multi_cell_ratio*100:.0f}%, "
                        f"required {min_ratio*100:.0f}%, "
                        f"is_merged_header={is_merged_header_table})")
            return False
        
        # Rule 3: Verify grid intersection pattern
        # In a real table, cells from different rows should share column positions
        # This creates a "cross-pattern" where row separators meet column separators
        
        # Count how many column positions are actually used across all rows
        used_col_positions = set()
        for row in table_rows:
            for cell in row:
                if cell.get('width', 0) > 5:  # Exclude border lines
                    cell_x = cell['x']
                    # Find which column this cell belongs to
                    for col_x in col_positions:
                        if abs(cell_x - col_x) <= self.alignment_tolerance * 2:
                            used_col_positions.add(col_x)
                            break
        
        col_usage_ratio = len(used_col_positions) / len(col_positions)
        if col_usage_ratio < 0.6:  # At least 60% of columns should be used
            logger.debug(f"Grid validation failed: low column usage "
                        f"({len(used_col_positions)}/{len(col_positions)} = {col_usage_ratio*100:.0f}%)")
            return False
        
        # Rule 4: Check for cells with borders/strokes (table indicator)
        # Real tables typically have visible borders, while decorative layouts may not
        cells_with_borders = 0
        total_cells = sum(len([c for c in row if c.get('width', 0) > 5]) for row in table_rows)
        
        for row in table_rows:
            for cell in row:
                if cell.get('width', 0) > 5:  # Real cell, not border line
                    if cell.get('stroke_color') or cell.get('fill_color'):
                        cells_with_borders += 1
        
        if total_cells > 0:
            border_ratio = cells_with_borders / total_cells
            # At least 50% of cells should have borders or fills
            if border_ratio < 0.5:
                logger.debug(f"Grid validation failed: insufficient bordered cells "
                            f"({cells_with_borders}/{total_cells} = {border_ratio*100:.0f}%)")
                return False
        
        # Rule 5: Check cell heights to detect decorative card layouts
        # CRITICAL FIX: Decorative card layouts (like timeline cards, info cards) have:
        # - Very tall cells (> 150pt typically)
        # - Only 1-2 rows
        # - Cells arranged horizontally but not forming a real table grid
        # 
        # Real tables have:
        # - Reasonable cell heights (typically 20-80pt, max ~100pt for merged cells)
        # - Multiple rows of data
        # 
        # Strategy: For small tables (2 rows), check if cells are abnormally tall
        # If average cell height > 150pt, likely a card layout, not a table
        
        if num_rows <= 2:
            all_cell_heights = []
            for row in table_rows:
                for cell in row:
                    if cell.get('width', 0) > 5:  # Real cell
                        height = cell.get('height', 0)
                        if height > 0:
                            all_cell_heights.append(height)
            
            if all_cell_heights:
                avg_height = sum(all_cell_heights) / len(all_cell_heights)
                max_height = max(all_cell_heights)
                
                # CRITICAL THRESHOLD: If average cell height > 150pt, likely decorative cards
                # Example from Page 2: cells with heights 306pt, 238pt -> avg ~270pt (clearly not a table)
                # Real tables: cells typically 20-80pt, even merged cells rarely exceed 150pt
                if avg_height > 150:
                    logger.debug(f"Grid validation failed: abnormally tall cells (avg height={avg_height:.1f}pt > 150pt) "
                               f"indicating decorative card layout, not a table")
                    return False
                
                # Additional check: if maximum cell height > 250pt, almost certainly decorative
                # This catches extreme cases like timeline cards (306pt height)
                if max_height > 250:
                    logger.debug(f"Grid validation failed: extremely tall cell (max height={max_height:.1f}pt > 250pt) "
                               f"indicating decorative card/timeline layout, not a table")
                    return False
        
        logger.debug(f"Grid validation passed: {num_rows}x{num_cols} table, "
                    f"multi-cell rows={multi_cell_ratio*100:.0f}%, "
                    f"col usage={col_usage_ratio*100:.0f}%, "
                    f"borders={border_ratio*100:.0f}%")
        return True
    
    def _columns_match(self, cols1: List[float], cols2: List[float]) -> bool:
        """
        Check if two column position lists roughly match.
        
        CRITICAL FIX: Support sparse columns where some columns appear only in header/footer
        Example: First row has 3 columns [A, B, C], but data rows only have 2 columns [B, C]
        We should still consider them as belonging to the same table.
        
        Args:
            cols1: First column position list (reference columns)
            cols2: Second column position list (current row columns)
            
        Returns:
            True if columns match within tolerance
        """
        # RELAXED CONDITION: Allow rows with fewer columns (sparse columns case)
        # As long as the current row has some columns that match the reference
        # Example: header [39, 105, 276] vs data row [105, 276] should match
        
        if len(cols2) == 0:
            return False
        
        # CRITICAL FIX: Allow single-column rows if they align with ANY column of reference
        # OR if the single column is to the LEFT of all reference columns (likely first column)
        # This handles cases where the first column is split into a separate row due to Y-coordinate差异
        # Example: Row Y=36 has [39], Row Y=39 has [105, 276] - they should be part of same table
        if len(cols2) == 1:
            # Single column row - check if it matches ANY column in reference
            for c1 in cols1:
                if abs(cols2[0] - c1) <= self.alignment_tolerance * 2:
                    logger.debug(f"Matched single-column row [{cols2[0]:.1f}] with column {c1:.1f} of reference {cols1}")
                    return True
            
            # CRITICAL: If single column is to the LEFT of all reference columns, include it
            # This handles sparse first column case
            # Example: [39] vs [105, 276] - 39 < 105, so it's likely the first column
            if cols2[0] < min(cols1) - 10:  # 10pt margin to avoid false positives
                logger.debug(f"Matched single-column row [{cols2[0]:.1f}] as likely first column (left of reference {cols1})")
                return True
            
            # If no match, fall through to standard matching
        
        # Check how many columns in cols2 match columns in cols1
        matches = 0
        for c2 in cols2:
            if any(abs(c2 - c1) <= self.alignment_tolerance * 2 for c1 in cols1):
                matches += 1
        
        # CRITICAL: As long as ALL columns in cols2 match SOME columns in cols1,
        # consider it a match. This handles sparse columns (missing columns in some rows).
        # Example: If cols2 = [105, 276] and both match entries in cols1 = [39, 105, 276],
        # then it's a valid row for the same table.
        return matches >= len(cols2) * 0.8  # Allow 80% match to handle minor alignment variations
    
    def _calculate_table_bbox(self, cells: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
        """
        Calculate the bounding box of a table.
        
        Args:
            cells: List of table cells
            
        Returns:
            Tuple (x0, y0, x1, y1)
        """
        if not cells:
            return (0, 0, 0, 0)
        
        x0 = min(cell['x'] for cell in cells)
        y0 = min(cell['y'] for cell in cells)
        x1 = max(cell['x2'] for cell in cells)
        y1 = max(cell['y2'] for cell in cells)
        
        return (x0, y0, x1, y1)
    
    def _remove_overlapping_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove overlapping table regions, keeping only the larger ones.
        
        Args:
            tables: List of table dictionaries
            
        Returns:
            Filtered list without overlapping tables
        """
        if len(tables) <= 1:
            return tables
        
        # Sort by area (descending)
        sorted_tables = sorted(tables, key=lambda t: 
                              (t['bbox'][2] - t['bbox'][0]) * (t['bbox'][3] - t['bbox'][1]), 
                              reverse=True)
        
        filtered = []
        for table in sorted_tables:
            bbox1 = table['bbox']
            
            # Check if this table overlaps with any already accepted table
            overlaps = False
            for accepted in filtered:
                bbox2 = accepted['bbox']
                
                # Calculate overlap
                overlap_x = max(0, min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0]))
                overlap_y = max(0, min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1]))
                overlap_area = overlap_x * overlap_y
                
                table_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
                
                # If overlap is > 50% of this table's area, skip it
                if overlap_area > table_area * 0.5:
                    overlaps = True
                    logger.info(f"Removing overlapping table region (overlap {overlap_area:.0f}/{table_area:.0f})")
                    break
            
            if not overlaps:
                filtered.append(table)
        
        return filtered
    
    def _populate_table_cells(self, table: Dict[str, Any], text_elements: List[Dict[str, Any]]):
        """
        Populate table cells with text content and organize into grid structure.
        
        Args:
            table: Table dictionary to populate
            text_elements: List of text elements from the page
        """
        table_bbox = table['bbox']
        cells = table['cells']
        
        # CRITICAL: DO NOT detect header row above table
        # The header row is already part of the table cells (first row)
        # Detecting "headers" above the table would incorrectly add paragraph text
        # as an extra header row, which duplicates the real header row in cells
        header_texts = []
        
        # NOTE: The original logic searched for text above table bbox:
        # - This incorrectly captured paragraph text above the table
        # - The real header row is already in cells (first row of table)
        # - So we disable this detection by keeping header_texts empty
        
        # Build a grid structure with proper row/col organization
        # Group cells by row first
        rows_dict = {}
        tolerance = self.alignment_tolerance
        
        for cell in cells:
            cell_y = cell['y']
            # Find row group
            row_key = round(cell_y / tolerance) * tolerance
            if row_key not in rows_dict:
                rows_dict[row_key] = []
            rows_dict[row_key].append(cell)
        
        # Sort rows by Y coordinate
        sorted_row_keys = sorted(rows_dict.keys())
        
        # CRITICAL FIX: Apply the same row merging logic as in _group_by_y_position
        # to ensure sparse vertical-span cells are merged into their logical rows
        merged_rows_dict = {}
        skip_row_keys = set()
        
        for i, row_key in enumerate(sorted_row_keys):
            if row_key in skip_row_keys:
                continue
            
            row_cells = rows_dict[row_key]
            
            # Check if this is a sparse row with tall cells (likely vertical merge)
            # Find cells with height > 50pt and width < 200pt (not table background)
            tall_narrow_cells = [c for c in row_cells if c['height'] > 50 and c['width'] < 200]
            
            # If we have 1-2 tall cells and a next row exists
            if 1 <= len(tall_narrow_cells) <= 2 and i + 1 < len(sorted_row_keys):
                next_row_key = sorted_row_keys[i + 1]
                next_row_cells = rows_dict[next_row_key]
                
                # Check if next row is close (< 10pt) and has cells at different X positions
                if abs(next_row_key - row_key) < 10 and len(next_row_cells) >= 1:
                    # Get X positions of tall cells and next row cells
                    tall_cell_x_positions = {round(c['x'] / 5) * 5 for c in tall_narrow_cells}
                    next_row_x_positions = {round(c['x'] / 5) * 5 for c in next_row_cells}
                    
                    # If X positions don't significantly overlap, merge
                    overlap_count = len(tall_cell_x_positions & next_row_x_positions)
                    
                    if overlap_count == 0:
                        # Merge tall cells into next row
                        merged_row = next_row_cells + tall_narrow_cells
                        merged_rows_dict[next_row_key] = merged_row
                        skip_row_keys.add(row_key)
                        skip_row_keys.add(next_row_key)
                        logger.debug(f"[populate] Merged tall cell(s) from Y={row_key:.1f} into Y={next_row_key:.1f}")
                        continue
            
            # Normal row, add as-is
            if row_key not in skip_row_keys:
                merged_rows_dict[row_key] = row_cells
        
        # Use merged rows instead of original rows
        rows_dict = merged_rows_dict
        sorted_row_keys = sorted(rows_dict.keys())
        
        # Build structured grid
        grid = []
        
        # Add header row if detected
        if header_texts:
            logger.info(f"Detected {len(header_texts)} header text elements for table")
            header_row = []
            
            # Group header texts by column (X position)
            # Determine column boundaries from first data row
            if rows_dict:
                first_row_cells = sorted(rows_dict[sorted_row_keys[0]], key=lambda c: c['x'])
                col_boundaries = [cell['x'] for cell in first_row_cells]
                col_boundaries.append(table_bbox[2])  # Right boundary
                
                # Assign each header text to a column based on X position
                # Use column centers to determine which header belongs to which column
                for i in range(len(first_row_cells)):
                    col_start = col_boundaries[i]
                    col_end = col_boundaries[i + 1] if i + 1 < len(col_boundaries) else table_bbox[2]
                    col_center = (col_start + col_end) / 2
                    
                    # Find header text closest to this column center
                    col_header_text = None
                    min_distance = float('inf')
                    
                    for t in header_texts:
                        t_x = t['x']
                        distance = abs(t_x - col_center)
                        if distance < min_distance and col_start - 20 <= t_x <= col_end + 20:
                            min_distance = distance
                            col_header_text = t
                    
                    # Get header text
                    if col_header_text:
                        combined_header = col_header_text.get('content', col_header_text.get('text', ''))
                        col_header_texts = [col_header_text]
                    else:
                        combined_header = ''
                        col_header_texts = []
                    
                    # Create header cell
                    # CRITICAL: Get header cell fill color from actual PDF cells in FIRST ROW
                    # The first row in rows_dict IS the header row, extract colors from it
                    header_fill_color = None
                    header_stroke_color = None
                    header_stroke_width = 0.5
                    
                    # Find actual cell in first row that matches this column position
                    if sorted_row_keys and rows_dict:
                        first_row_cells = rows_dict[sorted_row_keys[0]]
                        for first_cell in first_row_cells:
                            # Check if cell X position matches this column
                            if abs(first_cell['x'] - col_start) < 10:
                                header_fill_color = first_cell.get('fill_color')
                                header_stroke_color = first_cell.get('stroke_color')
                                header_stroke_width = first_cell.get('stroke_width', 0.5)
                                logger.debug(f"Header column {i} color from first row cell: {header_fill_color}")
                                break
                    
                    header_cell = {
                        'bbox': (col_start, table_bbox[1] - 20, col_end, table_bbox[1]),
                        'width': col_end - col_start,
                        'height': 20,
                        'text': combined_header,
                        'fill_color': header_fill_color,  # Use actual PDF color, not hardcoded
                        'stroke_color': header_stroke_color or '#DEE3EC',
                        'stroke_width': header_stroke_width,
                        'text_elements': col_header_texts,
                        'is_header': True
                    }
                    header_row.append(header_cell)
                
                grid.append(header_row)
                logger.info(f"Added header row with {len(header_row)} columns: {[c['text'] for c in header_row]}")
        
        # CRITICAL FIX: Define column boundaries from ALL rows, not just first row
        # This handles sparse columns (columns that only appear in some rows)
        # Example: First column may only appear in header row, not in data rows
        
        # Collect all unique column X positions from all rows
        # IMPORTANT: Filter out border lines (width < 5pt) - they are not actual columns
        all_col_x_positions = set()
        if sorted_row_keys and rows_dict:
            for row_key in sorted_row_keys:
                for cell in rows_dict[row_key]:
                    # CRITICAL: Skip narrow cells (< 5pt width) - these are border lines, not columns
                    # Example: Page 9 has X=[39.2, 39.7] (0.5pt) and X=[103.2, 103.7] (0.5pt) borders
                    # These should NOT be treated as columns
                    cell_width = cell.get('width', 0)
                    if cell_width >= 5.0:
                        all_col_x_positions.add(cell['x'])
                        logger.debug(f"Column candidate: X={cell['x']:.1f}, width={cell_width:.1f}pt, row_y={row_key:.1f}")
                    else:
                        logger.debug(f"Filtered border line: X={cell['x']:.1f}, width={cell_width:.1f}pt, row_y={row_key:.1f}")
            
            # Sort and group similar X positions (within tolerance)
            col_tolerance = 10  # 10pt tolerance for column matching
            unique_col_positions = []
            sorted_x_positions = sorted(all_col_x_positions)
            
            for x_pos in sorted_x_positions:
                # Check if this position is close to any existing unique position
                is_duplicate = False
                for existing_x in unique_col_positions:
                    if abs(x_pos - existing_x) < col_tolerance:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_col_positions.append(x_pos)
            
            col_x_positions = unique_col_positions
            num_cols = len(col_x_positions)
            
            logger.info(f"Detected {num_cols} actual columns (filtered border lines) from all rows: "
                        f"{[f'{x:.1f}' for x in col_x_positions]}")
        else:
            num_cols = 0
            col_x_positions = []
            col_tolerance = 10
        
        # Add data rows
        for row_key in sorted_row_keys:
            row_cells = sorted(rows_dict[row_key], key=lambda c: c['x'])
            
            # Create a grid row with correct column assignments
            # Initialize with empty cells
            grid_row = [None] * num_cols
            
            for cell in row_cells:
                # Find which column this cell belongs to based on X position
                cell_x = cell['x']
                col_idx = None
                
                for i, col_x in enumerate(col_x_positions):
                    if abs(cell_x - col_x) < col_tolerance:
                        col_idx = i
                        break
                
                if col_idx is None:
                    # Cell doesn't match any known column, skip it
                    logger.warning(f"Cell at X={cell_x:.1f} doesn't match any column, skipping")
                    continue
                
                # Find text elements within this cell
                cell_texts = []
                for text_elem in text_elements:
                    tx, ty = text_elem['x'], text_elem['y']
                    # Check if text is within cell bounds
                    if (cell['x'] <= tx <= cell['x2'] and 
                        cell['y'] <= ty <= cell['y2']):
                        cell_texts.append(text_elem)
                
                # Sort text by vertical position (top to bottom)
                cell_texts.sort(key=lambda t: t['y'])
                
                # Combine text content
                combined_text = ' '.join(t.get('content', t.get('text', '')) for t in cell_texts)
                
                # CRITICAL ENHANCEMENT: Detect text alignment within cell
                # Analyze text position relative to cell center for intelligent alignment detection
                text_alignment = 'left'  # Default alignment
                if cell_texts:
                    # Calculate cell center
                    cell_center_x = (cell['x'] + cell['x2']) / 2
                    cell_width = cell['width']
                    
                    # Calculate text bounding box
                    text_x_min = min(t['x'] for t in cell_texts)
                    text_x_max = max(t.get('x2', t['x'] + 50) for t in cell_texts)  # Estimate x2 if not available
                    text_center_x = (text_x_min + text_x_max) / 2
                    
                    # Calculate offset from cell center
                    center_offset = abs(text_center_x - cell_center_x)
                    
                    # Alignment detection heuristics:
                    # 1. If text center is within 8% of cell width from cell center -> CENTER aligned
                    # 2. If text left edge is close to cell left (< 5pt) -> LEFT aligned
                    # 3. If text right edge is close to cell right (< 5pt) -> RIGHT aligned
                    # 4. Otherwise, check which side text is closer to
                    
                    left_margin = text_x_min - cell['x']
                    right_margin = cell['x2'] - text_x_max
                    
                    if center_offset < cell_width * 0.08:
                        # Text is centered within cell
                        text_alignment = 'center'
                        logger.debug(f"Cell text centered: offset={center_offset:.1f}pt < {cell_width*0.08:.1f}pt (8% of width)")
                    elif left_margin < 5:
                        # Text hugs left edge
                        text_alignment = 'left'
                        logger.debug(f"Cell text left-aligned: left_margin={left_margin:.1f}pt")
                    elif right_margin < 5:
                        # Text hugs right edge
                        text_alignment = 'right'
                        logger.debug(f"Cell text right-aligned: right_margin={right_margin:.1f}pt")
                    elif left_margin < right_margin * 0.7:
                        # Text is closer to left
                        text_alignment = 'left'
                    elif right_margin < left_margin * 0.7:
                        # Text is closer to right
                        text_alignment = 'right'
                    else:
                        # Margins are balanced, likely centered
                        text_alignment = 'center'
                        logger.debug(f"Cell text centered (balanced margins): left={left_margin:.1f}pt, right={right_margin:.1f}pt")
                
                # Create cell info
                # CRITICAL: Preserve PDF cell colors exactly as they are
                # Do NOT remove white backgrounds - white is a valid cell color in PDF
                # Let PDF determine the true color
                cell_fill = cell.get('fill_color')
                cell_stroke = cell.get('stroke_color')
                cell_stroke_width = cell.get('stroke_width', 0.5)
                
                # CRITICAL FIX: PowerPoint adds internal padding on top of margin settings
                # When we set margin_top = 3.76pt, PowerPoint actually renders ~5-6pt margin
                # This prevents rows from shrinking to match PDF height
                # 
                # SOLUTION: Set margin values to ZERO or very minimal (0.5pt)
                # This allows PowerPoint's auto-layout to determine spacing naturally
                # and matches PDF's actual cell padding behavior
                # 
                # Analysis of PDF page 12 "托管服务器" cell:
                # - Cell height: 21.50pt
                # - Text Y range: 129.61 -> 139.54 (9.93pt)
                # - Top margin in PDF: 5.47pt
                # - Bottom margin in PDF: 6.09pt
                # - Total: 5.47 + 9.93 + 6.09 = 21.49pt ✓
                # 
                # When we set margin_top/bottom = 3.76pt (font_size/2), PowerPoint adds
                # extra padding making total > 21.5pt, causing rows to expand.
                # 
                # NEW STRATEGY: Use MINIMAL margins (0.5pt or 0pt)
                # PowerPoint will add its own internal padding naturally
                margin_top = 0.5  # Minimal margin - let PowerPoint handle spacing
                margin_bottom = 0.5
                margin_left = 0.5
                margin_right = 0.5
                
                # We don't need font-size-based calculation anymore
                # PowerPoint's auto-layout provides sufficient spacing
                
                cell_info = {
                    'bbox': (cell['x'], cell['y'], cell['x2'], cell['y2']),
                    'width': cell['width'],
                    'height': cell['height'],
                    'text': combined_text,
                    'fill_color': cell_fill,  # Keep PDF color, including white
                    'stroke_color': cell_stroke,
                    'stroke_width': cell_stroke_width,  # Use actual PDF stroke width
                    # Store text elements for style extraction
                    'text_elements': cell_texts,
                    # Store text alignment detected from PDF
                    'text_alignment': text_alignment,
                    # Store minimal margins - PowerPoint adds internal padding automatically
                    'margin_top': margin_top,
                    'margin_bottom': margin_bottom,
                    'margin_left': margin_left,
                    'margin_right': margin_right
                }
                grid_row[col_idx] = cell_info
            
            # Fill in empty cells
            for i in range(num_cols):
                if grid_row[i] is None:
                    grid_row[i] = {
                        'bbox': (0, 0, 0, 0),
                        'width': 0,
                        'height': 0,
                        'text': '',
                        'fill_color': None,
                        'stroke_color': None,
                        'stroke_width': 0,
                        'text_elements': []
                    }
            
            grid.append(grid_row)
        
        # CRITICAL: Normalize grid to ensure all rows have the same number of columns
        # Python-pptx requires a rectangular grid
        max_cols = max(len(row) for row in grid) if grid else 0
        
        for row in grid:
            while len(row) < max_cols:
                # Add empty cell placeholder
                empty_cell = {
                    'bbox': (0, 0, 0, 0),
                    'width': 0,
                    'height': 0,
                    'text': '',
                    'fill_color': None,
                    'stroke_color': None,
                    'stroke_width': 0,
                    'text_elements': []
                }
                row.append(empty_cell)
        
        # CRITICAL: Apply default border styling to cells without borders
        # PDF tables often have a single border rectangle rather than per-cell borders
        # Find any cell with border info and use it as default for cells without borders
        default_stroke_color = None
        default_stroke_width = None
        
        for row in grid:
            for cell in row:
                if cell.get('stroke_color'):
                    default_stroke_color = cell['stroke_color']
                    default_stroke_width = cell.get('stroke_width', 0.5)
                    break
            if default_stroke_color:
                break
        
        # Apply defaults to cells without borders
        if default_stroke_color:
            for row in grid:
                for cell in row:
                    if not cell.get('stroke_color'):
                        cell['stroke_color'] = default_stroke_color
                        cell['stroke_width'] = default_stroke_width
            
            logger.debug(f"Applied default border to table cells: {default_stroke_color} @ {default_stroke_width}pt")
        
        # CRITICAL FIX: Calculate actual column widths from the cells
        # Handle sparse columns by finding ANY row that has a cell for each column
        # IMPORTANT: Use col_x_positions to derive column widths, NOT grid cells
        # Reason: Grid cells may have merged cells (e.g., table header spanning multiple columns)
        # that report incorrect widths for individual columns
        # 
        # Strategy: Calculate width as the distance between adjacent column X positions
        # This matches the actual visual column width in the PDF
        col_widths = []
        if col_x_positions and len(col_x_positions) > 0:
            for col_idx in range(len(col_x_positions)):
                if col_idx < len(col_x_positions) - 1:
                    # Width = distance to next column
                    col_width = col_x_positions[col_idx + 1] - col_x_positions[col_idx]
                else:
                    # Last column: distance to table right edge
                    col_width = table_bbox[2] - col_x_positions[col_idx]
                
                col_widths.append(col_width)
                logger.debug(f"Column {col_idx} width calculated from X positions: {col_width:.1f}pt "
                           f"(X={col_x_positions[col_idx]:.1f}pt)")
        elif grid and len(grid) > 0:
            # Fallback: try to extract from grid cells (less reliable due to merged cells)
            # STRATEGY: Search from LAST row backwards to avoid merged header cells
            # Data rows typically have the correct individual column widths
            for col_idx in range(max_cols):
                col_width_found = False
                
                # Search backwards from last row to avoid header row merged cells
                for row in reversed(grid):
                    if col_idx < len(row) and row[col_idx]['width'] > 0:
                        # Additional check: is this a reasonable column width?
                        # Merged cells spanning multiple columns are usually much wider
                        # Reasonable width: less than 40% of table width
                        cell_width = row[col_idx]['width']
                        table_width = table_bbox[2] - table_bbox[0]
                        width_ratio = cell_width / table_width if table_width > 0 else 0
                        
                        if width_ratio < 0.4:  # Not a merged cell
                            col_widths.append(cell_width)
                            col_width_found = True
                            logger.debug(f"Column {col_idx} width from data row: {cell_width:.1f}pt")
                            break
                
                if not col_width_found:
                    # Last resort: use equal distribution
                    if max_cols > 0:
                        fallback_width = (table_bbox[2] - table_bbox[0]) / max_cols
                    else:
                        fallback_width = 50.0
                    col_widths.append(fallback_width)
                    logger.debug(f"Column {col_idx} width fallback (equal dist): {fallback_width:.1f}pt")
        
        logger.debug(f"Calculated column widths (pt): {[f'{w:.1f}' for w in col_widths]}")
        
        # CRITICAL FIX: Calculate actual row heights from grid cell data
        # IMPORTANT: Use MEDIAN height instead of MAXIMUM to avoid vertically merged cells
        # distorting the row height. Vertical merged cells can span multiple rows and have
        # much larger heights than the actual row.
        # 
        # Example: Row with cells [202.6pt, 43pt, 21.5pt, 21.5pt, 43pt]
        # - Maximum: 202.6pt (WRONG - this is a vertically merged cell spanning multiple rows)
        # - Median: 43pt (CORRECT - this is the actual row height)
        # 
        # This ensures PPT table rows match PDF table rows exactly
        row_heights = []
        if grid and len(grid) > 0:
            for row_idx, row in enumerate(grid):
                # Collect all cell heights in this row
                cell_heights = []
                for cell in row:
                    cell_height = cell.get('height', 0)
                    if cell_height > 0:
                        cell_heights.append(cell_height)
                
                if not cell_heights:
                    row_heights.append(21.5)  # Default row height
                    logger.debug(f"Row {row_idx}: No valid heights, using default 21.5pt")
                    continue
                
                # SIMPLE FIX: Use minimum valid cell height for each row
                # Rationale: In PDF tables with nested/merged cells, the smallest non-zero 
                # cell height represents the actual visual row height.
                # Example Row 2 from Page 12: [202.55pt, 42.95pt, 21.47pt, 0, 42.95pt]
                # - 202.55pt: merged cell spanning multiple rows (ignore)
                # - 21.47pt: actual row height (use this)
                
                # Filter valid heights: exclude zeros and extremely small values
                valid_heights = [h for h in cell_heights if h > 5]
                
                if not valid_heights:
                    # No valid heights, use first non-zero or fallback to 20pt
                    actual_height = next((h for h in cell_heights if h > 0), 20.0)
                    logger.debug(f"Row {row_idx}: No valid heights found, using fallback {actual_height:.1f}pt")
                else:
                    # Use minimum valid height (this is the actual row height)
                    actual_height = min(valid_heights)
                    max_height = max(valid_heights)
                    logger.debug(f"Row {row_idx}: Using minimum height {actual_height:.1f}pt "
                               f"(range: {actual_height:.1f}-{max_height:.1f}pt, {len(valid_heights)} cells)")
                
                row_heights.append(actual_height)
        
        logger.debug(f"Calculated row heights (pt): {[f'{h:.1f}' for h in row_heights]}")
        
        # Store the organized and normalized grid
        table['grid'] = grid
        table['num_rows'] = len(grid)
        table['num_cols'] = max_cols
        table['col_widths'] = col_widths  # Store actual column widths in points
        table['row_heights'] = row_heights  # Store actual row heights in points
        
        logger.debug(f"Populated table with {table['num_rows']}x{table['num_cols']} grid, "
                    f"total cells: {sum(len(row) for row in grid)}")

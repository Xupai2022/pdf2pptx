"""
Chart Detector - Detects chart regions containing complex vector graphics
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import fitz

logger = logging.getLogger(__name__)


class ChartDetector:
    """
    Detects chart regions in PDF pages by analyzing clusters of vector graphics.
    Charts are typically composed of multiple shapes in close proximity.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Chart Detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.min_shapes_for_chart = config.get('min_shapes_for_chart', 3)
        # 增大距离阈值，让更多相关的shapes聚成一个cluster
        # 第14页的饼图分散较广，需要更大的阈值
        self.cluster_distance_threshold = config.get('cluster_distance_threshold', 200)
        # 降低最小面积要求，让小饼图也能被检测到
        self.min_chart_area = config.get('min_chart_area', 3000)  # pixels²
        self.chart_render_dpi = config.get('chart_render_dpi', 300)
        
    def detect_chart_regions(self, page: fitz.Page, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect chart regions in a page by analyzing shape clusters.
        
        Args:
            page: PyMuPDF page object
            shapes: List of shape elements from parser
            
        Returns:
            List of chart region dictionaries with bbox and shapes
        """
        if len(shapes) < self.min_shapes_for_chart:
            return []
        
        # Filter out page-wide backgrounds and tiny decorations
        candidate_shapes = self._filter_candidate_shapes(shapes, page)
        
        if len(candidate_shapes) < self.min_shapes_for_chart:
            return []
        
        # Cluster shapes by spatial proximity
        clusters = self._cluster_shapes(candidate_shapes)
        
        # Identify chart clusters based on criteria
        chart_regions = []
        for cluster in clusters:
            if self._is_chart_cluster(cluster, page):
                bbox = self._calculate_cluster_bbox(cluster)
                chart_region = {
                    'bbox': bbox,
                    'shapes': cluster,
                    'shape_count': len(cluster),
                    'type': 'chart'
                }
                chart_regions.append(chart_region)
                logger.info(f"Detected chart region: bbox={bbox}, {len(cluster)} shapes")
        
        # Remove overlapping chart regions (keep the larger one)
        chart_regions = self._remove_overlapping_regions(chart_regions)
        
        return chart_regions
    
    def _filter_candidate_shapes(self, shapes: List[Dict[str, Any]], page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Filter shapes to find potential chart components.
        
        Excludes:
        - Page-wide backgrounds (> 50% of page area)
        - Small decorations (< 15x15 pixels)
        - Thin lines spanning entire width/height
        
        Args:
            shapes: List of shape elements
            page: PyMuPDF page object
            
        Returns:
            Filtered list of candidate shapes
        """
        candidates = []
        page_width = page.rect.width
        page_height = page.rect.height
        page_area = page_width * page_height
        
        for shape in shapes:
            width = shape['width']
            height = shape['height']
            area = width * height
            
            # Skip page backgrounds
            if area > page_area * 0.5:
                continue
            
            # Skip tiny decorations
            # CRITICAL FIX: Increase minimum size to filter out small decorative elements
            # Small icons, bullets, and decorative circles (< 15pt) should not be chart candidates
            # Real chart elements (pie sectors, bars, etc.) are typically larger
            #
            # IMPORTANT: BUT don't filter out lines! Chart grid lines have width=0 or height=0
            # and are essential components of bar/line charts
            is_line = (width < 2 and height >= 15) or (height < 2 and width >= 15)

            if not is_line and (width < 15 or height < 15):
                continue
            
            # Skip full-width thin lines (borders, headers)
            if height < 15 and width > page_width * 0.9:
                continue
            
            # Skip full-height thin lines (borders, sidebars)
            if width < 15 and height > page_height * 0.8:
                continue
            
            candidates.append(shape)
        
        logger.debug(f"Filtered {len(shapes)} shapes to {len(candidates)} candidates")
        return candidates
    
    def _cluster_shapes(self, shapes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Cluster shapes by spatial proximity using a simple distance-based algorithm.
        Enhanced to detect overlapping shapes (stacked pie charts).
        
        Args:
            shapes: List of shape elements
            
        Returns:
            List of shape clusters (each cluster is a list of shapes)
        """
        if not shapes:
            return []
        
        # Step 1: Find overlapping shape groups (stacked pie charts)
        overlapping_clusters = self._find_overlapping_shape_groups(shapes)
        
        # Track which shapes are already in overlapping clusters
        assigned = set()
        for cluster in overlapping_clusters:
            for shape in cluster:
                assigned.add(id(shape))
        
        # Step 2: Cluster remaining shapes by spatial proximity
        clusters = overlapping_clusters[:]
        
        for i, shape in enumerate(shapes):
            if id(shape) in assigned:
                continue
            
            # Start a new cluster
            cluster = [shape]
            assigned.add(id(shape))
            
            # Find nearby shapes
            shape_center = self._get_shape_center(shape)
            
            for j, other_shape in enumerate(shapes):
                if id(other_shape) in assigned:
                    continue
                
                other_center = self._get_shape_center(other_shape)
                distance = self._euclidean_distance(shape_center, other_center)
                
                if distance <= self.cluster_distance_threshold:
                    cluster.append(other_shape)
                    assigned.add(id(other_shape))
            
            if len(cluster) >= self.min_shapes_for_chart:
                clusters.append(cluster)
        
        logger.debug(f"Clustered shapes into {len(clusters)} clusters ({len(overlapping_clusters)} overlapping)")
        return clusters
    
    def _is_chart_cluster(self, cluster: List[Dict[str, Any]], page: fitz.Page) -> bool:
        """
        Determine if a cluster represents a chart.

        Criteria:
        - At least min_shapes_for_chart shapes
        - Multiple different fill colors (charts use color coding)
        - Reasonable area (not too small, not page-sized)
        - Shapes are relatively close together OR completely overlapping

        CRITICAL FIX:
        - Exclude simple vector charts (bar charts, line charts with simple shapes)
        - These should be kept as vector elements, not rendered as images

        Args:
            cluster: List of shapes in the cluster
            page: PyMuPDF page object

        Returns:
            True if cluster is likely a chart that should be rendered as image
        """
        if len(cluster) < self.min_shapes_for_chart:
            return False

        # CRITICAL FIX: Check if this is a simple vector chart (should be kept as vectors)
        # Simple vector charts have characteristics:
        # 1. Most shapes are simple rectangles or lines
        # 2. Limited shape complexity (no curves, paths, etc.)
        # 3. Shapes are mostly non-overlapping (bar charts vs pie charts)
        if self._is_simple_vector_chart(cluster):
            logger.info(f"Detected simple vector chart (bar/line chart) - keeping as vector shapes, NOT rendering as image")
            return False

        # Check color diversity (charts typically use 2+ colors)
        colors = set()
        for shape in cluster:
            fill_color = shape.get('fill_color')
            if fill_color and fill_color not in ['#FFFFFF', '#000000']:
                colors.add(fill_color)

        # Charts should have at least 2 distinct colors (excluding black/white)
        # EXCEPTION: Allow single-color clusters if they have large colored shapes (likely pie chart slices)
        if len(colors) < 2:
            # Check if cluster contains large colored shapes (pie chart slices)
            has_large_colored_shapes = any(
                shape.get('fill_color') not in ['#FFFFFF', '#000000', None] and
                shape.get('width', 0) * shape.get('height', 0) > 5000  # Large shape (>5000 pixels²)
                for shape in cluster
            )

            if has_large_colored_shapes:
                logger.debug(f"Accepting single-color cluster due to large colored shapes (likely pie chart)")
            else:
                return False
        
        # Check if this is an overlapping cluster (stacked shapes)
        is_overlapping = self._is_overlapping_cluster(cluster)
        
        # Check cluster area
        bbox = self._calculate_cluster_bbox(cluster)
        cluster_width = bbox[2] - bbox[0]
        cluster_height = bbox[3] - bbox[1]
        cluster_area = cluster_width * cluster_height
        
        # For overlapping clusters, use more relaxed area requirements
        if is_overlapping:
            # Overlapping shapes can be smaller (like small pie chart indicators)
            min_area = max(100, self.min_chart_area * 0.1)  # 10% of normal minimum
            if cluster_area < min_area:
                logger.debug(f"Overlapping cluster too small: {cluster_area:.0f} < {min_area:.0f}")
                return False
        else:
            # Regular scattered shapes need larger area
            if cluster_area < self.min_chart_area:
                return False
        
        # Too large (likely not a compact chart)
        page_area = page.rect.width * page.rect.height
        if cluster_area > page_area * 0.4:
            return False
        
        cluster_type = "overlapping" if is_overlapping else "scattered"
        logger.debug(f"Chart cluster validated ({cluster_type}): {len(cluster)} shapes, "
                    f"{len(colors)} colors, area={cluster_area:.0f}")
        return True

    def _is_simple_vector_chart(self, cluster: List[Dict[str, Any]]) -> bool:
        """
        Determine if a cluster is a simple vector chart that should be kept as vectors.

        Simple vector charts (bar charts, line charts) have these characteristics:
        1. Primarily composed of simple rectangles and lines (not complex paths/curves)
        2. Shapes are mostly non-overlapping (unlike pie charts which have overlapping slices)
        3. Contains vertical/horizontal grid lines or axis lines
        4. Relatively low shape count (<= 30 shapes, simple bar charts don't have 100s of shapes)

        Args:
            cluster: List of shapes in the cluster

        Returns:
            True if this is a simple vector chart (should keep as vectors)
        """
        if len(cluster) == 0:
            return False

        # Analyze shape types in the cluster
        shape_types = {}
        line_count = 0
        rect_count = 0
        complex_shape_count = 0
        vertical_lines = 0
        horizontal_lines = 0
        filled_rects = 0

        for shape in cluster:
            shape_type = shape.get('shape_type', 'unknown')
            shape_types[shape_type] = shape_types.get(shape_type, 0) + 1

            # Count lines
            if shape_type == 'line':
                line_count += 1

                # Check if vertical or horizontal
                x1, y1 = shape.get('x', 0), shape.get('y', 0)
                x2, y2 = shape.get('x2', x1), shape.get('y2', y1)

                # Vertical line (x coordinates similar)
                if abs(x2 - x1) < 2:
                    vertical_lines += 1
                # Horizontal line (y coordinates similar)
                elif abs(y2 - y1) < 2:
                    horizontal_lines += 1

            # Count rectangles
            elif shape_type == 'rectangle':
                rect_count += 1

                # Check if filled (bar chart bars are usually filled)
                if shape.get('fill_color') and shape.get('fill_color') not in ['#FFFFFF', 'None', None]:
                    filled_rects += 1

            # Count complex shapes (curves, paths, etc.)
            elif shape_type in ['curve', 'bezier', 'path', 'circle', 'ellipse']:
                complex_shape_count += 1

        total_shapes = len(cluster)
        simple_shapes = line_count + rect_count

        # Criteria for simple vector chart:
        # 1. Most shapes (>70%) are simple lines or rectangles
        simple_shape_ratio = simple_shapes / total_shapes if total_shapes > 0 else 0

        # 2. Has grid/axis lines (vertical or horizontal lines)
        has_grid_lines = (vertical_lines >= 2) or (horizontal_lines >= 2)

        # 3. Low complexity (few or no curves/paths)
        low_complexity = (complex_shape_count / total_shapes < 0.3) if total_shapes > 0 else True

        # 4. NOT too many shapes (simple bar charts have 5-30 shapes, not 100s)
        reasonable_count = total_shapes <= 30

        # 5. Check for bar chart pattern: filled rectangles + grid lines
        has_bar_pattern = (filled_rects >= 1) and has_grid_lines

        # Decision logic
        is_simple = (
            simple_shape_ratio > 0.7 and  # Mostly simple shapes
            has_grid_lines and            # Has grid/axis lines
            low_complexity and            # Low complexity
            reasonable_count              # Not too many shapes
        )

        # OR explicit bar chart pattern
        is_simple = is_simple or has_bar_pattern

        if is_simple:
            logger.debug(
                f"Simple vector chart detected: {total_shapes} shapes, "
                f"{simple_shapes} simple ({simple_shape_ratio:.1%}), "
                f"{line_count} lines ({vertical_lines}V+{horizontal_lines}H), "
                f"{rect_count} rects ({filled_rects} filled), "
                f"{complex_shape_count} complex"
            )

        return is_simple

    def _is_overlapping_cluster(self, cluster: List[Dict[str, Any]]) -> bool:
        """
        Check if a cluster consists of overlapping shapes.
        
        Args:
            cluster: List of shapes
            
        Returns:
            True if shapes are overlapping (same position and size)
        """
        if len(cluster) < 2:
            return False
        
        # Get position of first shape
        first_shape = cluster[0]
        ref_pos = (first_shape['x'], first_shape['y'], 
                  first_shape['width'], first_shape['height'])
        
        # Check if all other shapes are in nearly the same position
        overlapping_count = 1
        for shape in cluster[1:]:
            pos = (shape['x'], shape['y'], shape['width'], shape['height'])
            if self._are_positions_nearly_identical(ref_pos, pos, tolerance=5.0):
                overlapping_count += 1
        
        # If most shapes are overlapping, consider it an overlapping cluster
        return overlapping_count >= len(cluster) * 0.7  # 70% threshold
    
    def _calculate_cluster_bbox(self, cluster: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
        """
        Calculate the bounding box of a shape cluster.
        
        Args:
            cluster: List of shapes
            
        Returns:
            Tuple (x0, y0, x1, y1)
        """
        if not cluster:
            return (0, 0, 0, 0)
        
        x0 = min(shape['x'] for shape in cluster)
        y0 = min(shape['y'] for shape in cluster)
        x1 = max(shape['x2'] for shape in cluster)
        y1 = max(shape['y2'] for shape in cluster)
        
        # Add minimal padding (2% on each side) to avoid capturing surrounding content
        # Previous 5% was too large and would capture nearby text/shapes
        padding_x = (x1 - x0) * 0.02
        padding_y = (y1 - y0) * 0.02
        
        return (
            max(0, x0 - padding_x),
            max(0, y0 - padding_y),
            x1 + padding_x,
            y1 + padding_y
        )
    
    def _get_shape_center(self, shape: Dict[str, Any]) -> Tuple[float, float]:
        """Get the center point of a shape."""
        return (
            (shape['x'] + shape['x2']) / 2,
            (shape['y'] + shape['y2']) / 2
        )
    
    def _euclidean_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2) ** 0.5
    
    def _find_overlapping_shape_groups(self, shapes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Find groups of shapes that are completely overlapping (stacked).
        This detects cases like pie charts made from stacked colored rectangles.
        
        Args:
            shapes: List of shape elements
            
        Returns:
            List of overlapping shape groups
        """
        groups = []
        used_indices = set()
        
        for i, shape1 in enumerate(shapes):
            if i in used_indices:
                continue
            
            group = [shape1]
            pos1 = (shape1['x'], shape1['y'], shape1['width'], shape1['height'])
            color1 = shape1.get('fill_color')
            
            # Skip if this shape has no fill color
            if not color1 or color1 in ['#FFFFFF', '#000000']:
                continue
            
            for j, shape2 in enumerate(shapes):
                if j <= i or j in used_indices:
                    continue
                
                pos2 = (shape2['x'], shape2['y'], shape2['width'], shape2['height'])
                color2 = shape2.get('fill_color')
                
                # Skip if shape2 has no fill color
                if not color2 or color2 in ['#FFFFFF', '#000000']:
                    continue
                
                # Check if positions are nearly identical (tolerance: 5pt)
                if self._are_positions_nearly_identical(pos1, pos2, tolerance=5.0):
                    # Check if colors are different
                    if color1 != color2:
                        group.append(shape2)
                        used_indices.add(j)
            
            # A valid overlapping group needs at least 2 shapes with different colors
            if len(group) >= 2:
                groups.append(group)
                used_indices.add(i)
                logger.info(f"Found overlapping shape group: {len(group)} shapes at "
                          f"({shape1['x']:.1f}, {shape1['y']:.1f}), size {shape1['width']:.1f}x{shape1['height']:.1f}")
        
        return groups
    
    def _are_positions_nearly_identical(self, pos1: Tuple[float, float, float, float], 
                                       pos2: Tuple[float, float, float, float], 
                                       tolerance: float = 5.0) -> bool:
        """
        Check if two positions are nearly identical within a tolerance.
        
        Args:
            pos1: (x, y, width, height) of first shape
            pos2: (x, y, width, height) of second shape
            tolerance: Maximum difference in pixels
            
        Returns:
            True if positions are nearly identical
        """
        x1, y1, w1, h1 = pos1
        x2, y2, w2, h2 = pos2
        
        return (abs(x1 - x2) <= tolerance and 
                abs(y1 - y2) <= tolerance and 
                abs(w1 - w2) <= tolerance and 
                abs(h1 - h2) <= tolerance)
    
    def _remove_overlapping_regions(self, regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove overlapping chart regions, keeping only the larger ones.
        
        Args:
            regions: List of chart region dictionaries
            
        Returns:
            Filtered list without overlapping regions
        """
        if len(regions) <= 1:
            return regions
        
        # Sort by area (descending)
        sorted_regions = sorted(regions, key=lambda r: 
                               (r['bbox'][2] - r['bbox'][0]) * (r['bbox'][3] - r['bbox'][1]), 
                               reverse=True)
        
        filtered = []
        for region in sorted_regions:
            bbox1 = region['bbox']
            
            # Check if this region overlaps with any already accepted region
            overlaps = False
            for accepted in filtered:
                bbox2 = accepted['bbox']
                
                # Calculate overlap
                overlap_x = max(0, min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0]))
                overlap_y = max(0, min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1]))
                overlap_area = overlap_x * overlap_y
                
                region_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
                
                # If overlap is > 50% of this region's area, skip it
                if overlap_area > region_area * 0.5:
                    overlaps = True
                    logger.info(f"Removing overlapping chart region (overlap {overlap_area:.0f}/{region_area:.0f})")
                    break
            
            if not overlaps:
                filtered.append(region)
        
        return filtered
    
    def render_chart_as_image(self, page: fitz.Page, bbox: Tuple[float, float, float, float]) -> bytes:
        """
        Render a chart region as a high-resolution PNG image.
        
        Args:
            page: PyMuPDF page object
            bbox: Bounding box (x0, y0, x1, y1) of the chart region
            
        Returns:
            PNG image data as bytes
        """
        # Create clipping rectangle
        clip_rect = fitz.Rect(bbox)
        
        # Calculate zoom matrix for high-resolution rendering
        # DPI = 72 * zoom, so zoom = DPI / 72
        zoom = self.chart_render_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        
        # Render the region
        pixmap = page.get_pixmap(matrix=matrix, clip=clip_rect, alpha=False)
        
        # Convert to PNG bytes
        png_data = pixmap.tobytes("png")
        
        logger.info(f"Rendered chart region: {pixmap.width}x{pixmap.height}px at {self.chart_render_dpi} DPI")
        
        return png_data

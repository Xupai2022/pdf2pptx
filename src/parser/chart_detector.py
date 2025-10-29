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
        self.cluster_distance_threshold = config.get('cluster_distance_threshold', 50)
        self.min_chart_area = config.get('min_chart_area', 10000)  # pixels²
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
        
        return chart_regions
    
    def _filter_candidate_shapes(self, shapes: List[Dict[str, Any]], page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Filter shapes to find potential chart components.
        
        Excludes:
        - Page-wide backgrounds (> 50% of page area)
        - Tiny decorations (< 5x5 pixels)
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
            if width < 5 or height < 5:
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
        
        Args:
            shapes: List of shape elements
            
        Returns:
            List of shape clusters (each cluster is a list of shapes)
        """
        if not shapes:
            return []
        
        clusters = []
        assigned = set()
        
        for i, shape in enumerate(shapes):
            if i in assigned:
                continue
            
            # Start a new cluster
            cluster = [shape]
            assigned.add(i)
            
            # Find nearby shapes
            shape_center = self._get_shape_center(shape)
            
            for j, other_shape in enumerate(shapes):
                if j in assigned:
                    continue
                
                other_center = self._get_shape_center(other_shape)
                distance = self._euclidean_distance(shape_center, other_center)
                
                if distance <= self.cluster_distance_threshold:
                    cluster.append(other_shape)
                    assigned.add(j)
            
            if len(cluster) >= self.min_shapes_for_chart:
                clusters.append(cluster)
        
        logger.debug(f"Clustered shapes into {len(clusters)} clusters")
        return clusters
    
    def _is_chart_cluster(self, cluster: List[Dict[str, Any]], page: fitz.Page) -> bool:
        """
        Determine if a cluster represents a chart.
        
        Criteria:
        - At least min_shapes_for_chart shapes
        - Multiple different fill colors (charts use color coding)
        - Reasonable area (not too small, not page-sized)
        - Shapes are relatively close together
        
        Args:
            cluster: List of shapes in the cluster
            page: PyMuPDF page object
            
        Returns:
            True if cluster is likely a chart
        """
        if len(cluster) < self.min_shapes_for_chart:
            return False
        
        # Check color diversity (charts typically use 2+ colors)
        colors = set()
        for shape in cluster:
            fill_color = shape.get('fill_color')
            if fill_color and fill_color not in ['#FFFFFF', '#000000']:
                colors.add(fill_color)
        
        # Charts should have at least 2 distinct colors (excluding black/white)
        if len(colors) < 2:
            return False
        
        # Check cluster area
        bbox = self._calculate_cluster_bbox(cluster)
        cluster_width = bbox[2] - bbox[0]
        cluster_height = bbox[3] - bbox[1]
        cluster_area = cluster_width * cluster_height
        
        # Too small to be a meaningful chart
        if cluster_area < self.min_chart_area:
            return False
        
        # Too large (likely not a compact chart)
        page_area = page.rect.width * page.rect.height
        if cluster_area > page_area * 0.4:
            return False
        
        logger.debug(f"Chart cluster validated: {len(cluster)} shapes, {len(colors)} colors, area={cluster_area:.0f}")
        return True
    
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
        
        # Add small padding (5% on each side)
        padding_x = (x1 - x0) * 0.05
        padding_y = (y1 - y0) * 0.05
        
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

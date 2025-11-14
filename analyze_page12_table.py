"""
Analyze table on page 12 of 安全运营月报.pdf to diagnose row height issues
"""

import fitz
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def analyze_page12_table():
    """Analyze the table structure on page 12"""
    pdf_path = "./tests/安全运营月报.pdf"
    
    doc = fitz.open(pdf_path)
    page = doc[11]  # Page 12 (0-indexed)
    
    logger.info(f"Analyzing page 12 (0-indexed: {11})")
    logger.info(f"Page dimensions: {page.rect.width} x {page.rect.height}")
    
    # Extract all shapes (table cells)
    shapes = []
    for item in page.get_drawings():
        if item.get('type') == 'f' or item.get('type') == 's':
            rect = item.get('rect')
            if rect:
                x0, y0, x1, y1 = rect
                width = x1 - x0
                height = y1 - y0
                
                shapes.append({
                    'x': x0,
                    'y': y0,
                    'x2': x1,
                    'y2': y1,
                    'width': width,
                    'height': height,
                    'fill_color': item.get('fill'),
                    'stroke_color': item.get('color')
                })
    
    logger.info(f"Found {len(shapes)} shapes on page 12")
    
    # Extract text elements
    text_blocks = page.get_text("dict")['blocks']
    text_elements = []
    
    for block in text_blocks:
        if block.get('type') == 0:  # Text block
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    text_elements.append({
                        'text': span.get('text', ''),
                        'x': span.get('bbox', [0,0,0,0])[0],
                        'y': span.get('bbox', [0,0,0,0])[1],
                        'x2': span.get('bbox', [0,0,0,0])[2],
                        'y2': span.get('bbox', [0,0,0,0])[3],
                        'font_size': span.get('size', 10),
                        'font_name': span.get('font', 'Unknown')
                    })
    
    logger.info(f"Found {len(text_elements)} text elements on page 12")
    
    # Find table cells containing "托管服务器"
    target_cells = []
    for shape in shapes:
        # Check if any text element containing "托管服务器" is within this shape
        for text_elem in text_elements:
            if "托管服务器" in text_elem['text']:
                # Check if text is within shape bounds
                if (shape['x'] <= text_elem['x'] <= shape['x2'] and
                    shape['y'] <= text_elem['y'] <= shape['y2']):
                    target_cells.append({
                        'shape': shape,
                        'text': text_elem
                    })
                    logger.info(f"\nFound '托管服务器' cell:")
                    logger.info(f"  Cell bbox: ({shape['x']:.2f}, {shape['y']:.2f}) -> ({shape['x2']:.2f}, {shape['y2']:.2f})")
                    logger.info(f"  Cell size: {shape['width']:.2f} x {shape['height']:.2f} pt")
                    logger.info(f"  Text bbox: ({text_elem['x']:.2f}, {text_elem['y']:.2f}) -> ({text_elem['x2']:.2f}, {text_elem['y2']:.2f})")
                    logger.info(f"  Font size: {text_elem['font_size']:.2f}pt")
                    logger.info(f"  Font name: {text_elem['font_name']}")
                    
                    # Calculate margins
                    margin_top = text_elem['y'] - shape['y']
                    margin_bottom = shape['y2'] - text_elem['y2']
                    margin_left = text_elem['x'] - shape['x']
                    margin_right = shape['x2'] - text_elem['x2']
                    
                    logger.info(f"  Calculated margins:")
                    logger.info(f"    Top: {margin_top:.2f}pt")
                    logger.info(f"    Bottom: {margin_bottom:.2f}pt")
                    logger.info(f"    Left: {margin_left:.2f}pt")
                    logger.info(f"    Right: {margin_right:.2f}pt")
    
    if not target_cells:
        logger.warning("Could not find '托管服务器' cell")
        
        # Show all text on the page
        logger.info("\nAll text elements on page 12:")
        for i, text_elem in enumerate(text_elements[:20]):  # Show first 20
            logger.info(f"  {i}: '{text_elem['text']}' at ({text_elem['x']:.2f}, {text_elem['y']:.2f})")
    
    # Analyze table structure
    logger.info(f"\nAnalyzing table rows...")
    
    # Group shapes by Y position to identify rows
    y_tolerance = 3.0
    rows = {}
    
    for shape in shapes:
        if shape['width'] > 5 and shape['height'] > 5:  # Filter out borders
            y_key = round(shape['y'] / y_tolerance) * y_tolerance
            if y_key not in rows:
                rows[y_key] = []
            rows[y_key].append(shape)
    
    # Sort rows by Y position
    sorted_y_keys = sorted(rows.keys())
    
    logger.info(f"Found {len(sorted_y_keys)} potential rows:")
    for i, y_key in enumerate(sorted_y_keys[:15]):  # Show first 15 rows
        row_cells = rows[y_key]
        heights = [cell['height'] for cell in row_cells]
        min_height = min(heights) if heights else 0
        max_height = max(heights) if heights else 0
        
        # Find text in this row
        row_texts = []
        for cell in row_cells:
            for text_elem in text_elements:
                if (cell['x'] <= text_elem['x'] <= cell['x2'] and
                    cell['y'] <= text_elem['y'] <= cell['y2']):
                    if text_elem['text'] and text_elem['text'].strip():
                        row_texts.append(text_elem['text'].strip())
        
        row_text_preview = ' | '.join(row_texts[:3]) if row_texts else "(no text)"
        logger.info(f"  Row {i} (Y={y_key:.1f}): {len(row_cells)} cells, "
                   f"heights {min_height:.1f}-{max_height:.1f}pt, "
                   f"text: {row_text_preview}")
    
    doc.close()

if __name__ == '__main__':
    analyze_page12_table()

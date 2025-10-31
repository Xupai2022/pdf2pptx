"""
Detailed analysis of triangle lines on page 4.
"""

import yaml
from src.parser.pdf_parser import PDFParser

def analyze_page_4_details():
    """Detailed analysis of page 4 to find the triangle lines."""
    print("="*80)
    print("DETAILED ANALYSIS OF PAGE 4 TRIANGLE")
    print("="*80)
    
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    parser = PDFParser(config['parser'])
    pdf_path = 'tests/season_report_del.pdf'
    
    if not parser.open(pdf_path):
        print("Failed to open PDF")
        return
    
    # Extract page 4 (index 3)
    page_data = parser.extract_page_elements(3)
    parser.close()
    
    print(f"\nTotal elements on page 4: {len(page_data['elements'])}")
    
    # Count element types
    element_counts = {}
    for elem in page_data['elements']:
        elem_type = elem['type']
        if elem_type == 'shape':
            elem_type = f"shape ({elem.get('shape_type', 'unknown')})"
        element_counts[elem_type] = element_counts.get(elem_type, 0) + 1
    
    print("\nElement breakdown:")
    for elem_type, count in sorted(element_counts.items()):
        print(f"  {elem_type}: {count}")
    
    # Find all line shapes
    print("\n" + "="*80)
    print("ALL LINE SHAPES ON PAGE 4")
    print("="*80)
    
    line_shapes = [elem for elem in page_data['elements'] 
                   if elem['type'] == 'shape' and elem.get('shape_type') == 'line']
    
    print(f"\nFound {len(line_shapes)} line shape(s):")
    
    for i, line in enumerate(line_shapes):
        print(f"\nLine {i+1}:")
        print(f"  Position: ({line['x']:.1f}, {line['y']:.1f}) to ({line['x2']:.1f}, {line['y2']:.1f})")
        print(f"  Size: {line['width']:.1f} x {line['height']:.1f} pt")
        print(f"  Stroke color: {line.get('stroke_color')}")
        print(f"  Stroke width: {line.get('stroke_width')}")
        print(f"  Fill color: {line.get('fill_color')}")
    
    # Find all shapes (not just lines)
    print("\n" + "="*80)
    print("ALL SHAPES ON PAGE 4")
    print("="*80)
    
    all_shapes = [elem for elem in page_data['elements'] if elem['type'] == 'shape']
    
    print(f"\nFound {len(all_shapes)} shape(s) total:")
    
    for i, shape in enumerate(all_shapes):
        print(f"\nShape {i+1}: {shape.get('shape_type', 'unknown')}")
        print(f"  Position: ({shape['x']:.1f}, {shape['y']:.1f}) to ({shape['x2']:.1f}, {shape['y2']:.1f})")
        print(f"  Size: {shape['width']:.1f} x {shape['height']:.1f} pt")
        print(f"  Stroke: {shape.get('stroke_color')} (width: {shape.get('stroke_width')})")
        print(f"  Fill: {shape.get('fill_color')}")
    
    # Check triangle region specifically
    print("\n" + "="*80)
    print("SHAPES IN TRIANGLE REGION (x: 150-450, y: 150-350)")
    print("="*80)
    
    triangle_region = {'x_min': 150, 'x_max': 450, 'y_min': 150, 'y_max': 350}
    
    shapes_in_triangle = []
    for shape in all_shapes:
        x, y = shape['x'], shape['y']
        x2, y2 = shape['x2'], shape['y2']
        
        overlaps = (
            x < triangle_region['x_max'] and x2 > triangle_region['x_min'] and
            y < triangle_region['y_max'] and y2 > triangle_region['y_min']
        )
        
        if overlaps:
            shapes_in_triangle.append(shape)
    
    print(f"\nFound {len(shapes_in_triangle)} shape(s) in triangle region:")
    
    for i, shape in enumerate(shapes_in_triangle):
        print(f"\nShape {i+1}: {shape.get('shape_type', 'unknown')}")
        print(f"  Position: ({shape['x']:.1f}, {shape['y']:.1f}) to ({shape['x2']:.1f}, {shape['y2']:.1f})")
        print(f"  Size: {shape['width']:.1f} x {shape['height']:.1f} pt")
        print(f"  Stroke: {shape.get('stroke_color')} (width: {shape.get('stroke_width')})")
        print(f"  Fill: {shape.get('fill_color')}")

if __name__ == "__main__":
    analyze_page_4_details()

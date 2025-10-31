#!/usr/bin/env python3
"""
Detailed analysis of shape detection issues
"""

import fitz
from PIL import Image
import io

def analyze_path_details(path, idx):
    """Analyze a path in detail to understand its structure"""
    items = path.get('items', [])
    rect = path.get('rect')
    fill = path.get('fill', None)
    color = path.get('color', None)
    
    if not rect:
        return None
    
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]
    aspect_ratio = width / height if height > 0 else 0
    
    # Count item types
    line_count = sum(1 for item in items if item[0] == 'l')
    curve_count = sum(1 for item in items if item[0] == 'c')
    other_count = len(items) - line_count - curve_count
    
    # Determine shape type
    shape_type = "Unknown"
    
    # Circle/Oval detection: uses curves
    if curve_count >= 4 and 0.9 <= aspect_ratio <= 1.1:
        shape_type = "Circle (4+ curves, square aspect)"
    elif curve_count >= 4 and line_count <= 2:
        shape_type = "Oval/Ellipse (4+ curves)"
    elif curve_count > 0 and line_count > 0:
        shape_type = f"Mixed (curves + lines)"
    # Triangle: 3 lines
    elif line_count == 3 and curve_count == 0:
        shape_type = "Triangle (3 lines)"
    # Single line
    elif line_count == 1 and curve_count == 0:
        shape_type = "Single Line"
    # Two lines
    elif line_count == 2 and curve_count == 0:
        shape_type = "Two Lines"
    # Rectangle: 4 lines or 1 'rect' item
    elif line_count == 4 and curve_count == 0:
        shape_type = "Rectangle (4 lines)"
    elif len(items) == 1 and items[0][0] == 're':
        shape_type = "Rectangle (re command)"
    elif line_count > 4:
        shape_type = f"Complex path ({line_count} lines)"
    
    return {
        'index': idx,
        'shape_type': shape_type,
        'width': width,
        'height': height,
        'aspect_ratio': aspect_ratio,
        'items_total': len(items),
        'lines': line_count,
        'curves': curve_count,
        'others': other_count,
        'fill': fill,
        'stroke': color,
        'rect': rect,
        'items': items
    }


def main():
    pdf_path = "tests/season_report_del.pdf"
    doc = fitz.open(pdf_path)
    
    # Analyze Page 2 (index 1) - Circle vs Rectangle issue
    print("="*80)
    print("PAGE 2 ANALYSIS - Circles converted to rectangles")
    print("="*80)
    
    page = doc[1]
    paths = page.get_drawings()
    
    print(f"\nTotal paths: {len(paths)}")
    print("\nLooking for shapes around 01/02/04 areas (circles and rectangles):")
    print()
    
    # Analyze all paths with curves (potential circles)
    potential_circles = []
    for idx, path in enumerate(paths):
        analysis = analyze_path_details(path, idx)
        if analysis and (analysis['curves'] > 0 or "Circle" in analysis['shape_type'] or "Oval" in analysis['shape_type']):
            potential_circles.append(analysis)
    
    print(f"Found {len(potential_circles)} potential circles/ovals:")
    for circ in potential_circles:
        print(f"\nPath {circ['index']}:")
        print(f"  Type: {circ['shape_type']}")
        print(f"  Size: {circ['width']:.2f} x {circ['height']:.2f}")
        print(f"  Aspect ratio: {circ['aspect_ratio']:.3f}")
        print(f"  Items: {circ['items_total']} total ({circ['lines']} lines, {circ['curves']} curves)")
        print(f"  Fill: {circ['fill']}")
        print(f"  Stroke: {circ['stroke']}")
        print(f"  Position: ({circ['rect'][0]:.1f}, {circ['rect'][1]:.1f})")
        
        # Show first few items
        if circ['items']:
            print(f"  First 3 items:")
            for i, item in enumerate(circ['items'][:3]):
                print(f"    {i+1}. {item[0]} - {len(item)} parts")
    
    # Analyze Page 4 (index 3) - Triangle lines missing
    print("\n" + "="*80)
    print("PAGE 4 ANALYSIS - Triangle side lines missing")
    print("="*80)
    
    page = doc[3]
    paths = page.get_drawings()
    
    print(f"\nTotal paths: {len(paths)}")
    print("\nLooking for triangle-related shapes (3 lines or single/double lines):")
    print()
    
    potential_triangles = []
    for idx, path in enumerate(paths):
        analysis = analyze_path_details(path, idx)
        if analysis and (analysis['lines'] <= 3 and analysis['curves'] == 0 and analysis['lines'] > 0):
            potential_triangles.append(analysis)
    
    print(f"Found {len(potential_triangles)} potential triangle parts:")
    for tri in potential_triangles:
        print(f"\nPath {tri['index']}:")
        print(f"  Type: {tri['shape_type']}")
        print(f"  Size: {tri['width']:.2f} x {tri['height']:.2f}")
        print(f"  Items: {tri['items_total']} total ({tri['lines']} lines)")
        print(f"  Fill: {tri['fill']}")
        print(f"  Stroke: {tri['stroke']}")
        print(f"  Position: ({tri['rect'][0]:.1f}, {tri['rect'][1]:.1f})")
        
        # Show all items for lines
        if tri['items']:
            print(f"  All items:")
            for i, item in enumerate(tri['items']):
                print(f"    {i+1}. Type: {item[0]}")
                if item[0] == 'l' and len(item) >= 3:
                    print(f"       From: {item[1]}")
                    print(f"       To:   {item[2]}")
    
    # Analyze Page 6 (index 5) - Image quality
    print("\n" + "="*80)
    print("PAGE 6 ANALYSIS - Large PNG image quality")
    print("="*80)
    
    page = doc[5]
    images = page.get_images()
    
    print(f"\nTotal images: {len(images)}")
    print("\nLooking for large images (>200px):")
    print()
    
    large_images = []
    for img_idx, img_info in enumerate(images):
        xref = img_info[0]
        base_image = doc.extract_image(xref)
        if base_image:
            try:
                pil_image = Image.open(io.BytesIO(base_image['image']))
                if pil_image.width > 200 or pil_image.height > 200:
                    image_rects = page.get_image_rects(xref)
                    rect = image_rects[0] if image_rects else None
                    
                    large_images.append({
                        'index': img_idx,
                        'xref': xref,
                        'width_px': pil_image.width,
                        'height_px': pil_image.height,
                        'mode': pil_image.mode,
                        'format': pil_image.format,
                        'size_bytes': len(base_image['image']),
                        'rect': rect
                    })
            except:
                pass
    
    print(f"Found {len(large_images)} large images:")
    for img in large_images:
        print(f"\nImage {img['index']} (xref {img['xref']}):")
        print(f"  Dimensions: {img['width_px']} x {img['height_px']}")
        print(f"  Mode: {img['mode']}")
        print(f"  Format: {img['format']}")
        print(f"  Size: {img['size_bytes']} bytes")
        if img['rect']:
            rect = img['rect']
            display_width = rect.x1 - rect.x0
            display_height = rect.y1 - rect.y0
            print(f"  Display size: {display_width:.2f} x {display_height:.2f} pt")
            print(f"  Scale: {img['width_px']/display_width:.2f}x (width), {img['height_px']/display_height:.2f}x (height)")
    
    doc.close()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

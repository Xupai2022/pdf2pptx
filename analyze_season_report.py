#!/usr/bin/env python3
"""
Diagnostic script to analyze season_report_del.pdf conversion issues:
1. Page 4: Triangle side lines missing (only bottom line converted)
2. Page 2: Circles under 01/02 converted to rectangles (04 is correct)
3. Page 6: Large PNG image quality issue (jagged edges)
"""

import fitz  # PyMuPDF
from PIL import Image
import io
import json

def analyze_page_shapes(doc, page_num):
    """Analyze shapes on a specific page"""
    print(f"\n{'='*80}")
    print(f"ANALYZING PAGE {page_num + 1}")
    print(f"{'='*80}")
    
    page = doc[page_num]
    
    # Get page dimensions
    rect = page.rect
    print(f"\nPage dimensions: {rect.width:.2f} x {rect.height:.2f}")
    
    # Extract paths (vector shapes)
    paths = page.get_drawings()
    print(f"\nTotal drawings/paths found: {len(paths)}")
    
    # Analyze each path
    for idx, path in enumerate(paths):
        print(f"\n--- Path {idx + 1} ---")
        print(f"Type: {path.get('type', 'Unknown')}")
        print(f"Items in path: {len(path.get('items', []))}")
        print(f"Fill: {path.get('fill', None)}")
        print(f"Color: {path.get('color', None)}")
        print(f"Width: {path.get('width', None)}")
        print(f"Rect: {path.get('rect', None)}")
        
        # Analyze items (lines, curves, etc.)
        items = path.get('items', [])
        if items:
            print(f"Items breakdown:")
            for item_idx, item in enumerate(items[:5]):  # Show first 5 items
                print(f"  Item {item_idx + 1}: {item[0]} - {item[1]}")
                if item[0] == 'l':  # line
                    print(f"    Line from {item[1]} to {item[2]}")
                elif item[0] == 'c':  # curve
                    print(f"    Curve: control points {len(item) - 1}")
            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more items")
    
    # Extract images
    images = page.get_images()
    print(f"\n{'='*40}")
    print(f"Images on page {page_num + 1}: {len(images)}")
    print(f"{'='*40}")
    
    for img_idx, img_info in enumerate(images):
        xref = img_info[0]
        print(f"\n--- Image {img_idx + 1} (xref: {xref}) ---")
        
        # Get image details
        base_image = doc.extract_image(xref)
        if base_image:
            print(f"Format: {base_image['ext']}")
            print(f"Size: {len(base_image['image'])} bytes")
            
            # Analyze with PIL
            try:
                pil_image = Image.open(io.BytesIO(base_image['image']))
                print(f"Dimensions: {pil_image.width} x {pil_image.height}")
                print(f"Mode: {pil_image.mode}")
                print(f"Format: {pil_image.format}")
                
                # Check if it's a large image
                if pil_image.width > 200 or pil_image.height > 200:
                    print(f"⚠️  LARGE IMAGE DETECTED - Potential quality issue")
                
            except Exception as e:
                print(f"Error analyzing image with PIL: {e}")
    
    # Get text blocks for context
    text_blocks = page.get_text("dict")["blocks"]
    text_count = sum(1 for b in text_blocks if b.get("type") == 0)
    print(f"\nText blocks on page: {text_count}")
    
    return paths, images


def detect_shape_type(path):
    """Detect if a path is a circle, rectangle, triangle, or line"""
    items = path.get('items', [])
    rect = path.get('rect')
    
    if not items or not rect:
        return "Unknown"
    
    # Check for single line
    if len(items) == 1 and items[0][0] == 'l':
        return "Line"
    
    # Check for triangle (3 lines forming a closed path)
    if len(items) == 3:
        line_count = sum(1 for item in items if item[0] == 'l')
        if line_count == 3:
            return "Triangle"
    
    # Check for rectangle (4 lines)
    if len(items) == 4:
        line_count = sum(1 for item in items if item[0] == 'l')
        if line_count == 4:
            return "Rectangle"
    
    # Check for circle (curves)
    curve_count = sum(1 for item in items if item[0] == 'c')
    if curve_count >= 4:  # Typically circles use 4 Bezier curves
        # Check if bounding box is roughly square
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        aspect_ratio = width / height if height > 0 else 0
        if 0.9 <= aspect_ratio <= 1.1:
            return "Circle/Oval"
    
    return f"Complex ({len(items)} items, {curve_count} curves)"


def main():
    pdf_path = "tests/season_report_del.pdf"
    
    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    
    print(f"Total pages: {len(doc)}")
    
    # Analyze Page 2 (index 1) - Circle/Rectangle issue
    print("\n" + "="*80)
    print("ISSUE 1: Page 2 - Circles under 01/02 converted to rectangles")
    print("="*80)
    paths_p2, images_p2 = analyze_page_shapes(doc, 1)
    
    print(f"\nShape type detection for Page 2:")
    for idx, path in enumerate(paths_p2[:20]):  # First 20 shapes
        shape_type = detect_shape_type(path)
        rect = path.get('rect')
        if rect:
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            print(f"Path {idx + 1}: {shape_type} - Size: {width:.2f}x{height:.2f}")
    
    # Analyze Page 4 (index 3) - Triangle lines missing
    print("\n" + "="*80)
    print("ISSUE 2: Page 4 - Triangle side lines missing")
    print("="*80)
    paths_p4, images_p4 = analyze_page_shapes(doc, 3)
    
    print(f"\nShape type detection for Page 4:")
    for idx, path in enumerate(paths_p4):
        shape_type = detect_shape_type(path)
        rect = path.get('rect')
        if rect:
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            print(f"Path {idx + 1}: {shape_type} - Size: {width:.2f}x{height:.2f} - Items: {len(path.get('items', []))}")
            
            # Show detailed path info for potential triangles
            if "Triangle" in shape_type or len(path.get('items', [])) <= 3:
                print(f"  Detailed items:")
                for item in path.get('items', []):
                    print(f"    {item}")
    
    # Analyze Page 6 (index 5) - Image quality issue
    print("\n" + "="*80)
    print("ISSUE 3: Page 6 - Large PNG image quality")
    print("="*80)
    paths_p6, images_p6 = analyze_page_shapes(doc, 5)
    
    doc.close()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

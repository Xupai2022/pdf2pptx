"""
Analyze duplication issue in season_report_del.pdf conversion.

The problem:
- Page 4: Triangle region has both vector shapes (lines) AND a PNG overlay
- Page 6: Large images include extra content (text) that's already extracted separately

This causes overlapping/shadowing effects.
"""

import fitz
from src.parser.pdf_parser import PDFParser
import yaml
from pathlib import Path

def analyze_page_4_triangle():
    """Analyze page 4 triangle region to find duplication."""
    print("\n" + "="*80)
    print("ANALYZING PAGE 4 - TRIANGLE REGION")
    print("="*80)
    
    # Load config
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    parser = PDFParser(config['parser'])
    pdf_path = 'tests/season_report_del.pdf'
    
    if not parser.open(pdf_path):
        print("Failed to open PDF")
        return
    
    # Extract page 4 (index 3)
    page_data = parser.extract_page_elements(3)
    
    print(f"\nTotal elements on page 4: {len(page_data['elements'])}")
    
    # Triangle is around middle of page
    # Expected region: approximately x: 150-450, y: 150-350
    triangle_region = {
        'x_min': 150, 'x_max': 450,
        'y_min': 150, 'y_max': 350
    }
    
    print(f"\nSearching for elements in triangle region:")
    print(f"  X: {triangle_region['x_min']}-{triangle_region['x_max']}")
    print(f"  Y: {triangle_region['y_min']}-{triangle_region['y_max']}")
    
    images_in_region = []
    shapes_in_region = []
    lines_in_region = []
    
    for elem in page_data['elements']:
        x, y = elem.get('x', 0), elem.get('y', 0)
        x2, y2 = elem.get('x2', 0), elem.get('y2', 0)
        
        # Check if element overlaps with triangle region
        overlaps = (
            x < triangle_region['x_max'] and x2 > triangle_region['x_min'] and
            y < triangle_region['y_max'] and y2 > triangle_region['y_min']
        )
        
        if overlaps:
            if elem['type'] == 'image':
                images_in_region.append(elem)
            elif elem['type'] == 'shape':
                if elem.get('shape_type') == 'line':
                    lines_in_region.append(elem)
                else:
                    shapes_in_region.append(elem)
    
    print(f"\n  Images found: {len(images_in_region)}")
    print(f"  Lines found: {len(lines_in_region)}")
    print(f"  Other shapes found: {len(shapes_in_region)}")
    
    # Show details of images
    if images_in_region:
        print("\n  IMAGE DETAILS:")
        for i, img in enumerate(images_in_region):
            print(f"    Image {i+1}:")
            print(f"      Position: ({img['x']:.1f}, {img['y']:.1f}) to ({img['x2']:.1f}, {img['y2']:.1f})")
            print(f"      Size: {img['width']:.1f} x {img['height']:.1f} pt")
            print(f"      Pixels: {img['width_px']} x {img['height_px']} px")
            print(f"      Was rerendered: {img.get('was_rerendered', False)}")
    
    # Show details of lines
    if lines_in_region:
        print("\n  LINE DETAILS:")
        for i, line in enumerate(lines_in_region):
            print(f"    Line {i+1}:")
            print(f"      Position: ({line['x']:.1f}, {line['y']:.1f}) to ({line['x2']:.1f}, {line['y2']:.1f})")
            print(f"      Size: {line['width']:.1f} x {line['height']:.1f} pt")
            print(f"      Stroke: {line.get('stroke_color')}, width: {line.get('stroke_width')}")
    
    # CRITICAL CHECK: Are there both images AND lines in the same region?
    if images_in_region and lines_in_region:
        print("\n  ⚠️  DUPLICATION DETECTED!")
        print("  Both images and vector lines exist in the same region.")
        print("  The image is likely overlaying the vector shapes.")
    
    parser.close()

def analyze_page_6_images():
    """Analyze page 6 images to find overlapping text."""
    print("\n" + "="*80)
    print("ANALYZING PAGE 6 - IMAGE/TEXT OVERLAP")
    print("="*80)
    
    # Load config
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    parser = PDFParser(config['parser'])
    pdf_path = 'tests/season_report_del.pdf'
    
    if not parser.open(pdf_path):
        print("Failed to open PDF")
        return
    
    # Extract page 6 (index 5)
    page_data = parser.extract_page_elements(5)
    
    print(f"\nTotal elements on page 6: {len(page_data['elements'])}")
    
    # Find large images
    large_images = []
    texts = []
    
    for elem in page_data['elements']:
        if elem['type'] == 'image':
            if elem['width_px'] > 200 or elem['height_px'] > 200:
                large_images.append(elem)
        elif elem['type'] == 'text':
            texts.append(elem)
    
    print(f"\nLarge images (>200px): {len(large_images)}")
    print(f"Text elements: {len(texts)}")
    
    # Check for overlaps
    for i, img in enumerate(large_images):
        print(f"\n  Large Image {i+1}:")
        print(f"    Position: ({img['x']:.1f}, {img['y']:.1f}) to ({img['x2']:.1f}, {img['y2']:.1f})")
        print(f"    Size: {img['width']:.1f} x {img['height']:.1f} pt")
        print(f"    Pixels: {img['width_px']} x {img['height_px']} px")
        print(f"    Was rerendered: {img.get('was_rerendered', False)}")
        
        # Find overlapping text
        overlapping_texts = []
        for text in texts:
            # Check if text overlaps with image
            text_x, text_y = text['x'], text['y']
            text_x2, text_y2 = text['x2'], text['y2']
            
            overlaps = (
                text_x < img['x2'] and text_x2 > img['x'] and
                text_y < img['y2'] and text_y2 > img['y']
            )
            
            if overlaps:
                overlapping_texts.append(text)
        
        if overlapping_texts:
            print(f"    ⚠️  {len(overlapping_texts)} overlapping text elements detected:")
            for j, text in enumerate(overlapping_texts[:5]):  # Show first 5
                print(f"      Text {j+1}: '{text['content'][:30]}...'")
                print(f"        Position: ({text['x']:.1f}, {text['y']:.1f})")
            
            if len(overlapping_texts) > 5:
                print(f"      ... and {len(overlapping_texts) - 5} more")
    
    parser.close()

def check_raw_pdf_structure():
    """Check raw PDF structure to understand the issue."""
    print("\n" + "="*80)
    print("CHECKING RAW PDF STRUCTURE")
    print("="*80)
    
    doc = fitz.open('tests/season_report_del.pdf')
    
    # Page 4 analysis
    print("\nPAGE 4 - Raw extraction:")
    page4 = doc[3]
    
    # Get images
    images = page4.get_images(full=True)
    print(f"  Total images on page 4: {len(images)}")
    
    # Get drawings
    drawings = page4.get_drawings()
    print(f"  Total drawings on page 4: {len(drawings)}")
    
    # Find drawings in triangle region
    triangle_region = {'x_min': 150, 'x_max': 450, 'y_min': 150, 'y_max': 350}
    triangle_drawings = []
    
    for drawing in drawings:
        rect = drawing.get('rect')
        if rect:
            overlaps = (
                rect.x0 < triangle_region['x_max'] and rect.x1 > triangle_region['x_min'] and
                rect.y0 < triangle_region['y_max'] and rect.y1 > triangle_region['y_min']
            )
            if overlaps:
                triangle_drawings.append(drawing)
    
    print(f"  Drawings in triangle region: {len(triangle_drawings)}")
    
    # Page 6 analysis
    print("\nPAGE 6 - Raw extraction:")
    page6 = doc[5]
    
    images = page6.get_images(full=True)
    print(f"  Total images on page 6: {len(images)}")
    
    # Analyze each image
    for i, img_info in enumerate(images):
        xref = img_info[0]
        base_image = doc.extract_image(xref)
        
        if base_image:
            from PIL import Image
            import io
            
            image_bytes = base_image["image"]
            pil_image = Image.open(io.BytesIO(image_bytes))
            width, height = pil_image.size
            
            if width > 200 or height > 200:
                # Get position
                image_rects = page6.get_image_rects(xref)
                if image_rects:
                    rect = image_rects[0]
                    print(f"\n  Large Image {i+1}:")
                    print(f"    Embedded size: {width}x{height}px")
                    print(f"    Position on page: ({rect.x0:.1f}, {rect.y0:.1f}) to ({rect.x1:.1f}, {rect.y1:.1f})")
                    print(f"    Mode: {pil_image.mode}")
    
    doc.close()

if __name__ == "__main__":
    print("Analyzing duplication issues in season_report_del.pdf")
    
    check_raw_pdf_structure()
    analyze_page_4_triangle()
    analyze_page_6_images()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

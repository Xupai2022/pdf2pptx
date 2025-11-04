#!/usr/bin/env python3
"""
Analyze shapes in the PDF to understand the black/green rectangle issue.
"""

import fitz
import sys
from collections import defaultdict

def analyze_pdf_shapes(pdf_path, page_num):
    """Analyze shapes on a specific page of the PDF."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    print(f"\n{'='*80}")
    print(f"Analyzing Page {page_num + 1} of {pdf_path}")
    print(f"{'='*80}\n")
    
    # Get text blocks for reference
    text_dict = page.get_text("dict")
    print(f"Text blocks on page: {len(text_dict.get('blocks', []))}\n")
    
    # Get drawings (shapes)
    drawings = page.get_drawings()
    print(f"Total drawings (shapes) on page: {len(drawings)}\n")
    
    # Analyze shapes by color
    color_counts = defaultdict(int)
    small_colored_shapes = []
    
    for idx, drawing in enumerate(drawings):
        rect = drawing.get("rect")
        if not rect:
            continue
        
        fill_color = drawing.get("fill", None)
        stroke_color = drawing.get("color", None)
        
        # Convert to hex
        def rgb_to_hex(rgb_tuple):
            if rgb_tuple is None:
                return None
            if isinstance(rgb_tuple, (int, float)):
                rgb_tuple = (rgb_tuple, rgb_tuple, rgb_tuple)
            return '#{:02X}{:02X}{:02X}'.format(
                int(rgb_tuple[0] * 255),
                int(rgb_tuple[1] * 255),
                int(rgb_tuple[2] * 255)
            )
        
        fill_hex = rgb_to_hex(fill_color)
        stroke_hex = rgb_to_hex(stroke_color)
        
        if fill_hex:
            color_counts[f"fill_{fill_hex}"] += 1
        if stroke_hex and stroke_hex != fill_hex:
            color_counts[f"stroke_{stroke_hex}"] += 1
        
        # Focus on small shapes (likely text decoration)
        width = rect.width
        height = rect.height
        
        # Check for small shapes with specific colors (black #13161A or green #12A678)
        if fill_hex in ['#13161A', '#000000', '#12A678', '#13161A']:
            small_colored_shapes.append({
                'index': idx,
                'bbox': (rect.x0, rect.y0, rect.x1, rect.y1),
                'width': width,
                'height': height,
                'fill_color': fill_hex,
                'stroke_color': stroke_hex,
                'items': len(drawing.get('items', []))
            })
    
    # Print color distribution
    print("Color Distribution:")
    for color, count in sorted(color_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  {color}: {count}")
    
    # Print small colored shapes (potentially problematic)
    print(f"\n\nSmall shapes with black/green colors: {len(small_colored_shapes)}")
    print("\nDetailed view of potentially problematic shapes:")
    for shape in small_colored_shapes[:30]:  # Show first 30
        print(f"  Shape #{shape['index']}: "
              f"bbox=({shape['bbox'][0]:.1f}, {shape['bbox'][1]:.1f}, {shape['bbox'][2]:.1f}, {shape['bbox'][3]:.1f}), "
              f"size={shape['width']:.1f}x{shape['height']:.1f}, "
              f"fill={shape['fill_color']}, "
              f"items={shape['items']}")
    
    # Check if shapes overlap with text
    print("\n\nChecking if shapes overlap with text...")
    for block_idx, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    text_bbox = span.get("bbox", [0, 0, 0, 0])
                    
                    # Check overlaps
                    for shape in small_colored_shapes:
                        shape_bbox = shape['bbox']
                        
                        # Check if shapes overlap or are very close
                        x_overlap = not (shape_bbox[2] < text_bbox[0] or shape_bbox[0] > text_bbox[2])
                        y_overlap = not (shape_bbox[3] < text_bbox[1] or shape_bbox[1] > text_bbox[3])
                        
                        # Check if shape is very close to text (within 5 points)
                        x_close = abs(shape_bbox[0] - text_bbox[0]) < 5 or abs(shape_bbox[2] - text_bbox[2]) < 5
                        y_close = abs(shape_bbox[1] - text_bbox[1]) < 5 or abs(shape_bbox[3] - text_bbox[3]) < 5
                        
                        if (x_overlap and y_overlap) or (x_close and y_close):
                            is_bold = bool(span.get("flags", 0) & 2**4)
                            text_color = span.get("color", 0)
                            
                            # Convert text color to hex
                            if isinstance(text_color, (int, float)):
                                text_hex = f"#{int(text_color):06X}"
                            else:
                                text_hex = "N/A"
                            
                            print(f"  OVERLAP FOUND:")
                            print(f"    Text: \"{text[:40]}\" at ({text_bbox[0]:.1f}, {text_bbox[1]:.1f})")
                            print(f"    Text color: {text_hex}, Bold: {is_bold}")
                            print(f"    Shape: fill={shape['fill_color']} at ({shape_bbox[0]:.1f}, {shape_bbox[1]:.1f}), "
                                  f"size={shape['width']:.1f}x{shape['height']:.1f}")
                            print()
    
    doc.close()

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "tests/安全运营月报.pdf"
    
    # Analyze pages 2 (index 2, shown as page 3) and 3 (index 3, shown as page 4)
    for page_idx in [2, 3]:
        analyze_pdf_shapes(pdf_path, page_idx)

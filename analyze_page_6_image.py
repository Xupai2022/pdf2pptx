#!/usr/bin/env python3
"""
Analyze page 6 image and text overlap issue.
"""

import fitz
from PIL import Image
import io

def analyze_page_6():
    """Analyze page 6 to understand image and text positions."""
    print("="*80)
    print("Page 6 Analysis - Image Quality and Text Overlap")
    print("="*80)
    
    doc = fitz.open("tests/season_report_del.pdf")
    page = doc[5]  # Page 6 (0-indexed)
    
    # Get images
    image_list = page.get_image_info()
    print(f"\n📷 Images found: {len(image_list)}")
    
    for i, img in enumerate(image_list):
        bbox = img.get('bbox', (0, 0, 0, 0))
        xref = img.get('xref', 0)
        
        print(f"\n  Image {i+1}:")
        print(f"    BBox: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})")
        print(f"    Size: {bbox[2]-bbox[0]:.2f} x {bbox[3]-bbox[1]:.2f} pt")
        
        try:
            pix = fitz.Pixmap(doc, xref)
            print(f"    Pixel size: {pix.width} x {pix.height}")
            print(f"    Mode: {pix.colorspace.name if pix.colorspace else 'N/A'}, Alpha: {pix.alpha}")
            
            # Check if large
            is_large = bbox[2] - bbox[0] > 200 or bbox[3] - bbox[1] > 200
            print(f"    Large image: {is_large}")
            
        except Exception as e:
            print(f"    Error reading pixmap: {e}")
    
    # Get text blocks
    text_blocks = page.get_text("dict")["blocks"]
    text_only = [b for b in text_blocks if b.get("type") == 0]
    
    print(f"\n📝 Text blocks: {len(text_only)}")
    
    # Find "30.46分" text
    target_texts = []
    for block in text_only:
        bbox = block.get("bbox", [])
        text = "".join([span.get("text", "") for line in block.get("lines", []) for span in line.get("spans", [])])
        if "30.46" in text or "30.46分" in text:
            target_texts.append({
                'text': text,
                'bbox': bbox,
                'y': bbox[1]
            })
    
    if target_texts:
        print(f"\n🎯 Found target text(s):")
        for t in target_texts:
            print(f"    '{t['text']}' at bbox ({t['bbox'][0]:.2f}, {t['bbox'][1]:.2f}, {t['bbox'][2]:.2f}, {t['bbox'][3]:.2f})")
    
    # Check overlaps
    if image_list and target_texts:
        print(f"\n🔍 Checking overlaps:")
        for i, img in enumerate(image_list):
            img_bbox = img.get('bbox', (0, 0, 0, 0))
            
            for t in target_texts:
                text_bbox = t['bbox']
                
                # Check if bboxes overlap
                overlap_x = not (img_bbox[2] < text_bbox[0] or img_bbox[0] > text_bbox[2])
                overlap_y = not (img_bbox[3] < text_bbox[1] or img_bbox[1] > text_bbox[3])
                
                if overlap_x and overlap_y:
                    print(f"\n  ⚠️  Image {i+1} OVERLAPS with text '{t['text']}'")
                    print(f"      Image bbox: ({img_bbox[0]:.2f}, {img_bbox[1]:.2f}, {img_bbox[2]:.2f}, {img_bbox[3]:.2f})")
                    print(f"      Text bbox:  ({text_bbox[0]:.2f}, {text_bbox[1]:.2f}, {text_bbox[2]:.2f}, {text_bbox[3]:.2f})")
                    
                    # Calculate safe rerender bbox (exclude text)
                    # If text is above image, start rerender below text
                    if text_bbox[3] < img_bbox[3]:  # Text bottom < image bottom
                        safe_bbox = (img_bbox[0], text_bbox[3] + 2, img_bbox[2], img_bbox[3])
                        print(f"      Safe rerender bbox (excluding text): ({safe_bbox[0]:.2f}, {safe_bbox[1]:.2f}, {safe_bbox[2]:.2f}, {safe_bbox[3]:.2f})")
    
    # Get vector shapes
    drawings = page.get_drawings()
    print(f"\n📐 Vector drawings: {len(drawings)}")
    
    doc.close()


if __name__ == "__main__":
    analyze_page_6()

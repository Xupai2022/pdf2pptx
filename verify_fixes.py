#!/usr/bin/env python3
"""
Verify that all three issues have been fixed in the conversion
"""

import fitz
import sys
from pathlib import Path

def verify_circles_on_page_2(pdf_path):
    """Verify circles are properly detected on page 2"""
    print("\n" + "="*80)
    print("VERIFICATION 1: Page 2 - Circle Detection")
    print("="*80)
    
    doc = fitz.open(pdf_path)
    page = doc[1]  # Page 2 (0-indexed)
    
    # Import parser to test shape detection
    sys.path.insert(0, str(Path.cwd()))
    from src.parser.pdf_parser import PDFParser
    
    config = {'dpi': 300, 'extract_images': True}
    parser = PDFParser(config)
    
    drawings = page.get_drawings()
    circles_detected = 0
    
    for drawing in drawings:
        detected_type = parser._detect_shape_type(drawing)
        rect = drawing.get('rect')
        
        if detected_type == 'oval':
            circles_detected += 1
            print(f"✓ Circle detected at ({rect.x0:.1f}, {rect.y0:.1f}), size: {rect.width:.1f}x{rect.height:.1f}")
    
    doc.close()
    
    print(f"\nResult: {circles_detected} circles detected")
    if circles_detected >= 5:
        print("✅ PASS: Circles are properly detected (expected at least 5)")
        return True
    else:
        print("❌ FAIL: Not enough circles detected")
        return False


def verify_lines_on_page_4(pdf_path):
    """Verify triangle lines are detected on page 4"""
    print("\n" + "="*80)
    print("VERIFICATION 2: Page 4 - Triangle Line Detection")
    print("="*80)
    
    doc = fitz.open(pdf_path)
    page = doc[3]  # Page 4 (0-indexed)
    
    sys.path.insert(0, str(Path.cwd()))
    from src.parser.pdf_parser import PDFParser
    
    config = {'dpi': 300, 'extract_images': True}
    parser = PDFParser(config)
    
    drawings = page.get_drawings()
    lines_detected = 0
    diagonal_lines = 0
    
    for drawing in drawings:
        detected_type = parser._detect_shape_type(drawing)
        rect = drawing.get('rect')
        
        if detected_type == 'line':
            lines_detected += 1
            width = rect.width
            height = rect.height
            
            # Check if diagonal (both dimensions significant)
            if width > 50 and height > 50:
                diagonal_lines += 1
                print(f"✓ Diagonal line detected: {width:.1f}x{height:.1f} at ({rect.x0:.1f}, {rect.y0:.1f})")
            else:
                print(f"✓ Line detected: {width:.1f}x{height:.1f} at ({rect.x0:.1f}, {rect.y0:.1f})")
    
    doc.close()
    
    print(f"\nResult: {lines_detected} lines total, {diagonal_lines} diagonal lines")
    if diagonal_lines >= 2:
        print("✅ PASS: Triangle diagonal lines are detected (expected at least 2)")
        return True
    else:
        print("❌ FAIL: Missing diagonal lines for triangle")
        return False


def verify_image_quality_page_6(pdf_path):
    """Verify large images will be re-rendered on page 6"""
    print("\n" + "="*80)
    print("VERIFICATION 3: Page 6 - Large Image Quality")
    print("="*80)
    
    doc = fitz.open(pdf_path)
    page = doc[5]  # Page 6 (0-indexed)
    
    sys.path.insert(0, str(Path.cwd()))
    from src.parser.pdf_parser import PDFParser
    from PIL import Image
    import io
    
    config = {'dpi': 300, 'extract_images': True}
    parser = PDFParser(config)
    
    images = page.get_images()
    large_images_to_rerender = 0
    
    for img_info in images:
        xref = img_info[0]
        base_image = doc.extract_image(xref)
        
        if base_image:
            pil_image = Image.open(io.BytesIO(base_image['image']))
            quality_status = parser._check_image_quality(pil_image)
            
            if pil_image.width > 200 or pil_image.height > 200:
                if quality_status == 'rerender':
                    large_images_to_rerender += 1
                    print(f"✓ Large image will be re-rendered: {pil_image.width}x{pil_image.height}px")
                else:
                    print(f"  Large image: {pil_image.width}x{pil_image.height}px (status: {quality_status})")
    
    doc.close()
    
    print(f"\nResult: {large_images_to_rerender} large images marked for re-rendering")
    if large_images_to_rerender >= 3:
        print("✅ PASS: Large images will be re-rendered for better quality (expected at least 3)")
        return True
    else:
        print("❌ FAIL: Not enough large images marked for re-rendering")
        return False


def main():
    pdf_path = "tests/season_report_del.pdf"
    
    print("="*80)
    print("VERIFYING SEASON_REPORT_DEL.PDF FIXES")
    print("="*80)
    
    # Run all verifications
    test1 = verify_circles_on_page_2(pdf_path)
    test2 = verify_lines_on_page_4(pdf_path)
    test3 = verify_image_quality_page_6(pdf_path)
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print(f"1. Circle detection (Page 2):      {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"2. Triangle lines (Page 4):        {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"3. Large image quality (Page 6):   {'✅ PASS' if test3 else '❌ FAIL'}")
    
    if all([test1, test2, test3]):
        print("\n🎉 ALL VERIFICATIONS PASSED!")
        return 0
    else:
        print("\n⚠️  SOME VERIFICATIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

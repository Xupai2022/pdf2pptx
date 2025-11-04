"""
Analyze PNG images in PDF to detect black background issues
"""

import fitz  # PyMuPDF
from PIL import Image
import io
import sys

def analyze_pdf_images(pdf_path, pages_to_check):
    """
    Analyze PNG images in specific pages of a PDF
    """
    doc = fitz.open(pdf_path)
    
    print(f"=== Analyzing PDF: {pdf_path} ===\n")
    
    for page_num in pages_to_check:
        if page_num >= len(doc):
            print(f"Page {page_num + 1} does not exist (total pages: {len(doc)})")
            continue
            
        page = doc[page_num]
        image_list = page.get_images(full=True)
        
        print(f"\n{'='*60}")
        print(f"Page {page_num + 1} - Found {len(image_list)} images")
        print(f"{'='*60}")
        
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            
            if not base_image:
                print(f"  Image {img_index + 1}: Could not extract")
                continue
            
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Get image metadata
            pil_image = Image.open(io.BytesIO(image_bytes))
            width, height = pil_image.size
            mode = pil_image.mode
            
            # Get position on page
            image_rects = page.get_image_rects(xref)
            if image_rects:
                rect = image_rects[0]
                pos = f"({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f})"
            else:
                pos = "Unknown"
            
            print(f"\n  Image {img_index + 1}:")
            print(f"    Format: {image_ext.upper()}")
            print(f"    Size: {width}x{height}px")
            print(f"    Mode: {mode}")
            print(f"    Position: {pos}")
            
            # Analyze color distribution for PNG images
            if image_ext.lower() in ['png', 'jpeg', 'jpg']:
                # Sample multiple points to check for black background
                sample_points = [
                    (0, 0), (width//2, 0), (width-1, 0),  # Top row
                    (0, height//2), (width//2, height//2), (width-1, height//2),  # Middle row
                    (0, height-1), (width//2, height-1), (width-1, height-1)  # Bottom row
                ]
                
                colors = []
                for x, y in sample_points:
                    try:
                        pixel = pil_image.getpixel((x, y))
                        if not isinstance(pixel, tuple):
                            pixel = (pixel, pixel, pixel)
                        colors.append(pixel)
                    except:
                        continue
                
                # Check for black pixels
                black_count = sum(1 for c in colors if all(ch < 30 for ch in c[:3]))
                white_count = sum(1 for c in colors if all(ch > 225 for ch in c[:3]))
                
                print(f"    Sample analysis (9 points):")
                print(f"      Black pixels: {black_count}/9")
                print(f"      White pixels: {white_count}/9")
                print(f"      Sample colors: {colors[:3]}")
                
                # Check if image has alpha channel
                has_alpha = mode in ['RGBA', 'LA', 'PA']
                print(f"    Has alpha channel: {has_alpha}")
                
                if black_count >= 5 and not has_alpha and mode == 'RGB':
                    print(f"    ⚠️  WARNING: Likely has black background issue!")
                    print(f"    This is an RGB image (no alpha) with mostly black pixels")
                
                # Analyze alpha channel if present
                if has_alpha and mode == 'RGBA':
                    alpha_values = []
                    for x, y in sample_points:
                        try:
                            pixel = pil_image.getpixel((x, y))
                            if len(pixel) >= 4:
                                alpha_values.append(pixel[3])
                        except:
                            continue
                    
                    if alpha_values:
                        avg_alpha = sum(alpha_values) / len(alpha_values)
                        print(f"    Alpha channel analysis:")
                        print(f"      Average alpha: {avg_alpha:.1f}/255")
                        print(f"      Alpha values: {alpha_values[:5]}")
    
    doc.close()

if __name__ == "__main__":
    pdf_path = "tests/安全运营月报.pdf"
    
    # Check pages mentioned: 3, 4, 5, 10, 11, 13 (convert to 0-indexed)
    pages_to_check = [2, 3, 4, 9, 10, 12]  # 0-indexed
    
    analyze_pdf_images(pdf_path, pages_to_check)

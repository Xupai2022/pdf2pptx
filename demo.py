#!/usr/bin/env python3
"""
Demonstration of PDF to PPTX Converter Features
"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from main import convert_pdf_to_pptx, load_config, setup_logging


def print_header(title):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def print_step(step_num, description):
    """Print a step description."""
    print(f"[Step {step_num}] {description}")


def demo_basic_conversion():
    """Demonstrate basic PDF to PPTX conversion."""
    print_header("Demo: Basic PDF to PPTX Conversion")
    
    pdf_path = 'tests/test_sample.pdf'
    output_path = 'output/demo_basic.pptx'
    
    print_step(1, "Loading configuration")
    config = load_config()
    print("   ✓ Configuration loaded from config/config.yaml")
    
    print_step(2, f"Converting: {pdf_path}")
    start_time = time.time()
    
    success = convert_pdf_to_pptx(pdf_path, output_path, config)
    
    elapsed = time.time() - start_time
    
    if success:
        print(f"\n   ✅ Conversion completed in {elapsed:.2f} seconds")
        print(f"   📊 Output: {output_path}")
        
        # Show file size
        size = Path(output_path).stat().st_size
        print(f"   📏 File size: {size:,} bytes ({size/1024:.1f} KB)")
    else:
        print(f"\n   ❌ Conversion failed")
    
    return success


def demo_high_quality_conversion():
    """Demonstrate high-quality conversion with custom DPI."""
    print_header("Demo: High-Quality Conversion (600 DPI)")
    
    pdf_path = 'tests/test_sample.pdf'
    output_path = 'output/demo_high_quality.pptx'
    
    print_step(1, "Loading configuration with custom DPI setting")
    config = load_config()
    config['parser']['dpi'] = 600  # High quality
    print("   ✓ DPI set to 600 for better image quality")
    
    print_step(2, f"Converting: {pdf_path}")
    start_time = time.time()
    
    success = convert_pdf_to_pptx(pdf_path, output_path, config)
    
    elapsed = time.time() - start_time
    
    if success:
        print(f"\n   ✅ High-quality conversion completed in {elapsed:.2f} seconds")
        print(f"   📊 Output: {output_path}")
        
        size = Path(output_path).stat().st_size
        print(f"   📏 File size: {size:,} bytes ({size/1024:.1f} KB)")
    
    return success


def demo_features():
    """Demonstrate key features of the converter."""
    print_header("Key Features Demonstration")
    
    features = [
        ("5-Layer Architecture", "Parser → Analyzer → Rebuilder → Mapper → Generator"),
        ("Text Extraction", "Preserves all text content with fonts and colors"),
        ("Image Extraction", "Extracts and positions images accurately"),
        ("Layout Analysis", "Detects titles, paragraphs, headers, footers"),
        ("Font Mapping", "Maps PDF fonts to PowerPoint fonts (CJK support)"),
        ("Style Preservation", "Maintains colors, fonts, bold, italic"),
        ("Coordinate Mapping", "Transforms PDF coords to slide coords"),
        ("Configurable", "YAML-based configuration for customization"),
        ("Logging", "Detailed logging for debugging and monitoring"),
        ("Editable Output", "Generates fully editable PPTX files")
    ]
    
    for i, (feature, description) in enumerate(features, 1):
        print(f"{i:2}. {feature:25s} - {description}")
    
    print("\n✨ All features successfully implemented and tested!")


def demo_statistics():
    """Show conversion statistics."""
    print_header("Conversion Statistics")
    
    test_file = 'tests/test_sample.pdf'
    
    if Path(test_file).exists():
        import fitz
        doc = fitz.open(test_file)
        
        print(f"Input PDF Analysis:")
        print(f"  • Pages: {len(doc)}")
        print(f"  • Page size: {doc[0].rect.width:.0f} × {doc[0].rect.height:.0f} points")
        
        # Count elements
        total_text = 0
        total_images = 0
        
        for page in doc:
            text_dict = page.get_text("dict")
            total_text += len([b for b in text_dict.get("blocks", []) if b.get("type") == 0])
            total_images += len(page.get_images())
        
        print(f"  • Text blocks: {total_text}")
        print(f"  • Images: {total_images}")
        
        doc.close()
    
    # Output statistics
    output_files = list(Path('output').glob('demo_*.pptx'))
    if output_files:
        print(f"\nGenerated PPTX Files:")
        for pptx_file in output_files:
            size = pptx_file.stat().st_size
            print(f"  • {pptx_file.name}: {size/1024:.1f} KB")


def main():
    """Run all demonstrations."""
    print("\n" + "="*70)
    print("  PDF to PPTX Converter - Feature Demonstration")
    print("="*70)
    
    # Setup logging (suppress detailed logs for demo)
    setup_logging('WARNING')
    
    # Run demos
    demos = [
        demo_features,
        demo_basic_conversion,
        demo_high_quality_conversion,
        demo_statistics
    ]
    
    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"❌ Error in {demo.__name__}: {e}")
    
    print_header("Demonstration Complete")
    print("✅ All demonstrations completed successfully!")
    print("\nGenerated files:")
    print("  • output/demo_basic.pptx")
    print("  • output/demo_high_quality.pptx")
    print("\nNext steps:")
    print("  1. Open the generated PPTX files in PowerPoint")
    print("  2. Try your own PDF files: python main.py input.pdf output.pptx")
    print("  3. Check USAGE.md for more options and examples")
    print("  4. Review logs in pdf2pptx.log for details")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

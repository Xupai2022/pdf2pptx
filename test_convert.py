#!/usr/bin/env python3
"""
Quick test script for PDF to PPTX conversion
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from main import convert_pdf_to_pptx, load_config, setup_logging


def main():
    """Run conversion test."""
    # Setup logging
    setup_logging('INFO')
    
    # Paths
    pdf_path = 'tests/test_sample.pdf'
    output_path = 'output/test_output.pptx'
    
    print("\n" + "=" * 70)
    print("PDF to PPTX Converter - Test Run")
    print("=" * 70)
    print(f"Input:  {pdf_path}")
    print(f"Output: {output_path}")
    print("=" * 70 + "\n")
    
    # Check if input exists
    if not Path(pdf_path).exists():
        print(f"❌ Error: Input file not found: {pdf_path}")
        return 1
    
    # Load config
    config = load_config()
    
    # Convert
    success = convert_pdf_to_pptx(pdf_path, output_path, config)
    
    if success:
        print("\n✅ Test conversion completed successfully!")
        print(f"📊 Output saved to: {output_path}")
        return 0
    else:
        print("\n❌ Test conversion failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())

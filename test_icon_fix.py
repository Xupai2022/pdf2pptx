#!/usr/bin/env python3
"""
Test script to verify icon font detection and rendering fixes.
"""

import subprocess
import sys
from pathlib import Path

def test_pdf(pdf_path, output_path, description):
    """Test a single PDF conversion."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"PDF: {pdf_path}")
    print(f"Output: {output_path}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            ["python", "main.py", pdf_path, output_path, "--dpi", "600"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Conversion successful")
            
            # Check for icon font detection
            if "icon font" in result.stdout.lower():
                icon_count = result.stdout.count("Converted icon")
                print(f"✅ Detected and converted {icon_count} icon font(s)")
            
            # Check for chart detection
            if "chart" in result.stdout.lower():
                chart_count = result.stdout.count("charts rendered as images")
                print(f"✅ Chart detection working")
            
            return True
        else:
            print("❌ Conversion failed")
            print(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Conversion timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PDF to PPTX Icon Fix Verification Tests")
    print("="*60)
    
    tests = [
        ("tests/eee.pdf", "output/eee_verified.pptx", 
         "eee.pdf - Font Awesome icons (should display consistently)"),
        ("tests/2(pdfgear.com).pdf", "output/2_pdfgear_verified.pptx",
         "2(pdfgear.com).pdf - Special symbols under '关键发现'"),
        ("tests/3(pdfgear.com).pdf", "output/3_pdfgear_verified.pptx",
         "3(pdfgear.com).pdf - General compatibility test"),
        ("tests/test_sample.pdf", "output/test_sample_verified.pptx",
         "test_sample.pdf - Baseline compatibility test"),
    ]
    
    results = []
    for pdf_path, output_path, description in tests:
        if Path(pdf_path).exists():
            success = test_pdf(pdf_path, output_path, description)
            results.append((description, success))
        else:
            print(f"\n⚠️  Skipping {pdf_path} - file not found")
            results.append((description, None))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, success in results if success is True)
    failed = sum(1 for _, success in results if success is False)
    skipped = sum(1 for _, success in results if success is None)
    
    for desc, success in results:
        if success is True:
            print(f"✅ PASS: {desc}")
        elif success is False:
            print(f"❌ FAIL: {desc}")
        else:
            print(f"⚠️  SKIP: {desc}")
    
    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print("="*60)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

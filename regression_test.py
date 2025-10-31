#!/usr/bin/env python3
"""
Regression test - ensure existing PDFs still convert correctly
"""

import sys
import os
from pathlib import Path

# Test PDFs that should still work
TEST_PDFS = [
    ("tests/eee.pdf", "output/eee_regression.pptx"),
    ("tests/2(pdfgear.com).pdf", "output/2_regression.pptx"),
    ("tests/3(pdfgear.com).pdf", "output/3_regression.pptx"),
    ("tests/test_sample.pdf", "output/test_sample_regression.pptx"),
]

def run_conversion(input_path, output_path):
    """Run PDF to PPTX conversion"""
    import subprocess
    
    cmd = [sys.executable, "main.py", input_path, output_path, "--dpi", "600"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return result.returncode == 0, result.stdout, result.stderr


def main():
    print("="*80)
    print("REGRESSION TEST - Existing PDFs")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for input_pdf, output_pptx in TEST_PDFS:
        if not os.path.exists(input_pdf):
            print(f"\n⏭️  SKIP: {input_pdf} (file not found)")
            continue
        
        print(f"\n📄 Testing: {input_pdf}")
        success, stdout, stderr = run_conversion(input_pdf, output_pptx)
        
        if success and os.path.exists(output_pptx):
            file_size = os.path.getsize(output_pptx)
            print(f"✅ PASS: Generated {output_pptx} ({file_size} bytes)")
            passed += 1
        else:
            print(f"❌ FAIL: Conversion failed")
            if stderr:
                print(f"Error: {stderr[:200]}")
            failed += 1
    
    print("\n" + "="*80)
    print("REGRESSION TEST SUMMARY")
    print("="*80)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0 and passed > 0:
        print("\n✅ ALL REGRESSION TESTS PASSED")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED OR NO TESTS RUN")
        return 1


if __name__ == "__main__":
    sys.exit(main())

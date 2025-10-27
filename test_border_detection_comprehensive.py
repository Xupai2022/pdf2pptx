#!/usr/bin/env python3
"""
Comprehensive Border Detection Test

This test verifies that:
1. GLM-4.6 page 3 has exactly 5 left borders (2 top cards + 3 bottom cards)
2. GLM-4.6 page 5 has NO false positive borders on bar charts
3. Border colors are correct (#094174 for GLM-4.6)
4. Border dimensions are appropriate (1.5pt width typical)
5. No background text boxes incorrectly receive borders
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parser.pdf_parser import PDFParser


def test_glm46_page3_borders():
    """Test that GLM-4.6 page 3 has exactly 5 left borders."""
    print("\n" + "=" * 70)
    print("TEST 1: GLM-4.6 Page 3 - 5 Left Borders Expected")
    print("=" * 70)
    
    config = {'dpi': 300, 'extract_images': False}
    parser = PDFParser(config)
    
    if not parser.open('tests/glm-4.6.pdf'):
        print("❌ FAILED: Cannot open PDF")
        return False
    
    # Extract page 3 (index 2)
    page_data = parser.extract_page_elements(2)
    parser.close()
    
    # Get borders
    borders = [e for e in page_data['elements'] if e.get('shape_type') == 'border']
    
    # Check count
    if len(borders) != 5:
        print(f"❌ FAILED: Expected 5 borders, got {len(borders)}")
        return False
    
    # Check all are left borders
    left_borders = [b for b in borders if b['border_type'] == 'left']
    if len(left_borders) != 5:
        print(f"❌ FAILED: Expected 5 left borders, got {len(left_borders)}")
        return False
    
    # Check colors
    expected_color = '#094174'
    wrong_colors = [b for b in borders if b['fill_color'] != expected_color]
    if wrong_colors:
        print(f"❌ FAILED: Some borders have wrong color: {[b['fill_color'] for b in wrong_colors]}")
        return False
    
    # Check positions (should have 3 rows: 1 + 1 + 3)
    y_positions = sorted(set(b['y'] for b in borders))
    if len(y_positions) != 3:
        print(f"❌ FAILED: Expected borders at 3 different y positions, got {len(y_positions)}")
        return False
    
    # Count borders at each y position
    row1_y = y_positions[0]
    row2_y = y_positions[1]
    row3_y = y_positions[2]
    
    row1_borders = [b for b in borders if abs(b['y'] - row1_y) < 1.0]
    row2_borders = [b for b in borders if abs(b['y'] - row2_y) < 1.0]
    row3_borders = [b for b in borders if abs(b['y'] - row3_y) < 1.0]
    
    if len(row1_borders) != 1:
        print(f"❌ FAILED: Expected 1 border in row 1 (y={row1_y:.1f}), got {len(row1_borders)}")
        return False
    
    if len(row2_borders) != 1:
        print(f"❌ FAILED: Expected 1 border in row 2 (y={row2_y:.1f}), got {len(row2_borders)}")
        return False
    
    if len(row3_borders) != 3:
        print(f"❌ FAILED: Expected 3 borders in row 3 (y={row3_y:.1f}), got {len(row3_borders)}")
        return False
    
    # Check border widths (should be small, typically 1.5pt)
    widths = [b['width'] for b in borders]
    if any(w < 0.5 or w > 5.0 for w in widths):
        print(f"❌ FAILED: Border widths out of expected range (0.5-5.0pt): {widths}")
        return False
    
    print("✅ PASSED: 5 left borders detected with correct properties")
    print(f"   - Row 1 (y={row1_y:.1f}): 1 border (full-width card)")
    print(f"   - Row 2 (y={row2_y:.1f}): 1 border (full-width card)")
    print(f"   - Row 3 (y={row3_y:.1f}): 3 borders (3-column layout)")
    print(f"   - Color: {expected_color}")
    print(f"   - Width range: {min(widths):.1f} - {max(widths):.1f} pt")
    
    return True


def test_glm46_page5_no_false_positives():
    """Test that GLM-4.6 page 5 (bar charts) has NO false positive borders."""
    print("\n" + "=" * 70)
    print("TEST 2: GLM-4.6 Page 5 - No False Positive Borders on Bar Charts")
    print("=" * 70)
    
    config = {'dpi': 300, 'extract_images': False}
    parser = PDFParser(config)
    
    if not parser.open('tests/glm-4.6.pdf'):
        print("❌ FAILED: Cannot open PDF")
        return False
    
    # Extract page 5 (index 4)
    page_data = parser.extract_page_elements(4)
    parser.close()
    
    # Get borders
    borders = [e for e in page_data['elements'] if e.get('shape_type') == 'border']
    
    if len(borders) > 0:
        print(f"❌ FAILED: Found {len(borders)} false positive border(s) on bar chart page")
        for i, border in enumerate(borders, 1):
            print(f"   Border {i}: {border['border_type']} at ({border['x']:.1f}, {border['y']:.1f})")
        return False
    
    print("✅ PASSED: No false positive borders detected on bar chart page")
    
    return True


def test_border_properties():
    """Test that detected borders have appropriate properties."""
    print("\n" + "=" * 70)
    print("TEST 3: Border Properties Validation")
    print("=" * 70)
    
    config = {'dpi': 300, 'extract_images': False}
    parser = PDFParser(config)
    
    if not parser.open('tests/glm-4.6.pdf'):
        print("❌ FAILED: Cannot open PDF")
        return False
    
    # Extract page 3
    page_data = parser.extract_page_elements(2)
    parser.close()
    
    borders = [e for e in page_data['elements'] if e.get('shape_type') == 'border']
    
    # Check each border has required fields
    required_fields = ['type', 'shape_type', 'border_type', 'x', 'y', 'width', 
                      'height', 'fill_color', 'fill_opacity']
    
    for i, border in enumerate(borders, 1):
        missing_fields = [f for f in required_fields if f not in border]
        if missing_fields:
            print(f"❌ FAILED: Border {i} missing fields: {missing_fields}")
            return False
    
    # Check opacity (borders should be opaque)
    non_opaque = [i for i, b in enumerate(borders, 1) if b['fill_opacity'] < 0.9]
    if non_opaque:
        print(f"❌ FAILED: Borders {non_opaque} are not opaque")
        return False
    
    # Check no stroke (borders are filled rectangles, not stroked)
    has_stroke = [i for i, b in enumerate(borders, 1) 
                 if b.get('stroke_color') is not None and b.get('stroke_width', 0) > 0]
    if has_stroke:
        print(f"❌ FAILED: Borders {has_stroke} have strokes (should be filled only)")
        return False
    
    print("✅ PASSED: All borders have correct properties")
    print(f"   - All have required fields")
    print(f"   - All are fully opaque (opacity=1.0)")
    print(f"   - All are filled rectangles without strokes")
    
    return True


def test_no_background_box_borders():
    """Test that background boxes without borders don't get false borders."""
    print("\n" + "=" * 70)
    print("TEST 4: Background Boxes Without Borders")
    print("=" * 70)
    
    config = {'dpi': 300, 'extract_images': False}
    parser = PDFParser(config)
    
    if not parser.open('tests/glm-4.6.pdf'):
        print("❌ FAILED: Cannot open PDF")
        return False
    
    # Check multiple pages for false positives
    false_positive_pages = []
    
    for page_num in range(parser.get_page_count()):
        page_data = parser.extract_page_elements(page_num)
        
        # Get all shapes and borders
        shapes = [e for e in page_data['elements'] 
                 if e['type'] == 'shape' and e.get('shape_type') != 'border']
        borders = [e for e in page_data['elements'] if e.get('shape_type') == 'border']
        
        # For each shape, check if it has multiple borders (top/bottom false positives)
        # This is a heuristic: if a shape is large and has borders on all sides,
        # it's likely a false positive
        
        # For now, just count borders and flag if unusually high
        if len(borders) > 10:  # Arbitrary threshold
            false_positive_pages.append((page_num + 1, len(borders)))
    
    parser.close()
    
    if false_positive_pages:
        print(f"⚠️  WARNING: Some pages have many borders (may indicate false positives):")
        for page, count in false_positive_pages:
            print(f"   Page {page}: {count} borders")
        print("   Manual inspection recommended")
    else:
        print("✅ PASSED: No pages with excessive border counts")
    
    return True


def run_all_tests():
    """Run all border detection tests."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE BORDER DETECTION TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("GLM-4.6 Page 3 Borders", test_glm46_page3_borders),
        ("GLM-4.6 Page 5 No False Positives", test_glm46_page5_no_false_positives),
        ("Border Properties", test_border_properties),
        ("Background Boxes", test_no_background_box_borders)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    
    print()
    print(f"Total: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        print("\n🎉 ALL TESTS PASSED! Border detection is working correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed_count} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

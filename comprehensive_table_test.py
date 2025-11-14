#!/usr/bin/env python3
"""Comprehensive table detection test for both PDFs"""

import sys
import logging
from src.parser.pdf_parser import PDFParser

# Setup logging - only show INFO and above to reduce noise
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Create config
config = {
    'dpi': 300,
    'table_alignment_tolerance': 3.0,
    'min_table_rows': 2,
    'min_table_cols': 2,
}

def test_pdf_pages(pdf_path, pages_to_test, expected_results):
    """
    Test table detection on specific pages.
    
    Args:
        pdf_path: Path to PDF file
        pages_to_test: List of page numbers (1-based) to test
        expected_results: Dict mapping page_num -> expected table count
    
    Returns:
        Dict with test results
    """
    parser = PDFParser(config)
    parser.open(pdf_path)
    
    results = {}
    
    for page_num in pages_to_test:
        page_idx = page_num - 1  # Convert to 0-based
        page_data = parser.extract_page_elements(page_idx)
        
        elements = page_data.get('elements', [])
        tables = [e for e in elements if e.get('type') == 'table']
        
        expected = expected_results.get(page_num, None)
        
        results[page_num] = {
            'found': len(tables),
            'expected': expected,
            'pass': len(tables) == expected if expected is not None else None,
            'tables': tables
        }
    
    parser.close()
    return results

print("\n" + "="*70)
print("COMPREHENSIVE TABLE DETECTION TEST")
print("="*70)

# Test 1: 安全运营月报.pdf - existing tables should still work
print("\n📋 Test 1: 安全运营月报.pdf (existing tables)")
print("-" * 70)
anquan_results = test_pdf_pages(
    "./tests/安全运营月报.pdf",
    [8, 9, 12],
    {8: 1, 9: 1, 12: 1}  # Expected: 1 table on each page
)

for page_num in sorted(anquan_results.keys()):
    result = anquan_results[page_num]
    status = "✅ PASS" if result['pass'] else "❌ FAIL"
    print(f"  Page {page_num}: {status} - Found {result['found']} table(s), "
          f"Expected {result['expected']}")
    if result['tables']:
        for idx, table in enumerate(result['tables']):
            print(f"    Table {idx+1}: {table.get('rows', '?')}x{table.get('cols', '?')} "
                  f"at bbox {table.get('bbox', '?')}")

# Test 2: season_report_del.pdf - new table on page 9
print("\n📋 Test 2: season_report_del.pdf page 9 (NEW table to detect)")
print("-" * 70)
season_page9_results = test_pdf_pages(
    "./tests/season_report_del.pdf",
    [9],
    {9: 1}  # Expected: 1 table (the right-side table)
)

for page_num in sorted(season_page9_results.keys()):
    result = season_page9_results[page_num]
    status = "✅ PASS" if result['pass'] else "❌ FAIL"
    print(f"  Page {page_num}: {status} - Found {result['found']} table(s), "
          f"Expected {result['expected']}")
    if result['tables']:
        for idx, table in enumerate(result['tables']):
            print(f"    Table {idx+1}: {table.get('rows', '?')}x{table.get('cols', '?')} "
                  f"at bbox {table.get('bbox', '?')}")

# Test 3: season_report_del.pdf pages 2, 6 - should NOT detect tables
print("\n📋 Test 3: season_report_del.pdf pages 2, 6 (NO false positives)")
print("-" * 70)
season_no_tables_results = test_pdf_pages(
    "./tests/season_report_del.pdf",
    [2, 6],
    {2: 0, 6: 0}  # Expected: NO tables
)

for page_num in sorted(season_no_tables_results.keys()):
    result = season_no_tables_results[page_num]
    status = "✅ PASS" if result['pass'] else "❌ FAIL"
    print(f"  Page {page_num}: {status} - Found {result['found']} table(s), "
          f"Expected {result['expected']}")
    if result['tables']:
        print(f"    WARNING: Unexpected tables detected!")
        for idx, table in enumerate(result['tables']):
            print(f"    Table {idx+1}: {table.get('rows', '?')}x{table.get('cols', '?')}")

# Test 4: season_report_del.pdf pages 7, 10, 13, 16 - existing tables
print("\n📋 Test 4: season_report_del.pdf pages 7, 10, 13, 16 (existing tables)")
print("-" * 70)
season_existing_results = test_pdf_pages(
    "./tests/season_report_del.pdf",
    [7, 10, 13, 16],
    {7: 1, 10: 2, 13: 1, 16: 1}  # Expected table counts (based on logs)
)

for page_num in sorted(season_existing_results.keys()):
    result = season_existing_results[page_num]
    # For existing tables, we just want to make sure they're still detected
    # The exact count might vary, so we check if ANY tables are found
    status = "✅ FOUND" if result['found'] > 0 else "⚠️  NONE"
    print(f"  Page {page_num}: {status} - Found {result['found']} table(s)")
    if result['tables']:
        for idx, table in enumerate(result['tables']):
            print(f"    Table {idx+1}: {table.get('rows', '?')}x{table.get('cols', '?')}")

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

all_results = {
    **anquan_results,
    **season_page9_results,
    **season_no_tables_results,
    **season_existing_results
}

passed = sum(1 for r in all_results.values() if r['pass'])
failed = sum(1 for r in all_results.values() if r['pass'] == False)
skipped = sum(1 for r in all_results.values() if r['pass'] is None)

print(f"\nTotal tests: {len(all_results)}")
print(f"  ✅ Passed: {passed}")
print(f"  ❌ Failed: {failed}")
print(f"  ⚠️  Info only: {skipped}")

if failed == 0:
    print("\n🎉 ALL CRITICAL TESTS PASSED!")
else:
    print(f"\n⚠️  {failed} test(s) failed - review above output")


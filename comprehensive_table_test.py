#!/usr/bin/env python3
"""
Comprehensive test for table optimization
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from parser.pdf_parser import PDFParser

def test_all():
    config = {'dpi': 300, 'table_alignment_tolerance': 3.0, 'min_table_rows': 2, 'min_table_cols': 2}
    
    # Load expected results
    with open('table_backup_before_optimization.json') as f:
        expected = json.load(f)
    
    test_cases = [
        {
            'file': 'tests/行业化季报_主线测试自动化专用_APEX底座客户_2025-05-21至2025-08-18(pdfgear.com).pdf',
            'tests': [
                {'page': 23, 'expected': '6x4', 'name': 'Page 24 (text alignment test)'},
                {'page': 26, 'expected': '3x5', 'name': 'Page 27 (chart+table test)'},
            ]
        },
        {
            'file': 'tests/安全运营月报.pdf',
            'tests': [
                {'page': 7, 'expected': '11x3', 'name': 'Page 8'},
                {'page': 8, 'expected': '7x3', 'name': 'Page 9'},
                {'page': 11, 'expected': '9x5', 'name': 'Page 12'},
            ]
        },
        {
            'file': 'tests/season_report_del.pdf',
            'tests': [
                {'page': 1, 'expected': 'no table', 'name': 'Page 2'},
                {'page': 5, 'expected': 'no table', 'name': 'Page 6'},
                {'page': 6, 'expected': '6x4', 'name': 'Page 7'},
                {'page': 8, 'expected': '3x5', 'name': 'Page 9'},
                {'page': 9, 'expected': '2 tables: 7x3, 5x3', 'name': 'Page 10'},
                {'page': 12, 'expected': '7x5', 'name': 'Page 13'},
                {'page': 15, 'expected': '7x4', 'name': 'Page 16'},
            ]
        }
    ]
    
    all_passed = True
    
    for file_test in test_cases:
        pdf_path = file_test['file']
        if not Path(pdf_path).exists():
            print(f"⚠️  Skipping {pdf_path}: file not found")
            continue
        
        parser = PDFParser(config)
        if not parser.open(pdf_path):
            print(f"❌ Failed to open: {pdf_path}")
            all_passed = False
            continue
        
        try:
            print(f"\n{'='*80}")
            print(f"Testing: {Path(pdf_path).name}")
            print(f"{'='*80}")
            
            for test in file_test['tests']:
                page_data = parser.extract_page_elements(test['page'])
                tables = [e for e in page_data['elements'] if e.get('type') == 'table']
                
                actual = f"{len(tables)} table(s)"
                if tables:
                    table_dims = [f"{t['rows']}x{t['cols']}" for t in tables]
                    if len(tables) == 1:
                        actual = table_dims[0]
                    else:
                        actual = f"{len(tables)} tables: " + ", ".join(table_dims)
                else:
                    actual = "no table"
                
                if actual == test['expected']:
                    print(f"  ✅ {test['name']}: {actual}")
                else:
                    print(f"  ❌ {test['name']}: Expected '{test['expected']}', got '{actual}'")
                    all_passed = False
        
        finally:
            parser.close()
    
    print(f"\n{'='*80}")
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print(f"{'='*80}\n")
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    exit(test_all())

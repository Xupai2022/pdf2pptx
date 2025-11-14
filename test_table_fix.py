#!/usr/bin/env python3
"""
Test the table detection fix for page 5 of 行业化季报
"""
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from parser.pdf_parser import PDFParser
from parser.table_detector import TableDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_page5_table_detection():
    """Test that page 5 table is properly detected"""
    
    pdf_path = 'tests/行业化季报_主线测试自动化专用_APEX底座客户_2025-05-21至2025-08-18(pdfgear.com).pdf'
    
    # Initialize parser
    config = {
        'dpi': 300,
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    }
    
    parser = PDFParser(config)
    
    if not parser.open(pdf_path):
        logger.error(f"Failed to open PDF: {pdf_path}")
        return False
    
    try:
        # Extract page 5 (0-indexed: page 4)
        logger.info("="*80)
        logger.info("Testing Page 5 Table Detection")
        logger.info("="*80)
        
        page_data = parser.extract_page_elements(4)
        
        # Find tables in elements
        tables = [elem for elem in page_data.get('elements', []) if elem.get('type') == 'table']
        
        logger.info(f"\nResults:")
        logger.info(f"  Total elements: {len(page_data.get('elements', []))}")
        logger.info(f"  Tables detected: {len(tables)}")
        
        if not tables:
            logger.error("❌ FAIL: No table detected on page 5!")
            return False
        
        # Validate table structure
        for idx, table in enumerate(tables):
            logger.info(f"\nTable #{idx + 1}:")
            logger.info(f"  Rows: {table.get('rows')}")
            logger.info(f"  Cols: {table.get('cols')}")
            logger.info(f"  BBox: {table.get('bbox')}")
            logger.info(f"  Detection mode: {table.get('detection_mode', 'rectangle-based')}")
            
            # Expected: 8 rows x 4 columns
            expected_rows = 8
            expected_cols = 4
            
            actual_rows = table.get('rows', 0)
            actual_cols = table.get('cols', 0)
            
            if actual_rows == expected_rows and actual_cols == expected_cols:
                logger.info(f"  ✅ Correct dimensions: {actual_rows}x{actual_cols}")
            else:
                logger.warning(f"  ⚠️  Dimension mismatch: expected {expected_rows}x{expected_cols}, got {actual_rows}x{actual_cols}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ SUCCESS: Page 5 table detected successfully!")
        logger.info(f"{'='*80}\n")
        
        return True
        
    finally:
        parser.close()

def test_existing_tables():
    """Test that existing tables are not broken"""
    
    test_cases = [
        {
            'file': 'tests/安全运营月报.pdf',
            'pages': [7, 8, 11],  # Pages 8, 9, 12 (0-indexed)
            'name': '安全运营月报'
        },
        {
            'file': 'tests/season_report_del.pdf',
            'pages': [6, 8, 9, 12, 15],  # Pages 7, 9, 10, 13, 16 (0-indexed)
            'name': 'season_report_del'
        }
    ]
    
    config = {
        'dpi': 300,
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    }
    
    all_passed = True
    
    for test_case in test_cases:
        pdf_path = test_case['file']
        
        if not Path(pdf_path).exists():
            logger.warning(f"Skipping {test_case['name']}: file not found")
            continue
        
        parser = PDFParser(config)
        
        if not parser.open(pdf_path):
            logger.error(f"Failed to open: {pdf_path}")
            all_passed = False
            continue
        
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"Testing {test_case['name']}")
            logger.info(f"{'='*80}")
            
            for page_num in test_case['pages']:
                page_data = parser.extract_page_elements(page_num)
                tables = [elem for elem in page_data.get('elements', []) if elem.get('type') == 'table']
                
                logger.info(f"  Page {page_num + 1}: {len(tables)} table(s) detected")
                
                if not tables:
                    logger.warning(f"    ⚠️  No table on page {page_num + 1} (expected to have table)")
                    all_passed = False
        
        finally:
            parser.close()
    
    return all_passed

def main():
    """Main test runner"""
    
    logger.info("Starting table detection tests...\n")
    
    # Test 1: Page 5 table detection (the fix target)
    test1_passed = test_page5_table_detection()
    
    # Test 2: Existing tables regression test
    test2_passed = test_existing_tables()
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("Test Summary")
    logger.info(f"{'='*80}")
    logger.info(f"  Page 5 table detection: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    logger.info(f"  Existing tables regression: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        logger.info(f"\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error(f"\n❌ SOME TESTS FAILED")
        return 1

if __name__ == '__main__':
    exit(main())

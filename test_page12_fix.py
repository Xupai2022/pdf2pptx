"""
Test script to verify the cell margin fix for page 12 table
"""

import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import convert_pdf_to_pptx, load_config

def test_page12_conversion():
    """Test conversion of page 12 with fixed cell margins"""
    pdf_path = "./tests/安全运营月报.pdf"
    output_path = "./tests/test_page12_margin_fix.pptx"
    
    logger.info(f"Converting {pdf_path} to {output_path}")
    logger.info("Focus: Page 12 table with '托管服务器' cell")
    logger.info("Expected: Row heights should match PDF (21.5pt)")
    logger.info("Fix: Cell margins reduced to 0.5pt (minimal)")
    
    try:
        # Load config
        config = load_config()
        
        # Convert PDF (full conversion for now)
        convert_pdf_to_pptx(
            pdf_path=pdf_path,
            output_path=output_path,
            config=config
        )
        
        logger.info(f"✓ Conversion completed successfully")
        logger.info(f"✓ Output saved to: {output_path}")
        logger.info("")
        logger.info("Please verify in PowerPoint:")
        logger.info("1. Open the generated PPTX file")
        logger.info("2. Find the table with '托管服务器' cell")
        logger.info("3. Check if the row height matches PDF (should be compact, not tall)")
        logger.info("4. Try to manually shrink the row - it should already be at minimum")
        
    except Exception as e:
        logger.error(f"✗ Conversion failed: {e}", exc_info=True)
        return False
    
    return True

if __name__ == '__main__':
    success = test_page12_conversion()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
PDF to PPTX Converter - Main Entry Point
Converts PDF files to editable PowerPoint presentations.
"""

import sys
import argparse
import logging
from pathlib import Path
import yaml
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parser.pdf_parser import PDFParser
from src.analyzer.layout_analyzer import LayoutAnalyzer
from src.rebuilder.coordinate_mapper import CoordinateMapper
from src.generator.pptx_generator import PPTXGenerator


def setup_logging(level: str = "INFO"):
    """
    Setup logging configuration.
    
    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('pdf2pptx.log')
        ]
    )


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Configuration dictionary
    """
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    # Default config path
    default_config = Path(__file__).parent / 'config' / 'config.yaml'
    if default_config.exists():
        with open(default_config, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    # Fallback to minimal config
    return {
        'parser': {'dpi': 300, 'extract_images': True},
        'analyzer': {'title_threshold': 20, 'group_tolerance': 10},
        'rebuilder': {'slide_width': 10, 'slide_height': 7.5},
        'mapper': {'font_mapping': {}, 'default_font': 'Arial'},
        'generator': {'preserve_layout': True}
    }


def convert_pdf_to_pptx(pdf_path: str, output_path: str, config: Dict[str, Any]) -> bool:
    """
    Convert a PDF file to PPTX.
    
    Args:
        pdf_path: Path to input PDF file
        output_path: Path to output PPTX file
        config: Configuration dictionary
        
    Returns:
        True if successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Parse PDF
        logger.info("=" * 60)
        logger.info("Step 1: Parsing PDF")
        logger.info("=" * 60)
        
        parser = PDFParser(config['parser'])
        if not parser.open(pdf_path):
            logger.error("Failed to open PDF file")
            return False
        
        all_pages = parser.extract_all_pages()
        parser.close()
        
        logger.info(f"Extracted {len(all_pages)} pages from PDF")
        
        # Step 2: Analyze Layout
        logger.info("=" * 60)
        logger.info("Step 2: Analyzing Layout")
        logger.info("=" * 60)
        
        analyzer = LayoutAnalyzer(config['analyzer'])
        analyzed_pages = []
        
        for page_data in all_pages:
            layout_data = analyzer.analyze_page(page_data)
            analyzed_pages.append(layout_data)
            logger.info(f"Page {layout_data['page_num'] + 1}: Found {len(layout_data['layout'])} regions")
        
        # Step 3: Build Slide Models
        logger.info("=" * 60)
        logger.info("Step 3: Building Slide Models")
        logger.info("=" * 60)
        
        mapper = CoordinateMapper(config['rebuilder'])
        slide_models = []
        
        for layout_data in analyzed_pages:
            slide_model = mapper.create_slide_model(layout_data)
            slide_models.append(slide_model)
            logger.info(f"Slide {slide_model.slide_number + 1}: {len(slide_model.elements)} elements")
        
        # Step 4: Generate PPTX
        logger.info("=" * 60)
        logger.info("Step 4: Generating PowerPoint")
        logger.info("=" * 60)
        
        generator = PPTXGenerator(config['generator'])
        
        if not generator.generate_from_models(slide_models):
            logger.error("Failed to generate presentation")
            return False
        
        if not generator.save(output_path):
            logger.error("Failed to save presentation")
            return False
        
        logger.info("=" * 60)
        logger.info(f"✅ Conversion complete!")
        logger.info(f"📄 Input:  {pdf_path}")
        logger.info(f"📊 Output: {output_path}")
        logger.info(f"📑 Pages:  {len(slide_models)}")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Convert PDF files to PowerPoint presentations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py input.pdf output.pptx
  python main.py input.pdf output.pptx --config custom_config.yaml
  python main.py input.pdf output.pptx --log-level DEBUG
        """
    )
    
    parser.add_argument('input', help='Input PDF file path')
    parser.add_argument('output', help='Output PPTX file path')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    parser.add_argument('--dpi', type=int, help='DPI for image extraction')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Validate input file
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        return 1
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with command line arguments
    if args.dpi:
        config['parser']['dpi'] = args.dpi
    
    # Convert
    success = convert_pdf_to_pptx(args.input, args.output, config)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""备份所有指定页面的表格识别结果"""

import json
import logging
from pathlib import Path
from src.parser.pdf_parser import PDFParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backup_tables():
    """备份指定PDF文件和页面的表格"""
    
    config = {
        'dpi': 300,
        'extract_images': False,
        'min_text_size': 6,
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    }
    
    test_cases = [
        {
            'file': 'tests/安全运营月报.pdf',
            'pages': [7, 8, 11]  # 第8,9,12页 (索引-1)
        },
        {
            'file': 'tests/行业化季报_主线测试自动化专用_APEX底座客户_2025-05-21至2025-08-18(pdfgear.com).pdf',
            'pages': [23, 24, 26, 27, 38]  # 第24,25,27,28,39页 (索引-1)
        }
    ]
    
    backup_data = {}
    
    for test_case in test_cases:
        pdf_path = Path(test_case['file'])
        if not pdf_path.exists():
            logger.warning(f"文件不存在: {pdf_path}")
            continue
        
        parser = PDFParser(config)
        parser.open(str(pdf_path))
        
        file_key = pdf_path.stem
        backup_data[file_key] = {}
        
        for page_idx in test_case['pages']:
            try:
                page_data = parser.extract_page_elements(page_idx)
                tables = page_data.get('tables', [])
                
                logger.info(f"{file_key} 第{page_idx+1}页: 检测到 {len(tables)} 个表格")
                
                if tables:
                    backup_data[file_key][f'page_{page_idx+1}'] = []
                    for table in tables:
                        backup_data[file_key][f'page_{page_idx+1}'].append({
                            'rows': table.get('rows'),
                            'cols': table.get('cols'),
                            'bbox': table.get('bbox'),
                            'cells_count': len(table.get('cells', [])),
                            'detection_mode': table.get('detection_mode', 'unknown'),
                            'num_rows': table.get('num_rows'),
                            'num_cols': table.get('num_cols')
                        })
            except Exception as e:
                logger.error(f"处理 {file_key} 第{page_idx+1}页时出错: {e}")
        
        parser.close()
    
    # 保存备份
    output_file = 'table_backup_detailed.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n表格备份已保存到: {output_file}")
    
    # 打印摘要
    print("\n" + "="*80)
    print("表格备份摘要:")
    print("="*80)
    for file_key, pages in backup_data.items():
        print(f"\n文件: {file_key}")
        for page_key, tables in pages.items():
            print(f"  {page_key}: {len(tables)} 个表格")
            for i, table in enumerate(tables):
                print(f"    表格 #{i+1}: {table['rows']}行x{table['cols']}列, "
                      f"模式={table.get('detection_mode', 'N/A')}")

if __name__ == '__main__':
    backup_tables()

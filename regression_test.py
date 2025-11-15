#!/usr/bin/env python3
"""回归测试 - 确保其他表格不受影响"""

import json
import logging
from pathlib import Path
from src.parser.pdf_parser import PDFParser

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def regression_test():
    """测试所有基线表格"""
    
    config = {
        'dpi': 300,
        'extract_images': False,
        'min_text_size': 6,
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    }
    
    # 加载基线数据
    with open('table_backup_before_optimization.json', 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    
    test_results = []
    all_pass = True
    
    # 测试用例
    test_files = {
        '安全运营月报': 'tests/安全运营月报.pdf',
        'season_report_del': 'tests/season_report_del.pdf'
    }
    
    for file_key, pdf_file in test_files.items():
        pdf_path = Path(pdf_file)
        if not pdf_path.exists():
            print(f"⚠️  文件不存在: {pdf_file}")
            continue
        
        if file_key not in baseline:
            print(f"⚠️  没有基线数据: {file_key}")
            continue
        
        parser = PDFParser(config)
        parser.open(str(pdf_path))
        
        for page_key, expected_tables in baseline[file_key].items():
            page_num = int(page_key.split('_')[1]) - 1  # page_8 -> index 7
            
            page_data = parser.extract_page_elements(page_num)
            elements = page_data.get('elements', [])
            actual_tables = [e for e in elements if e.get('type') == 'table']
            
            # 比较表格数量
            expected_count = len(expected_tables)
            actual_count = len(actual_tables)
            
            match = expected_count == actual_count
            
            # 比较行列数
            details_match = True
            if match and expected_count > 0:
                for i, (exp, act) in enumerate(zip(expected_tables, actual_tables)):
                    exp_rows = exp.get('rows')
                    exp_cols = exp.get('cols')
                    act_rows = act.get('rows')
                    act_cols = act.get('cols')
                    
                    if exp_rows != act_rows or exp_cols != act_cols:
                        details_match = False
                        print(f"  ❌ 表格#{i+1} 尺寸不匹配: 预期{exp_rows}x{exp_cols}, 实际{act_rows}x{act_cols}")
            
            status = "✅" if (match and details_match) else "❌"
            result_str = f"{status} {file_key} {page_key}: "
            
            if match and details_match:
                result_str += f"{actual_count} 个表格 (符合预期)"
            elif match:
                result_str += f"{actual_count} 个表格 (数量匹配但细节不同)"
                all_pass = False
            else:
                result_str += f"预期{expected_count}个, 实际{actual_count}个 (不匹配)"
                all_pass = False
            
            print(result_str)
            
            # 显示详情
            if actual_count > 0:
                for i, table in enumerate(actual_tables):
                    mode = table.get('detection_mode', 'unknown')
                    print(f"    表格#{i+1}: {table.get('rows')}行x{table.get('cols')}列, 模式={mode}")
        
        parser.close()
    
    # 测试第5页
    print("\n" + "="*80)
    print("新修复的第5页表格测试:")
    print("="*80)
    
    pdf_path = Path('tests/行业化季报_主线测试自动化专用_APEX底座客户_2025-05-21至2025-08-18(pdfgear.com).pdf')
    parser = PDFParser(config)
    parser.open(str(pdf_path))
    page_data = parser.extract_page_elements(4)
    elements = page_data.get('elements', [])
    tables = [e for e in elements if e.get('type') == 'table']
    
    if len(tables) > 0:
        print(f"✅ 第5页成功检测到 {len(tables)} 个表格")
        for i, table in enumerate(tables):
            print(f"  表格#{i+1}: {table.get('rows')}行x{table.get('cols')}列")
            print(f"    检测模式: {table.get('detection_mode', 'N/A')}")
            print(f"    位置: {table.get('bbox', 'N/A')}")
    else:
        print("❌ 第5页未检测到表格（修复失败）")
        all_pass = False
    
    parser.close()
    
    # 总结
    print("\n" + "="*80)
    if all_pass:
        print("🎉 回归测试通过！所有表格识别正常。")
    else:
        print("⚠️  回归测试发现问题，请检查上述失败项。")
    print("="*80)
    
    return all_pass

if __name__ == '__main__':
    success = regression_test()
    exit(0 if success else 1)

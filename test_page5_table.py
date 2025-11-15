#!/usr/bin/env python3
"""测试第5页表格识别情况"""

import sys
import fitz
import json
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.parser.pdf_parser import PDFParser
from src.parser.table_detector import TableDetector

def analyze_page5():
    """分析第5页表格结构"""
    pdf_path = Path("tests/行业化季报_主线测试自动化专用_APEX底座客户_2025-05-21至2025-08-18(pdfgear.com).pdf")
    
    if not pdf_path.exists():
        logger.error(f"文件不存在: {pdf_path}")
        return
    
    # 打开PDF
    doc = fitz.open(str(pdf_path))
    page = doc[4]  # 第5页（索引从0开始）
    
    logger.info(f"分析第5页 (索引4)，页面尺寸: {page.rect.width}x{page.rect.height}")
    
    # 解析页面
    config = {
        'dpi': 300,
        'extract_images': False,
        'min_text_size': 6,
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    }
    
    parser = PDFParser(config)
    parser.open(str(pdf_path))
    
    page_data = parser.extract_page_elements(4)
    
    # 分析shapes
    shapes = page_data.get('shapes', [])
    logger.info(f"\n{'='*80}")
    logger.info(f"第5页总共有 {len(shapes)} 个shape元素")
    
    # 按类型分类shapes
    shape_types = {}
    for shape in shapes:
        shape_type = shape.get('shape_type', 'unknown')
        if shape_type not in shape_types:
            shape_types[shape_type] = []
        shape_types[shape_type].append(shape)
    
    logger.info("\nShape类型分布:")
    for shape_type, items in shape_types.items():
        logger.info(f"  {shape_type}: {len(items)} 个")
    
    # 详细分析线条
    if 'line' in shape_types:
        lines = shape_types['line']
        h_lines = [l for l in lines if l.get('width', 0) > l.get('height', 0)]
        v_lines = [l for l in lines if l.get('height', 0) >= l.get('width', 0)]
        
        logger.info(f"\n线条详情:")
        logger.info(f"  水平线: {len(h_lines)} 条")
        logger.info(f"  垂直线: {len(v_lines)} 条")
        
        # 显示前5条水平线的位置
        logger.info(f"\n前5条水平线位置:")
        for i, line in enumerate(h_lines[:5]):
            logger.info(f"  H{i+1}: Y={line['y']:.1f}, X={line['x']:.1f}-{line['x2']:.1f}, width={line['width']:.1f}pt")
        
        # 显示前5条垂直线的位置
        logger.info(f"\n前5条垂直线位置:")
        for i, line in enumerate(v_lines[:5]):
            logger.info(f"  V{i+1}: X={line['x']:.1f}, Y={line['y']:.1f}-{line['y2']:.1f}, height={line['height']:.1f}pt")
    
    # 详细分析矩形
    if 'rectangle' in shape_types:
        rectangles = shape_types['rectangle']
        logger.info(f"\n矩形详情 (共{len(rectangles)}个):")
        
        # 按尺寸分类
        small_rects = [r for r in rectangles if r.get('width', 0) < 50 or r.get('height', 0) < 20]
        medium_rects = [r for r in rectangles if 50 <= r.get('width', 0) < 200 and 20 <= r.get('height', 0) < 100]
        large_rects = [r for r in rectangles if r.get('width', 0) >= 200 or r.get('height', 0) >= 100]
        
        logger.info(f"  小矩形 (w<50 or h<20): {len(small_rects)} 个")
        logger.info(f"  中等矩形 (50<=w<200, 20<=h<100): {len(medium_rects)} 个")
        logger.info(f"  大矩形 (w>=200 or h>=100): {len(large_rects)} 个")
        
        # 显示前10个中等矩形
        if medium_rects:
            logger.info(f"\n前10个中等矩形:")
            for i, rect in enumerate(medium_rects[:10]):
                logger.info(f"  R{i+1}: pos=({rect['x']:.1f}, {rect['y']:.1f}), "
                          f"size={rect['width']:.1f}x{rect['height']:.1f}, "
                          f"fill={rect.get('fill_color')}, stroke={rect.get('stroke_color')}")
    
    # 直接从page_data获取表格（PDF Parser已经检测过了）
    logger.info(f"\n{'='*80}")
    logger.info("获取PDF Parser检测的表格...")
    
    tables = page_data.get('tables', [])
    
    logger.info(f"\n检测到 {len(tables)} 个表格")
    
    for i, table in enumerate(tables):
        logger.info(f"\n表格 #{i+1}:")
        logger.info(f"  位置: {table.get('bbox')}")
        logger.info(f"  尺寸: {table.get('rows')}行 x {table.get('cols')}列")
        logger.info(f"  检测模式: {table.get('detection_mode', 'N/A')}")
        logger.info(f"  单元格数: {len(table.get('cells', []))}")
    
    doc.close()
    
    # 保存详细分析结果
    result = {
        'page': 5,
        'shapes_total': len(shapes),
        'shape_types': {k: len(v) for k, v in shape_types.items()},
        'tables_detected': len(tables),
        'tables': [{
            'bbox': t.get('bbox'),
            'rows': t.get('rows'),
            'cols': t.get('cols'),
            'detection_mode': t.get('detection_mode', 'N/A'),
            'cells_count': len(t.get('cells', []))
        } for t in tables]
    }
    
    output_file = 'page5_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n分析结果已保存到: {output_file}")

if __name__ == '__main__':
    analyze_page5()

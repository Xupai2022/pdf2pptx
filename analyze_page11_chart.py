#!/usr/bin/env python3
"""
分析第11页的饼状图区域和周围元素
"""
import fitz
from src.parser.pdf_parser import PDFParser
from src.parser.chart_detector import ChartDetector
import json


def main():
    pdf_path = "tests/season_report_del.pdf"
    
    # 打开PDF
    doc = fitz.open(pdf_path)
    page = doc[10]  # 第11页，索引10
    
    print("="*80)
    print("第11页分析 - 饼状图区域")
    print("="*80)
    
    # 初始化parser和detector
    config = {
        'dpi': 300,
        'extract_images': True,
        'min_shapes_for_chart': 3,
        'cluster_distance_threshold': 200,
        'min_chart_area': 3000,
        'chart_render_dpi': 300
    }
    
    parser = PDFParser(config)
    parser.doc = doc
    
    # 提取绘图元素
    opacity_map = parser._extract_opacity_map(page)
    drawing_elements = parser._extract_drawings(page, opacity_map)
    
    print(f"\n绘图元素数量: {len(drawing_elements)}")
    
    # 检测图表
    chart_detector = ChartDetector(config)
    chart_regions = chart_detector.detect_chart_regions(page, drawing_elements)
    
    print(f"\n检测到的图表区域数量: {len(chart_regions)}")
    
    for i, chart in enumerate(chart_regions):
        bbox = chart['bbox']
        print(f"\n图表 {i+1}:")
        print(f"  bbox: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})")
        print(f"  宽度: {bbox[2] - bbox[0]:.2f}pt")
        print(f"  高度: {bbox[3] - bbox[1]:.2f}pt")
        print(f"  形状数量: {chart['shape_count']}")
        
        # 检查bbox周围是否有文字或其他元素
        text_dict = page.get_text("dict")
        nearby_texts = []
        
        margin = 10  # 10pt的边距
        expanded_bbox = (
            bbox[0] - margin,
            bbox[1] - margin,
            bbox[2] + margin,
            bbox[3] + margin
        )
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # 文本块
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        span_bbox = span.get("bbox", [0, 0, 0, 0])
                        
                        # 检查文字是否在扩展的bbox区域内
                        text_center_x = (span_bbox[0] + span_bbox[2]) / 2
                        text_center_y = (span_bbox[1] + span_bbox[3]) / 2
                        
                        if (expanded_bbox[0] <= text_center_x <= expanded_bbox[2] and
                            expanded_bbox[1] <= text_center_y <= expanded_bbox[3]):
                            # 但不在原始bbox内（在边缘）
                            if not (bbox[0] <= text_center_x <= bbox[2] and
                                   bbox[1] <= text_center_y <= bbox[3]):
                                nearby_texts.append({
                                    'text': text,
                                    'bbox': span_bbox,
                                    'distance_from_chart': min(
                                        abs(span_bbox[0] - bbox[2]),  # 右边
                                        abs(span_bbox[2] - bbox[0]),  # 左边
                                        abs(span_bbox[1] - bbox[3]),  # 下边
                                        abs(span_bbox[3] - bbox[1])   # 上边
                                    )
                                })
        
        if nearby_texts:
            print(f"\n  ⚠️ bbox边缘附近的文字（可能被误截取）:")
            for t in nearby_texts[:5]:  # 只显示前5个
                print(f"     '{t['text'][:20]}...' (距离: {t['distance_from_chart']:.2f}pt)")
        
        # 计算图表实际内容的紧凑bbox（不含padding）
        shapes = chart['shapes']
        actual_x0 = min(shape['x'] for shape in shapes)
        actual_y0 = min(shape['y'] for shape in shapes)
        actual_x1 = max(shape['x2'] for shape in shapes)
        actual_y1 = max(shape['y2'] for shape in shapes)
        
        actual_width = actual_x1 - actual_x0
        actual_height = actual_y1 - actual_y0
        
        print(f"\n  实际内容bbox（不含padding）:")
        print(f"    ({actual_x0:.2f}, {actual_y0:.2f}, {actual_x1:.2f}, {actual_y1:.2f})")
        print(f"    实际宽度: {actual_width:.2f}pt")
        print(f"    实际高度: {actual_height:.2f}pt")
        
        # 计算当前padding
        current_padding_x = bbox[0] - actual_x0
        current_padding_y = bbox[1] - actual_y0
        padding_pct_x = (current_padding_x / actual_width * 100) if actual_width > 0 else 0
        padding_pct_y = (current_padding_y / actual_height * 100) if actual_height > 0 else 0
        
        print(f"\n  当前padding:")
        print(f"    X方向: {current_padding_x:.2f}pt ({padding_pct_x:.1f}%)")
        print(f"    Y方向: {current_padding_y:.2f}pt ({padding_pct_y:.1f}%)")
        print(f"\n  建议: 减小padding到2-3%以避免截取周围样式")
    
    doc.close()


if __name__ == "__main__":
    main()

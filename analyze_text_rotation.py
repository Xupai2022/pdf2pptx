#!/usr/bin/env python3
"""
详细分析PDF中文字的旋转角度信息
"""
import fitz  # PyMuPDF
import math


def analyze_text_rotation(pdf_path, page_num):
    """分析指定页面的文本旋转"""
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    
    print(f"\n{'='*80}")
    print(f"第 {page_num} 页文本旋转分析")
    print(f"{'='*80}\n")
    
    # 使用dict格式获取详细信息
    text_dict = page.get_text("dict")
    
    for block_idx, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") == 0:  # 文本块
            for line_idx, line in enumerate(block.get("lines", [])):
                line_dir = line.get("dir", (1.0, 0.0))
                dx, dy = line_dir
                
                # 计算角度
                rotation_angle = math.degrees(math.atan2(dy, dx))
                
                # 归一化到 [-180, 180]
                while rotation_angle > 180:
                    rotation_angle -= 360
                while rotation_angle < -180:
                    rotation_angle += 360
                
                for span_idx, span in enumerate(line.get("spans", [])):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    
                    # 检测关键文本
                    if "10.64.5.37" in text:
                        print(f"🔍 找到关键文本: '{text}'")
                        print(f"   位置: bbox={bbox}")
                        print(f"   宽度: {bbox[2] - bbox[0]:.2f}")
                        print(f"   高度: {bbox[3] - bbox[1]:.2f}")
                        print(f"   line.dir = ({dx:.6f}, {dy:.6f})")
                        print(f"   计算角度 = {rotation_angle:.2f}°")
                        print(f"   ")
                        print(f"   ⚠️ 分析:")
                        
                        # 判断旋转方向
                        bbox_width = bbox[2] - bbox[0]
                        bbox_height = bbox[3] - bbox[1]
                        
                        print(f"   - bbox宽度 ({bbox_width:.2f}) vs 高度 ({bbox_height:.2f})")
                        
                        if bbox_width < bbox_height:
                            print(f"   - 宽度 < 高度，说明文字是竖直或斜着的")
                        
                        # 根据dir向量判断
                        if dx > 0 and abs(dy) < 0.1:
                            print(f"   - dir向量表示：水平向右 (正常文字)")
                            print(f"   - 推荐旋转角度: 0°")
                        elif abs(dx) < 0.1 and dy > 0:
                            print(f"   - dir向量表示：竖直向下")
                            print(f"   - 推荐旋转角度: 90°")
                        elif abs(dx) < 0.1 and dy < 0:
                            print(f"   - dir向量表示：竖直向上")
                            print(f"   - 推荐旋转角度: -90°")
                        elif dx > 0 and dy > 0:
                            print(f"   - dir向量表示：向右下倾斜 (从左上到右下 \\)")
                            print(f"   - 计算角度: {rotation_angle:.2f}°")
                            print(f"   - 这是PDF实际的旋转方向")
                        elif dx > 0 and dy < 0:
                            print(f"   - dir向量表示：向右上倾斜 (从左下到右上 /)")
                            print(f"   - 计算角度: {rotation_angle:.2f}°")
                            print(f"   - 这是PDF实际的旋转方向")
                        elif dx < 0 and dy > 0:
                            print(f"   - dir向量表示：向左下倾斜")
                            print(f"   - 计算角度: {rotation_angle:.2f}°")
                        elif dx < 0 and dy < 0:
                            print(f"   - dir向量表示：向左上倾斜")
                            print(f"   - 计算角度: {rotation_angle:.2f}°")
                        
                        print(f"   ")
                        print(f"   📐 坐标系分析:")
                        print(f"   - PDF坐标系: 原点在左上角，X轴向右，Y轴向下")
                        print(f"   - dir=(dx, dy) 表示文字基线的方向向量")
                        print(f"   - 如果 dy > 0，文字基线向下倾斜 (\\方向)")
                        print(f"   - 如果 dy < 0，文字基线向上倾斜 (/方向)")
                        print(f"   ")
                        print(f"   🔧 PPT旋转修正:")
                        print(f"   - PPT rotation: 顺时针为正")
                        print(f"   - atan2(dy, dx)的结果: 逆时针为正")
                        print(f"   - 需要取反: ppt_rotation = -pdf_angle")
                        print(f"   - 当前计算: {rotation_angle:.2f}° (PDF)")
                        print(f"   - 应用到PPT: {-rotation_angle:.2f}° (PPT)")
                        print()
    
    doc.close()


def main():
    pdf_path = "tests/season_report_del.pdf"
    
    # 分析第11页
    print("分析第11页的文字旋转")
    analyze_text_rotation(pdf_path, 11)
    
    # 也分析第15页
    print("\n\n分析第15页的文字旋转")
    analyze_text_rotation(pdf_path, 15)


if __name__ == "__main__":
    main()

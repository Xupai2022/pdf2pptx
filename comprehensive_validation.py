#!/usr/bin/env python3
"""
全面验证修复结果
"""
from pptx import Presentation
import sys


def validate_fixes(pptx_path):
    """验证所有修复"""
    prs = Presentation(pptx_path)
    
    print("\n" + "="*80)
    print("PDF到PPT转换修复验证报告")
    print("="*80 + "\n")
    
    results = {
        'rotation': False,
        'brackets': False,
        'chart_padding': False,
        'triangle': None  # 需要人工检查
    }
    
    # ========================================================================
    # 1. 验证文字旋转方向修复（第11页和第15页）
    # ========================================================================
    print("1. 文字旋转方向验证")
    print("-" * 40)
    
    rotation_check = []
    for page_num in [11, 15]:
        if page_num > len(prs.slides):
            continue
        
        slide = prs.slides[page_num - 1]
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text.strip()
                if "10.64.5.37" in text or "10.74.145.44" in text:
                    rotation = shape.rotation
                    # 归一化到-180到180
                    while rotation > 180:
                        rotation -= 360
                    
                    # 检查文本框的宽度和高度，判断是否应该旋转
                    # 如果宽度远大于高度，说明是水平文本，不需要旋转
                    is_horizontal = shape.width > shape.height * 1.5
                    
                    if is_horizontal:
                        # 水平文本，应该是0度
                        if rotation == 0:
                            print(f"  ℹ️  第{page_num}页 '{text[:30]}...' 水平文本，旋转角度正确: {shape.rotation}°")
                        else:
                            print(f"  ⚠️  第{page_num}页 '{text[:30]}...' 水平文本，旋转角度异常: {shape.rotation}°")
                    else:
                        # 旋转文本，应该是-45度或315度
                        if rotation == -45 or rotation == 315:
                            rotation_check.append(True)
                            print(f"  ✅ 第{page_num}页 '{text[:30]}...' 旋转角度正确: {shape.rotation}° (归一化: {rotation}°)")
                        else:
                            rotation_check.append(False)
                            print(f"  ❌ 第{page_num}页 '{text[:30]}...' 旋转角度错误: {shape.rotation}°")
    
    results['rotation'] = all(rotation_check) if rotation_check else False
    
    # ========================================================================
    # 2. 验证括号位置修复（第15页）
    # ========================================================================
    print("\n2. 括号位置验证（第15页）")
    print("-" * 40)
    
    if len(prs.slides) >= 15:
        slide = prs.slides[14]
        
        # 统计独立的括号文本框
        standalone_brackets = []
        merged_ip_brackets = []
        
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text.strip()
                
                # 检查是否是独立的括号
                if text in ['(', ')', '（', '）']:
                    standalone_brackets.append(text)
                
                # 检查是否是合并后的IP+括号+业务类型
                if any(ip in text for ip in ['10.74.145.44', '10.64.5.37']) and \
                   any(b in text for b in ['(', ')', '（', '）']):
                    merged_ip_brackets.append(text)
        
        if len(standalone_brackets) == 0:
            results['brackets'] = True
            print(f"  ✅ 没有独立的括号文本框")
            print(f"  ✅ 找到 {len(merged_ip_brackets)} 个正确合并的IP+括号+业务类型文本框:")
            for text in merged_ip_brackets[:5]:
                print(f"     - '{text}'")
        else:
            results['brackets'] = False
            print(f"  ❌ 发现 {len(standalone_brackets)} 个独立的括号文本框")
    
    # ========================================================================
    # 3. 验证图表padding优化（第11页）
    # ========================================================================
    print("\n3. 图表截图padding验证（第11页）")
    print("-" * 40)
    print("  ℹ️  需要人工检查生成的PPT第11页")
    print("  ℹ️  饼状图PNG截图四周应该紧凑，不应截取周围样式")
    results['chart_padding'] = None  # 需要人工检查
    
    # ========================================================================
    # 4. 验证三角形底边（第4页）
    # ========================================================================
    print("\n4. 三角形底边验证（第4页）")
    print("-" * 40)
    print("  ℹ️  需要人工检查生成的PPT第4页")
    print("  ℹ️  中间的三角形图案底边的横线应该正常显示")
    results['triangle'] = None  # 需要人工检查
    
    # ========================================================================
    # 总结
    # ========================================================================
    print("\n" + "="*80)
    print("验证总结")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v == True)
    failed = sum(1 for v in results.values() if v == False)
    manual = sum(1 for v in results.values() if v is None)
    
    print(f"\n自动验证:")
    print(f"  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {failed}")
    print(f"  ⏳ 需人工检查: {manual}")
    
    if results['rotation']:
        print(f"\n✅ 文字旋转方向修复: 成功")
    else:
        print(f"\n❌ 文字旋转方向修复: 失败")
    
    if results['brackets']:
        print(f"✅ 括号位置修复: 成功")
    else:
        print(f"❌ 括号位置修复: 失败")
    
    print(f"\n⏳ 请人工检查:")
    print(f"  - 第11页饼状图PNG截图是否紧凑（padding是否合适）")
    print(f"  - 第4页三角形底边横线是否显示")
    
    print("\n" + "="*80 + "\n")
    
    return results


if __name__ == "__main__":
    pptx_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_all_fixes.pptx"
    results = validate_fixes(pptx_file)
    
    # 返回退出码
    if any(v == False for v in results.values()):
        sys.exit(1)  # 有失败的测试
    else:
        sys.exit(0)  # 全部通过或需人工检查

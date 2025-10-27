"""
完整测试脚本：验证 glm-4.6.pdf 第4-10页的颜色和透明度转换
"""
import sys
import logging
from pathlib import Path
from src.parser.pdf_parser import PDFParser
from src.generator.pptx_generator import PPTXGenerator

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_pages_extraction(pdf_path, start_page, end_page):
    """测试指定页面范围的颜色和透明度提取"""
    config = {
        'dpi': 300,
        'extract_images': True,
        'image_format': 'PNG',
        'min_text_size': 6,
        'max_text_size': 72
    }
    
    parser = PDFParser(config)
    parser.open(pdf_path)
    
    test_results = []
    
    for page_num in range(start_page - 1, end_page):  # 转换为0索引
        print(f"\n{'='*80}")
        print(f"测试第 {page_num + 1} 页")
        print(f"{'='*80}")
        
        page_data = parser.extract_page_elements(page_num)
        
        # 统计形状
        shape_count = sum(1 for e in page_data['elements'] if e['type'] == 'shape')
        text_count = sum(1 for e in page_data['elements'] if e['type'] == 'text')
        image_count = sum(1 for e in page_data['elements'] if e['type'] == 'image')
        
        # 筛选 RGB(9, 65, 116) 的形状
        target_shapes = []
        for element in page_data['elements']:
            if element['type'] == 'shape' and element['fill_color'] == '#094174':
                target_shapes.append(element)
        
        # 按透明度分组
        opacity_groups = {}
        for shape in target_shapes:
            opacity = round(shape['fill_opacity'], 4)
            if opacity not in opacity_groups:
                opacity_groups[opacity] = []
            opacity_groups[opacity].append(shape)
        
        print(f"元素统计: {shape_count} 形状, {text_count} 文本, {image_count} 图像")
        print(f"RGB(9,65,116) 的形状: {len(target_shapes)} 个")
        print(f"\n透明度分布:")
        for opacity in sorted(opacity_groups.keys()):
            shapes = opacity_groups[opacity]
            print(f"  {opacity:.4f}: {len(shapes)} 个形状")
        
        # 验证
        has_transparent = any(o < 0.5 for o in opacity_groups.keys())
        has_multiple_levels = len(opacity_groups) > 1
        
        result = {
            'page': page_num + 1,
            'total_shapes': shape_count,
            'target_shapes': len(target_shapes),
            'opacity_levels': len(opacity_groups),
            'opacities': sorted(opacity_groups.keys()),
            'has_transparent': has_transparent,
            'has_multiple_levels': has_multiple_levels,
            'pass': has_transparent or shape_count == 0  # 通过条件：有透明形状或没有形状
        }
        
        test_results.append(result)
        
        if result['pass']:
            print(f"✅ 通过: 透明度提取正常")
        else:
            print(f"❌ 失败: 未检测到透明形状")
    
    parser.close()
    
    return test_results

def generate_pptx_test(pdf_path, output_path, start_page, end_page):
    """生成 PPTX 并验证"""
    from main import main as convert_main
    import sys
    
    print(f"\n{'='*80}")
    print(f"生成 PPTX: {output_path}")
    print(f"{'='*80}\n")
    
    # 备份原 sys.argv
    old_argv = sys.argv
    try:
        # 模拟命令行参数
        sys.argv = ['main.py', str(pdf_path), str(output_path)]
        convert_main()
        print(f"\n✅ PPTX 生成成功: {output_path}")
        return True
    except Exception as e:
        print(f"\n❌ PPTX 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sys.argv = old_argv

def main():
    """主测试函数"""
    pdf_path = Path('tests/glm-4.6.pdf')
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / 'glm-4.6_test.pptx'
    
    print(f"\n{'#'*80}")
    print(f"# glm-4.6.pdf 颜色和透明度测试")
    print(f"{'#'*80}\n")
    
    # 第一部分：提取测试
    print(f"\n第一部分：PDF 解析和透明度提取测试")
    print(f"-" * 80)
    
    test_results = test_pages_extraction(pdf_path, 4, 10)
    
    # 第二部分：PPTX 生成测试
    print(f"\n第二部分：PPTX 生成测试")
    print(f"-" * 80)
    
    pptx_success = generate_pptx_test(pdf_path, output_path, 4, 10)
    
    # 汇总报告
    print(f"\n{'='*80}")
    print(f"测试总结")
    print(f"{'='*80}\n")
    
    passed = sum(1 for r in test_results if r['pass'])
    total = len(test_results)
    
    print(f"PDF 解析测试: {passed}/{total} 页通过")
    print(f"PPTX 生成: {'✅ 成功' if pptx_success else '❌ 失败'}")
    
    print(f"\n详细结果:")
    for result in test_results:
        status = "✅" if result['pass'] else "❌"
        print(f"  {status} 第{result['page']}页: "
              f"{result['target_shapes']}个目标形状, "
              f"{result['opacity_levels']}个透明度级别 {result['opacities']}")
    
    # 最终判定
    all_pass = passed == total and pptx_success
    print(f"\n{'='*80}")
    if all_pass:
        print(f"✅✅✅ 所有测试通过！ ✅✅✅")
    else:
        print(f"❌ 部分测试失败")
    print(f"{'='*80}\n")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())

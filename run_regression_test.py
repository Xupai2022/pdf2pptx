#!/usr/bin/env python3
"""
回归测试：确保修复没有破坏其他功能
"""

import subprocess
import sys
from pathlib import Path

def run_test(test_file, description):
    """运行单个测试"""
    print(f"\n{'='*80}")
    print(f"测试: {description}")
    print('='*80)
    
    result = subprocess.run(
        ['python', 'main.py', test_file, f'output_{Path(test_file).stem}.pptx'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )
    
    success = result.returncode == 0
    
    if success:
        print(f"✅ {description} - 转换成功")
    else:
        print(f"❌ {description} - 转换失败")
        print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
    
    return success

def main():
    """运行所有回归测试"""
    
    print("="*80)
    print("PDF转PPT回归测试套件")
    print("="*80)
    
    tests = [
        ('tests/test_sample.pdf', 'test_sample.pdf (CVE修复验证)'),
    ]
    
    # 如果有其他测试文件，添加它们
    test_dir = Path('tests')
    for pdf_file in test_dir.glob('*.pdf'):
        if pdf_file.name != 'test_sample.pdf':
            tests.append((str(pdf_file), f'{pdf_file.name} (其他PDF)'))
    
    results = []
    for test_file, description in tests:
        success = run_test(test_file, description)
        results.append((description, success))
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {description}")
    
    print("\n" + "="*80)
    print(f"总计: {passed}/{total} 通过 ({passed*100//total}%)")
    
    if passed == total:
        print("✅✅✅ 所有回归测试通过！")
    else:
        print("❌ 部分测试失败，请检查")
    print("="*80)
    
    # 清理输出文件
    print("\n清理测试输出文件...")
    for test_file, _ in tests:
        output_file = Path(f'output_{Path(test_file).stem}.pptx')
        if output_file.exists():
            output_file.unlink()
            print(f"  删除: {output_file}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

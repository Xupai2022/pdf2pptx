#!/usr/bin/env python3
"""
LayoutLM快速验证脚本
测试LayoutLM在您的PDF上的实际效果
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 检查依赖
try:
    from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
    import torch
except ImportError:
    print("❌ 缺少依赖，请先安装:")
    print("   pip install transformers torch")
    sys.exit(1)

from src.parser.pdf_parser import PDFParser
import yaml

def load_test_config():
    """加载配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def test_layoutlm_on_pdf(pdf_path: str):
    """测试LayoutLM在指定PDF上的表现"""
    print(f"\n{'='*60}")
    print(f"LayoutLM POC验证")
    print(f"{'='*60}\n")
    
    # 1. 加载模型
    print("📥 Loading LayoutLMv3 model...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"   Device: {device}")
    
    if device == 'cpu':
        print("   ⚠️  警告: CPU模式性能较低，建议使用GPU")
    
    start = time.time()
    try:
        # 使用tokenizer而不是processor,因为我们已经有文本和bbox
        from transformers import LayoutLMv3Tokenizer
        tokenizer = LayoutLMv3Tokenizer.from_pretrained("microsoft/layoutlmv3-base")
        model = LayoutLMv3ForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")
        model.to(device)
        model.eval()
    except Exception as e:
        print(f"   ❌ Failed to load model: {e}")
        print("   提示: 首次运行需要下载约500MB模型文件")
        return None
    
    load_time = time.time() - start
    print(f"   ✅ Model loaded in {load_time:.2f}s\n")
    
    # 2. 解析PDF
    print("📄 Parsing PDF with PyMuPDF...")
    config = load_test_config()
    parser = PDFParser(config['parser'])
    
    if not parser.open(pdf_path):
        print(f"   ❌ Failed to open PDF: {pdf_path}")
        return None
    
    start = time.time()
    page_data = parser.extract_page_elements(0)  # 测试第一页
    parser.close()
    parse_time = time.time() - start
    print(f"   ✅ PDF parsed in {parse_time:.2f}s")
    print(f"   📊 Elements extracted: {len(page_data['elements'])}")
    
    text_elements = [e for e in page_data['elements'] if e.get('type') == 'text']
    print(f"   📝 Text blocks: {len(text_elements)}\n")
    
    # 3. 准备LayoutLM输入
    print("🔄 Converting to LayoutLM format...")
    words = []
    boxes = []
    page_width = page_data['width']
    page_height = page_data['height']
    
    for element in text_elements[:50]:  # 限制处理前50个文本块
        # 尝试两个字段: 'content' (新版) 或 'text' (旧版)
        text = element.get('content', element.get('text', '')).strip()
        if not text:
            continue
        
        # 归一化坐标
        x1 = int((element['x'] / page_width) * 1000)
        y1 = int((element['y'] / page_height) * 1000)
        x2 = int((element['x2'] / page_width) * 1000)
        y2 = int((element['y2'] / page_height) * 1000)
        
        # 简单分词
        tokens = text.split()
        for token in tokens:
            words.append(token)
            boxes.append([x1, y1, x2, y2])
    
    if not words:
        print("   ❌ No text found in PDF")
        return None
    
    print(f"   ✅ Prepared {len(words)} tokens\n")
    
    # 4. LayoutLM推理
    print("🤖 Running LayoutLM inference...")
    start = time.time()
    
    try:
        # 使用tokenizer直接处理,已经有文本和bbox
        encoding = tokenizer(
            text=words,
            boxes=boxes,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=512,
            is_split_into_words=True  # 已经分词
        )
        
        for k, v in encoding.items():
            if isinstance(v, torch.Tensor):
                encoding[k] = v.to(device)
        
        with torch.no_grad():
            outputs = model(**encoding)
            predictions = outputs.logits.argmax(-1).squeeze().tolist()
        
        infer_time = time.time() - start
        print(f"   ✅ Inference completed in {infer_time:.2f}s\n")
    except Exception as e:
        print(f"   ❌ Inference failed: {e}")
        return None
    
    # 5. 分析结果
    print("📊 Analysis Results:")
    print(f"   Total processing time: {load_time + parse_time + infer_time:.2f}s")
    print(f"     - Model loading: {load_time:.2f}s (一次性开销)")
    print(f"     - PDF parsing: {parse_time:.2f}s")
    print(f"     - LayoutLM inference: {infer_time:.2f}s")
    
    if isinstance(predictions, int):
        predictions = [predictions]
    
    predictions = predictions[:len(words)]
    
    # 统计标签分布
    from collections import Counter
    label_counts = Counter(predictions)
    print(f"\n   Label distribution:")
    for label, count in label_counts.most_common(5):
        print(f"     Label {label}: {count} tokens ({count/len(predictions)*100:.1f}%)")
    
    # 6. 评估建议
    print(f"\n{'='*60}")
    print("💡 Evaluation & Recommendations:")
    print(f"{'='*60}\n")
    
    if device == 'cpu' and infer_time > parse_time * 2:
        print("⚠️  LayoutLM推理时间显著高于PDF解析")
        print("   建议: 仅在GPU环境下使用LayoutLM\n")
    elif device == 'cuda' and infer_time < parse_time * 0.5:
        print("✅ LayoutLM推理性能良好 (GPU加速有效)")
        print("   可以考虑集成到生产环境\n")
    else:
        print("⚙️  性能可接受，建议进一步评估准确率提升\n")
    
    if len(text_elements) < 10:
        print("ℹ️  当前页面较简单 (文本块<10)")
        print("   LayoutLM的优势在复杂布局中更明显\n")
    
    print("📝 Next Steps:")
    print("   1. 使用更多测试PDF (特别是复杂表格/多列布局)")
    print("   2. 量化准确率提升 (对比现有布局分析结果)")
    print("   3. 评估在实际应用场景中的ROI\n")
    
    return {
        'load_time': load_time,
        'parse_time': parse_time,
        'infer_time': infer_time,
        'total_time': load_time + parse_time + infer_time,
        'device': device,
        'text_blocks': len(text_elements),
        'tokens': len(words)
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python layoutlm_quick_test.py <pdf_path>")
        print("\nExample:")
        print("  python layoutlm_quick_test.py tests/test_sample.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        sys.exit(1)
    
    result = test_layoutlm_on_pdf(pdf_path)
    
    if result:
        print(f"{'='*60}")
        print("✅ Test completed successfully")
        print(f"{'='*60}\n")

#!/usr/bin/env python3
"""调试文本渲染问题"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main import load_config
from src.parser.pdf_parser import PDFParser
from src.analyzer.layout_analyzer import LayoutAnalyzer

config = load_config()
parser_config = config.get('parser', {})
analyzer_config = config.get('analyzer', {})

# Parse PDF
parser = PDFParser(parser_config)
parser.open("tests/test_sample.pdf")
pages_data = parser.extract_all_pages()
parser.close()

print("=" * 60)
print("TEXT ELEMENT DEBUG")
print("=" * 60)

page_data = pages_data[0]
text_elements = [e for e in page_data['elements'] if e['type'] == 'text']

print(f"\nTotal text elements: {len(text_elements)}")
print(f"\nFirst 10 text elements:")

for i, elem in enumerate(text_elements[:10]):
    content = elem['content']
    print(f"\n{i+1}. Text: \"{content}\"")
    print(f"   Font size: {elem['font_size']:.1f}pt")
    print(f"   Length: {len(content)}")
    print(f"   Repr: {repr(content[:50])}")
    
    # Check for problematic characters
    has_problem = False
    for c in content:
        code = ord(c)
        if code < 32 and c not in '\t\n\r':
            print(f"   WARNING: Control char U+{code:04X}")
            has_problem = True
        elif code == 0xFFFF:
            print(f"   WARNING: Non-character U+FFFF found")
            has_problem = True
    
    if not has_problem:
        print(f"   ✓ Clean text")

# Now analyze layout
print("\n" + "=" * 60)
print("LAYOUT ANALYSIS")
print("=" * 60)

analyzer = LayoutAnalyzer(analyzer_config)
layout = analyzer.analyze_page(page_data)
print(f"\nTotal regions: {len(layout['layout'])}")
print(f"\nFirst 5 text regions:")

text_regions = [r for r in layout['layout'] if r['role'] in ['title', 'heading', 'text', 'paragraph']]

for i, region in enumerate(text_regions[:5]):
    print(f"\n{i+1}. Role: {region['role']}")
    print(f"   Text: \"{region.get('text', 'NO TEXT')}\"")
    print(f"   Elements: {len(region.get('elements', []))}")
    if region.get('elements'):
        first_elem = region['elements'][0]
        if first_elem.get('content'):
            print(f"   First element content: \"{first_elem['content'][:50]}\"")

import fitz

pdf_path = "tests/season_report_del.pdf"
doc = fitz.open(pdf_path)
page = doc[3]

drawings = page.get_drawings()
print(f"=== 检查Drawing颜色信息 ===\n")

for i, drawing in enumerate(drawings[:11]):  # First 11 drawings
    rect = drawing['rect']
    print(f"\nDrawing {i+1}: {rect.width:.1f}x{rect.height:.1f}")
    print(f"  fill: {drawing.get('fill')}")
    print(f"  color: {drawing.get('color')}")
    print(f"  type: {drawing.get('type')}")
    print(f"  width: {drawing.get('width')}")
    print(f"  closePath: {drawing.get('closePath')}")
    print(f"  evenOdd: {drawing.get('evenOdd')}")
    print(f"  items count: {len(drawing.get('items', []))}")

doc.close()

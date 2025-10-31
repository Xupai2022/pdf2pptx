import fitz
import sys

pdf_path = "tests/season_report_del.pdf"
doc = fitz.open(pdf_path)
page = doc[3]  # Page 4 (0-indexed page 3)

print("=== PDF Page 3 完整Drawing分析 ===\n")

# Get all drawings
drawings = page.get_drawings()
print(f"总共 {len(drawings)} 个 drawings\n")

for i, drawing in enumerate(drawings):
    rect = drawing['rect']
    width = rect.width
    height = rect.height
    x, y = rect.x0, rect.y0
    
    # Get fill and stroke colors
    fill_color = None
    stroke_color = None
    
    for item in drawing['items']:
        item_type, *args = item
        if item_type == 'f':  # fill
            fill_color = args[0] if args else None
        elif item_type == 's':  # stroke
            stroke_color = args[0] if args else None
    
    # Analyze the drawing type
    aspect_ratio = width / height if height > 0 else float('inf')
    is_circle = 0.85 <= aspect_ratio <= 1.15 if height > 0 else False
    is_horizontal = height < 5
    is_vertical = width < 5
    is_diagonal = not is_horizontal and not is_vertical and width > 50 and height > 50
    
    print(f"Drawing {i+1}: 位置({x:.1f}, {y:.1f}), 尺寸 {width:.1f}x{height:.1f}")
    print(f"  类型判断: circle={is_circle}, horizontal={is_horizontal}, vertical={is_vertical}, diagonal={is_diagonal}")
    print(f"  填充颜色: {fill_color}")
    print(f"  描边颜色: {stroke_color}")
    print(f"  Aspect ratio: {aspect_ratio:.2f}")
    
    # Analyze items in detail
    print(f"  Items ({len(drawing['items'])} 个):")
    for j, item in enumerate(drawing['items']):
        item_type = item[0]
        if item_type == 'l':  # line
            print(f"    Item {j}: line - {item}")
        elif item_type == 'c':  # curve
            print(f"    Item {j}: curve - {item}")
        elif item_type == 're':  # rectangle
            print(f"    Item {j}: rectangle - {item}")
        elif item_type == 'qu':  # quad
            print(f"    Item {j}: quad")
        elif item_type == 'f':  # fill
            print(f"    Item {j}: fill - color={item[1] if len(item) > 1 else None}")
        elif item_type == 's':  # stroke
            print(f"    Item {j}: stroke - color={item[1] if len(item) > 1 else None}, width={item[2] if len(item) > 2 else None}")
    
    print()

doc.close()

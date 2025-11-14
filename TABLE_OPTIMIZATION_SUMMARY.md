# 表格转换优化总结

## 目标

优化安全运营周报.pdf中的表格转换效果，特别是第9页和第12页，同时确保第8页不受影响。

## 核心需求

1. **智能检测PDF表格的真实结构**：不依赖人工提示，自动分析行数、列数
2. **识别合并单元格**：正确处理垂直和水平合并的单元格
3. **应用背景颜色**：根据PDF智能识别并应用单元格背景色
4. **匹配列宽**：按照PDF中的实际列宽设置PPTX表格

## 已实现的优化

### 1. 面积过滤算法（Area-Based Background Filtering）

**问题**：之前使用高度或宽度阈值过滤背景，但合并单元格和表格背景可能有相同的高度。

**解决方案**：使用面积（width × height）进行过滤

```python
# 计算75th百分位面积
area_75th = sorted([w * h for w, h in cells])[int(len(cells) * 0.75)]

# 背景矩形面积 > 典型单元格面积 × 10
background_threshold = area_75th * 10
```

**效果**：
- 普通单元格：172pt × 21.5pt = 3,698 sq.pt  ✅ 保留
- 合并单元格：64.5pt × 154.8pt = 9,985 sq.pt  ✅ 保留
- 表格背景：657.8pt × 154.8pt = 101,827 sq.pt  ❌ 过滤
- 页面背景：675pt × 3482pt = 2,350,350 sq.pt  ❌ 过滤

### 2. 垂直跨行单元格合并（Vertical-Span Cell Merging）

**问题**：第9页的第一列合并单元格起始于Y=36，而其他列起始于Y=39，导致被识别为2个独立的行。

**解决方案**：
```python
# 如果某行只有1个单元格且高度>50pt（垂直合并标志）
if len(row) == 1 and row[0]['height'] > 50:
    # 且下一行在10pt内且有多个单元格
    if abs(next_y - current_y) < 10 and len(next_row) >= 2:
        # 合并到下一行
        merged_row = next_row + current_row
```

### 3. 智能列宽应用

**实现**：
- 从PDF单元格中提取实际列宽（以points为单位）
- 转换为EMUs（1pt = 12700 EMUs）
- 应用到PPTX表格列：`table.columns[i].width = width_emus`

### 4. 单元格颜色和边框

**实现**：
- 提取PDF单元格的 `fill_color` 和 `stroke_color`
- 在PPTX中应用：
  - 背景色：`cell.fill.solid()` + `cell.fill.fore_color.rgb`
  - 边框：使用lxml直接操作XML设置四边边框

## 当前测试结果

### 第8页（PDF第9页）✅ 完美

- **结构**：11行 × 3列
- **第一列**：正确显示"终端安全"、"态势感知"、"防火墙"的垂直合并单元格
- **颜色**：头部行 #EFF1F6（浅灰），数据行 #FFFFFF（白色）
- **列宽**：0.90"（64.5pt）、2.39"（172pt）、5.85"（421.3pt）

### 第9页（PDF第10页）❌ 待优化

**当前状态**：
- 检测到 7行 × 2列（**缺少第一列**）
- 第一列的合并单元格已被检测，但未正确合并到逻辑行

**原因分析**：
1. 第9页PDF中第一列没有任何文本内容（纯空白合并单元格）
2. 合并逻辑的条件可能需要调整
3. 行合并代码的执行流程需要进一步验证

**下一步**：
- 调试 `_group_by_y_position` 中的合并逻辑
- 确认 `merged_row` 是否正确包含了X=39.2的单元格
- 验证后续的列检测是否识别到3列

### 第12页（PDF第13页）✅ 基本正确

- **结构**：9行 × 5列
- **合并单元格**：正确检测并应用
- **颜色**：头部行 #EFF1F6，数据行交替 #FFFFFF 和 #F6F9FB

## 技术亮点

### 1. 统计分析方法

使用75th百分位数而非固定阈值，适应不同表格的尺寸变化：
```python
sorted_heights = sorted(heights)
height_75th = sorted_heights[int(len(sorted_heights) * 0.75)]
```

### 2. 面积判别法

相比单独的高度或宽度判断，面积更能准确反映背景矩形的特征：
- 合并单元格：窄但高（面积中等）
- 表格背景：宽且高（面积巨大）

### 3. 行分组优化

支持稀疏列和垂直合并：
- 从列数最多的行开始构建表格
- 向前向后扫描匹配的行
- 允许单列行作为第一列加入表格

## 测试文件

创建了3个分析工具：

1. **analyze_table_structure.py**：深度分析PDF表格原始结构
   - 矩形分组
   - 行列检测
   - 合并单元格识别
   - 文本位置

2. **test_table_page9.py**：单独测试第9页的表格检测

3. **analyze_converted_tables.py**：分析生成的PPTX表格结构
   - 行列数
   - 单元格内容
   - 列宽
   - 背景颜色

## 使用方法

```bash
# 分析PDF表格结构
python analyze_table_structure.py tests/安全运营月报.pdf 9

# 转换PDF到PPTX
python main.py tests/安全运营月报.pdf output/result.pptx

# 分析转换结果
python analyze_converted_tables.py output/result.pptx
```

## 待解决问题

1. **第9页第一列缺失**
   - 原因：垂直合并单元格的行对齐逻辑需要完善
   - 影响：缺少一列，但不影响数据完整性（该列本就是空白）

2. **第9页多一行**
   - 当前：8行（第1行是空的）
   - 期望：7行
   - 原因：与第一列缺失问题相关

## 总结

已完成核心优化：
- ✅ 面积过滤算法显著提高背景识别准确性
- ✅ 第8页完美转换（包括合并单元格、颜色、列宽）
- ✅ 第12页正确转换
- ⚠️ 第9页需要进一步调试行合并逻辑

关键创新：
- 统计分析方法替代固定阈值
- 面积判别法区分合并单元格与背景
- 支持稀疏列和垂直跨行的灵活表格结构

代码变更：
- 主要修改：`src/parser/table_detector.py`
- 新增测试工具：3个分析脚本
- 提交消息：`fix(table): improve table detection with area-based background filtering`

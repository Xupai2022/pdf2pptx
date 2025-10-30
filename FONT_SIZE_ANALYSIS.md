# 字体大小问题深度分析

## 🔍 问题现象

转换 `season_report_del.pdf` 后，文字看起来比原始PPT小很多。

## 📊 数据分析

### 原始PPT → PDF → 新PPT 的尺寸变化

```
原始PPT (用户创建)
├─ 画布: 960 × 540 pt (16:9 标准宽屏)
└─ 文字: 24 pt
    ↓ 导出PDF
    
PDF文件 (season_report_del.pdf)
├─ 页面: 960 × 540 pt (保持原样)
└─ 文字: 24 pt
    ↓ 使用当前代码转换
    
新PPT (转换结果)
├─ 画布: 1920 × 1080 pt (配置固定值，扩大2倍！)
└─ 文字: 24 × 1.333 = 32 pt (只扩大1.333倍)
```

### 核心问题

**画布和文字的缩放比例不一致！**

- ❌ 画布缩放：960 → 1920 = **2.0倍**
- ❌ 文字缩放：24 → 32 = **1.333倍**
- 结果：文字相对于画布缩小了 `1.333 / 2.0 = 0.665`，即**显示为原来的66.5%**

### 视觉验证

用户测试：
- 在转换后PPT中创建24pt文本框
- 复制到原始PPT
- 两个文本框显示大小一样 ✅

**说明：问题不是字号本身，而是画布大小的差异！**

## 🔧 代码分析

### 1. 配置文件 `config/config.yaml`

```yaml
rebuilder:
  slide_width: 26.667   # 1920px at 72 DPI = 26.667"
  slide_height: 15.0    # 1080px at 72 DPI = 15.0"
  pdf_to_html_scale: 1.333  # 固定值！

mapper:
  font_size_scale: 1.333  # 固定值！
```

**问题：这些值是硬编码的，针对特定的PDF尺寸！**

注释说明：
```yaml
# PDF is generated at 75% scale (1440×811 pt), need to scale back to 1920×1080 px
# PDF scale correction: PDF is 75% of HTML size, multiply by 1.333 to restore
```

### 2. 为什么是1.333？

这个系数来自于**特定的HTML→PDF转换场景**：

```
HTML Canvas: 1920 × 1080 px
    ↓ 75% 缩放 (某些PDF导出工具的默认行为)
PDF Page: 1440 × 811 pt
    ↓ 需要恢复到原始尺寸
Scale Factor: 1920 / 1440 = 1.333
```

但是 `season_report_del.pdf` 的情况完全不同：

```
原始PPT: 960 × 540 pt
    ↓ 直接导出 (100% 比例)
PDF: 960 × 540 pt
    ↓ 应该保持原样或按实际比例缩放
正确的Scale: 1.0 或 (1920/960 = 2.0)
```

### 3. 坐标映射逻辑

`src/rebuilder/coordinate_mapper.py`:

```python
# 第169-174行：应用PDF缩放修正
x1 *= self.pdf_to_html_scale  # 960 × 1.333 = 1280
y1 *= self.pdf_to_html_scale
x2 *= self.pdf_to_html_scale
y2 *= self.pdf_to_html_scale

# 第195-197行：再次缩放PDF尺寸
scaled_pdf_width = pdf_width * self.pdf_to_html_scale   # 960 × 1.333 = 1280
scaled_pdf_height = pdf_height * self.pdf_to_html_scale # 540 × 1.333 = 720

# 第199-203行：归一化到0-1
norm_x = x1 / scaled_pdf_width  # 归一化到 1280 的尺度
# ...然后映射到 1920 的画布
```

**流程**：
1. PDF坐标 × 1.333 = 中间坐标 (1280×720)
2. 归一化到0-1
3. 映射到最终PPT画布 (1920×1080)

**实际效果**：
- 文字字号：24 × 1.333 = 32 pt
- 画布尺寸：960 → (1280归一化) → 1920 = **2.0倍**

### 4. 字体样式应用

`src/mapper/style_mapper.py` 第69-70行：

```python
font_size_raw = style.get('font_size', self.default_font_size)  # 24
font_size = font_size_raw * self.font_size_scale  # 24 × 1.333 = 32
```

## ✅ 解决方案

### 方案1：动态计算缩放比例（推荐）

**原理：根据PDF实际尺寸动态计算缩放因子**

```python
# 在 CoordinateMapper.__init__ 中
pdf_width = ...  # 从PDF获取
target_width = self.slide_width * 72  # 转换为pt

# 动态计算缩放比例
if pdf_width > 0:
    self.pdf_to_html_scale = target_width / pdf_width
else:
    self.pdf_to_html_scale = 1.0
```

**效果**：
- `season_report_del.pdf`: scale = 1920 / 960 = **2.0**
- 1440×811的PDF: scale = 1920 / 1440 = **1.333**
- 其他尺寸的PDF：自动适配

**优点**：
- ✅ 自动适配任何PDF尺寸
- ✅ 保持视觉一致性
- ✅ 无需配置
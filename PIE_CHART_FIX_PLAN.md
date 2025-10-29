# 饼图转换问题分析与修复方案

## 问题概述

### 问题1: complete_report_16_7.pdf 第5页 - 饼图显示为矩形
**现象**：威胁情报推送构成饼图转换后所有颜色块都显示为矩形而非扇形

**根本原因**：
- PDF中发现4个形状完全重叠在同一位置 (583.2, 649.8)
- 所有形状尺寸完全相同：86.4 x 86.4 pt
- 4种不同颜色：
  1. 蓝色 (0.102, 0.451, 0.910)
  2. 红色 (0.898, 0.224, 0.208)
  3. 黄色 (0.984, 0.753, 0.176)
  4. 绿色 (0.220, 0.557, 0.235)
- 这是叠加的矩形形成的"假饼图"效果

**当前代码问题**：
`ChartDetector` 要求图表中的形状满足：
- 至少3个形状
- 多种颜色（2+）
- 形状需要在空间上接近（cluster_distance_threshold = 50）

但4个完全重叠的矩形中心距离为0，会被归为一个聚类，但可能无法正确识别为图表。

### 问题2: eee.pdf 第2页 - 图片下方重复出现文字
**现象**：漏洞分布情况饼图已经在图片中包含"高危"、"中危"等文字，但图片下方还出现了重复的文本框

**根本原因**：
- PDF中发现3个形状构成的真实饼图 (309.2, 234.0) - 150x150 pt
  - 红色矩形 (22x75)
  - 黄色矩形 (58.3x71.7)
  - 绿色正方形 (150x150) - 作为背景
- 还有1个白色圆形 (1011.0, 275.2) - 90x90 pt
- 嵌入图片数量：0（说明饼图是矢量图）

**当前代码问题**：
- 饼图被正确转换为图像
- 但文本提取器同时提取了该区域的文字标签
- 没有检测机制来判断某个文本是否已经包含在图片中

## 修复方案

### 方案1: 增强ChartDetector识别完全重叠的形状组

**位置**：`src/parser/chart_detector.py`

**修改点**：
1. 在 `_cluster_shapes()` 中添加检测完全重叠形状的逻辑
2. 将完全重叠且颜色不同的形状组识别为特殊的"叠加图表"
3. 在 `_is_chart_cluster()` 中放宽对形状位置分散度的要求

```python
def _cluster_shapes(self, shapes):
    """改进的聚类算法，支持完全重叠的形状"""
    # 先检测完全重叠的形状组
    overlapping_clusters = self._find_overlapping_shape_groups(shapes)
    
    # 然后对剩余形状进行常规空间聚类
    remaining_shapes = [s for s in shapes if not in overlapping_clusters]
    spatial_clusters = self._spatial_clustering(remaining_shapes)
    
    return overlapping_clusters + spatial_clusters

def _find_overlapping_shape_groups(self, shapes):
    """查找完全重叠的形状组"""
    groups = []
    used_indices = set()
    
    for i, shape1 in enumerate(shapes):
        if i in used_indices:
            continue
        
        group = [shape1]
        pos1 = (shape1['x'], shape1['y'], shape1['width'], shape1['height'])
        
        for j, shape2 in enumerate(shapes):
            if j <= i or j in used_indices:
                continue
            
            pos2 = (shape2['x'], shape2['y'], shape2['width'], shape2['height'])
            
            # 检查位置和尺寸是否完全相同（容差5pt）
            if self._are_positions_identical(pos1, pos2, tolerance=5):
                # 检查颜色是否不同
                if shape1['fill_color'] != shape2['fill_color']:
                    group.append(shape2)
                    used_indices.add(j)
        
        if len(group) >= 2:  # 至少2个重叠形状
            groups.append(group)
            used_indices.add(i)
    
    return groups
```

### 方案2: 实现文本-图片区域冲突检测

**位置**：`src/analyzer/layout_analyzer_v2.py` 或新建 `src/parser/text_image_overlap_detector.py`

**实现**：
1. 在页面元素提取完成后，检测每个文本元素
2. 判断文本是否与图片区域重叠
3. 如果重叠且图片来源是图表渲染，则移除该文本

```python
class TextImageOverlapDetector:
    """检测并移除与图片重叠的文本元素"""
    
    def __init__(self, overlap_threshold=0.5):
        """
        Args:
            overlap_threshold: 重叠比例阈值（0-1）
        """
        self.overlap_threshold = overlap_threshold
    
    def filter_overlapping_texts(self, elements):
        """
        过滤掉与图片重叠的文本元素
        
        Args:
            elements: 页面元素列表
            
        Returns:
            过滤后的元素列表
        """
        # 提取图片和文本元素
        images = [e for e in elements if e['type'] == 'image']
        texts = [e for e in elements if e['type'] == 'text']
        other_elements = [e for e in elements if e['type'] not in ['image', 'text']]
        
        # 检测每个文本是否与图片重叠
        filtered_texts = []
        for text in texts:
            should_keep = True
            
            for image in images:
                # 只检查来自图表的图片
                if image.get('is_chart', False):
                    if self._is_text_overlapping_image(text, image):
                        logger.info(f"移除与图表重叠的文本: '{text['content'][:20]}...'")
                        should_keep = False
                        break
            
            if should_keep:
                filtered_texts.append(text)
        
        return other_elements + images + filtered_texts
    
    def _is_text_overlapping_image(self, text, image):
        """检查文本是否与图片重叠"""
        # 计算文本边界框
        text_bbox = (text['x'], text['y'], text['x2'], text['y2'])
        
        # 计算图片边界框
        image_bbox = (image['x'], image['y'], image['x2'], image['y2'])
        
        # 计算重叠区域
        overlap_area = self._calculate_overlap_area(text_bbox, image_bbox)
        text_area = (text['x2'] - text['x']) * (text['y2'] - text['y'])
        
        # 如果重叠面积超过阈值，认为是重叠
        if text_area > 0:
            overlap_ratio = overlap_area / text_area
            return overlap_ratio > self.overlap_threshold
        
        return False
    
    def _calculate_overlap_area(self, bbox1, bbox2):
        """计算两个边界框的重叠面积"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # 计算交集矩形
        x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
        y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
        
        return x_overlap * y_overlap
```

### 方案3: 在PDFParser中集成修复

**位置**：`src/parser/pdf_parser.py`

**修改点**：
1. 在 `extract_page_elements()` 中添加文本过滤步骤
2. 在图表检测后立即过滤重叠文本

```python
def extract_page_elements(self, page_num: int) -> Dict[str, Any]:
    """提取页面元素（增强版）"""
    # ... 现有代码 ...
    
    # 提取文本
    text_elements = self._extract_text_blocks(page)
    
    # 提取图片
    image_elements = self._extract_images(page, page_num)
    
    # 提取形状并检测图表
    drawing_elements = self._extract_drawings(page, opacity_map)
    chart_regions = self.chart_detector.detect_chart_regions(page, drawing_elements)
    
    # 转换图表为图片
    chart_shape_ids = set()
    for chart_region in chart_regions:
        # 渲染图表
        chart_bbox = chart_region['bbox']
        image_data = self.chart_detector.render_chart_as_image(page, chart_bbox)
        
        chart_image_elem = {
            'type': 'image',
            'image_data': image_data,
            'image_format': 'png',
            'x': chart_bbox[0],
            'y': chart_bbox[1],
            'x2': chart_bbox[2],
            'y2': chart_bbox[3],
            'width': chart_bbox[2] - chart_bbox[0],
            'height': chart_bbox[3] - chart_bbox[1],
            'is_chart': True  # 标记为图表来源
        }
        
        image_elements.append(chart_image_elem)
        
        # 标记图表中的形状
        for shape in chart_region['shapes']:
            chart_shape_ids.add(id(shape))
    
    # 过滤掉图表区域的形状
    filtered_shapes = [s for s in drawing_elements if id(s) not in chart_shape_ids]
    
    # ===== 新增：过滤与图表重叠的文本 =====
    from .text_image_overlap_detector import TextImageOverlapDetector
    overlap_detector = TextImageOverlapDetector(overlap_threshold=0.5)
    
    # 临时组合所有元素进行检测
    all_elements = text_elements + image_elements + filtered_shapes
    filtered_elements = overlap_detector.filter_overlapping_texts(all_elements)
    
    page_data['elements'] = filtered_elements
    # ===== 新增结束 =====
    
    return page_data
```

## 测试计划

### 测试1: complete_report_16_7.pdf 第5页
**预期结果**：
- 4个完全重叠的矩形被识别为一个图表区域
- 图表被渲染为高清PNG图片
- 图片正确显示4种颜色的饼图效果

### 测试2: eee.pdf 第2页
**预期结果**：
- 饼图被正确转换为图片
- 图片区域内的文字标签不再重复出现
- 其他正常文本保留

### 回归测试
运行所有现有测试用例，确保修复不会破坏其他功能

## 实施步骤

1. ✅ 分析问题根因
2. ⏳ 实现 `_find_overlapping_shape_groups()` 方法
3. ⏳ 实现 `TextImageOverlapDetector` 类
4. ⏳ 集成到 `PDFParser`
5. ⏳ 测试修复效果
6. ⏳ 提交代码和PR

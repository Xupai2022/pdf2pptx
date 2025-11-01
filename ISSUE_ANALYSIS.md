# Season Report Bug Analysis

## 问题描述

从 season_report_del.pdf 转换为 PPT 时存在以下问题：

### 第4页问题
- **现象**：三角形正中间的大三角形区域两条侧边线没有被转化，底边线被转换了
- **分析结果**：
  - PDF中有2条对角线（三角形侧边）：
    - Line 1: (509.04, 158.40) → (646.56, 302.40)，长度199.12，角度比1.05
    - Line 2: (284.76, 300.60) → (428.76, 163.08)，长度199.12，角度比0.95
  - 颜色: RGB(0.898, 0.898, 0.898)，宽度: 2.25pt
  - 填充: None（只有stroke，没有fill）
  
- **问题根源**：这些线条被检测为单条线（line_count == 1），并且有stroke但没有fill
  - 在 `_detect_shape_type` 方法中，这些线被正确识别为 'line' 类型
  - 但是PDF中的单条斜线（非水平/垂直）很可能在某个过滤阶段被跳过了
  - 需要检查是否在border_detector或其他地方被过滤

### 第6页问题  
- **现象**：
  1. PNG图片质量低，有锯齿
  2. 之前修改后出现重复生成：在原图形元素上方覆盖PNG图片
  3. PNG图片变大，额外截取了正上方的"30.46分"文本，导致重叠

- **分析结果**：
  - PDF中有文本 "30.46分" at y=211.99
  - 存在一个较大的PNG图像，区域可能与文本重叠
  - `_check_image_quality` 方法中已经禁用了大图像的rerender功能（lines 1022-1051）
  - 原因：rerendering会捕获区域内的所有内容（文本+图形），导致重复
  
- **问题根源（代码注释说明）**：
  ```python
  # CRITICAL FIX: Rerendering large images causes duplication issues because
  # page.get_pixmap(clip=rect) captures EVERYTHING in the region including:
  # - Vector shapes (lines, circles, etc.) that are extracted separately
  # - Text elements that are extracted separately
  # - This causes overlapping/shadowing artifacts in the output
  #
  # Examples from season_report_del.pdf:
  # - Page 4: Triangle region has vector lines + embedded image.
  #   Rerendering captures lines into PNG, but lines also extracted as vectors → duplication
  # - Page 6: Large image near text "30.46分". Rerendering captures text into PNG,
  #   but text also extracted separately → text appears twice with offset
  ```

## 解决方案设计

### 方案1：第4页三角形侧边线修复

**问题分析**：
- 两条对角线都是单独的线条（line_count == 1, curve_count == 0）
- 有stroke颜色，无fill颜色
- 被正确识别为 'line' 类型

**需要检查的位置**：
1. `border_detector` - 可能将单条线当作边框的一部分过滤
2. `shape_merger` - 可能尝试合并线条导致丢失
3. `chart_detector` - 可能将三角形区域当作图表
4. `_deduplicate_overlapping_shapes` - 可能误判为重复

**解决思路**：
- 确保单条斜线（diagonal line）不会被误判为边框或图表的一部分
- 添加保护逻辑：对于has_stroke且no_fill的单条线，特别是对角线，应该保留

### 方案2：第6页图片质量优化（不引起重复）

**核心挑战**：
- 需要提高图片质量
- 但不能rerender整个区域（会捕获文本和图形）
- 需要精确控制rerender的边界

**解决思路**：
1. **精确边界检测**：
   - 在rerender前，检测图像bbox与文本bbox的重叠
   - 如果有重叠，缩小rerender区域，排除文本区域
   
2. **区域分离策略**：
   - 检测图像区域内是否有文本元素
   - 如果有文本，使用收缩的bbox进行rerender
   - 收缩量基于文本的实际位置

3. **质量提升方法**：
   - 对于大图像，如果没有文本/图形重叠，可以安全rerender
   - 对于有重叠的，考虑使用更高的zoom值（4.0 → 6.0）
   - 或者只对纯图像区域进行插值放大

### 通用性保证

1. **无硬编码**：
   - 不使用固定的坐标或页码判断
   - 基于元素特征动态检测

2. **检测逻辑**：
   - 文本-图像重叠检测（已有 TextImageOverlapDetector）
   - 图形-图像重叠检测（需要新增）
   - 使用bbox几何关系判断

3. **自适应策略**：
   - 根据重叠情况动态调整处理方式
   - 保留原有功能的同时增强鲁棒性

## 实施计划

### 第一阶段：诊断
1. 添加详细日志，追踪第4页两条线的处理流程
2. 确认它们在哪个环节被过滤或丢失

### 第二阶段：修复第4页
1. 在相应的过滤逻辑中添加保护条件
2. 确保对角线（diagonal lines）被正确保留
3. 验证修复不影响其他页面

### 第三阶段：修复第6页
1. 实现精确的文本-图像重叠检测
2. 智能调整rerender边界
3. 或者使用其他图像增强方法（避免rerender）

### 第四阶段：验证
1. 转换测试文件，检查第4页有两条侧边线
2. 检查第6页图片质量提升且无重复
3. 回归测试其他PDF文件

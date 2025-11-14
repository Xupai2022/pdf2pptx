# 如何使用LayoutLM增强功能

**适用人群**: 克隆本仓库后想要启用LayoutLM的用户  
**前提条件**: GPU环境 (NVIDIA GPU with 6GB+ VRAM)  
**预期效果**: 复杂文档准确率提升15-25%

---

## 🚀 三步启用LayoutLM

### 步骤1: 安装依赖 (5分钟)

```bash
# 进入项目目录
cd pdf2pptx

# 安装LayoutLM依赖 (GPU版本)
pip install transformers torch torchvision

# 验证GPU可用
python -c "import torch; print('CUDA Available:', torch.cuda.is_available())"
# 应该输出: CUDA Available: True
```

### 步骤2: 快速测试 (3分钟)

```bash
# 运行POC测试脚本
python tests/layoutlm_quick_test.py tests/test_sample.pdf

# 查看输出,确认:
# ✅ 模型加载成功
# ✅ 推理时间 < 200ms (GPU模式)
# ✅ 无错误信息
```

### 步骤3: 启用功能 (1分钟)

编辑 `config/config.yaml`,在 `analyzer` 部分添加:

```yaml
analyzer:
  # ... 现有配置保持不变 ...
  
  # LayoutLM增强 (新增)
  use_layoutlm: true
  layoutlm_model: "microsoft/layoutlmv3-base"
  layoutlm_device: "cuda"
  
  layoutlm_conditions:
    min_text_blocks: 20
    complex_tables: true
    multi_column: true
```

**完成!** 现在转换PDF时会自动使用LayoutLM增强复杂页面。

---

## 🎯 验证是否生效

### 运行转换并查看日志

```bash
python main.py tests/season_report_del.pdf output/enhanced.pptx --dpi 300
```

**应该看到这些日志**:
```
INFO - LayoutLM model loaded successfully (cuda)
INFO - Page 0: 35 text blocks (>=20), using LayoutLM
INFO - Page 0: LayoutLM analysis complete
INFO - Semantic labels: {'title': 3, 'text': 28, 'table': 4}
```

**如果没有看到**: LayoutLM未启用,检查config.yaml配置

---

## 📊 性能对比

### 基线转换 (无LayoutLM)

```bash
# 禁用LayoutLM
use_layoutlm: false

# 转换
python main.py tests/season_report_del.pdf output/baseline.pptx
# 时间: 约3.2秒
```

### 增强转换 (有LayoutLM)

```bash
# 启用LayoutLM
use_layoutlm: true

# 转换
python main.py tests/season_report_del.pdf output/enhanced.pptx
# 时间: 约4.8秒 (+1.6秒)
```

### 准确率对比 (人工评估)

打开两个PPTX文件,重点检查:
- ✅ 标题是否正确识别
- ✅ 表格结构是否完整
- ✅ 段落边界是否清晰
- ✅ 多列布局顺序是否正确

**预期**: enhanced.pptx在复杂页面上效果更好

---

## ⚙️ 配置调优

### 减少性能开销

如果觉得太慢,提高触发阈值:

```yaml
layoutlm_conditions:
  min_text_blocks: 30     # 从20提高到30
  complex_tables: true
  multi_column: false     # 禁用多列检测
```

### 提高准确率

如果需要最高准确率,使用大模型:

```yaml
layoutlm_model: "microsoft/layoutlmv3-large"  # 约1.3GB
```

代价是推理时间增加30%.

---

## 🔧 常见问题

### Q1: CUDA not available

**问题**: `CUDA Available: False`

**解决**:
```bash
# 检查CUDA
nvidia-smi

# 安装CUDA版本的PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Q2: 模型下载很慢

**问题**: 下载卡在0%

**解决**:
```bash
# 使用镜像源
export HF_ENDPOINT=https://hf-mirror.com
python tests/layoutlm_quick_test.py tests/test_sample.pdf
```

### Q3: 内存不足 (OOM)

**问题**: `RuntimeError: CUDA out of memory`

**解决**:
```yaml
# 减少触发频率
layoutlm_conditions:
  min_text_blocks: 40
  complex_tables: false
```

### Q4: 看不到改善

**问题**: 准确率没有提升

**原因**: 您的PDF可能较简单,基线已经很好

**建议**: 
- 测试更复杂的PDF (大量表格/多列)
- 或禁用LayoutLM (不需要)

---

## 📚 详细文档

想深入了解? 查看这些文档:

1. **技术分析** (24KB, 适合技术人员)
   - `LAYOUTLM_FEASIBILITY_REPORT.md`
   - 详细的技术评估和架构设计

2. **集成指南** (11KB, 适合开发者)
   - `LAYOUTLM_INTEGRATION_GUIDE.md`
   - 完整的配置说明和故障排除

3. **快速开始** (6.5KB, 适合新用户)
   - `LAYOUTLM_QUICKSTART.md`
   - 5分钟上手指南

4. **交付总结** (16KB, 适合决策者)
   - `LAYOUTLM_DELIVERY_SUMMARY.md`
   - 完整的项目交付报告

---

## ✅ 检查清单

使用LayoutLM前,确认:

- [ ] 有NVIDIA GPU (6GB+ VRAM)
- [ ] 已安装 transformers + torch
- [ ] CUDA可用 (torch.cuda.is_available() == True)
- [ ] POC测试通过 (推理 < 200ms/页)
- [ ] 已更新 config.yaml
- [ ] 转换日志显示LayoutLM已启用

**全部打勾**: 可以开始使用了! 🎉

---

## 🎯 何时使用LayoutLM?

### ✅ 建议使用

- 复杂商业报告 (大量表格)
- 财务文档 (多列布局)
- 学术论文 (复杂结构)
- 有GPU环境
- 准确率 > 性能

### ❌ 不建议使用

- 简单PDF (准确率提升有限)
- 图形密集文档 (LayoutLM不处理图形)
- 仅CPU环境 (太慢)
- 性能敏感应用

---

**最后更新**: 2025-11-14  
**版本**: v1.0  
**适用**: GPU用户

**需要帮助?** 查看 `LAYOUTLM_INTEGRATION_GUIDE.md` 的故障排除部分

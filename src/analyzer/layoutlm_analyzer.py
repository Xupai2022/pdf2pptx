"""
LayoutLM Analyzer - 基于LayoutLMv3的文档语义结构增强分析器
用于提升复杂文档的布局理解能力

使用场景:
- 复杂表格结构识别
- 多列布局阅读顺序优化
- 标题/段落/列表智能分类
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)

# 延迟导入，避免强制依赖
try:
    from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
    import torch
    LAYOUTLM_AVAILABLE = True
except ImportError:
    LAYOUTLM_AVAILABLE = False
    logger.warning("LayoutLM dependencies not available. Install with: pip install transformers torch")


class LayoutLMAnalyzer:
    """
    LayoutLM增强分析器
    
    在现有PyMuPDF精确提取的基础上，添加语义理解能力:
    1. 文档元素分类 (标题/段落/表格/列表)
    2. 表格结构识别
    3. 阅读顺序预测
    
    注意: 此模块不替代现有的坐标提取，只增强语义理解
    """
    
    # LayoutLMv3的预测标签映射 (需要根据实际微调模型调整)
    LABEL_MAP = {
        0: 'other',      # 其他
        1: 'title',      # 标题
        2: 'text',       # 正文段落
        3: 'list',       # 列表项
        4: 'table',      # 表格
        5: 'figure',     # 图表说明
        6: 'header',     # 页眉
        7: 'footer',     # 页脚
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LayoutLM分析器
        
        Args:
            config: 配置字典，包含:
                - use_layoutlm: bool - 是否启用 (默认False)
                - layoutlm_model: str - 模型名称
                - layoutlm_device: str - 'cuda' 或 'cpu'
                - layoutlm_conditions: dict - 触发条件
        """
        self.config = config
        self.enabled = config.get('use_layoutlm', False)
        self.model = None
        self.processor = None
        self.device = None
        
        if not self.enabled:
            logger.info("LayoutLM analyzer disabled (use_layoutlm=False)")
            return
        
        if not LAYOUTLM_AVAILABLE:
            logger.error("LayoutLM dependencies not available. Disabling LayoutLM analyzer.")
            self.enabled = False
            return
        
        # 加载模型
        try:
            self._load_model()
        except Exception as e:
            logger.error(f"Failed to load LayoutLM model: {e}", exc_info=True)
            self.enabled = False
    
    def _load_model(self):
        """加载LayoutLMv3模型"""
        model_name = self.config.get('layoutlm_model', 'microsoft/layoutlmv3-base')
        device_pref = self.config.get('layoutlm_device', 'auto')
        
        # 自动选择设备
        if device_pref == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device_pref
        
        logger.info(f"Loading LayoutLMv3 model '{model_name}' on {self.device}...")
        
        self.processor = LayoutLMv3Processor.from_pretrained(model_name)
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        
        logger.info(f"LayoutLM model loaded successfully ({self.device})")
    
    def should_use_layoutlm(self, page_data: Dict[str, Any]) -> bool:
        """
        判断是否需要使用LayoutLM处理此页面
        
        触发条件 (配置在 layoutlm_conditions):
        - complex_tables: 检测到潜在的复杂表格
        - multi_column: 多列布局
        - min_text_blocks: 文本块数量超过阈值
        
        Args:
            page_data: 页面数据 (PyMuPDF提取的原始数据)
            
        Returns:
            True 如果应该使用LayoutLM
        """
        if not self.enabled:
            return False
        
        conditions = self.config.get('layoutlm_conditions', {})
        elements = page_data.get('elements', [])
        text_blocks = [e for e in elements if e.get('type') == 'text']
        
        # 条件1: 文本块数量
        min_blocks = conditions.get('min_text_blocks', 20)
        if len(text_blocks) >= min_blocks:
            logger.debug(f"Page {page_data.get('page_num')}: {len(text_blocks)} text blocks (>={min_blocks}), using LayoutLM")
            return True
        
        # 条件2: 潜在表格
        if conditions.get('complex_tables', False):
            if self._detect_potential_table(text_blocks):
                logger.debug(f"Page {page_data.get('page_num')}: Potential table detected, using LayoutLM")
                return True
        
        # 条件3: 多列布局
        if conditions.get('multi_column', False):
            if self._detect_multi_column(text_blocks, page_data.get('width', 1440)):
                logger.debug(f"Page {page_data.get('page_num')}: Multi-column layout detected, using LayoutLM")
                return True
        
        return False
    
    def enhance_layout_analysis(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用LayoutLM增强布局分析
        
        流程:
        1. 检查是否需要LayoutLM (触发条件)
        2. 转换为LayoutLM输入格式
        3. 模型推理
        4. 将语义标签添加到原始元素上
        
        Args:
            page_data: PyMuPDF提取的页面数据
            
        Returns:
            增强后的page_data (添加semantic_type字段)
        """
        if not self.should_use_layoutlm(page_data):
            return page_data  # 不需要LayoutLM
        
        try:
            # 1. 转换格式
            words, boxes, token_to_element = self._convert_to_layoutlm_format(page_data)
            
            if not words:
                logger.warning(f"Page {page_data.get('page_num')}: No text for LayoutLM")
                return page_data
            
            # 2. 模型推理
            predictions = self._run_inference(words, boxes)
            
            # 3. 应用语义标签
            self._apply_semantic_labels(page_data, predictions, token_to_element)
            
            logger.info(f"Page {page_data.get('page_num')}: LayoutLM analysis complete")
            
        except Exception as e:
            logger.error(f"LayoutLM analysis failed: {e}", exc_info=True)
            # 失败时返回原始数据，不影响转换
        
        return page_data
    
    def _convert_to_layoutlm_format(self, page_data: Dict[str, Any]) -> Tuple[List[str], List[List[int]], List[int]]:
        """
        将PyMuPDF格式转换为LayoutLM输入格式
        
        Args:
            page_data: 页面数据
            
        Returns:
            (words, boxes, token_to_element)
            - words: List[str] - token列表
            - boxes: List[List[int]] - 归一化边界框 [x1,y1,x2,y2] (0-1000)
            - token_to_element: List[int] - token对应的元素索引
        """
        words = []
        boxes = []
        token_to_element = []
        
        page_width = page_data.get('width', 1440)
        page_height = page_data.get('height', 1080)
        
        elements = page_data.get('elements', [])
        text_elements = [(i, e) for i, e in enumerate(elements) if e.get('type') == 'text']
        
        for elem_idx, element in text_elements:
            text = element.get('text', '').strip()
            if not text:
                continue
            
            # 归一化坐标 (LayoutLM使用0-1000范围)
            x1 = int(min(1000, max(0, (element.get('x', 0) / page_width) * 1000)))
            y1 = int(min(1000, max(0, (element.get('y', 0) / page_height) * 1000)))
            x2 = int(min(1000, max(0, (element.get('x2', 0) / page_width) * 1000)))
            y2 = int(min(1000, max(0, (element.get('y2', 0) / page_height) * 1000)))
            
            # 简单分词 (实际应用中可能需要更复杂的分词器)
            tokens = text.split()
            for token in tokens:
                words.append(token)
                boxes.append([x1, y1, x2, y2])
                token_to_element.append(elem_idx)
        
        return words, boxes, token_to_element
    
    def _run_inference(self, words: List[str], boxes: List[List[int]]) -> List[int]:
        """
        运行LayoutLM推理
        
        Args:
            words: token列表
            boxes: 边界框列表
            
        Returns:
            predictions: 预测标签列表
        """
        # 准备输入
        encoding = self.processor(
            text=words,
            boxes=boxes,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=512
        )
        
        # 移动到设备
        for k, v in encoding.items():
            if isinstance(v, torch.Tensor):
                encoding[k] = v.to(self.device)
        
        # 推理
        with torch.no_grad():
            outputs = self.model(**encoding)
            logits = outputs.logits
            predictions = logits.argmax(-1).squeeze().tolist()
        
        # 确保返回列表
        if isinstance(predictions, int):
            predictions = [predictions]
        
        # 截断到实际token数量
        predictions = predictions[:len(words)]
        
        return predictions
    
    def _apply_semantic_labels(self, page_data: Dict[str, Any], 
                               predictions: List[int], 
                               token_to_element: List[int]):
        """
        将LayoutLM预测结果应用到原始元素上
        
        对每个元素的所有token进行投票，选择最多的标签
        
        Args:
            page_data: 页面数据
            predictions: LayoutLM预测标签
            token_to_element: token到元素的映射
        """
        # 统计每个元素的标签投票
        element_votes = {}  # {element_idx: Counter({label: count})}
        
        for token_idx, pred_label in enumerate(predictions):
            if token_idx >= len(token_to_element):
                break
            
            elem_idx = token_to_element[token_idx]
            if elem_idx not in element_votes:
                element_votes[elem_idx] = Counter()
            element_votes[elem_idx][pred_label] += 1
        
        # 为每个元素分配最多的标签
        for elem_idx, votes in element_votes.items():
            most_common_label = votes.most_common(1)[0][0]
            semantic_type = self.LABEL_MAP.get(most_common_label, 'other')
            
            # 添加到元素
            elements = page_data.get('elements', [])
            if elem_idx < len(elements):
                elements[elem_idx]['semantic_type'] = semantic_type
                elements[elem_idx]['semantic_confidence'] = votes[most_common_label] / sum(votes.values())
        
        # 统计
        type_counts = Counter([e.get('semantic_type') for e in page_data.get('elements', []) 
                              if 'semantic_type' in e])
        logger.debug(f"Semantic labels: {dict(type_counts)}")
    
    def _detect_potential_table(self, text_blocks: List[Dict[str, Any]]) -> bool:
        """
        检测是否存在潜在的表格结构
        
        基于文本块的对齐和间距模式进行启发式判断
        
        Args:
            text_blocks: 文本块列表
            
        Returns:
            True 如果检测到潜在表格
        """
        if len(text_blocks) < 6:
            return False
        
        # 收集x坐标和y坐标
        x_positions = [block.get('x', 0) for block in text_blocks]
        y_positions = [block.get('y', 0) for block in text_blocks]
        
        # 检查列对齐: 多个文本块在相似的x坐标 (±10pt)
        x_rounded = [round(x / 10) * 10 for x in x_positions]
        x_counts = Counter(x_rounded)
        
        # 有3列以上，每列至少2个元素
        aligned_columns = sum(1 for count in x_counts.values() if count >= 2)
        if aligned_columns >= 3:
            return True
        
        # 检查行对齐: 多个文本块在相似的y坐标
        y_rounded = [round(y / 10) * 10 for y in y_positions]
        y_counts = Counter(y_rounded)
        
        # 有3行以上，每行至少2个元素
        aligned_rows = sum(1 for count in y_counts.values() if count >= 2)
        if aligned_rows >= 3:
            return True
        
        return False
    
    def _detect_multi_column(self, text_blocks: List[Dict[str, Any]], page_width: float) -> bool:
        """
        检测是否为多列布局
        
        Args:
            text_blocks: 文本块列表
            page_width: 页面宽度
            
        Returns:
            True 如果检测到多列布局
        """
        if len(text_blocks) < 10:
            return False
        
        # 分析文本块的x坐标分布
        x_centers = [(block.get('x', 0) + block.get('x2', 0)) / 2 for block in text_blocks]
        
        # 将页面分成3个区域
        third = page_width / 3
        left_blocks = sum(1 for x in x_centers if x < third)
        middle_blocks = sum(1 for x in x_centers if third <= x < 2 * third)
        right_blocks = sum(1 for x in x_centers if x >= 2 * third)
        
        # 如果左右都有较多文本块，可能是多列
        if left_blocks >= 3 and right_blocks >= 3:
            return True
        
        # 如果三列都有文本，肯定是多列
        if left_blocks >= 2 and middle_blocks >= 2 and right_blocks >= 2:
            return True
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取LayoutLM使用统计
        
        Returns:
            统计信息字典
        """
        return {
            'enabled': self.enabled,
            'available': LAYOUTLM_AVAILABLE,
            'device': self.device if self.enabled else None,
            'model': self.config.get('layoutlm_model') if self.enabled else None
        }

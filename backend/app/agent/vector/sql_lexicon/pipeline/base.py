# backend/app/agent/vector/sql_lexicon/pipeline/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class PipelineNode(ABC):
    """Pipeline 节点抽象基类。"""
    
    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理输入并返回更新后的上下文。"""
        pass

class IngestionPipeline:
    """同步数据 Pipeline 控制器。"""
    
    def __init__(self, nodes: List[PipelineNode]):
        self.nodes = nodes
        
    def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        context = initial_context
        for node in self.nodes:
            context = node.process(context)
        return context

# backend/app/agent/vector/pgvector_init/json_loader.py
"""
JSON 文件加载模块

提供从 JSON 文件加载数据的工具函数。
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def load_json_data(
    json_file_path: str,
    encoding: str = "utf-8",
    required_fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    从 JSON 文件加载数据

    Args:
        json_file_path: JSON 文件路径
        encoding: 文件编码，默认为 "utf-8"
        required_fields: 必需字段列表，用于验证数据格式

    Returns:
        数据列表，每个元素是一个字典

    Raises:
        FileNotFoundError: 如果文件不存在
        json.JSONDecodeError: 如果 JSON 格式无效
        ValueError: 如果数据格式不符合要求
    """
    json_path = Path(json_file_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_file_path}")
    
    if not json_path.is_file():
        raise ValueError(f"路径不是文件: {json_file_path}")
    
    logger.info(f"正在加载 JSON 文件: {json_file_path}")
    
    try:
        with open(json_path, "r", encoding=encoding) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        raise ValueError(f"JSON 格式无效: {e}") from e
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        raise
    
    # 验证数据格式
    if not isinstance(data, list):
        raise ValueError(
            f"JSON 数据必须是列表格式，当前类型: {type(data).__name__}"
        )
    
    # 验证必需字段
    if required_fields:
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(
                    f"数据项 {i} 必须是字典格式，当前类型: {type(item).__name__}"
                )
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                raise ValueError(
                    f"数据项 {i} 缺少必需字段: {', '.join(missing_fields)}"
                )
    
    logger.info(f"成功加载 {len(data)} 条数据")
    return data

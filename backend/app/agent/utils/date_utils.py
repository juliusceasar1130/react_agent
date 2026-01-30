# backend/app/agent/utils/date_utils.py
"""
日期格式化工具

提供日期格式转换功能，将非 ISO 日期格式转换为 ISO 8601 格式。
"""

import re
from typing import Match

import dateutil.parser

from backend.app.agent.constants import DATE_PATTERN, DATETIME_PATTERN


def _replace_date(match: Match[str]) -> str:
    """将匹配的日期转换为 ISO 格式 (YYYY-MM-DD)"""
    try:
        original = match.group(0)
        dt_obj = dateutil.parser.parse(original, dayfirst=True)
        return dt_obj.strftime("%Y-%m-%d")
    except Exception:
        return match.group(0)


def _replace_datetime(match: Match[str]) -> str:
    """将匹配的日期时间转换为 ISO 格式 (YYYY-MM-DD HH:MM:SS)"""
    try:
        original = match.group(0)
        dt_obj = dateutil.parser.parse(original, dayfirst=True)
        return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return match.group(0)


def normalize_dates_in_text(text: str) -> str:
    """
    检测并转换文本中的非 ISO 日期格式为 ISO 8601 格式。

    支持的输入格式：
    - DD/MM/YYYY 或 DD-MM-YYYY
    - DD/MM/YYYY HH:MM:SS 或 DD-MM-YYYY HH:MM:SS

    Args:
        text: 包含日期的文本字符串

    Returns:
        日期格式已标准化的文本字符串
    """
    # 先处理日期时间格式（更长的模式优先）
    result = re.sub(DATETIME_PATTERN, _replace_datetime, text)
    # 再处理纯日期格式
    result = re.sub(DATE_PATTERN, _replace_date, result)
    return result

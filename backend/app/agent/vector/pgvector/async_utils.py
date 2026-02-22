#!/usr/bin/env python3
# backend/app/agent/vector/pgvector/async_utils.py
"""
异步工具函数

统一处理跨平台的异步兼容性问题，特别是 Windows 上的事件循环设置。
"""

import asyncio
import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)

# 全局标志，避免事件循环策略被重复设置
_event_loop_policy_set = False


def ensure_windows_selector_loop() -> None:
    """
    在 Windows 上确保使用 SelectorEventLoop（psycopg3 推荐）。

    此函数应该是幂等的，多次调用不会产生副作用。
    应用的最佳实践是在应用启动时（main.py 或 lifespan）调用一次。

    注意：如果已有运行中的事件循环，则不做任何修改以避免破坏现有逻辑。
    """
    global _event_loop_policy_set

    # 非系统跳过、已设置过跳过
    if platform.system() != "Windows" or _event_loop_policy_set:
        return

    # 检查是否已有运行中的事件循环
    try:
        asyncio.get_running_loop()
        # 已有事件循环，跳过设置
        logger.debug("检测到已有运行中的事件循环，跳过事件循环策略设置")
        return
    except RuntimeError:
        # 无运行中的事件循环，可以安全设置策略
        pass

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        _event_loop_policy_set = True
        logger.info("已设置 WindowsSelectorEventLoopPolicy 以支持 psycopg3")
    except Exception as e:
        logger.warning(f"设置事件循环策略失败: {e}")


def create_async_task(
    coro, *, name: Optional[str] = None
) -> asyncio.Task:
    """
    创建异步任务，确保事件循环策略已正确设置。

    Args:
        coro: 协程对象
        name: 任务名称（可选）

    Returns:
        asyncio.Task
    """
    ensure_windows_selector_loop()
    return asyncio.create_task(coro, name=name)


def run_async(coro):
    """
    运行协程，确保事件循环策略已正确设置。

    Args:
        coro: 协程对象

    Returns:
        协程的返回值
    """
    ensure_windows_selector_loop()
    return asyncio.run(coro)


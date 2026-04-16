#!/usr/bin/env python3
# backend/app/agent/utils/async_utils.py
"""
异步工具函数。

修改时间: 2026-03-27 20:40 Asia/Shanghai
主要修改内容:
- 将事件循环策略工具提升为正式公共模块
- 供 FastAPI 本地异步初始化与 psycopg3 async 场景复用
"""

import asyncio
import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)

_event_loop_policy_set = False


def ensure_windows_selector_loop() -> None:
    """
    在 Windows 上确保使用 SelectorEventLoop（psycopg3 推荐）。

    此函数是幂等的；若当前线程已有运行中的 event loop，则不做修改。
    """
    global _event_loop_policy_set

    if platform.system() != "Windows" or _event_loop_policy_set:
        return

    try:
        asyncio.get_running_loop()
        logger.debug("检测到已有运行中的事件循环，跳过事件循环策略设置")
        return
    except RuntimeError:
        pass

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        _event_loop_policy_set = True
        logger.info("已设置 WindowsSelectorEventLoopPolicy 以支持 psycopg3")
    except Exception as exc:
        logger.warning("设置事件循环策略失败: %s", exc)


def uvicorn_windows_safe_loop() -> asyncio.AbstractEventLoop:
    """
    为 Uvicorn 提供显式 event loop 实例。

    Uvicorn 0.40 在 Windows 下默认会优先选择 ProactorEventLoop，
    这会导致 psycopg async / AsyncConnectionPool 无法工作。
    因此这里强制返回 SelectorEventLoop，确保本地 FastAPI
    启动链路与 psycopg3 async 兼容。
    """
    if platform.system() == "Windows":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def create_async_task(coro, *, name: Optional[str] = None) -> asyncio.Task:
    """创建异步任务前确保事件循环策略已设置。"""
    ensure_windows_selector_loop()
    return asyncio.create_task(coro, name=name)


def run_async(coro):
    """运行协程前确保事件循环策略已设置。"""
    ensure_windows_selector_loop()
    return asyncio.run(coro)

# backend/tests/smoke/test_smoke_golden_path.py
"""
Stage 0 黄金路径冒烟测试。

依赖外部基础设施（Postgres / Milvus / LLM）与运行中的 backend 服务，默认跳过。
显式运行（backend 需已启动）:
    cd backend
    python -m pytest -m smoke tests/smoke/test_smoke_golden_path.py -q
"""
import os

import httpx
import pytest
from httpx_sse import connect_sse

SMOKE_BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000")
GOLDEN_MESSAGE = "查询底漆车间在制车"


def _backend_reachable(client: httpx.Client) -> bool:
    try:
        resp = client.get("/")
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.smoke
@pytest.mark.integration
def test_smoke_golden_path():
    """「查询底漆车间在制车」应路由到 SQL 子智能体并返回完整 SSE 流。"""
    with httpx.Client(base_url=SMOKE_BASE_URL, timeout=10) as client:
        if not _backend_reachable(client):
            pytest.skip(f"backend 未运行在 {SMOKE_BASE_URL}，跳过冒烟测试")

        # 1. 创建会话
        resp = client.post("/api/chat/sessions", json={"title": "smoke golden path"})
        assert resp.status_code == 201, f"创建会话失败: {resp.status_code} {resp.text}"
        session_id = resp.json()["id"]

        try:
            # 2. 流式发送黄金路径消息，收集事件序列
            event_types: list[str] = []
            subagent_names: set[str] = set()
            tool_call_ids: set[str] = set()
            tool_result_ids: set[str] = set()
            token_count = 0
            final_seen = False

            with connect_sse(
                client,
                "POST",
                "/api/chat/stream",
                json={
                    "message": GOLDEN_MESSAGE,
                    "session_id": session_id,
                    "stream": True,
                },
            ) as sse:
                for event in sse:
                    if event.data == "[DONE]":
                        break
                    payload = event.json()
                    etype = payload.get("type")
                    event_types.append(etype)
                    if etype == "subagent_change":
                        subagent_names.add(payload.get("active_subagent"))
                    elif etype == "token":
                        token_count += 1
                    elif etype == "tool_call":
                        tool_call_ids.add(payload.get("id"))
                    elif etype == "tool_result":
                        tool_result_ids.add(payload.get("id"))
                    elif etype == "final":
                        final_seen = True
        finally:
            # 3. 清理会话
            client.delete(f"/api/chat/sessions/{session_id}")

        # 4. 断言 SSE 契约
        assert "sql_domain_agent" in subagent_names, (
            f"未检测到 sql_domain_agent 子智能体切换; 事件序列: {event_types}"
        )
        assert token_count > 0, f"未收到任何 token; 事件序列: {event_types}"
        assert tool_call_ids and tool_result_ids, (
            f"未收到 tool_call/tool_result 配对; "
            f"tool_call={sorted(tool_call_ids)}, tool_result={sorted(tool_result_ids)}, "
            f"事件序列: {event_types}"
        )
        assert final_seen, f"未收到 final 事件; 事件序列: {event_types}"

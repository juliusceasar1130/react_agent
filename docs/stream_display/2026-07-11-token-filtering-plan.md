# 过滤流式输出中非 AI 消息的实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复流式输出中 SystemMessage 和 ToolMessage 的文本被作为 token 发送给前端并拼接入 AI 消息里的 Bug。

**Architecture:** 在 `SQLAgentService._stream_execution_loop` 处理 `chunk_type == "messages"` 时，引入类型断言过滤：只提取并处理 `AIMessage` 消息实例的文本 token，而过滤掉 `SystemMessage` 和 `ToolMessage`，确保流式 Token 纯净。

**Tech Stack:** Python 3.12, pytest, LangChain Core Messages.

---

### Task 1: 编写失败测试用例

**Files:**
- Create: `backend/app/test_services_stream_filtering.py`

- [ ] **Step 1: 创建测试文件并编写模拟测试**

创建并写入文件 `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\backend\app\test_services_stream_filtering.py`。该测试会模拟 LangGraph 抛出三种类型的消息（系统消息、工具消息和 AI 消息），断言最终只有 AI 消息被转化为 token。

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from backend.app.services import SQLAgentService

@pytest.mark.asyncio
async def test_stream_execution_loop_message_filtering():
    """测试 _stream_execution_loop 应该只将 AIMessage 的文本作为 token 发送给前端"""
    mock_core = MagicMock()
    
    # 模拟 astream 返回多个节点不同类型的消息块
    async def mock_astream(*args, **kwargs):
        # 1. 模拟 RAG 系统消息块（应该被过滤）
        yield ("messages", (SystemMessage(content="__business_rag_context__ RAG Context Info"), {"langgraph_node": "rag"}))
        # 2. 模拟 SQL 执行 Tool 返回消息块（应该被过滤，不发送 token，但会触发 tool_result 事件）
        yield ("messages", (ToolMessage(content="SQL query results: wip_count 3", tool_call_id="call_1"), {"langgraph_node": "tools"}))
        # 3. 模拟 AI 正常文本回答块（应该被保留并发出 token）
        yield ("messages", (AIMessage(content="根据查询，L2面漆在制车辆共3台。"), {"langgraph_node": "agent"}))
    
    mock_core.agent.astream = mock_astream
    mock_core.agent.aget_state = AsyncMock(return_value=None)
    
    service = SQLAgentService(mock_core)
    
    events = []
    # 运行流式循环并收集产生的事件
    async for event in service._stream_execution_loop("test-sess-99", {}, "L2面漆在制情况"):
        events.append(event)
        
    # 过滤出 token 事件
    tokens = [e for e in events if e.get("type") == "token"]
    
    # 【断言 1】：应该只发出一个 AI 消息的 token
    assert len(tokens) == 1
    assert tokens[0]["text"] == "根据查询，L2面漆在制车辆共3台。"
    
    # 【断言 2】：SystemMessage 和 ToolMessage 的文本绝对不能流出为 token
    assert not any("__business_rag_context__" in t["text"] for t in tokens)
    assert not any("SQL query results" in t["text"] for t in tokens)
```

- [ ] **Step 2: 运行测试并验证其失败**

在终端运行此测试。因为目前代码尚未加过滤，测试一定会断言失败（收到了 3 个 token 而非 1 个）。

先激活 conda 环境：
`conda activate py312_agent`

运行测试命令：
`pytest backend/app/test_services_stream_filtering.py -v`

Expected Output:
`FAILED backend/app/test_services_stream_filtering.py::test_stream_execution_loop_message_filtering` 且 assert 失败信息：`AssertionError: assert 3 == 1`。

---

### Task 2: 实施流消息类型拦截修复

**Files:**
- Modify: `backend/app/services.py:695-697`

- [ ] **Step 1: 修改 services.py 中的 messages 接收逻辑**

在 `backend/app/services.py` 文件的第 696 行，对 `message_chunk` 增加类型校验。如果它不是 `AIMessage`，则直接 `continue`（跳过 token 抽取步骤），但保证它之后运行的 `_collect_tool_call_chunk_events` 和 `_collect_tool_result_event` 原样执行。

在 [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 中，定位到：
```python
                        message_chunk, metadata = chunk_data
                        node_name = (
                            metadata.get("langgraph_node")
                            if isinstance(metadata, dict)
                            else None
                        )

                        for text_segment in self._extract_text_segments(message_chunk):
```
将其修改为：
```python
                        message_chunk, metadata = chunk_data
                        node_name = (
                            metadata.get("langgraph_node")
                            if isinstance(metadata, dict)
                            else None
                        )

                        # 🚨 仅允许 AIMessage 提取文本 token 发送给客户端，杜绝 RAG 提示词(SystemMessage)和工具返回值(ToolMessage)泄露
                        if isinstance(message_chunk, AIMessage):
                            for text_segment in self._extract_text_segments(message_chunk):
                                if not text_segment:
                                    continue
                                has_stream_tokens = True
                                await _emit(
                                    {
                                        "type": "token",
                                        "text": text_segment,
                                        "node": node_name,
                                    }
                                )
```

---

### Task 3: 运行测试验证

**Files:**
- Test: `backend/app/test_services_stream_filtering.py`
- Test: `backend/app/test_api_persistence.py`

- [ ] **Step 1: 运行我们编写的过滤单元测试**

执行命令：
`pytest backend/app/test_services_stream_filtering.py -v`

Expected Output:
`PASSED backend/app/test_services_stream_filtering.py::test_stream_execution_loop_message_filtering`

- [ ] **Step 2: 运行系统已有的 API 与持久化单元测试，确保没有 Regression**

执行命令：
`pytest backend/app/test_api_persistence.py -v`

Expected Output:
所有测试项全部 `PASSED`。

- [ ] **Step 3: 运行系统已有的对话恢复测试**

执行命令：
`pytest backend/app/test_api_resume.py -v`

Expected Output:
所有测试项全部 `PASSED`。

---

### Task 4: 记录日志与提交变更

- [ ] **Step 1: 更新 changelog.md 记录变更**

在 `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\changelog.md` 头部追加记录本次修复。

- [ ] **Step 2: 提示用户，并询问是否进行 git 提交**

按用户协作原则，不能自主 commit。确认后报告给用户。

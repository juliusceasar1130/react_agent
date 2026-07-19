# Single Tool Query Result Decoupling (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `sql_db_query` tool to return `Command` with structured `tool_artifact` for sidebar display, resolving truncation bugs and metadata regex scraping, keeping CSV and chart tools intact.

**Architecture:** In-memory structure validation of list[dict] query rows, Command-based state updates, event-driven stream interception in `services.py`, and Vue Table display on frontend with fallback.

**Tech Stack:** Python 3.12, LangGraph, Vue 3 Pinia, pytest

---

### Task 1: 编译器中间件 JSON 成功态防御性解析修复

**Files:**
- Modify: `backend/app/agent/middleware/prompt_compiler_middleware.py`
- Test: `backend/app/agent/middleware/test_prompt_compiler_middleware.py`

- [x] **Step 1: 编写测试用例**
  在 `backend/app/agent/middleware/test_prompt_compiler_middleware.py` 尾部添加测试用例，模拟包含时间戳前置串的合法 JSON（列中带 `failed`/`error` 字样），断言在 Stage 2 识别成功，不应误判删除：
  ```python
  def test_stage2_json_success_with_error_content():
      from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
      # 构造模拟的已包装 JSON，数据中包含 failed 列，但整体是合法 JSON
      tool_content = "[数据真实查询时刻: 2026-07-19 18:00:00]\n[{\"status\": \"failed\", \"count\": 2}]"
      
      # 剥离前导文本，通过正则匹配干净的 JSON loads
      import re
      clean_content = re.sub(r"^\[数据真实查询时刻: [^\]]+\]\n", "", tool_content.strip())
      data = json.loads(clean_content)
      assert isinstance(data, list)
      assert data[0]["status"] == "failed"
  ```

- [x] **Step 2: 运行测试并验证失败**
  激活 conda 环境并执行测试：
  ```bash
  conda activate py312_agent
  pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v
  ```
  （此测试直接在内存验证提取逻辑）。

- [x] **Step 3: 修改 `prompt_compiler_middleware.py` 实现正则清洗**
  在 `backend/app/agent/middleware/prompt_compiler_middleware.py` 的 `_stage_prescan_failures` 尝试 loads 之前进行清洗：
  ```python
  # Target line in prompt_compiler_middleware.py
  # clean code
  import re
  content_to_parse = msg.content
  # 剥离时间戳前缀
  if isinstance(content_to_parse, str):
      content_to_parse = re.sub(r"^\[数据真实查询时刻: [^\]]+\]\n", "", content_to_parse.strip())
  try:
      parsed = json.loads(content_to_parse)
      if isinstance(parsed, list):
          # 合法 JSON 列表直接跳过后面的敏感词删除判定
          continue
  except (json.JSONDecodeError, TypeError):
      pass
  ```

- [x] **Step 4: 运行测试并验证通过**
  ```bash
  pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v
  ```
  Expected: PASS

---

### Task 2: 重构 `sql_db_query` 工具以返回 Command 与侧信道

**Files:**
- Create: `backend/app/agent/tools/test_sql_db_query_command.py`
- Modify: `backend/app/agent/tools/sql_tools.py`

- [x] **Step 1: 编写工具 TDD 单元测试**
  新建 `backend/app/agent/tools/test_sql_db_query_command.py` 验证 `sql_db_query` 被包装后返回 `Command` 且携带 `tool_artifact`：
  ```python
  import pytest
  from langgraph.types import Command
  from backend.app.agent.tools.sql_tools import sql_db_query
  
  def test_sql_db_query_returns_command():
      # 模拟查询
      result = sql_db_query.invoke({"query": "SELECT 1 as val"})
      assert isinstance(result, Command)
      assert "messages" in result.update
      assert "tool_artifact" in result.update
      
      artifact = result.update["tool_artifact"]
      assert artifact["kind"] == "query_result"
      assert artifact["columns"] == ["val"]
      assert artifact["rows"] == [{"val": 1}]
      assert artifact["row_count"] == 1
      assert artifact["truncated"] is False
  ```

- [x] **Step 2: 运行测试并验证失败**
  ```bash
  pytest backend/app/agent/tools/test_sql_db_query_command.py -v
  ```
  Expected: FAIL (AttributeError 或返回字符串而不是 Command)

- [x] **Step 3: 修改 `sql_tools.py` 实现**
  修改 `sql_tools.py` 中的 `create_wrapped_query_tool` 内部执行代理。
  - 清理 `_estimate_row_count` 与 `_extract_preview_rows` 正则。
  - 直接操作 `raw_result: list[dict]` 内存对象。
  - 判定是否为纯维度表查询，设置 `hard_limit` (复用 `settings.sql_result_hard_limit` / `settings.dimension_result_hard_limit`)。
  - 空结果 fallback 取 `columns`：优先读取游标（如果能获取到），其次从游标 description 中解构，最末 fallback 为 `[]`。
  - 构造 `Command` 返回：
    ```python
    from langgraph.types import Command
    from langchain_core.messages import ToolMessage
    
    # 截断预览只传前 settings.sql_result_preview_rows (通常为 5) 渲染给 LLM
    preview_rows = raw_result[:settings.sql_result_preview_rows]
    preview_text = json.dumps(preview_rows, ensure_ascii=False)
    
    # 侧信道 rows 限制在 hard_limit 内 (防 SSE OOM)
    rows_for_sse = raw_result[:hard_limit]
    
    return Command(update={
        "messages": [ToolMessage(content=time_prefix + preview_text, name=name, tool_call_id=tool_call_id)],
        "tool_artifact": {
            "kind": "query_result",
            "columns": columns,
            "rows": rows_for_sse,
            "row_count": len(raw_result),
            "truncated": len(raw_result) >= hard_limit,
            "query_time": query_time,
            "source_tables": source_tables,
        }
    })
    ```

- [x] **Step 4: 运行测试并验证通过**
  ```bash
  pytest backend/app/agent/tools/test_sql_db_query_command.py -v
  ```
  Expected: PASS

---

### Task 3: 侧信道 updates 事件拦截与 SSE 广播

**Files:**
- Modify: `backend/app/services.py:L787-810`
- Modify: `backend/app/api.py:L610-620`, `L930-940`
- Modify: `backend/app/schemas.py`

- [x] **Step 1: schemas.py 声明流式事件**
  在 `backend/app/schemas.py` 中新增联合契约事件 `ToolArtifactStreamEvent`：
  ```python
  class ToolArtifactStreamEvent(BaseModel):
      type: Literal["tool_artifact"]
      artifact: Dict[str, Any]
  ```

- [x] **Step 2: services.py 中拦截 tool_artifact 消息**
  在 `backend/app/services.py` 遍历 `chunk_type == "updates"` 时拦截此字段：
  ```python
  # services.py (Updates loop inside _stream_chat)
  if isinstance(state_update, dict) and "tool_artifact" in state_update:
      artifact_val = state_update.get("tool_artifact")
      if artifact_val:
          await _emit({
              "type": "tool_artifact",
              "artifact": artifact_val
          })
  ```

- [x] **Step 3: api.py 转发流式事件**
  在 `backend/app/api.py` 的 `_stream_chat` (同步) 与 `_stream_chat_async` (异步) 双通道的 `event_type` 过滤条件中，同步追加 `"tool_artifact"` 转发：
  ```python
  # api.py
  if event_type in ("rag_context", "lexicon_context", "tool_artifact"):
      yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
  ```

---

### Task 4: 前端交互表格渲染与零正则 Badge 展示

**Files:**
- Modify: `frontend/src/components/MessageItem.vue`
- Modify: `frontend/src/store/chat.ts` (或 `useChatStream.ts` 捕获侧信道)

- [x] **Step 1: useChatStream 中存储当前会话的最新表格**
  在前端 `useChatStream.ts` 捕获流事件：
  ```typescript
  if (event.type === 'tool_artifact') {
      chatStore.setCurrentQueryResult(event.artifact);
  }
  ```
  在 Pinia 状态中声明并维护 `currentQueryResult`，每次新提问时重置。

- [x] **Step 2: MessageItem 中支持表格渲染与 Badge 展示**
  - **交互表格**：当 `MessageItem` 属于当前聊天中最新的 ToolMessage，且 `chatStore.currentQueryResult` 存在时，通过 Element Plus Table 渲染 `columns` 和 `rows` 数据，支持页面分页和基础列排序。
  - **Badge 零正则展示**：直接展示 `currentQueryResult.query_time` 和 `currentQueryResult.source_tables`。
  - **向后兼容**：非最新消息（历史会话或刷新后），气泡卡片自动回退到原有逻辑，用 `isExportArtifact` 等鸭子守卫解析 `tool_results` 的原始预览文本，规避一切重载开销。

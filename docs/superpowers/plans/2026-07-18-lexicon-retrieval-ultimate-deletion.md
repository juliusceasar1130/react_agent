# 三层检索工具极限物理删除与折叠重构 实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构滑动窗口外的辅助工具精简机制，将三层检索工具在窗口外一律物理删除，将案例检索工具维持常规折叠，基于「体积收益 vs 复用价值」的性价比模型最大化压缩长对话上下文。

**Architecture:** 
1. 在 `prompt_compiler_middleware.py` 中引入常量 `ULTIMATE_DELETION_TOOLS`（只含三个词典/表结构检索工具），并将它们从 `COLLAPSIBLE_TOOLS` 中移除。
2. 在 `_stage_prescan_failures` 方法中增加拦截，若工具名在 `ULTIMATE_DELETION_TOOLS` 中且处于滑动窗口外，无条件添加至 `deleted_call_ids`，使其在 Stage 4 被彻底成对物理删除。
3. 在 `test_prompt_compiler_middleware.py` 中补充窗口内保留、窗口外物理删除、混合多 tool_call 剥离等自动化单测。

**Tech Stack:** Python 3.12, pytest, LangChain

---

### Task 1: 重构 `prompt_compiler_middleware.py` 的常量定义

**Files:**
- Modify: [prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)

- [ ] **Step 1: 修改常量定义**

修改 `prompt_compiler_middleware.py` 第 36-46 行，定义 `ULTIMATE_DELETION_TOOLS` 并移去 `COLLAPSIBLE_TOOLS` 里的三个检索工具。

修改前：
```python
# 定义需折叠替换的白名单工具名
COLLAPSIBLE_TOOLS = {
    "sql_db_query",
    "search_saved_correct_tool_uses",
    "build_chart_artifact",
    "export_to_csv",
    "export_query_to_csv",
    "search_db_value_lexicon",
    "search_db_row_lexicon",
    "search_db_table_schema",
}
```

修改后：
```python
# 定义需要在滑动窗口外物理删除的辅助检索工具（极限删除）
ULTIMATE_DELETION_TOOLS = {
    "search_db_value_lexicon",
    "search_db_row_lexicon",
    "search_db_table_schema",
}

# 定义需折叠替换的白名单工具名
COLLAPSIBLE_TOOLS = {
    "sql_db_query",
    "search_saved_correct_tool_uses",
    "build_chart_artifact",
    "export_to_csv",
    "export_query_to_csv",
}
```

- [ ] **Step 2: 验证现有测试集仍能通过**

运行：
`pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
预期：PASS

- [ ] **Step 3: 提交修改**

运行：
```bash
git add backend/app/agent/middleware/prompt_compiler_middleware.py
git commit -m "refactor: define ULTIMATE_DELETION_TOOLS and adjust COLLAPSIBLE_TOOLS"
```

---

### Task 2: 增加预扫描阶段对检索工具的物理删除收集

**Files:**
- Modify: [prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)

- [ ] **Step 1: 修改 `_stage_prescan_failures` 逻辑**

修改 `prompt_compiler_middleware.py` 中的 `_stage_prescan_failures` 方法（大约第 149-165 行），无条件收集滑动窗口外的 `ULTIMATE_DELETION_TOOLS` 呼叫 ID。

修改前：
```python
    def _stage_prescan_failures(self, ctx: _CollapseContext) -> None:
        """Stage 2: Pre-scan window-out messages for failed tool calls."""
        for idx in range(ctx.boundary_index):
            msg = ctx.messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name not in self._DELETION_TARGET_CONFIG:
                continue

            config = self._DELETION_TARGET_CONFIG[msg.name]
```

修改后：
```python
    def _stage_prescan_failures(self, ctx: _CollapseContext) -> None:
        """Stage 2: Pre-scan window-out messages for failed tool calls."""
        for idx in range(ctx.boundary_index):
            msg = ctx.messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            
            # 对于三层检索辅助工具，在滑动窗口外一律无条件执行物理删除
            if msg.name in ULTIMATE_DELETION_TOOLS:
                ctx.deleted_call_ids.add(msg.tool_call_id)
                continue

            if msg.name not in self._DELETION_TARGET_CONFIG:
                continue

            config = self._DELETION_TARGET_CONFIG[msg.name]
```

- [ ] **Step 2: 运行测试验证**

运行：
`pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
预期：PASS

- [ ] **Step 3: 提交修改**

运行：
```bash
git add backend/app/agent/middleware/prompt_compiler_middleware.py
git commit -m "feat: add ultimate physical deletion for retrieval tools in Stage 2"
```

---

### Task 3: 编写检索工具极限物理删除的单元测试

**Files:**
- Modify: [test_prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_prompt_compiler_middleware.py)

- [ ] **Step 1: 在测试文件末尾追加单测**

修改 `test_prompt_compiler_middleware.py` 末尾，追加 `test_prompt_compiler_lexicon_retrieval_window_in_preservation`、`test_prompt_compiler_lexicon_retrieval_window_out_ultimate_deletion` 和 `test_prompt_compiler_lexicon_retrieval_mixed_tool_calls_deletion` 三个测试函数。

在末尾追加：
```python

def test_prompt_compiler_lexicon_retrieval_window_in_preservation():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    # 模拟处于滑动窗口内部的检索，应完好保留
    messages = [
        HumanMessage(content="Query table schema"),
        AIMessage(content="Let me check schema", tool_calls=[{"name": "search_db_table_schema", "args": {"query": "ods.process_areas"}, "id": "call_schema"}]),
        ToolMessage(content="CREATE TABLE ods.process_areas (id VARCHAR);", name="search_db_table_schema", tool_call_id="call_schema"),
        HumanMessage(content="Helpful query"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # 验证窗口内消息完整，不被删除
    assert len(new_request.messages) == 4
    assert new_request.messages[2].content == "CREATE TABLE ods.process_areas (id VARCHAR);"
    assert new_request.messages[1].tool_calls[0]["name"] == "search_db_table_schema"


def test_prompt_compiler_lexicon_retrieval_window_out_ultimate_deletion():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    # 模拟超出滑动窗口边界的检索工具调用，应当成对物理删除
    messages = [
        HumanMessage(content="Old query"),
        AIMessage(content="Search old table DDL", tool_calls=[{"name": "search_db_table_schema", "args": {"query": "old_table"}, "id": "call_old_schema"}]),
        ToolMessage(content="CREATE TABLE old_table (id INT);", name="search_db_table_schema", tool_call_id="call_old_schema"),
        
        # 3 个 HumanMessage 确保其被推到窗口外
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # 验证窗口外检索对已完全被物理删除（从 6 条消息缩减为 4 条，去掉了 AIMessage 和 ToolMessage 对）
    assert len(new_request.messages) == 4  # H0, M1, M2, M3
    for msg in new_request.messages:
        if isinstance(msg, ToolMessage):
            assert msg.tool_call_id != "call_old_schema"
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            assert all(tc["id"] != "call_old_schema" for tc in msg.tool_calls)


def test_prompt_compiler_lexicon_retrieval_mixed_tool_calls_deletion():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    # 模拟并行调用：一个检索工具（需删除）和一个成功SQL工具（需保留折叠）
    messages = [
        HumanMessage(content="Find and Query"),
        AIMessage(
            content="Check schema and data",
            tool_calls=[
                {"name": "search_db_table_schema", "args": {"query": "t1"}, "id": "c_schema"},
                {"name": "sql_db_query", "args": {"query": "SELECT * FROM t1"}, "id": "c_sql"}
            ]
        ),
        ToolMessage(content="CREATE TABLE t1 (id INT);", name="search_db_table_schema", tool_call_id="c_schema"),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="c_sql"),
        
        # 推动其滑出窗口
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # 检索对应当删除，SQL成功对应当折叠
    # 消息列表中，检索的 ToolMessage (index 2) 被剔除，SQL 的 ToolMessage (index 3) 被折叠
    tool_msgs = [m for m in new_request.messages if isinstance(m, ToolMessage)]
    # 只剩下 SQL 成功查询对应的 ToolMessage，且被成功折叠
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "c_sql"
    assert tool_msgs[0].content == "[SQL execution successful. Result content collapsed. Re-run query if details are needed.]"
    
    # 并行 AIMessage 应该只保留 SQL 调用，剥离检索调用
    ai_msgs = [m for m in new_request.messages if isinstance(m, AIMessage)]
    assert len(ai_msgs) == 1
    assert len(ai_msgs[0].tool_calls) == 1
    assert ai_msgs[0].tool_calls[0]["id"] == "c_sql"
```

- [ ] **Step 2: 运行测试并验证**

运行：
`python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
预期：全部 PASS，输出中有 `test_prompt_compiler_lexicon_retrieval_window_in_preservation` 等新增测试成功的记录。

- [ ] **Step 3: 提交测试修改**

运行：
```bash
git add backend/app/agent/middleware/test_prompt_compiler_middleware.py
git commit -m "test: add test cases for lexicon retrieval window preservation and physical deletion"
```

---

### Task 4: 更新更新日志 (Changelog)

**Files:**
- Modify: [changelog.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/changelog.md)

- [ ] **Step 1: 追加变更记录**

在 `changelog.md` 顶部的最新日志下添加对应说明。

修改后：
```markdown
### 2026-07-18
- **Refactor (Context Collapse)**: 精细化重塑滑动窗口外辅助工具清理逻辑。
  - 将三层检索工具 (`search_db_value_lexicon`, `search_db_row_lexicon`, `search_db_table_schema`) 归为 `ULTIMATE_DELETION_TOOLS`，在滑动窗口外执行 100% 物理删除，消除 DDL 对上下文带来的极度臃肿。
  - 维持 `search_saved_correct_tool_uses` 在 `COLLAPSIBLE_TOOLS` 中的折叠逻辑，利用占位符防范大模型重复检索，平衡跨轮复用价值。
  - 在 `test_prompt_compiler_middleware.py` 中补充了针对混合多 tool_call 剥离、窗口内外物理删除等边界条件的自动化单测。
```

- [ ] **Step 2: 提交日志变更**

运行：
```bash
git add changelog.md
git commit -m "docs: document lexicon retrieval context collapse optimization in changelog"
```

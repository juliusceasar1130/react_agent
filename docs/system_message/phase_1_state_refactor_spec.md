# Phase 1 详细设计规范 (Detailed Design Specification)
## 主题：数据流去耦与状态化 RAG 传递 (State Refactoring & RAG Decoupling)

本规范书定义了 **阶段 1：数据流去耦与状态化传递** 的具体代码修改细节，包括接口契约、中间件输入输出行为以及单元测试对齐策略。

---

## 1. 状态结构契约 (State Schema Alignment)

在 [state.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/state.py) 中，已预留了 `lexicon_context` 与 `rag_context` 两个状态键：
```python
class CustomState(AgentState):
    rag_context: NotRequired[List[Document]]
    lexicon_context: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
```

### 1.1 `lexicon_context` 数据结构规范
为了使装配层能够直接读取预格式化的 RAG 文本，规范 `lexicon_context` 的字典格式如下：
```python
{
    "formatted_text": str,       # 由 RAG 检索器生成并拼装好的 Markdown 格式的混合参考数据
    "tables": List[str],         # 命中的物理表名列表（用于后续去重研究）
    "values_count": int,         # 物理值映射命中条数
    "rows_count": int            # 物理行对照命中条数
}
```

---

## 2. RAG 中间件重构设计 (`BusinessRagMiddleware`)

### 2.1 修改目标
消除 RAG 中间件对 `messages` 历史列表的写入操作，彻底阻断历史消息污染。

### 2.2 具体修改点 ([rag_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/rag_middleware.py))

*   **重构函数 `_format_and_assemble_state`**:
    - **移除** 往 `messages` 列表中定位并替换/插入 `rag_system_message` 的所有代码（第 410 行至 444 行将全部废弃）。
    - **调整返回值**：返回值字典中**严禁包含 `"messages"` 键**。
    - **数据填充**：将原来组装好的 `rag_system_content` 字符串直接作为 `"formatted_text"` 字段写入 `lexicon_context` 中。

*   **新旧返回值对照**：

**❌ 重构前（旧代码）**：
```python
return {
    "messages": new_messages,  # ⚠️ 导致历史消息被物理污染的元凶
    "rag_context": retrieved_docs,
    "rag_query": user_query,
    "lexicon_context": {
        "tables": table_lexicon_context,
        "values_count": len(lexicon_results.get("values", [])),
        "rows_count": len(lexicon_results.get("rows", []))
    }
}
```

**🟢 重构后（新设计）**：
```python
return {
    # 彻底移除了 "messages" 字段更新！
    "rag_context": retrieved_docs,
    "rag_query": user_query,
    "lexicon_context": {
        "formatted_text": rag_system_content,  # 👈 新增：直接将格式化的 RAG 文本存入 state
        "tables": table_lexicon_context,
        "values_count": len(lexicon_results.get("values", [])),
        "rows_count": len(lexicon_results.get("rows", []))
    }
}
```

---

## 3. 合并中间件重构设计 (`SafeMergeSystemMiddleware`)

### 3.1 修改目标
改从状态（`request.state`）直接获取 RAG 文本，不再从历史 `messages` 列表里扫描提取。

### 3.2 具体修改点 ([safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/safe_merge_middleware.py))

*   **重构函数 `_modify_request`**：
    - **逻辑替换**：不再遍历 `projected_messages` 寻找带 `__business_rag_context__` 的消息（第 401 至 426 行移除）。
    - **直接读取**：通过 `request.state` 直接安全读取 `lexicon_context`：
      ```python
      # 从 state 中安全读取 RAG 预编译好的文本块
      lexicon_ctx = request.state.get("lexicon_context") or {}
      rag_text = lexicon_ctx.get("formatted_text", "")
      ```
    - **物理合并**：
      如果存在 `rag_text`，直接将其拼接到全局 system_prompt 后部：
      ```python
      # 获取原始 system_message 文本
      sys_text = _get_string_content(request.system_message)
      
      if rag_text:
          # 保持原有的合并格式
          merged_content = f"{sys_text}\n\n{rag_text}{date_prompt}"
      else:
          merged_content = f"{sys_text}{date_prompt}"
      ```
    - **容灾兼容（防旧历史污染干扰）**：
      由于历史会话可能已在数据库中存留了旧的带 `__business_rag_context__` 的临时消息，在过滤消息队列时，增加一步对历史垃圾消息的防御性过滤（仅在内存处理中扔掉它们，不影响新会话，防止历史报错）：
      ```python
      # 防御性过滤已存在于数据库历史中的老旧污染消息
      filtered_messages = []
      for msg in projected_messages:
          if isinstance(msg, SystemMessage):
              content = getattr(msg, "content", "")
              if isinstance(content, str) and "__business_rag_context__" in content:
                  continue
          filtered_messages.append(msg)
      ```

---

## 4. 单元测试对齐设计 (`test_safe_merge_middleware.py`)

### 4.1 修改点 ([test_safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_safe_merge_middleware.py))

*   **修改测试用例 `test_safe_merge_injects_current_date_with_rag`**：
    - **测试机制调整**：从前是通过将 `rag_msg` 塞入 `messages` 来测试合并；重构后，测试应当通过**填充 `state.lexicon_context`** 来验证合并效果：
    ```python
    def test_safe_merge_injects_current_date_with_rag():
        # 重构后：数据通过 state 传输，messages 保持干净
        state = CustomState(
            messages=[],
            lexicon_context={
                "formatted_text": "This is __business_rag_context__ info",
                "tables": []
            }
        )
        request = ModelRequest(
            model=None,
            messages=[],
            system_message=SystemMessage(content="Base system prompt"),
            state=state
        )
        
        middleware = SafeMergeSystemMiddleware()
        new_request = middleware._modify_request(request)
        
        content = str(new_request.system_message.content)
        
        # 验证是否正确合并，且 messages 依然保持 0 条
        assert "Base system prompt" in content
        assert "This is __business_rag_context__ info" in content
        assert len(new_request.messages) == 0
    ```

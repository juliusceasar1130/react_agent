# Phase 3 详细设计规范 (Detailed Design Specification)
## 主题：静态与动态分区物理隔离设计 (XML Isolation & Prompt Caching Optimization)

本规范书定义了 **阶段 3：静态与动态分区物理隔离** 的设计与实现方案。通过引入 `<system_rules>`（静态规则区）和 `<runtime_context>`（动态上下文区）两个 XML 标签分区，最大化 Prompt Cache（如 DeepSeek/Anthropic 的 Prefix Caching）的命率，减少 Token 开销并缩短响应首字节延迟（TTFT）。

---

## 1. 物理分区设计方案 (Zoning Architecture)

提示词的整体架构将被编译组装成以下物理隔离结构：

```xml
<system_rules>
# 1. 角色定义与最优先级红线 (Role & Redlines)
...（来自 base_system_prompt.md）...

## Available Skills
- **paint_defect**: ...
...（来自 SkillMiddleware 注入的可用技能列表）...
</system_rules>

<runtime_context>
[系统提示: 当前日期: YYYY-MM-DD (星期X)]

## Active Domain Knowledge: paint_defect
...（当前激活的领域 DDL 结构及易错 Gotchas）...

## Secondary Domain Knowledge
### 辅助关联技能表结构: ...
...（关联加载的辅助技能骨架 DDL）...

__business_rag_context__
# 辅助知识参考 (RAG & DB Lexicon)
...（业务知识与行级/列级词典推荐 DDL）...
</runtime_context>
```

### 1.1 缓存优化原理解析
*   **`<system_rules>` 区（静态缓存区）**：不随对话轮数、当前日期、检索内容或用户加载的技能而改变。在会话生存期内保持绝对静止，使 LLM 服务端能够 100% 缓存该前缀。
*   **`<runtime_context>` 区（动态挥发区）**：包含时间戳、动态检索的 RAG 知识、当前按需加载的表 DDL 结构。这部分内容随轮次变化，置于静态区之后，以防污染静态缓存前缀。

---

## 2. 关键代码修改点 (Key Implementation Points)

### 2.1 修改 `PromptCompilerMiddleware` ([prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py))

*   **重构方法 `_modify_request`**：
    - 从 `request.system_message` 的 `content_blocks` 中提取不同类别的文本块。
    - 将它们归类为**静态块**（基础提示词、Available Skills）和**动态块**（Active DDL、Secondary DDL）。
    - 结合 RAG 文本（`rag_text`）和当前日期（`date_prompt`），用 XML 标签包装静态和动态内容，融合成最终的 SystemMessage。

#### 修改后的 `_modify_request` 核心伪代码：

```python
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        self._inject_thinking_config(request)
        
        raw_messages = list(request.messages) if request.messages else []
        projected_messages = self._project_and_collapse_messages(raw_messages)

        # 1. 提取 RAG 文本
        lexicon_ctx = request.state.get("lexicon_context") if request.state else {}
        if not lexicon_ctx:
            lexicon_ctx = {}
        rag_text = lexicon_ctx.get("formatted_text", "")

        # 2. 清洗历史残留 RAG 消息
        filtered_messages = []
        for msg in projected_messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                if isinstance(content, str) and "__business_rag_context__" in content:
                    continue
                elif hasattr(msg, "content_blocks"):
                    is_legacy_rag = False
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if "__business_rag_context__" in block.get("text", ""):
                                is_legacy_rag = True
                                break
                    if is_legacy_rag:
                        continue
            filtered_messages.append(msg)

        # 3. 解析 content_blocks 区分静态与动态部分
        blocks = getattr(request.system_message, "content_blocks", None)
        base_sys_text = ""
        skills_addendum = ""
        active_ddl = ""
        secondary_ddl = ""

        if isinstance(blocks, list) and len(blocks) > 0:
            # 默认第 0 块是 base_system_prompt
            base_sys_text = blocks[0].get("text", "") if isinstance(blocks[0], dict) else str(blocks[0])
            for block in blocks[1:]:
                text = block.get("text", "") if isinstance(block, dict) else str(block)
                if "## Available Skills" in text:
                    skills_addendum = text
                elif "## Active Domain Knowledge" in text:
                    active_ddl = text
                elif "## Secondary Domain Knowledge" in text:
                    secondary_ddl = text
        else:
            base_sys_text = _get_string_content(request.system_message)

        # 4. 组装静态区 (System Rules)
        static_parts = [base_sys_text]
        if skills_addendum:
            static_parts.append(skills_addendum)
        system_rules_content = "\n\n".join(static_parts).strip()
        system_rules_xml = f"<system_rules>\n{system_rules_content}\n</system_rules>"

        # 5. 组装动态区 (Runtime Context)
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"[系统提示: {date_str}]"

        dynamic_parts = [date_prompt]
        if active_ddl:
            dynamic_parts.append(active_ddl.strip())
        if secondary_ddl:
            dynamic_parts.append(secondary_ddl.strip())
        if rag_text:
            dynamic_parts.append(rag_text.strip())
            
        runtime_context_content = "\n\n".join(dynamic_parts).strip()
        runtime_context_xml = f"<runtime_context>\n{runtime_context_content}\n</runtime_context>"

        # 6. 合并编译成唯一的 SystemMessage
        compiled_content = f"{system_rules_xml}\n\n{runtime_context_xml}"
        new_system_message = SystemMessage(content=compiled_content)
        
        logger.info("🛡️ PromptCompilerMiddleware: 静态/动态双分区编译合并完成。")
        return request.override(
            system_message=new_system_message,
            messages=filtered_messages
        )
```

---

## 3. 单元测试更新细则 (Test Assertions Update)

修改 [test_prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_prompt_compiler_middleware.py)，增加对 XML 标签位置和包含内容的严格断言：

*   **断言 1**：最终编译的 system prompt 必须包含 `<system_rules>` 和 `</system_rules>`。
*   **断言 2**：最终编译的 system prompt 必须包含 `<runtime_context>` 和 `</runtime_context>`。
*   **断言 3**：静态内容（如 `Base system prompt`）必须位于 `<system_rules>` 内部。
*   **断言 4**：动态内容（如日期提示、RAG 文本）必须位于 `<runtime_context>` 内部。

---

## 4. 验证计划 (Verification Plan)

1.  **运行单元测试**：
    `conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
    **预期结果**：测试覆盖 XML 分区解析与装配，全量测试 PASS。
2.  **服务集成测试**：
    启动服务并使用 `load_skill` 检查完整链路，验证日志中最终输出的提示词是否严格符合 XML 双分区格式。

# 大模型三层检索工具上下文极限物理删除优化提案 (Proposal 3)

> **Status:** 💡 **PROPOSAL (REVISED)**  
> **Author:** Antigravity (AI Coding Assistant)  
> **Date:** 2026-07-18  
> **Target Path:** [prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)  
> **Related Tests:** [test_prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_prompt_compiler_middleware.py)

---

## 一、 背景 (Background)

在当前的生产数据查询智能体系统中，为了降低长对话中的 Token 消耗，我们实现了一套基于 [PromptCompilerMiddleware](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py) 的上下文精简与清理机制。

当前的设计仅对 **SQL 查询** (`sql_db_query`) 和 **图表生成** (`build_chart_artifact`) 工具进行了精细的分类治理：
* **失败调用**：在滑动窗口外执行**物理删除**（成对 Pop 移除 `AIMessage` + `ToolMessage`）。
* **成功调用**：在滑动窗口外执行**占位折叠**（保留消息骨架，将 content 替换为极简占位文本）。

然而，对于作为辅助工具的**三层检索工具**（`search_db_value_lexicon`、`search_db_row_lexicon`、`search_db_table_schema`）：
1. 它们虽然在类顶部的 `COLLAPSIBLE_TOOLS` 白名单中，但由于 `_stage_standard_collapse` 和 `_stage_prescan_failures` 中缺少对应的处理分支，导致它们在滑动窗口外**实际上既没有被折叠，也没有被删除**。
2. 尤其是表结构检索返回的 DDL 文本，单次调用就可能产生数千 Token 的消耗。随着对话轮次增加，历史遗留的 DDL 会迅速累计并污染大模型的上下文。

---

## 二、 核心分析：体积收益 vs 复用价值 的性价比抉择 (Core Analysis)

我们对辅助类检索工具的清理策略并不是简单一刀切，而是基于 **「体积收益 vs 复用价值」的性价比模型** 进行精细化决策，并在此基础上合理平衡“防重复检索”的 Trade-off：

| 工具名称 | 单次体积 | 跨轮复用价值 | 重复检索代价 | 推荐处理策略 | 性价比与设计取向 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`search_db_table_schema`** (DDL 探索) | **极高**（数千 Token） | **低**（一次性消费，SQL 生成后即失效） | **极低**（内存字典检索，重新查询极其廉价） | **物理删除** (Ultimate Deletion) | 省得多、丢得少。物理删除即使导致模型偶尔重新检索，代价也微乎其微。 |
| **`search_db_value_lexicon`** (列值纠偏) | **中**（数百 Token） | **低**（一次性实体/字段对齐） | **低**（重新检索代价低） | **物理删除** (Ultimate Deletion) | 物理去噪，最大化规避历史过期词值对模型当次判断的干扰。 |
| **`search_db_row_lexicon`** (行实体对齐) | **中**（数百 Token） | **低**（一次性主键/描述对齐） | **低**（重新检索代价低） | **物理删除** (Ultimate Deletion) | 物理去噪，确保旧问题的实体主键不污染新问题。 |
| **`search_saved_correct_tool_uses`** (案例检索) | **小**（一两条 SQL，极少 Token） | **极高**（跨轮的 Few-shot 语法/业务复用） | **高**（重新检索容易诱发模型思维发散与多余工具调用） | **占位折叠** (Collapse) | 占位成本极低，且折叠骨架能向模型明确传达“已参考过案例 X”的线索，有效抑制重复检索。 |

### 核心论证与 Trade-off 权衡：
1. **为什么 lexicon / schema 工具选择直接物理删除？**
   这三个检索工具提供的是纯粹的一次性背景知识。一旦在保护窗口内生成了正确的 SQL，这些背景知识在历史消息中就失去了价值。由于这些工具的后端实现是极轻量廉价的本地向量字典检索，哪怕模型在极少数长对话回溯时需要重新检索，系统付出的计算代价也极其低廉，相比其带来的海量 Token 压缩收益，性价比极高。
2. **为什么案例检索工具 `search_saved_correct_tool_uses` 维持折叠？**
   Few-shot 案例不仅体积非常小，而且它承载着“纠正模型 SQL 语法与业务逻辑”的重要线索。如果将其物理删除，模型极易产生认知偏差，在后续提问中重复发起案例检索调用。保留其折叠占位符，既阻断了大部分内容空间，又能在历史中为模型留下一个强有力的指示灯——“已经查过示例，无需重复检索”。

---

## 三、 推荐方案与代码设计 (Recommended Plan)

我们建议在 [prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py) 中，将三层检索工具定义为独立的模块级常量，并修改 Pipeline 的逻辑：

### 1. 定义模块级常量
在文件顶部（[第 36 行左右](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py#L36)），引入 `ULTIMATE_DELETION_TOOLS` 集合，并从 `COLLAPSIBLE_TOOLS` 中将这三个检索工具剥离，形成对称：

```python
# 定义需要在滑动窗口外物理删除的辅助检索工具（极限删除）
ULTIMATE_DELETION_TOOLS = {
    "search_db_value_lexicon",
    "search_db_row_lexicon",
    "search_db_table_schema",
}

# 定义需在滑动窗口外折叠占位的工具名（维持 search_saved 在内）
COLLAPSIBLE_TOOLS = {
    "sql_db_query",
    "search_saved_correct_tool_uses",
    "build_chart_artifact",
    "export_to_csv",
    "export_query_to_csv",
}
```

### 2. 修改 Stage 2：预扫描物理删除判定
在 [_stage_prescan_failures](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py#L149-L186) 中，对于在滑动窗口（`boundary_index`）之外的 `ULTIMATE_DELETION_TOOLS`，**无条件**将其 `tool_call_id` 加入 `deleted_call_ids`：

```python
    def _stage_prescan_failures(self, ctx: _CollapseContext) -> None:
        """Stage 2: Pre-scan window-out messages for failed tool calls and ultimate deletion tools."""
        for idx in range(ctx.boundary_index):
            msg = ctx.messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            
            # ── 新增：滑动窗口外，三层检索辅助工具一律无条件执行物理删除 ──
            if msg.name in ULTIMATE_DELETION_TOOLS:
                ctx.deleted_call_ids.add(msg.tool_call_id)
                continue

            if msg.name not in self._DELETION_TARGET_CONFIG:
                continue

            # 原有 sql_db_query / build_chart_artifact 失败判定逻辑保持不变...
            config = self._DELETION_TARGET_CONFIG[msg.name]
            content_str = str(msg.content)
            is_failed = False
            ...
```

*注：在 Stage 4 `_stage_physical_deletion` 中，所有处于 `ctx.deleted_call_ids` 中的工具对都将被自动成对物理删除。*

---

## 四、 收益预估 (Estimated Benefits)

* **Token 节省**：根据生产环境中长会话的平均情况评估，物理删除 DDL 检索（单次约 1000-2000 Tokens）以及行/列词典匹配表（单次约 200-400 Tokens），相比原折叠方案，**长对话上下文体积预计可额外缩减 30% 以上（具体数值取决于长对话中检索工具被调用的次数，待实测数据对齐）**。
* **推理效率**：降低上下文的无用噪声堆积，提升大模型关注 SQL 生成核心指令的专注度，提升推理耗时性能。

---

## 五、 验证方案与单测设计 (Verification Plan)

我们将在 [test_prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_prompt_compiler_middleware.py) 中补充以下覆盖完备的单测逻辑：

### 1. `_stage_prescan_failures` 的边界测试
* **窗口内用例**：
  * **输入**：`HumanMessage` $\rightarrow$ `AIMessage(search_db_table_schema)` $\rightarrow$ `ToolMessage(DDL数据)`。处于滑动窗口内。
  * **预期**：`deleted_call_ids` 为空，检索消息完整保留。
* **窗口外用例**：
  * **输入**：同上，但检索工具对处于滑动窗口外。
  * **预期**：`deleted_call_ids` 包含该检索的 `tool_call_id`，在物理删除后该消息对在列表中消失。

### 2. 混合多 `tool_call` 的剥离测试
* **输入**：一个 `AIMessage` 同时触发了 `search_db_table_schema`（物理删除目标）和 `sql_db_query`（保留/常规折叠目标）两个并发调用。
* **预期**：
  * 该 `AIMessage` **不会被整条删除**。
  * `AIMessage.tool_calls` 中仅被移除了 `search_db_table_schema` 那项调用，保留 `sql_db_query` 调用的骨架。
  * 列表中仅保留 `sql_db_query` 的 `ToolMessage`，检索的 `ToolMessage` 被安全物理删除。

### 3. Pipeline 端到端集成测试
* **输入**：模拟一个 5 轮对话的长消息流，其中包含多次 `search_db_table_schema` 成功调用、多次失败的 SQL 重试、以及一个成功的 SQL 执行。
* **预期**：
  * 窗口外的检索工具彻底消失。
  * 窗口外的 SQL 失败彻底消失。
  * 窗口外的 SQL 成功折叠为占位符。
  * 窗口内的重试留存符合 `keep_count` 设定。

---

## 六、 更新日志 (Changelog)

在完成代码实施后，同步在 `changelog.md` 中增加以下记录：
```markdown
### 2026-07-18
- **Refactor (Context Collapse)**: 精细化重塑滑动窗口外辅助工具清理逻辑。
  - 将三层检索工具 (`search_db_value_lexicon`, `search_db_row_lexicon`, `search_db_table_schema`) 归为 `ULTIMATE_DELETION_TOOLS`，在滑动窗口外执行 100% 物理删除，消除 DDL 对上下文带来的极度臃肿。
  - 维持 `search_saved_correct_tool_uses` 在 `COLLAPSIBLE_TOOLS` 中的折叠逻辑，利用占位符防范大模型重复检索，平衡跨轮复用价值。
  - 在 `test_prompt_compiler_middleware.py` 中补充了针对混合多 tool_call 剥离、窗口内外物理删除等边界条件的自动化单测。
```

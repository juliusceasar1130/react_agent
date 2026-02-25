# SQL 示例自主检索机制详解 (Autonomous SQL Example Retrieval)

在 Vanna 2.0 架构中，SQL 示例（Few-shot Examples）的检索逻辑从“后台预处理”转型为了“Agent 自主行为”。这种机制确保了检索的精准度，并赋予了 LLM 解决复杂问题的思考空间。

---

## 1. 核心原理：自主性 (Autonomy)

与 DDL（表结构）和业务文档（TextMemory）不同，SQL 示例不再是默认强制注入系统提示词（System Prompt）的。

*   **按需检索**：只有当 LLM 认为需要参考类似案例时，才会发起检索。
*   **工具驱动**：检索过程被封装为一个标准工具 `search_saved_correct_tool_uses`。
*   **提示词引导**：系统通过指令引导 LLM “在写 SQL 前先查笔记”。

---

## 2. 完整工作机制

整个工作流可以划分为以下五个阶段：

### 阶段 1：策略定义 (System Prompt)
在 `vanna/core/system_prompt/default.py` 中，定义了 Agent 的行为准则：
```markdown
BEFORE executing any tool (run_sql...), you MUST first call 
search_saved_correct_tool_uses with the user's question.
```
这在逻辑上将“查找示例”变为了 LLM 执行任务的标准前置动作。

### 阶段 2：自主触发 (Tool Selection)
LLM 根据用户问题，生成一个工具调用请求：
*   **工具名**：`search_saved_correct_tool_uses`
*   **参数**：`question`（通常是原始问题的语义改写）

### 阶段 3：底层检索逻辑 (Agent Memory)
工具执行器调用 `AgentMemory` 接口。以 [ChromaAgentMemory](file:///d:/Python/workplace/NL2SQL/vanna-main/src/vanna/integrations/chromadb/agent_memory.py) 为例：
1.  **向量转化**：将问题文本通过 Embedding 模型转化为高维向量。
2.  **硬性过滤**：
    *   `success == True`：只检索历史上成功运行的 SQL。
    *   `tool_name == "run_sql"`：确保检索到的是 SQL 执行记录而非其他。
3.  **多租户隔离**：利用 `ToolContext` 中的 `user_id` 或 `org_id` 进行元数据过滤（Metadata Filtering），确保数据安全。

### 阶段 4：结果反馈 (Tool Result)
检索到的结果（相似的 Question 和对应的 SQL）不会直接进入 Prompt，而是作为 **Tool Result** 回传给 LLM。
*   **格式**：JSON 数组，包含相似度得分、历史问题和对应的执行参数（即 SQL）。

### 阶段 5：模仿与生成 (Few-shot Learning)
LLM 观察 Tool Result 中的示例：
*   如果找到相似结构的 SQL，LLM 会**模仿**其 Join 逻辑、Where 条件或特定的业务函数。
*   如果没有找到，LLM 则根据 DDL（由 Enhancer 提前注入的内容）进行原创生成。

---

## 3. 技术优势与差异

| 特性 | 背景知识检索 (DDL/Docs) | SQL 示例检索 (Few-shot) |
| :--- | :--- | :--- |
| **所属路径** | **Enhancer Path** (主动注入) | **Tool Path** (自主检索) |
| **注入时机** | 第一时间，在 LLM 思考前 | 思考中，由 LLM 决定 |
| **存在形式** | System Prompt 的一部分 | 对话流中的工具返回结果 |
| **目的** | 提供语义上下文 | 提供逻辑/技能范例 |

---

## 4. 关键代码参考

*   **工具注册与执行**： [vanna/tools/agent_memory.py](file:///d:/Python/workplace/NL2SQL/vanna-main/src/vanna/tools/agent_memory.py)
*   **向量库实现**： [vanna/integrations/chromadb/agent_memory.py](file:///d:/Python/workplace/NL2SQL/vanna-main/src/vanna/integrations/chromadb/agent_memory.py)
*   **行为准则定义**： [vanna/core/system_prompt/default.py](file:///d:/Python/workplace/NL2SQL/vanna-main/src/vanna/core/system_prompt/default.py)

---

## 5. 最佳实践建议

1.  **保存高质量记录**：只将验证正确的 SQL 通过 `save_question_tool_args` 保存到内存，避免污染检索池。
2.  **问题多样化**：在训练（保存）示例时，尽量覆盖各种同义提问方式，提高向量匹配命中率。
3.  **针对性问题生成**：如果原始问题太模糊，可以引导 LLM 生成更具“搜索性”的 `question` 参数。

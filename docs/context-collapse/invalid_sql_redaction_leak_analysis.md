# 关于前端异常显示 `[Invalid SQL attempt. Redacted to save context space.]` 的深度分析与治理报告

> **文档创建时间：** 2026-07-31  
> **文档位置：** `docs/context-collapse/invalid_sql_redaction_leak_analysis.md`  
> **涉及核心文件：**
> - [prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)
> - [services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/services.py)
> - [messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/stores/messages.ts)

---

## 一、 现象描述 (Problem Description)

在 SQL Agent 的多轮数据查询与分析场景中，用户在前端对话界面中有时会看到 AI 回复消息的顶部或单独的回复卡片中显示如下字符串：

> `[Invalid SQL attempt. Redacted to save context space.]`

### 典型出现场景：
1. 用户提出一个复杂查询请求（例如 `VFF-09`），Agent 在第一轮 ReAct 循环中尝试生成的 SQL 校验失败（如被 SQL Linter 拦截或数据库执行报错）。
2. Agent 进入第二轮/后续 ReAct 循环进行自纠错重试。
3. 界面在输出最终回复卡片的同时，暴露了上述内部占位符文本，导致用户看到不属于业务范畴的调试术语，严重影响产品体验。

---

## 二、 机制设计初衷 (Design Context)

该文本并非系统异常崩溃崩溃日志，而是后端**上下文折叠与脱敏机制 (Context Collapse / Linter Redaction)** 的内部占位符。

### 1. 技术背景
SQL Agent 在执行多轮工具调用时，若中间步骤产生多次 SQL 语法报错、Linter 校验拦截或大量失败堆栈，将这些无用的错 SQL 完整保留在消息历史中，会导致大模型的 Token 上下文窗口（Context Window）急剧暴涨，甚至引发 `Context Window Overflow` 错误。

### 2. 原始设计方案
在 [prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py#L270-L308) 的 Stage 3 (`_stage_redaction`) 中设计了脱敏抹除逻辑：
* 当发现某次 `sql_db_query` 校验/执行失败且已超出保留的纠错线索窗口（`llm_context_redaction_keep_count`）时：
  * 将对应的 `ToolMessage.content` 替换为 `"[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"`
  * 将产生该调用的 `AIMessage.content` 替换为 `"[Invalid SQL attempt. Redacted to save context space.]"`

### 3. 理想行为视角 (Expected Behavior)
该脱敏改写操作应当是**纯内存级的临时视图投影 (Memory-only Projection)**：
* 仅仅在发往大模型的 HTTP 网络包（`ModelRequest`）中临时生效，让大模型看到精简后的 Context。
* **对终端用户（前端 UI）应当是 100% 隐形、透明无感知的**。

---

## 三、 根因深度剖析 (Root Cause Analysis)

为何原本只该存在于后端模型发包内存里的脱敏文本，会泄露并显示在前端 UI 上？

经过对后端中间件、LangGraph 执行引擎、持久化 Checkpointer 及前端渲染链路的全面追踪，确定根因包含以下 3 个层级：

```
┌────────────────────────────────────────────────────────────────────────┐
│ 根因 1: 后端状态污染 (State Side-Effect)                                │
│ Middleware 浅拷贝改写了 AIMessage，LangGraph 顺手将改写后的消息写回了    │
│ 全局 CustomState 并保存到了 Checkpointer 数据库。                       │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 根因 2: 消息数据流泄露 (Streaming & History Leakage)                     │
│ SSE 流 (updates 事件) 或历史消息 GET 接口从数据库/State 提取了已经被    │
│ 污染改写的 AIMessage 发送给前端。                                       │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 根因 3: 前端渲染防护缺失 (Frontend UI Filtering Defect)                 │
│ 前端未对带 tool_calls 的中间态 AIMessage 或 [Redacted...] 内部占位符    │
│ 进行拦截过滤，将其作为普通 AI 文本回复呈现给用户。                      │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. 根因一：后端状态隔离缺陷导致“假投影、真污染”
* 在 `PromptCompilerMiddleware._modify_request` 中，虽然使用了 `projected = list(messages)` 浅拷贝，但在进行元素改写时：
  ```python
  projected[back_idx] = AIMessage(
      content="[Invalid SQL attempt. Redacted to save context space.]",
      tool_calls=aimsg.tool_calls
  )
  ```
  修改后的 `projected_messages` 随 `request.override(messages=filtered_messages)` 返回给了 LangChain / LangGraph Agent 引擎。
* **关键盲区**：LangGraph 在每次 LLM 节点执行完毕后，会将 `request.messages` 绑定的最新消息列表合并回全局状态 `CustomState`，并同步写入持久化数据库 Checkpointer。
* **结果**：内存中的临时脱敏占位符**反向污染了全局数据库**。

### 2. 根因二：中间态工具消息（Tool Call AIMessage）暴露
* 在 ReAct 循环中，AI 发起 `sql_db_query` 工具调用时产生的消息也是 `AIMessage`。
* 当第一轮查询失败、第二轮重试触发时，第一轮的 `AIMessage` 被改写为 `[Invalid SQL attempt...]`。当后端发送 SSE 的 `updates` 事件或前端加载 Session History 时，这条带有脱敏 content 的 `AIMessage` 被推送到前端 Store 中。

### 3. 根因三：LLM 对 Prompt 上下文中占位符的模式模仿（次要因素）
* 当重试发生时，发送给 LLM 的历史 Prompt 里包含 `[Invalid SQL attempt...]` 字符串。
* 在极少数情况下（如多轮补全或请求打断），LLM 会在生成文本时模仿 Prompt 上下文中的这一格式，直接在 Output Token 中吐出该文本。

---

## 四、 关键技术误区澄清 (Myth Clarification)

### ❓ 疑问：既然消息投影泄露了，是不是应该改为“持久化”？

* **回答：绝对不能改为持久化！**
* **分析**：如果将其“持久化”（即把 `[Invalid SQL attempt...]` 真正永久写入数据库）：
  1. 用户的真实历史提问与 AI 的原始思考过程将永久丢失。
  2. 用户无论刷新页面还是查看历史记录，都永远会在界面上看到这句话。
* **正确结论**：问题不是“没有持久化”，恰恰是**“本不该持久化的内存临时投影，不小心写进了持久层”**。

---

## 五、 推荐治理措施 (Recommended Actions)

建议采用 **后端根治 + 前端纵深防御** 的组合治理策略：

### 措施 1：后端实现 100% 隔离的“纯内存临时投影”（推荐优先实施）

在 `PromptCompilerMiddleware` 中改写消息时，确保**深拷贝与状态隔离**，禁止将修改后的消息写回 LangGraph State。

* **实施思路**：
  在 `_modify_request` 内部，构造传给底层模型调用的消息副本，仅修改传给 `request.override(...)` 的副本；同时确保中间件不触发 LangGraph 的状态追加（State Update），保证写回 Checkpointer 数据库的消息永远是干净的原始消息。

```python
# 示意逻辑（仅供参考）：
import copy

def _modify_request(self, request: ModelRequest) -> ModelRequest:
    # 使用深拷贝隔离原始 State 消息
    raw_messages = copy.deepcopy(request.messages) if request.messages else []
    projected_messages = self._project_and_collapse_messages(raw_messages)
    
    # 仅覆写 ModelRequest，保证仅在当次 LLM HTTP 请求生效
    return request.override(
        system_message=new_system_message,
        messages=projected_messages
    )
```

### 措施 2：前端增加渲染层防护（纵深防御）

在前端消息 Store (`frontend/src/stores/messages.ts`) 或消息渲染组件中增加黑名单与类型过滤。

* **实施思路**：
  1. **识别中间态 Tool Call**：若 `AIMessage` 包含 `tool_calls` 且未完成终态输出，默认不将其 `content` 直接展示在对话主面板中。
  2. **脱敏文本拦截**：在渲染 Markdown 或消息 content 前，检测是否包含 `[Invalid SQL attempt.` 或 `[SQL validation failed` 等内部系统占位符。若匹配到，则屏蔽显示或替换为用户友好的提示（如“正在优化 SQL 查询...”）。

---

## 六、 总结

| 关注点 | 结论与说明 |
| :--- | :--- |
| **问题定位** | 属于典型的 **后端内部调试状态泄露与前端隔离缺失缺陷 (Bug)**。 |
| **影响范围** | 影响包含 SQL Linter 重试/纠错的多轮 Agent 对话视觉体验，不影响数据查询结果的准确性。 |
| **核心解法** | 保持“内存投影”的设计方向，在后端做到 **纯内存深度隔离**，切断向 Checkpointer 数据库与前端 UI 的泄漏路径。 |

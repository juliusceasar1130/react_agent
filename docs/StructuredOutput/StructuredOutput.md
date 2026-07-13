# 引入多格式结构化输出（Structured Output）评估报告

> **适用版本**：`python>=3.12` / `langchain>=1.2.15` / `langgraph>=1.1.8`  
> **修订日期**：2026-07-12  
> **核心变更**：废弃 `create_agent` 单模型决策黑盒，全面迁移至 LangGraph 状态图以实现分阶段工具动态路由

---

## 一、 项目现状与痛点分析

通过查阅后端核心逻辑（[service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py)）及前端 Markdown 解析工具（[markdown.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/utils/markdown.ts)），当前交互机制存在以下结构性痛点：

### 1. 元数据提取依赖正则（脆弱性高）
前端使用正则表达式提取 `[数据真实查询时刻: YYYY-MM-DD]` 和 `数据来源: table_name` 等元数据。大模型生成时微调标点、换行或多吐空格，都会导致正则匹配失效，前端 Badge 信息丢失。

### 2. 数据展示维度受限（交互性差）
数据库查询结果以原始 Markdown 表格混杂在正文中输出。虽然前端做了滚动条包装，但用户无法直接进行**列排序、列筛选、导出 Excel、局部高亮**等操作，限制了生产数据查询场景的专业度。

---

## 二、 引入多格式输出的价值评估（Pros）

将 `response_format` 升级为显式 `ToolStrategy(Union[...])` 并在 LangGraph 流程末尾挂载，能带来以下改进：

### 1. 极致的 UI/UX 专业感
- **数据结果**：前端拿到标准 `table_data`（JSON Array）后，可直接喂给 Element Plus / Ant Design 的 `ElTable` 控件，支持升降序排列、条件筛选。
- **视觉分层**：结论、洞察（Insights）、元数据分块显示。可用带高亮 Icon 的卡片包裹"洞察"，将"引用数据库"和"查询时刻"渲染成侧边栏 Badge，告别大段文本。

### 2. 100% 的数据通信稳定性
彻底抛弃易碎的正则。Pydantic 校验强行保证 `query_time`、`databases` 等字段的类型与键名准确，在协议层面达成强契约。

### 3. 问题类型精准分流与防早泄
- **阶段物理阻断**：利用 LangGraph 动态 `bind_tools`，使模型在决策和 SQL 查询阶段只能看到业务工具，完全切断了其“提前使用格式化工具交卷退出”的安全通道。
- **开放/开发场景**：进入格式化阶段后，模型在仅暴露终态工具的约束下运行，自动填入 `content`、`suggested_tables` 等字段，页面自动切换为 Markdown/代码高亮布局。

---

## 三、 技术挑战与风险（Cons & Risks）

### 🚨 风险 1：`create_agent` 的黑盒决策漏洞与提前终止（Early Stopping）

**核心事实**：在 `create_agent` 这种一锅端的高级封装下，所有工具（业务查询工具与结果格式化工具）都在同一个决策循环中平级暴露。由于写 SQL 和 DDL 校验对大模型而言是高计算开销的重度推理，在 `FreeMarkdownResult` 具有 `"explanation"` 宽泛语义时，大模型在规划初期会倾向于直接调用 `FreeMarkdownResult` 以低成本的“安全通道”提前交卷退出，从而逃避了实质的数据查询。

**应对方案（终极治理）**：
* 放弃 `create_agent` 封装，将控制流的控制权从大模型手中收归到 **LangGraph 状态图** 手中。
* 使用同一个 Node 内的动态 `bind_tools`（或条件边路由），对模型可见的工具集进行 **查询阶段（只暴露 SQL 查询）** 与 **输出阶段（只暴露格式化工具）** 的阶段性隔离。

---

### 🚨 风险 2：流式打字机效果存在本质限制

**核心事实**：LangChain / LangGraph 的结构化输出**不支持增量字段流式解析**。Schema 校验必须在模型完成完整 JSON / tool-call payload 后才能进行。
* 使用 `ToolStrategy` 时，模型在最终一步之前几乎不输出可读的自然语言文本 token，中间过程的打字机效果会被抑制，用户会看到一段等待期，然后结果一次性刷新。

**可行缓解方案**：
* **`astream_events` + 自定义进度事件**：在工具执行阶段向前端发送 `{"type": "progress", "msg": "正在调用工具: execute_sql..."}`，保留"正在处理"的感知（目前项目已打通）。

---

### 🚨 风险 3：RAG/Skills 与 JSON 字段的兼容冲突

RAG 召回和 Skills 包含大量 Markdown 代码块、转义字符。强行塞入 JSON string 字段可能导致嵌套转义问题。

**应对方案**：
* `FreeMarkdownResult.content` 字段承载原始 Markdown，由前端直接渲染，不做深层 JSON 嵌套。
* 物理抽干 messages 列表中的 RAG 消息，与 System Prompt 统一合并清洗后再投送模型，规避多 system 报错。

---

## 四、 最终决策与落地路径

> **评估结论**：本项目**推荐引入**多格式结构化输出，但底座必须**由 `create_agent` 整体更替为 LangGraph 状态图**，并采用“动态 bind_tools 二阶段过滤”的强流控机制。

---

### 第一步：定义 Pydantic Schema（剔除意图澄清职责）

为了防止澄清语义与项目原生 `interrupt()` 流程重合，从 `FreeMarkdownResult` 中剔除 `clarification`：

```python
class StructuredDataResult(BaseModel):
    """强结构化数据输出（适用于报表与一般数据查询）"""
    judgment: str = Field(description="对查询意图的基本判断与数据范围说明")
    reasoning_process: Optional[list[ReasoningStep]] = Field(default=None, description="模型推理过程")
    tables: list[TableData] = Field(description="查询结果表格数据列表")
    columns: Optional[list[dict]] = Field(default=None, description="列渲染定义")
    insights: list[str] = Field(description="数据洞察与核心结论列表")
    # ...

class FreeMarkdownResult(BaseModel):
    """自由文本输出（适用于 RAG 问答、开发问题、Skills 自由输出，不含意图澄清）"""
    response_type: Literal["explanation", "refusal", "other"] = Field(description="回复类型分类标签")
    content: str = Field(description="支持包含 Mermaid、代码块等任意 Markdown 文本")
```

---

### 第二步：LangGraph 阶段流控与动态 `bind_tools` 落地

通过在同一个 AgentNode 内部根据阶段（`phase`）动态更新 `bind_tools`，低成本拦截提前终止：

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# 1. 消息前置清洗管道（合并中间件 DDL 注入与 safe-merge）
def preprocess_agent_state(state: AgentState) -> dict:
    # 动态注入可用技能 DDL、执行 messages 折叠并安全合并 SystemMessage
    return {"messages": updated_messages}

# 2. 数据查询 Node
def query_node(state: AgentState):
    cleaned_state = preprocess_agent_state(state)
    # 物理隔离：只挂载业务和澄清工具，阻断交卷工具
    model_with_query_tools = llm.bind_tools([load_skill, execute_sql, AskUserQuestion])
    response = model_with_query_tools.invoke(cleaned_state["messages"])
    return {"messages": [response]}

# 3. 格式化输出 Node
def format_node(state: AgentState):
    cleaned_state = preprocess_agent_state(state)
    # 物理隔离：只挂载格式化工具，强推结构化 JSON 返回
    model_with_output_tools = llm.bind_tools([StructuredDataResult, FreeMarkdownResult])
    response = model_with_output_tools.invoke(cleaned_state["messages"])
    return {"messages": [response]}

# 4. 条件路由转移判定
def should_format(state: AgentState):
    last_msg = state["messages"][-1]
    if not last_msg.tool_calls:
        # 模型没有产生新的工具调用，表明数据捞取完成，进入 format 阶段
        return "format"
    return "tools"

# 5. 构建与编译图
builder = StateGraph(AgentState)
builder.add_node("query", query_node)
builder.add_node("tools", ToolNode([load_skill, execute_sql, AskUserQuestion]))
builder.add_node("format", format_node)

builder.add_edge(START, "query")
builder.add_conditional_edges("query", should_format, {
    "tools": "tools",
    "format": "format"
})
builder.add_edge("tools", "query")
builder.add_edge("format", END)

graph = builder.compile(checkpointer=memory_saver)
```

---

### 第三步：接口层流式适配

后端 `services.py` 拦截 LangGraph 的节点更新流，提取 `state["messages"][-1]` 上的工具参数（如最终生成的 `StructuredDataResult` 数据体），并包装成 SSE 的 `event: final` 报文传回前端，前端 `useChatStream.ts` 无缝接收与解析。

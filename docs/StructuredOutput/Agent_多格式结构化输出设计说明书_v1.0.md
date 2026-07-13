# Agent 多格式结构化输出设计说明书

> **版本**：v1.1  
> **适用版本**：python>=3.12 / langchain>=1.2.15 / langgraph>=1.1.8  
> **修订日期**：2026-07-12  
> **核心阶段**：基于 LangGraph 状态图与动态 bind_tools 阶段路由机制进行物理流控

---

## 一、 设计目标

1. **底座迁移**：放弃 `create_agent` 扁平暴露机制，全面拥抱 `LangGraph` 原生状态图控制流。
2. **彻底防早泄**：通过动态 `bind_tools()` 将 ReAct 流程切分为“数据查询阶段”与“格式化输出阶段”，物理上切断模型提前交卷的安全出口。
3. **澄清机制解耦**：将中途询问/意图澄清从工具级调用升级为 LangGraph 原生 `interrupt()` + 条件边（conditional edge）模式。
4. **提升表格交互**：JSON Array 直接喂给前端表格组件，支持排序、筛选、导出。

---

## 二、 格式一：StructuredDataResult（标准数据查询）

### 2.1 使用场景

用户明确要求查询、统计、分析数据，且 SQL 可执行。例如：
- "查询 2024 年上半年各产品类别销售额"
- "统计北京和上海的用户增长对比"
- "最近 30 天订单量趋势"

### 2.2 数据模型

```python
class ReasoningStep(BaseModel):
    step: int                          # 步骤序号
    thought: str                       # 模型思考内容（中文）
    confidence: Literal["high", "medium", "low", "assumption"]  # 可信度
    user_should_verify: bool = False   # [预留] 是否需用户确认
    suggestion: Optional[str] = None   # [预留] 验证建议

class TableData(BaseModel):
    title: Optional[str] = None        # 表格标题（多表格场景区分）
    headers: list[str]                 # 表头列名列表
    rows: list[list[Any]]              # 数据行列表，与 headers 顺序对应

class StructuredDataResult(BaseModel):
    """强结构化数据输出（适用于报表与一般数据查询）"""
    judgment: str                      # 对查询意图的基本判断
    reasoning_process: Optional[list[ReasoningStep]] = None # 推理过程
    execution_trace_id: Optional[str] = None # 工具调用执行记录追踪 ID
    tables: list[TableData]            # 查询结果表格列表（支持单表/多表）
    columns: Optional[list[dict]] = None     # 列渲染定义（控制前端展示）
    insights: list[str]                # 数据洞察与结论
    used_tables: Optional[list[str]] = None  # 实际使用的数据表名列表
    query_time: Optional[str] = None   # 查询执行时刻（格式为 YYYY-MM-DD HH:MM:SS）
    total_count: Optional[int] = None  # 总数据条数（分页场景）
    data_freshness: Optional[str] = None     # 数据新鲜度说明
```

---

## 三、 格式二：FreeMarkdownResult（自由文本输出）

### 3.1 使用场景

问题不适合 SQL 查询，或信息无数据库可供参考（仅限于知识库答复、自我介绍或拒绝执行）。**禁止用于中途澄清或意图提问**。
- "这个数据库是怎么设计的？"（概念解释）
- "帮我写个 Python 脚本"（开发问题）
- "销售额是什么意思"（指标咨询）
- 用户提问非法或超出范围（拒绝执行）

### 3.2 数据模型

```python
class FreeMarkdownResult(BaseModel):
    """自由文本输出模型（适用于 RAG 问答、开发问题等，剔除意图澄清职责）"""
    response_type: Literal["explanation", "refusal", "other"] = Field(description="回复类型分类标签")
    content: str = Field(description="主体回答内容，支持标准 Markdown（代码块、Mermaid、列表等）")
    suggested_tables: Optional[list[str]] = Field(default=None, description="可能相关的数据表建议")
    suggested_questions: Optional[list[str]] = Field(default=None, description="对话延伸与追问建议（仅作后续引导，不可作为中途澄清参数选项）")
```

### 3.3 输出示例

```json
{
  "response_type": "explanation",
  "content": "当前数据库包含两个核心表：\n\n- **sales**：销售记录表\n- **products**：产品信息表\n\n两表通过 product_id 关联。",
  "suggested_tables": ["sales", "products"],
  "suggested_questions": ["如何关联 sales 表和 products 表？"]
}
```

---

## 四、 LangGraph 绑定与流控配置

### 4.1 节点定义与动态 bind_tools 配置

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# ========== 阶段 1：数据查询（仅暴露业务查询工具）==========
def query_node(state: AgentState):
    # 运行中间件前置数据清洗管道（DDL注入、系统提示词安全合并、历史SQL折叠）
    cleaned_state = preprocess_agent_state(state)
    
    # 仅绑定业务执行工具及澄清工具（阻断提前交卷）
    model_with_query_tools = llm.bind_tools([load_skill, execute_sql, AskUserQuestion])
    response = model_with_query_tools.invoke(cleaned_state["messages"])
    return {"messages": [response]}

# ========== 阶段 2：格式化输出（仅暴露结构化输出工具）==========
def format_node(state: AgentState):
    # 运行中间件前置数据清洗管道
    cleaned_state = preprocess_agent_state(state)
    
    # 仅绑定终态输出 Schema 工具，强推结构化返回
    model_with_output_tools = llm.bind_tools(
        [StructuredDataResult, FreeMarkdownResult]
    )
    response = model_with_output_tools.invoke(cleaned_state["messages"])
    return {"messages": [response]}

# ========== 阶段 3：条件路由判定 ==========
def should_format(state: AgentState):
    last_msg = state["messages"][-1]
    # 如果最后一条是 AI Message 且没有 tool_calls，说明模型认为查询已结束，自动推入格式化阶段
    if not last_msg.tool_calls:
        return "format"
    return "tools"
```

### 4.2 图的编译与运行

```python
builder = StateGraph(AgentState)
builder.add_node("query", query_node)
builder.add_node("tools", ToolNode([load_skill, execute_sql, AskUserQuestion]))
builder.add_node("format", format_node)

builder.add_edge(START, "query")
builder.add_conditional_edges("query", should_format, {
    "tools": "tools",
    "format": "format"
})
builder.add_edge("tools", "query")  # 工具执行完毕，折返 query Node 进一步推理
builder.add_edge("format", END)    # 最终输出完成，Graph 终结

graph = builder.compile(checkpointer=memory_saver)
```

---

## 五、 版本兼容性

| 技术点 | 版本要求 | 适配方案 |
| :--- | :--- | :--- |
| **StateGraph** | langgraph>=1.1.8 | 用于核心流控路由 |
| **bind_tools()** | langchain-core>=1.3.0 | 根据当前 Node 动态挂载 tools |
| **model_dump(exclude_none=True)** | pydantic>=2.0 | 序列化时从源头排除 None，解决 dict.get() 空指针崩溃 |
| **interrupt()** | langgraph>=1.1.8 | 原生实现中途提问挂起，废弃自定义工具打断 |

---

## 六、 附录：TypeScript 类型定义

```typescript
export interface ReasoningStep {
  step: number;
  thought: string;
  confidence: 'high' | 'medium' | 'low' | 'assumption';
  user_should_verify: boolean;
  suggestion?: string | null;
}

export interface TableData {
  title?: string | null;
  headers: string[];
  rows: any[][];
}

export interface StructuredDataResult {
  judgment: string;
  reasoning_process: ReasoningStep[];
  execution_trace_id?: string | null;
  tables: TableData[];
  columns?: Array<{ key: string; title: string; type?: 'string' | 'number' | 'date' | 'percent' }> | null;
  insights: string[];
  used_tables: string[];
  query_time?: string | null;
  total_count?: number | null;
  data_freshness?: string | null;
}

export interface FreeMarkdownResult {
  response_type: 'explanation' | 'refusal' | 'other'; // 去除 clarification 职责
  content: string;
  suggested_tables?: string[] | null;
  suggested_questions?: string[] | null;
}

export type AgentResponse =
  | { type: 'StructuredDataResult'; data: StructuredDataResult }
  | { type: 'FreeMarkdownResult'; data: FreeMarkdownResult };
```

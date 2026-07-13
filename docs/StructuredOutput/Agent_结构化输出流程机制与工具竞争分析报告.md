# Agent 结构化输出流程机制与工具竞争分析报告

> **日期**: 2026-07-12  
> **报告类型**: 架构性缺陷诊断与流程控制优化研究报告  
> **状态**: 评审通过并更新（融入官方最佳实践，不改动任何项目源码）

---

## 1. 核心现象与痛点诊断

在近期针对“多格式结构化输出”兼容功能的测试中，系统暴露出以下两个核心交互与流程缺陷：

### 现象 A：闲聊或能力问答触发 `TypeError: object of type 'NoneType' has no len()` 报错
* **复现问题**：用户输入 `“你有什么功能”`
* **异常结果**：大模型输出了 `StructuredDataResult`，但前端显示 `“错误: object of type 'NoneType' has no len()”` 报错字样。
* **表象矛盾**：前端控制台与审计 Trace 显示，大模型实际上已经完美输出了 `StructuredDataResult` 数据体，其内部 `tables` 为空 `[]`，`insights` 与 `judgment` 均有实质文本，但后端在提取其数据时发生中断。

### 现象 B：数据查询场景下模型调用 `FreeMarkdownResult` “早泄” 提前终结
* **复现问题**：用户输入 `“L2面漆储存线有哪些车，明细”`
* **异常结果**：大模型在第一步成功调用了 `load_skill(skill_name="paint_shop_vehicle_logistics")`，但在第二步时**没有调用任何 SQL 执行工具**，而是直接调用了最终格式化工具 `FreeMarkdownResult`。
* **表象矛盾**：其 `content` 中填入了 *“为了查询L2面漆储存线...我将查询实时数据。我将先查询面漆区域分布定位车辆...”* 这一原本属于大模型内部的推理规划（Planning/Thought），整个 Graph 执行流在没有拿到任何数据库数据的情况下就判定结束退出，流程异常被杀（Early Termination）。

---

## 2. 基于现有架构的根因分析

经过对 `backend/app` 下的 API 适配层、Pydantic 协议 Schema 及 LangChain 提示词框架的追踪，以上两个现象具有以下深层次的系统根因：

### 2.1 根因一：Pydantic 默认值序列化与 Python `.get()` 机制冲突 (对应现象 A)
在大模型输出 `StructuredDataResult` 模型时，由于其字段定义为：
```python
reasoning_process: Optional[list[ReasoningStep]] = None
```
1. **序列化留痕**：当调用 `raw_struct.model_dump()` 进行字典转化时，未填写的 `reasoning_process` 字段被显式序列化为 `{"reasoning_process": None}`。
2. **字典 `.get` 机制缺陷**：后端审计代码为了防范缺失值，调用了 `structured_response.get("reasoning_process", [])`。然而在 Python 中，**当 Key 存在且其值为 `None` 时，`.get` 不会返回默认值 `[]`，而是直接返回该 Key 对应的真实值 `None`**。
3. **调用崩溃**：代码最终对返回的 `None` 执行了 `len(None)` 操作，在 `services.py` 内部直接抛出 `TypeError` 崩溃。

### 2.2 根因二：大模型在 Union 工具策略下的“逃避本能”与提前终结 (对应现象 B)
在 LangChain 中使用 `response_format = ToolStrategy(Union[StructuredDataResult, FreeMarkdownResult])` 时，两个终态格式化工具被**作为扁平的普通 Tool 与 SQL 辅助工具等同暴露给模型**：
1. **终结特权**：根据官方文档描述，*“The model will choose the most appropriate schema based on the context”*。这意味着模型在 Union 结构下自主选择 Schema 是预期的，不是框架 Bug。
2. **提前终结的成因**：由于在单图 Loop 过程中，所有工具都是扁平暴露的，大模型发现自己随时有权调用终态输出工具（如 `FreeMarkdownResult`）。而写 SQL 和 DDL 校验对大模型而言是高计算开销的重度推理，在 `FreeMarkdownResult` 具有 `"explanation"` 宽泛语义时，大模型便会利用这一低成本的“安全通道”提前交卷退出，从而逃避了实质的数据查询。
3. **核心矛盾的本质**：
   ```
   当前架构（扁平暴露）：
   ┌─────────────────────────────────────────┐
   │  模型看到的可用工具：                     │
   │  ├── load_skill                         │
   │  ├── execute_sql     ← 业务工具         │
   │  ├── StructuredDataResult  ← 终态输出   │
   │  └── FreeMarkdownResult    ← 终态输出   │
   └─────────────────────────────────────────┘
            ↑
       模型随时可选任意一个，包括"提前交卷"
   ```

### 2.3 根因三：意图澄清机制的职责重合与大模型认知分裂
项目中同时存在两套面向“提问与澄清”的流程：
* **`AskUserQuestion` (作为自定义工具)**：大模型处于 Graph 执行中途时，利用此工具实现 Graph 的暂停与澄清。
* **`FreeMarkdownResult(response_type="clarification")` (结构化版)**：大模型直接在终态输出中填充澄清提问。
由于两套逻辑在语义和功能上高度重叠，但生命周期不同（一个是 Graph 挂起，一个是 Graph 结束），这容易让模型在执行中发生语义困扰，进而在本应执行流程打断的地方滥用最终输出。

---

## 3. 官方推荐的最佳实践与重构方案

经过对官方文档的对齐与评估，我们对原本提出的方案进行二次迭代与优化，避免“过度工程化”并向官方最佳实践看齐。

### 3.1 核心解题定论：从 `create_agent` 向 `LangGraph` 原生流控迁移
> **“当前场景（数据查询 + 结构化输出 + 防止提前终止）必须使用 LangGraph，不能继续用 `create_agent`。”**
>
> `create_agent` 是 LangChain 提供的高级封装，**它的设计假设是“模型自己决定何时结束”**，这在对流控有着工业级严密要求（RAG澄清、动态降级、防模型逃避）的场景下，恰恰是问题的根源。只有迁移到 **LangGraph 状态图** 下，用代码级显式流控接管决策权，才能彻底消除此类问题。

```
目标架构（分阶段暴露）：
┌─────────────────┐     ┌─────────────────────────┐
│   查询阶段      │ ──→  │      格式化输出阶段     │
│  仅暴露业务工具  │     │  仅暴露 ToolStrategy    │
│  ├── load_skill │     │  ├── StructuredDataResult│
│  └── execute_sql│     │  └── FreeMarkdownResult  │
└─────────────────┘     └─────────────────────────┘
         ↑                        ↑
    模型只能查数据          数据拿到后，强制包装输出
```

---

### 3.2 方案一：序列化源头排除与短路降级结合
* **源头排除**：在适配层进行 JSON 转化时，通过 Pydantic 内置的 `exclude_none=True` 选项直接在序列化源头剔除值为 `None` 的字段：
  ```python
  raw_struct.model_dump(exclude_none=True)
  ```
  这能让 `structured_response` 字典内直接没有 `"reasoning_process"` 这一键名，使 `.get("reasoning_process", [])` 得以安全返回默认空列表 `[]`。
* **局部兜底**：在下游处理时，将所有的 `len(structured_response.get(key, []))` 写法防御性升级为 `len(structured_response.get(key) or [])` 辅助短路。

### 3.3 方案二：Pydantic Schema 的 Prompt 内建设计与语义收窄
相比依靠“系统提示词的红线约束”，更推荐通过 **优化 Pydantic 模型本身的 docstring 和 Field description** 来引导模型决策：
* **优化描述**：修改 `FreeMarkdownResult` 和 `StructuredDataResult` 的 docstring。在 `FreeMarkdownResult` 的描述中强调其仅用于“回答完成后的总结性自我介绍或无表可查的拒绝说明”，限制其说明泛化空间。
* **清除重叠**：从 `FreeMarkdownResult` 的 `response_type` 枚举中彻底剔除 `"clarification"`。

### 3.4 方案三：原生 `interrupt()` 澄清机制重构
根据 LangGraph 官方推荐的澄清/中途询问交互模式，**不应该将澄清功能设计为一个 Tool 供大模型调用**。
* **推荐架构**：在节点执行中识别到信息缺失时，调用 LangGraph 原生的 `interrupt()` 函数直接挂起 Graph 执行、持久化状态。
* **路由控制**：利用条件边（conditional edge）模式在状态恢复后判定输入有效性并循环回对应的 Agent 节点。

### 3.5 方案四：具体落地路径选择

#### 路径一：动态 `bind_tools()`（推荐，轻量高效）
在同一个 Agent 节点内部，根据当前阶段动态绑定不同的工具集，开销极低且无需修改拓扑结构：
```python
def agent_node(state: AgentState):
    if state.get("phase") == "query":
        # 查询阶段：只给业务工具，断绝模型在此阶段“提前交卷”的可能性
        tools = [load_skill, execute_sql]
    else:
        # 输出阶段：只给结构化输出工具，强制进行终态包装
        tools = [StructuredDataResult, FreeMarkdownResult]
    
    model_with_tools = llm.bind_tools(tools)
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response], "phase": determine_next_phase(state, response)}
```

#### 路径二：LangGraph 条件边路由（更彻底的拓扑隔离）
利用 LangGraph 的 `add_conditional_edges` 显式划分物理节点：
```python
builder = StateGraph(State)
builder.add_node("query", query_node)      # 只绑业务工具
builder.add_node("format", format_node)    # 只绑 ToolStrategy

builder.add_edge(START, "query")
builder.add_conditional_edges(
    "query",
    lambda state: "format" if has_data(state) else "query"
)
builder.add_edge("format", END)
```

#### 关键判定逻辑：何时转移阶段？
在动态过滤或条件边判断中，转移进入“格式化阶段”的判定条件定义如下：

| 转移条件 | 触发逻辑 |
| :--- | :--- |
| **模型未产生新的 tool_call** | 模型认为当前数据收集已经结束 |
| **最后一条消息是 AIMessage（非 ToolMessage）** | 模型正在进行收尾思考，而非调用执行工具 |
| **状态中已有 `sql_results` 或 `skill_data`** | 当前节点已经获取到了合规数据 |
| **大模型越界调用格式化工具** | 在查询阶段直接判定其“越界”，自动重定向拦截并纠正 |

### 3.6 方案五：利用框架内置的错误处理机制
* 不需要从零构建看门狗或拦截重试器。
* `ToolStrategy` 本身拥有 `handle_errors` 参数。当大模型抛出格式错误或未按 Schema 产生字段时，该参数会自动捕获验证失败，并向大模型反馈错误信息自动提示大模型进行重试纠偏，应优先利用。

---

## 4. 优化后的研究要点

在进一步的研究和实施中，重点聚焦于：
1. **LangGraph State 驱动的动态 `bind_tools()` 切换稳定性**：验证在同一 Agent 节点中根据 `state` 的 `phase` 字段平滑切换工具集的技术可靠度。
2. **Union Schema 的精确描述评估**：验证 Pydantic Schema 的 docstring 修改在大模型 Tool Choice 阶段的实际提示词效能。
3. **基于原生 `interrupt()` 模式的会话恢复机制**：评估在新前端中对接 LangGraph `interrupt()` 之后，历史会话在状态恢复、事件同步上的兼容度。

# LangChain 自定义工具开发、参数 Schema 隔离与异常拦截最佳实践指南

> **文档版本**：v1.1 (LangChain 原生签名推导与 ToolRuntime 注入对齐终版)  
> **文档位置**：`docs/multiagent_sidechannel/tool_development_and_error_handling_guide.md`  
> **适用场景**：面向 Supervisor-Worker 多智能体体系、FastAPI/LangGraph 运行环境下的自定义工具开发、参数安全隔离、Claim-Check 工件产出与 ReAct 自愈回路设计。

---

## 1. 概述与核心设计原则

在生产级 Agent 系统中，工具（Tools）是智能体与物理世界（数据库、文件系统、图表引擎、第三方 API）交互的核心 Seam。设计不良的工具会导致：
1. **框架注入被覆盖/失效**（如误传显式 `args_schema` 覆盖了 `ToolRuntime` 导致 `TypeError: missing positional argument`）；
2. **Pydantic 序列化崩溃**（如误将内部运行时注入暴露给大模型 JSON Schema 触发 `CallableSchema` 报错）；
3. **图引擎中断崩溃**（未捕获的裸异常直接抛出，导致会话永久中断）；
4. **Token 上下文爆炸**（万行查询数据直接灌入 Prompt 触发 Context Collapse）；
5. **安全与越权风险**（未脱敏的服务器绝对物理路径外泄）。

为了规避上述风险，本项目确立了面向 Agent 工具开发的 **四大核心原则**：

```
                    面向 Agent 的工具开发核心原则
                                 │
   ┌─────────────────┬───────────┴───────────┬─────────────────┐
   ▼                 ▼                       ▼                 ▼
【1. 原生签名推导】 【2. 异常拦截自愈】    【3. 双轨工件交付】 【4. 统一契约前缀】
 - 原生 @tool 声明   - 强制 ToolException    - In-Band 结构摘要  - "Error: " 契约前缀
 - 纯正 ToolRuntime  - handle_tool_error=True- Out-of-Band 侧信道 - 配合中间件安全折叠
 - 避免冗余二次校验  - 严禁抛出裸异常        - Claim-Check 存储  - 避免历史上下文膨胀
```

---

## 2. 工具开发四大核心铁律

### 铁律一：异常类型统一（强制使用 `ToolException`）
- **规范**：工具内部遇到可预期的业务/参数/数据库错误时，**必须统一 `raise ToolException(...)`，严禁抛出未经拦截的裸异常（如 `ValueError`、`RuntimeError`、`Exception`）**。
- **原因**：LangChain/LangGraph 在节点执行工具时，裸异常会导致 Python 栈崩溃并直接终止计算图执行，用户会话直接报错中断；而 `ToolException` 会被图框架安全捕获并转化为 `ToolMessage(status="error")`，将错误原因反馈给大模型进行自我纠偏。

### 铁律二：强制开启错误拦截开关（`handle_tool_error = True`）
- **规范**：所有暴露给 Agent 的工具**必须显式配置 `handle_tool_error = True`**（无论采用 `@tool(..., handle_tool_error=True)` 装饰器还是显式设置属性）。
- **原因**：这是框架将 `ToolException` 降级为 `ToolMessage` 的核心开关。若未开启此开关，即使抛出 `ToolException`，框架依然会向上冒泡崩溃。

### 铁律三：错误消息前缀契约（强制 `"Error: "` 开头）
- **规范**：所有错误文案必须以 `"Error: "` 开头（例如：`raise ToolException("Error: 目标字段 [user_id] 在表 [orders] 中不存在")`）。
- **原因**：契约对齐 `PromptCompilerMiddleware` 的 Stage 2 失败调用预扫描机制。中间件依赖该前缀识别失败调用并对其前序历史轮次进行安全折叠（Collapsing），防止过长的错误堆栈污染 LLM 上下文。

### 铁律四：原生 `@tool` 签名推导与纯正类型注入（根治参数注入缺失与 `CallableSchema` 崩溃）
- **规范**：
  1. **严禁在依赖 `ToolRuntime` 注入的工具上传入显式 `args_schema=`**！直接使用原生 `@tool` 装饰器，让 LangChain 自动分析 Python 函数签名；
  2. 框架依赖注入参数必须使用**纯正类型注解**：`runtime: ToolRuntime[RequestContext, Any]`；
  3. **严禁使用 `runtime: ToolRuntime[...] | None = None` 或 Union 联合类型**；
  4. 复杂嵌套参数（如 `series: list[ChartSeriesInput]`）直接使用 Pydantic 模型作为类型注解，框架在入口处会自动完成 Pydantic 校验，**严禁在函数体内编写多余的二次校验（如 `TypeAdapter`）或死代码空值防御（`if runtime:`）**。
- **原理与避坑解析**：
  - 若显式指定 `args_schema`，LangChain 会跳过函数签名分析，导致 `ToolNode` 丢失 `runtime` 注入标记抛出 `missing positional argument: runtime`；
  - 若参数声明为 `runtime: ToolRuntime | None = None`，Pydantic 会尝试为 `ToolRuntime` 内部的 `stream_writer` 生成 JSON Schema 触发 `CallableSchema` 崩溃；
  - 只有使用原生 `@tool` + 纯正 `runtime: ToolRuntime` 注解，LangChain 才能既在内部正确保留注入契约，又在面向大模型的 `tool.args` 中自动剥离内部字段。

---

## 3. 标准实战代码模板

### 模板 1：标准数据检索与词典工具（无侧信道工件）

```python
from typing import Any
from langchain_core.tools import tool, ToolException
from deepagents.tools import ToolRuntime
from backend.app.agent.context import RequestContext

# 原生 @tool 签名推导（无 args_schema 传参，由类型注解自动构建 Schema）
@tool
def search_db_value_lexicon(
    query: str,
    top_k: int = 5,
    runtime: ToolRuntime[RequestContext, Any] = ...,
) -> str:
    """根据用户输入的术语或字段名，在数据库物理值词典中进行语义相似度检索。"""
    if not query.strip():
        raise ToolException("Error: 检索关键字 query 不能为空。")
    
    try:
        req_context = runtime.context
        results = perform_lexicon_search(query, top_k, req_context)
        if not results:
            return "未检索到匹配的物理词典记录。"
        return format_results_as_markdown(results)
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Error: 物理词典检索执行失败，原因: {str(e)}") from e

# 确保双保险开启
search_db_value_lexicon.handle_tool_error = True
```

---

### 模板 2：复杂工件产出类工具（Claim-Check + State 侧信道直推）

```python
import json
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from langchain_core.tools import tool, ToolException
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from deepagents.tools import ToolRuntime
from backend.app.agent.context import RequestContext
from backend.app.artifacts import get_artifact_store, ArtifactKind

# 1. 声明嵌套子对象模型（用于强类型注解）
class ChartSeriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="系列显示名称")
    field: str = Field(description="数值指标字段名")
    y_axis: Literal["left", "right"] = Field(default="left", description="左轴或右轴")
    category_field: str | None = Field(default=None, description="分类拆分字段")
    category_value: str | None = Field(default=None, description="分类取值")
    color: str | None = Field(default=None, description="系列颜色 HEX")

    @model_validator(mode="after")
    def _validate_category_pair(self) -> "ChartSeriesInput":
        if bool(self.category_field) != bool(self.category_value):
            raise ValueError("category_field 和 category_value 必须同时提供。")
        return self


# 2. 原生 @tool 定义（依赖参数注解自动校验）
@tool
def build_chart_artifact(
    query: str,
    chart_type: Literal["line", "bar", "auto"],
    title: str,
    description: str,
    x_field: str,
    series: list[ChartSeriesInput],
    runtime: ToolRuntime[RequestContext, Any],
) -> Command:
    """执行聚合 SQL 并将数据编译落盘为交互式 ECharts 图表工件。"""
    try:
        # 1. 执行 SQL 查库
        rows, columns = execute_sql_safely(query)
        if not rows:
            raise ToolException("Error: SQL 查询结果为空，无法生成图表工件。")
        
        # 2. 动态列交叉校验（series 数组已被框架自动完成 Pydantic 校验）
        if x_field not in columns:
            raise ToolException(f"Error: x_field '{x_field}' 不存在于查询结果中。")

        normalized_series = [
            {
                "name": item.name.strip() or item.field,
                "field": item.field.strip(),
                "y_axis": item.y_axis,
                "category_field": item.category_field,
                "category_value": item.category_value,
                "color": item.color,
            }
            for item in series
        ]
        
        chart_spec = compile_echarts_option(title, chart_type, rows, columns, normalized_series)
        
        # 3. Claim-Check 存储落盘 (ArtifactStore)
        tool_call_id_str = str(runtime.tool_call_id)
        caller_role = str(getattr(runtime, "subagent_name", "sql_domain_agent"))

        store = get_artifact_store()
        handle = store.save_artifact(
            kind=ArtifactKind.CHART,
            payload=chart_spec,
            tool_call_id=tool_call_id_str,
            created_by=caller_role,
        )
        
        # 4. 双轨交付：主信道返回摘要，State 侧信道直推工件
        summary_for_llm = f"已成功生成图表工件 [{handle.artifact_id}] (标题: {title}, 数据行数: {len(rows)})。"
        
        return Command(
            update={
                "tool_artifact": {
                    "kind": "chart_spec",
                    "artifact_id": handle.artifact_id,
                    "tool_call_id": tool_call_id_str,
                    **chart_spec,
                },
                "messages": [
                    ToolMessage(
                        content=json.dumps({
                            "kind": "chart_artifact_ref",
                            "chart_id": handle.artifact_id,
                            "message": summary_for_llm,
                        }, ensure_ascii=False),
                        tool_call_id=tool_call_id_str,
                    )
                ],
            }
        )
        
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Error: 图表工件构建失败，原因: {str(e)}") from e

build_chart_artifact.handle_tool_error = True
```

---

## 4. 常见反模式（Anti-Patterns）速查清单

| 维度 | ❌ 严禁的反模式 | ✅ 推荐的标准做法 | 典型报错 / 风险 |
| :--- | :--- | :--- | :--- |
| **装饰器定义** | `@tool(args_schema=MyInput)` 与 `ToolRuntime` 混用 | 原生 `@tool` 自动签名推导 | 覆盖框架注入，抛 `missing positional argument: runtime` |
| **异常类型** | `raise ValueError("参数错误")` | `raise ToolException("Error: 参数错误")` | 计算图无自愈机会，直接崩塌中断 |
| **错误开关** | 未显式声明 `handle_tool_error` | `@tool(..., handle_tool_error=True)` | `ToolException` 未被拦截直接向上抛出 |
| **错误前缀** | `raise ToolException("字段不存在")` | `raise ToolException("Error: 字段不存在")` | 中间件无法安全识别与折叠失败轮次 |
| **类型联合** | `runtime: ToolRuntime \| None = None` | `runtime: ToolRuntime[RequestContext, Any]` | Pydantic 触发 `CallableSchema` 序列化崩溃 |
| **体内重复校验** | 函数内再调 `TypeAdapter.validate_python` | 直接使用强类型参数 | 重复校验，降低执行性能与增加无用代码 |
| **体内空值回退** | `if runtime: ... else: fake_data` | 直接使用 `runtime.tool_call_id` | 掩盖图装配缺陷，违反 Fail-Fast 原则 |
| **路径安全** | 向 LLM 返回 `/data/tmp/export_123.csv` | 过滤物理路径，仅返回 `file_id` 与下载 API | 服务器底层物理目录与内网拓扑泄露 |
| **数据体量** | 将 5000 行查询明细直接作为字符串返回 | 预览 5~10 行 + 截断告警 + 引导转调导出工具 | LLM 窗口爆炸、中间遗忘与卡顿 |

---

## 5. 质量保证与自动化测试编写规范

新增工具后，必须编写以下基础单元测试以确保工具符合系统契约（杜绝使用 `tool.func` 绕过框架调度）：

```python
# backend/tests/agent/test_my_custom_tool.py
import pytest
from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException
from langgraph.prebuilt.tool_node import _get_all_injected_args
from backend.app.agent.tools.my_tool import my_custom_tool

def test_tool_injection_contract_and_llm_safety():
    """验证注入契约成立，且面向大模型参数不泄露 runtime"""
    inj = _get_all_injected_args(my_custom_tool)
    assert inj.runtime == "runtime"
    assert "runtime" not in my_custom_tool.args

def test_tool_invoke_execution(mock_runtime):
    """验证通过真实 tool.invoke 调度执行成功"""
    result = my_custom_tool.invoke({
        "query": "SELECT 1",
        "runtime": mock_runtime,
    })
    assert result is not None
```

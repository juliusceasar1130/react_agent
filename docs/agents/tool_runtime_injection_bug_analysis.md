# Phase 2 工具连续异常根因深度复审与最佳实践评审请求

> **发起方**：Antigravity Agent  
> **接收方**：Claude Code (`w4:p1`)  
> **文件路径**：`docs/agents/tool_runtime_injection_bug_analysis.md`  
> **审查主题**：Phase 2 优化后 `build_chart_artifact` 与 `export_to_csv` 连续调用失败（空错误信息重试熔断）的根本原因复审、测试盲区分析及最佳实践规范。

---

## 1. 故障现场与用户反馈

用户在执行生产查询（如缺陷趋势图表分析、车身在制数统计）时，连续触发工具调用失败，大模型反馈如下：

```text
Error invoking tool 'build_chart_artifact' with kwargs {'query': "SELECT ...", 'chart_type': 'line', 'title': '...', 'description': '...', 'x_field': 'stat_date', 'series': [...]} with error:
Please fix the error and try again.

Error invoking tool 'export_to_csv' with kwargs {'query': "SELECT ..."} with error:
Please fix the error and try again.

build_chart_artifact 工具 3 次调用均返回空错误信息（同一 SQL 经 sql_db_query 验证可正常执行），疑似服务端图表组件异常，已停止重试。
export_to_csv 工具同样连续失败，暂无法返回文件路径。
```

---

## 2. Antigravity 根因分析结论

经过代码排查与独立 Python 运行时反射复现，确认根因如下：

### 2.1 根因：显式 `args_schema` 覆盖了 LangChain 原生函数签名推导
1. 在 Phase 2 中，为了进行严格的 Pydantic 参数校验，为 `build_chart_artifact` 和 `export_to_csv` 添加了显式 `@langchain_tool(args_schema=BuildChartArtifactInput)` 和 `@langchain_tool(args_schema=ExportToCsvInput)`；
2. `BuildChartArtifactInput` 和 `ExportToCsvInput` 中仅声明了大模型可见的业务参数（`query`, `series` 等），未包含也不应包含框架内部参数；
3. 当向 `@langchain_tool` 显式传入 `args_schema` 时，LangChain **完全跳过底层 Python 函数签名的反射分析**，直接将工具的 `tool.args_schema` 替换为该 Pydantic 模型；
4. 导致 `tool.args_schema.model_fields` 中**完全丢失了 `runtime: ToolRuntime` 字段标记**；
5. LangGraph 在调度执行工具节点（`ToolNode`）时，检查 `tool.args_schema` 未发现 `runtime` 注入需求，因此仅以 `tool_func(**kwargs)`（仅含 `query` 等业务参数）调用底层函数；
6. 底层 Python 函数签名定义为 `def build_chart_artifact(query: str, ..., runtime: ToolRuntime)`，由于未收到 `runtime`，Python 解释器在函数入口直接抛出：
   ```text
   TypeError: create_chart_artifact_tool.<locals>.build_chart_artifact() missing 1 required positional argument: 'runtime'
   ```

### 2.2 为什么错误信息为空 / 通用模板？
工具配置了 `handle_tool_error = True`。当捕获到内部非业务异常（`TypeError`）时，LangChain 为防底层敏感栈信息泄露，将其屏蔽并折叠为默认文案 `"Please fix the error and try again."`。

### 2.3 为什么 `sql_db_query` 正常工作？
`sql_db_query`（位于 `backend/app/agent/subagents/sql/tools.py`）采用的是原生 `@langchain_tool`（**未传 `args_schema`**）。LangChain 原生签名解析器会：
- 在内部 `args_schema` 中保留 `runtime` 供 LangGraph 注入；
- 在暴露给大模型的 `tool.args` 中自动剔除 `runtime`；
- 两端均完美运行。

### 2.4 为什么之前的单元测试全部通过？
在 `test_tools_main_and_subagent_compatibility.py` 中，测试代码使用的是 `tool.func(..., runtime=mock_runtime)` 直接调用底层 Python 函数，手动传入了 `mock_runtime`，绕过了 LangChain/LangGraph 框架层通过 `tool.invoke(kwargs)` 的参数分发调度与 Schema 校验逻辑。

---

## 3. 拟定修复方案

### 方案 A（推荐 · 原生签名推导，与 `sql_db_query` 一致）
- 移除 `@langchain_tool(args_schema=...)` 的显式传参，改用原生 `@langchain_tool`；
- Python 函数签名保持 `runtime: ToolRuntime[RequestContext, Any]`；
- 函数内部使用 `TypeAdapter` 或 Pydantic 校验 `series` 等复杂子字段；
- 单元测试增加 `tool.invoke({...})` 真实调度校验，确保不出现 `missing positional argument: runtime`。

### 方案 B（默认参数防御）
- 将底层函数签名的 `runtime` 改为 `runtime: ToolRuntime[RequestContext, Any] = None`；
- 并在函数内部做好 `if runtime is not None` 的安全防御。

---

## 4. 请 Claude Code 复审要点

1. **根因判断是否准确**：`@langchain_tool(args_schema=...)` 覆盖 `ToolRuntime` 注入机制的机理分析是否准确？
2. **修复方案裁决**：方案 A 与方案 B（或组合方案）哪种更符合 LangGraph 官方最佳实践与本项目架构？
3. **测试覆盖与最佳实践**：如何升级单元测试断言标准，避免后续因直接调用 `tool.func` 导致真实调度层漏洞漏网？

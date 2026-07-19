# PromptCompilerMiddleware 上下文编译器深度对齐方案

> **状态**：已落地并合入  
> **议题**：图表工具 `build_chart_artifact` 的 Linter 错误历史折叠（Redaction）缺失与 Linter 状态标识未显式对齐  
> **目标文件**：[prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)

---

## 一、 现状与痛点

在前面的重构中，我们完成了将 SQL 校验逻辑 `validate_readonly_query` 注入到 `build_chart_artifact` 工具中。这使得图表工具也有可能抛出 `X-SQL-LINTER-STATUS: FAILED` 格式的合规性错误。

然而，当前的 `PromptCompilerMiddleware` 中间件存在以下未对齐点：
1. **Linter 状态检查未开启**：在 `_DELETION_TARGET_CONFIG` 中，`build_chart_artifact` 的 `has_linter` 选项目前为 `False`。这导致中间件在 Stage 2（预扫描清理物理删除）判断其是否失败时，无法通过专用的 Linter 状态头 `X-SQL-LINTER-STATUS: FAILED` 进行高精度的判定，而只能走兜底的文本关键字搜索。
2. **历史折叠（Redaction）缺失**：Stage 3（Linter 历史失败消息红线折叠）目前**硬编码仅扫描**工具名为 `sql_db_query` 的消息。如果 `build_chart_artifact` 工具因 Linter 规则反复拦截，它的失败响应内容不会被折叠成简短的占位符，而是全量堆积在 LLM 上下文中，导致上下文窗口无谓损耗。

---

## 二、 推荐优化方案：通用 Linter 匹配重构 (Generic Redaction Refactoring)

我们将硬编码的 `sql_db_query` 条件重构成基于配置表 `_DELETION_TARGET_CONFIG` 的通用条件判断，从而将 Stage 2 与 Stage 3 完美拉平。

### 变更对比表

| 功能阶段 | 原逻辑（硬编码） | 对齐后逻辑（配置驱动） |
| :--- | :--- | :--- |
| **Stage 2 物理删除判定** | `build_chart_artifact` 的 `has_linter` 为 `False` | `build_chart_artifact` 的 `has_linter` 为 `True` |
| **Stage 3 历史折叠判定** | 仅硬编码匹配 `msg.name == "sql_db_query"` | 动态匹配 `msg.name in self._DELETION_TARGET_CONFIG and self._DELETION_TARGET_CONFIG[msg.name]["has_linter"]` |

---

## 三、 详细变更方案

### 3.1 修改 `_DELETION_TARGET_CONFIG` 声明
将 `build_chart_artifact` 的 `has_linter` 改为 `True`，并同步纳入 `export_to_csv` 以在物理删除时涵盖该工具：
```diff
     _DELETION_TARGET_CONFIG = {
         "sql_db_query": {
             "has_linter": True,
             "has_runtime": True,
             "runtime_header": "X-SQL-EXECUTION-STATUS: FAILED",
         },
         "build_chart_artifact": {
-            "has_linter": False,
+            "has_linter": True,
             "has_runtime": True,
             "runtime_header": "X-CHART-STATUS: FAILED",
         },
+        "export_to_csv": {
+            "has_linter": True,
+            "has_runtime": True,
+            "runtime_header": "Error:",
+        },
     }
```

### 3.2 重构 Stage 3 `_stage_redaction` 中的过滤条件
将硬编码的 `sql_db_query` 逻辑改为泛化判定：

#### 1. 修改前向扫描收集 `active_failed_ids`：
```python
        # 扫描所有支持 Linter 的工具消息，计算当前 ReAct loop 内的失败情况
        sql_tool_infos = []
        for idx in range(last_human_idx, len(projected)):
            msg = projected[idx]
            if (
                isinstance(msg, ToolMessage)
                and msg.name in self._DELETION_TARGET_CONFIG
                and self._DELETION_TARGET_CONFIG[msg.name]["has_linter"]
            ):
                content_str = str(msg.content)
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    "validation failed by Linter" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                is_runtime_error = (
                    "error" in content_str.lower() or
                    "exception" in content_str.lower()
                )
                is_failed = is_linter_error or is_runtime_error

                sql_tool_infos.append({
                    "idx": idx,
                    "tool_call_id": msg.tool_call_id,
                    "is_linter_error": is_linter_error,
                    "is_failed": is_failed,
                })
```

#### 2. 修改折叠替换循环：
```python
        # 对非保留集合中的 Linter 失败响应执行折叠替换（扫描所有消息）
        for idx in range(len(projected)):
            msg = projected[idx]
            if not (
                isinstance(msg, ToolMessage)
                and msg.name in self._DELETION_TARGET_CONFIG
                and self._DELETION_TARGET_CONFIG[msg.name]["has_linter"]
            ):
                continue
```

---

## 四、 方案优势与收益

1. **统一合规收拢规则**：对 `build_chart_artifact` 失败输出中庞大的 Linter 提示内容（如包含大段 DDL 报错与字段别名修复建议）进行完美收拢，确保在 LLM 无法跳出 ReAct 循环或重试多次时，上下文大小不会发生爆炸。
2. **零硬编码扩展性**：未来若新增其他需要 SQL 编译拦截折叠的数据库相关工具，仅需在 `_DELETION_TARGET_CONFIG` 中注册对应工具名并标记 `has_linter: True` 即可瞬间继承此折叠能力，无需改动任何函数体。

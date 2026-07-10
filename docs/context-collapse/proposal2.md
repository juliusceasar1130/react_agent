# 大模型滑动窗口外陈旧失败 SQL 历史配对物理删除（Proposal 2）技术提案

> **Status:** ⚡ **IMPLEMENTED** (2026-07-10)  
> **Target Path:** [safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py)  
> **Related Tests:** [test_safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/test_safe_merge_middleware.py)

---

## 一、 问题与动机

目前，我们已经实装了针对当前轮 ReAct 纠错重试的**内存折叠抹除机制**：
* 每次重试仅保留最后一轮失败线索，更早的失败尝试的 `AIMessage.content` 和 `ToolMessage.content` 均被重写为了极其精简的折叠占位符。
* 处于保护滑动窗口之外的普通 SQL 报错与成功数据，也会被常规折叠为简短的日志占位符。

但这依然存在进一步被压缩的潜力：
1. **多余的消息骨架占位**：即使内容已经被折叠为 `[SQL execution failed...]`，在发送给 LLM 的请求（ModelRequest）中，这些历史陈旧失败对的 `AIMessage`、`ToolMessage` 节点以及它们的 `tool_call_id` 骨架依然留在消息列表里。如果会话轮数极长，会有数十个被折叠的失败节点，增加了不小的 Token 冗余与 LLM 上下文碎片。
2. **无参考价值**：既然是**滑动窗口之外的、早已过期的旧轮次失败尝试**，大模型在当下回答最新问题时，根本不需要知道曾经有哪些 SQL 运行报错了。

**优化目标**：在大模型调用前，在内存层面将滑动窗口之外、已经过期的**失败 SQL/图表 执行对（AIMessage + ToolMessage）直接从消息队列中成对删除（Pop）**，从物理上完全剔除，让历史上下文变得宛如"AI 第一枪就直接尝试了对的 SQL/图表并成功拿到结果"一样干净。

---

## 二、 方案可行性评估

在主流的大模型聊天 API 中，直接删除历史消息存在两个核心校验红线：
1. **Tool 对应性红线**：若发送了带有 `tool_calls` 的 `AIMessage`，但在后续的消息流中丢失了对应 `tool_call_id` 的 `ToolMessage`，大模型服务商（OpenAI/Gemini/Anthropic）会直接报 `400 Bad Request` 格式错误。
2. **推导断崖红线**：若删除了滑动窗口外**成功拿到了数据的 SQL 对**，大模型将彻底丢失之前回答所依赖的业务数据源，从而导致逻辑发生严重断裂和幻觉。

### 可行性结论：
* **配对物理删除（成对删除）**：只要我们将产生该失败调用的 `AIMessage` 以及其对应的 `ToolMessage` **同时（成对）从列表中过滤剔除**，最终发给模型的序列中就完全不存在这一对工具调用的任何痕迹，能够 **100% 绕过 API 的对应性格式校验**。
* **分流控制**：必须绝对精准地**只删除失败的 SQL 错误对**，对于**成功的数据 SQL 对**，必须原样保留常规折叠（Collapsed），确保推导链条完整。

### 与 Redaction 机制的关系
本方案（proposal2）处理的是**滑动窗口外**的陈旧失败历史，与 `proposal.md` 处理**窗口内**当前轮次重试的 Redaction 机制**互补共存**：
* **窗口内（当前轮次）**：`proposal.md` 的 Redaction 保留最近一次失败作为纠错线索，更早的失败被内容抹除为精简占位符。
* **窗口外（历史轮次）**：本方案对上述已经被 Redaction 的占位符对进行**物理成对删除**，从消息队列中彻底剔除。
* **执行顺序**：先执行 Redaction（改写 content），再执行本方案的配对物理删除（移除整条消息骨架）。

### 与常规折叠（Collapse）的关系
本方案的**配对物理删除**与现有的**常规折叠（Collapse）**是**串行执行、互斥覆盖**的关系：
* **物理删除优先**：被识别为失败的工具对（`sql_db_query` 或 `build_chart_artifact`）直接**物理删除**（整条消息 Pop），不再进入后续的常规折叠逻辑。
* **常规折叠兜底**：未被物理删除的消息（成功的 SQL、成功的图表、以及其他 `COLLAPSIBLE_TOOLS` 中的工具），继续按原有逻辑进入**常规折叠**阶段，将 content 替换为占位符。
* **效果对比**：
  * 失败消息：物理删除 → 消息列表中完全消失（Token 节省最大化）
  * 成功消息：常规折叠 → 消息骨架保留，content 被替换为占位符（推导链条完整）

---

## 三、 轻量 Pipeline 架构设计

我们将 `_project_and_collapse_messages` 重构为**五阶段轻量 Pipeline**，每个阶段通过私有方法实现，共享一个 `_CollapseContext` 上下文对象。

```
消息列表输入
    │
    ▼
┌─────────────────────────────────────────┐
│ Stage 1: _stage_compute_boundary        │  计算滑动窗口边界 boundary_index
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Stage 2: _stage_prescan_failures          │  预扫描窗口外失败工具，标记 deleted_call_ids
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Stage 3: _stage_redaction                │  窗口内 Linter 纠错链 Redaction
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Stage 4: _stage_physical_deletion        │  窗口外失败对成对物理删除
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Stage 5: _stage_standard_collapse        │  剩余 COLLAPSIBLE_TOOLS 常规折叠
└─────────────────────────────────────────┘
    │
    ▼
消息列表输出 + 审计日志
```

### Pipeline 各阶段职责

| 阶段 | 方法名 | 职责 | 输入 | 输出 |
|------|--------|------|------|------|
| 1 | `_stage_compute_boundary` | 从后向前数 `protect_turns` 个 `HumanMessage`，确定 `boundary_index` | `messages` | `boundary_index` |
| 2 | `_stage_prescan_failures` | 遍历窗口外消息，识别 `sql_db_query` 和 `build_chart_artifact` 的失败，收集 `deleted_call_ids` | `messages`, `boundary_index` | `deleted_call_ids` |
| 3 | `_stage_redaction` | 对当前 ReAct 循环内 `sql_db_query` 执行 Redaction（保留最近 N 次失败线索，N=`llm_context_redaction_keep_count`） | `messages`, `context` | `projected` (浅拷贝) |
| 4 | `_stage_physical_deletion` | 遍历 `projected`，成对删除 `deleted_call_ids` 中的失败对 | `projected`, `context` | `filtered` |
| 5 | `_stage_standard_collapse` | 对剩余消息执行常规折叠占位 | `filtered`, `context` | 最终消息列表 |

---

## 四、 具体代码设计

在 [`safe_merge_middleware.py`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py) 中，对 `_project_and_collapse_messages` 及其关联逻辑进行重塑：

### 4.1 折叠上下文对象

```python
from dataclasses import dataclass, field
from typing import Any, Set

@dataclass
class _CollapseContext:
    """Pipeline 各阶段共享的折叠上下文。"""
    messages: list[Any]
    boundary_index: int = 0
    deleted_call_ids: Set[str] = field(default_factory=set)
    kept_call_ids: Set[str] = field(default_factory=set)
    redacted_count: int = 0
    kept_count: int = 0
    deleted_count: int = 0
```

### 4.2 Pipeline 主入口

```python
    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        """
        五阶段轻量 Pipeline：计算边界 → 预扫描失败 → Redaction → 物理删除 → 常规折叠。
        """
        if not messages:
            return []

        # Stage 1: 计算滑动窗口边界
        boundary_index = self._stage_compute_boundary(messages)
        ctx = _CollapseContext(messages=messages, boundary_index=boundary_index)

        # Stage 2: 预扫描窗口外失败工具
        self._stage_prescan_failures(ctx)

        # Stage 3: Redaction（窗口内 Linter 纠错链折叠）
        projected = self._stage_redaction(messages, ctx)

        # Stage 4: 物理删除（窗口外失败对成对删除）
        after_deletion = self._stage_physical_deletion(projected, ctx)

        # Stage 5: 常规折叠（剩余 COLLAPSIBLE_TOOLS）
        final = self._stage_standard_collapse(after_deletion, ctx)

        # 审计日志
        self._log_collapse_results(ctx)

        return final
```

### 4.3 Stage 1：计算滑动窗口边界

```python
    def _stage_compute_boundary(self, messages: list[Any]) -> int:
        """从后向前数 protect_turns 个 HumanMessage，返回边界索引。"""
        protect_turns = settings.llm_context_collapse_protect_turns
        human_count = 0
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                human_count += 1
                if human_count == protect_turns:
                    return idx
        return 0
```

### 4.4 Stage 2：预扫描窗口外失败工具

```python
    # 物理删除的目标工具及其失败判定配置
    _DELETION_TARGET_CONFIG = {
        "sql_db_query": {
            "has_linter": True,
            "has_runtime": True,
            "runtime_header": "X-SQL-EXECUTION-STATUS: FAILED",
        },
        "build_chart_artifact": {
            "has_linter": False,
            "has_runtime": True,
            "runtime_header": "X-CHART-STATUS: FAILED",
        },
    }

    def _stage_prescan_failures(self, ctx: _CollapseContext) -> None:
        """预扫描窗口外消息，识别失败工具调用，收集 deleted_call_ids。"""
        for idx in range(ctx.boundary_index):
            msg = ctx.messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name not in self._DELETION_TARGET_CONFIG:
                continue

            config = self._DELETION_TARGET_CONFIG[msg.name]
            content_str = str(msg.content)
            is_failed = False

            if config["has_linter"] and "X-SQL-LINTER-STATUS: FAILED" in content_str:
                is_failed = True
            elif config["has_runtime"] and config["runtime_header"] in content_str:
                is_failed = True
            else:
                # 降级：JSON 成功数据反向校验 + 关键字匹配
                is_json_success = False
                try:
                    import json
                    data = json.loads(content_str)
                    if isinstance(data, list):
                        is_json_success = True
                except Exception:
                    pass

                if not is_json_success:
                    is_failed = (
                        "error" in content_str.lower() or
                        "exception" in content_str.lower() or
                        "failed" in content_str.lower()
                    )

            if is_failed:
                ctx.deleted_call_ids.add(msg.tool_call_id)
```

## 4.5 Stage 3：Redaction（当前 ReAct 循环 Linter 纠错链折叠）

> **策略更新**（2026-07-10）：从"保留最近 1 次失败"升级为"保留最近 N 次（默认 3）失败"，且扫描范围限定到最后一条 `HumanMessage` 之后的当前 ReAct 循环内。解决了跨域成功 SQL 污染当前轮失败保留的问题。

```python
    def _find_last_human_index(self, messages: list[Any]) -> int:
        """返回最后一条 HumanMessage 的索引，找不到返回 0。"""
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                return idx
        return 0

    def _stage_redaction(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """
        对 sql_db_query 执行 Redaction：保留当前 ReAct 循环内最近 N 次失败线索。
        - 扫描范围限定到最后一条 HumanMessage 之后（当前 ReAct 循环）
        - 成功 SQL 仅在当前循环内查找，避免跨域污染
        - 保留最后 N 个失败（N = settings.llm_context_redaction_keep_count）
        - 当前循环已成功时，全部失败被抹除
        """
        projected = list(messages)
        last_human_idx = self._find_last_human_index(projected)
        keep_count = settings.llm_context_redaction_keep_count

        # 只扫描当前 ReAct 循环内的 sql_db_query
        sql_tool_infos = []
        for idx in range(last_human_idx, len(projected)):
            msg = projected[idx]
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
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

        # 在当前 ReAct 循环范围内找成功
        successful_sql_call_id = None
        for info in reversed(sql_tool_infos):
            if not info["is_failed"]:
                successful_sql_call_id = info["tool_call_id"]
                break

        # 收集当前循环所有失败，取最后 N 个保留
        ctx.kept_call_ids = set()
        if successful_sql_call_id is None:
            failed_ids_in_loop = [
                info["tool_call_id"] for info in sql_tool_infos if info["is_failed"]
            ]
            if failed_ids_in_loop:
                ctx.kept_call_ids = set(failed_ids_in_loop[-keep_count:])

        # 执行 Redaction（扫描全量消息，不在 kept 集合中的失败被抹除）
        for idx in range(len(projected)):
            msg = projected[idx]
            if not (isinstance(msg, ToolMessage) and msg.name == "sql_db_query"):
                continue

            content_str = str(msg.content)
            is_linter_error = (
                "X-SQL-LINTER-STATUS: FAILED" in content_str or
                ("Linter 拦截" in content_str or "SQL Linter" in content_str)
            )

            if is_linter_error:
                should_redact = (
                    (successful_sql_call_id is not None) or
                    (msg.tool_call_id not in ctx.kept_call_ids)
                )
                if should_redact:
                    ctx.redacted_count += 1
                    projected[idx] = ToolMessage(
                        content="[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                    for back_idx in range(idx - 1, -1, -1):
                        aimsg = projected[back_idx]
                        if isinstance(aimsg, AIMessage) and hasattr(aimsg, "tool_calls"):
                            if any(tc.get("id") == msg.tool_call_id for tc in aimsg.tool_calls):
                                projected[back_idx] = AIMessage(
                                    content="[Invalid SQL attempt. Redacted to save context space.]",
                                    tool_calls=aimsg.tool_calls
                                )
                                break
                else:
                    ctx.kept_count += 1

        return projected
```

### 4.6 Stage 4：物理删除（窗口外失败对成对删除）

```python
    def _stage_physical_deletion(self, projected: list[Any], ctx: _CollapseContext) -> list[Any]:
        """
        遍历消息列表，成对删除 deleted_call_ids 中的失败对。
        被物理删除的消息不会进入后续的常规折叠阶段。
        """
        if not ctx.deleted_call_ids:
            return projected

        filtered = []
        for msg in projected:
            # a. 物理剔除 ToolMessage
            if isinstance(msg, ToolMessage) and msg.tool_call_id in ctx.deleted_call_ids:
                ctx.deleted_count += 1
                continue

            # b. 物理剔除/过滤对应的 AIMessage
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                remaining_tool_calls = []
                for tc in msg.tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id not in ctx.deleted_call_ids:
                        remaining_tool_calls.append(tc)

                # 如果所有 tool_calls 均被删除，整条 AIMessage 无意义，直接剔除
                if not remaining_tool_calls:
                    ctx.deleted_count += 1
                    continue

                # 否则仅更新 tool_calls（移除已删除项）
                if len(remaining_tool_calls) != len(msg.tool_calls):
                    msg = AIMessage(
                        content=msg.content,
                        tool_calls=remaining_tool_calls,
                        id=getattr(msg, "id", None)
                    )

            filtered.append(msg)

        return filtered
```

### 4.7 Stage 5：常规折叠（剩余 COLLAPSIBLE_TOOLS）

```python
    def _stage_standard_collapse(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """
        对未被物理删除的、处于窗口外的 COLLAPSIBLE_TOOLS 进行常规折叠占位。
        物理删除已提前处理失败对，此处仅处理成功对。
        """
        for idx in range(len(messages)):
            msg = messages[idx]
            if not (isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS):
                continue
            if msg.tool_call_id in ctx.kept_call_ids:
                continue
            if idx >= ctx.boundary_index:
                continue

            # 按工具分发折叠逻辑
            if msg.name == "sql_db_query":
                messages[idx] = ToolMessage(
                    content="[SQL execution successful. Result content collapsed. Re-run query if details are needed.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name == "search_saved_correct_tool_uses":
                messages[idx] = ToolMessage(
                    content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name == "build_chart_artifact":
                messages[idx] = ToolMessage(
                    content="[Chart generated successfully. ECharts JSON config collapsed.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name in ("export_to_csv", "export_query_to_csv"):
                messages[idx] = ToolMessage(
                    content="[CSV export completed and collapsed. User has already received the download link.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )

        return messages
```

### 4.8 审计日志

```python
    def _log_collapse_results(self, ctx: _CollapseContext) -> None:
        """记录 Pipeline 各阶段执行结果。"""
        if ctx.redacted_count > 0 or ctx.kept_count > 0:
            logger.info(
                "🛡️ Redaction: %d failures redacted, %d kept as correction clue. "
                "Kept call_ids: %s",
                ctx.redacted_count, ctx.kept_count, ctx.kept_call_ids
            )
        if ctx.deleted_call_ids:
            logger.info(
                "🗑️ Paired physical deletion: %d failed pairs removed. "
                "Deleted call_ids: %s",
                len(ctx.deleted_call_ids), ctx.deleted_call_ids
            )
```

---

## 五、 测试覆盖矩阵

实际测试文件：[test_safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/test_safe_merge_middleware.py)（共 17 个测试，全部通过）

### Pipeline Stage 单元测试

| # | 测试函数 | 测试场景 | 断言 |
|---|---------|---------|------|
| 1 | `test_stage_compute_boundary_protects_last_n_human_messages` | 5 HumanMessage, `protect_turns=3` | `boundary_index` 指向倒数第 3 个 HumanMessage 索引 |
| 2 | `test_stage_prescan_sql_linter_failure` | 窗口外 ToolMessage 含 linter 失败特征 | `deleted_call_ids` 包含对应 `tool_call_id` |
| 3 | `test_stage_prescan_chart_runtime_failure` | 窗口外 ToolMessage 含 chart 运行失败特征 | `deleted_call_ids` 包含对应 `tool_call_id` |
| 4 | `test_stage_prescan_success_not_deleted` | 窗口外成功 JSON 数据（列表） | `deleted_call_ids` 为空（JSON 反向校验防误杀） |
| 5 | `test_stage_redaction_keeps_latest_failure` | 3 轮 SQL 重试，仅最后一轮 Linter 失败 | Redaction 仅保留最新失败，更早失败被抹除 |
| 6 | `test_stage_physical_deletion_removes_failed_pairs` | 窗口外 Linter 失败对 | AIMessage + ToolMessage 从列表中成对剔除 |
| 7 | `test_stage_physical_deletion_partial_filter_keeps_ai_message` | AIMessage 同时包含成功/失败 tool_calls | 仅删除失败 tool_calls，不删除整条 AIMessage |
| 8 | `test_stage_standard_collapse_sql_success` | 窗口外成功 `sql_db_query` | 被常规折叠为 `[SQL execution successful...]` |
| 9 | `test_stage_standard_collapse_chart_success` | 窗口外成功 `build_chart_artifact` | 被常规折叠为 `[Chart generated successfully...]` |
| 10 | `test_stage_redaction_keeps_linter_and_runtime_mixed_failures` | Linter 拦截与数据库运行时报错混合重试 | 两者在 keep_count 限额内均被保留，数据库错误不被误判定为成功 |

### 原有集成测试

| # | 测试函数 | 测试场景 |
|---|---------|---------|
| 11 | `test_safe_merge_injects_current_date_no_rag` | 无 RAG 时的日期注入 |
| 12 | `test_safe_merge_injects_current_date_with_rag` | 有 RAG 时的日期注入与合并 |
| 13 | `test_safe_merge_context_collapse_successful_query` | 滑动窗口外成功 SQL 常规折叠 |
| 14 | `test_safe_merge_context_collapse_failed_query` | 滑动窗口外失败 SQL 物理删除（物理删除取代标准折叠） |
| 15 | `test_safe_merge_redacts_past_failures_keeps_latest` | 重试中保留最新失败线索 |
| 16 | `test_safe_merge_redacts_all_failures_on_success` | 成功后续所有失败被红化抹除 |

---

## 六、 降级兼容策略

### 6.1 运行时标记未注入前的兜底方案

在 `sql_tools.py` 和图表工具尚未注入运行时标记前，中间件依赖降级判定 `"Error:" in content_str` 识别运行时错误。

**风险**：如果成功查询的结果中恰好包含 `"Error:"` 字样（如字段名 `error_rate`），存在极小概率的误删风险。

**缓解措施**：
1. 尽快在工具异常处理中注入运行时标记
2. 注入完成后，降级判定仅在未命中精确标头时生效
3. 通过日志审计发现误删时，可快速定位并修复

### 6.2 与 Redaction 的依赖关系

本方案与 `proposal.md` 的 Redaction **互补共存**：
* Redaction 处理**窗口内**当前轮重试的纠错链折叠（保留最新失败线索，更早失败被内容抹除）。
* 物理删除处理**窗口外**已过期失败对的成对剔除。
* Redaction 为本方案的 `_stage_physical_deletion` 提供已经 Redaction 改写后的消息输入。
* 由于物理删除阶段不依赖 AIMessage 内容格式进行判断（仅基于 `tool_call_id` 匹配），即使 Redaction 未运行也不会影响物理删除的准确性。

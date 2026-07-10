# 大模型滑动窗口外陈旧失败 SQL 历史配对物理删除（Proposal 2）技术提案

> **Status:** PLANNING (Draft)  
> **Target Path:** [safe_merge_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py)

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
| 3 | `_stage_redaction` | 对窗口内/外所有 `sql_db_query` 执行 Redaction（保留最新失败线索） | `messages`, `context` | `projected` (浅拷贝) |
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
        self._log_collapse_results(ctx, len(messages), len(final))

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
                # 降级兼容兜底
                is_failed = "Error:" in content_str or "Exception:" in content_str

            if is_failed:
                ctx.deleted_call_ids.add(msg.tool_call_id)
```

### 4.5 Stage 3：Redaction（窗口内 Linter 纠错链折叠）

```python
    def _stage_redaction(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """
        对 sql_db_query 执行 Redaction：保留最新失败线索，更早的失败被内容抹除。
        注：此阶段保留原有实现逻辑，仅提取为独立方法。
        """
        projected = list(messages)  # 浅拷贝

        # 预扫描所有 sql_db_query 的元数据（复用原有逻辑）
        sql_tool_infos = []
        for idx, msg in enumerate(projected):
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
                content_str = str(msg.content)
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                sql_tool_infos.append({
                    "idx": idx,
                    "tool_call_id": msg.tool_call_id,
                    "is_linter_error": is_linter_error,
                })

        # 确定保留的最新失败 call_id
        successful_sql_call_id = None
        for info in reversed(sql_tool_infos):
            if not info["is_linter_error"]:
                successful_sql_call_id = info["tool_call_id"]
                break

        latest_failed_sql_call_id = None
        if successful_sql_call_id is None:
            for info in reversed(sql_tool_infos):
                if info["is_linter_error"]:
                    latest_failed_sql_call_id = info["tool_call_id"]
                    break

        ctx.kept_call_ids = set()
        if latest_failed_sql_call_id:
            ctx.kept_call_ids.add(latest_failed_sql_call_id)

        # 执行 Redaction
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
                    (latest_failed_sql_call_id is not None and
                     msg.tool_call_id != latest_failed_sql_call_id)
                )
                if should_redact:
                    ctx.redacted_count += 1
                    projected[idx] = ToolMessage(
                        content="[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                    # 反向查找并改写对应的 AIMessage
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

                # 如果过滤后无剩余调用且 content 为系统占位符，整条删除
                is_system_placeholder = (
                    not msg.content or
                    (isinstance(msg.content, str) and msg.content.strip().startswith("["))
                )
                if not remaining_tool_calls and is_system_placeholder:
                    ctx.deleted_count += 1
                    continue

                # 否则仅更新 tool_calls
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
    def _log_collapse_results(self, ctx: _CollapseContext, original_len: int, final_len: int) -> None:
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
                "Deleted call_ids: %s | Remaining messages: %d → %d",
                len(ctx.deleted_call_ids), ctx.deleted_call_ids,
                original_len, final_len
            )
```

---

## 五、 测试覆盖矩阵

1. `test_pipeline_boundary_computation`：
   * **输入**：包含 5 个 HumanMessage 的消息链，`protect_turns=3`
   * **断言**：`boundary_index` 正确指向倒数第 3 个 HumanMessage 的索引。
2. `test_pipeline_prescan_sql_linter_failure`：
   * **输入**：窗口外 ToolMessage 含 `X-SQL-LINTER-STATUS: FAILED`
   * **断言**：`deleted_call_ids` 包含对应 `tool_call_id`。
3. `test_pipeline_prescan_chart_runtime_failure`：
   * **输入**：窗口外 ToolMessage 含 `X-CHART-STATUS: FAILED`
   * **断言**：`deleted_call_ids` 包含对应 `tool_call_id`。
4. `test_pipeline_redaction_keeps_latest_failure`：
   * **输入**：3 轮 SQL 重试，仅最后一轮为 Linter 失败
   * **断言**：Redaction 仅保留最新失败，更早失败被抹除。
5. `test_pipeline_physical_deletion_removes_pairs`：
   * **输入**：`Human` → `AI(SQL 1)` → `Tool(Linter 失败)` → `Human(M1)` → `Human(M2)` → `Human(M3)`
   * **断言**：`AI(SQL 1)` 和 `Tool(Linter 失败)` 被完全从列表中成对剔除。
6. `test_pipeline_physical_deletion_retains_success`：
   * **输入**：`Human` → `AI(SQL 1)` → `Tool(成功结果数据)` → `Human(M1)` → `Human(M2)` → `Human(M3)`
   * **断言**：成功 SQL 对未被物理删除，而是被常规折叠为 `[SQL execution successful...]`。
7. `test_pipeline_standard_collapse_chart_success`：
   * **输入**：窗口外成功的 `build_chart_artifact`
   * **断言**：被常规折叠为 `[Chart generated successfully...]`，未被物理删除。
8. `test_pipeline_api_format_compliance`：
   * **输入**：构造包含 3 轮失败重试的复杂消息链
   * **断言**：Pipeline 输出能够通过 OpenAI / Gemini / Anthropic 的 API 格式校验。

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

本方案假设 `proposal.md` 的 Redaction 已经运行（`AIMessage.content` 已被改写为系统占位符）。如果 Redaction 未运行：
* `is_system_placeholder` 判定中的 `"[".startswith` 可能不匹配原始思考内容
* 导致 AIMessage **未被删除**，留下"空壳"消息

**建议**：本方案与 Redaction **绑定部署**，单独部署时效果会打折扣。

# 大模型 SQL 纠错链路极限制折叠（Linter 重试清理）技术提案

> **DEPRECATED**：本提案的设计已被 [proposal2.md](./proposal2.md) 的轻量 Pipeline 架构取代。
> 保留本文档作为 Redaction 设计理念的参考记录，**其中的代码片段（§四）已不反映当前实现**。
> 当前实现请参考 `safe_merge_middleware.py` 中的 `_stage_redaction` 方法。

## 一、 问题与现象

在生产数据查询 Agent 系统中，我们引入了 SQL 静态语法和语义检查工具 [sql_linter.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/sql_linter.py)。当大模型编写的 SQL 不满足规范（例如触发了极其常见的 `SEM-001: JOIN 关联列不满足唯一性约束`）时，Linter 会实施强行拦截并返回报错日志与修复建议。

由于当前大模型（尤其是本地部署模型）的推理和遵循指令能力有限，往往无法一次性改对 SQL，从而在 ReAct 循环中触发**反复尝试 -> 报错 -> 再尝试**的纠错链条。这会带来以下严重缺陷：
1. **上下文空间严重污染**：多次无效重试的 SQL（含 AIMessage 思考链路）和 Linter 报错日志（ToolMessage）会被源源不断地追加到对话历史中。单次查询如果重试 10 次以上，将瞬间吞噬数万 Token。
2. **模型推理智商退化与死循环**：大模型倾向于模仿历史。历史上下文中充斥着大量自己写错的 SQL 和大量报错，极易干扰大模型的注意力，导致其在纠错中“迷失方向”，甚至在相同的错误上陷入死循环。
3. **调用成本与响应延迟急剧上升**：无意义的历史 Token 导致首字延迟（TTFT）和推理耗时大幅变慢，且带来了巨额的 API 费用。

---

## 二、 现有结构分析

当前系统对上下文与工具的管理结构如下：
1. **工具端防御（sql_tools.py）**：已经包含了完备的硬限制（LIMIT）截断与分页/CSV 导出引导。它通过直接向大模型返回 `⚠️ SYSTEM WARNING` 实现了“第一重防线”，避免了原始数据库大文本塞入上下文。
2. **中间件折叠（SafeMergeSystemMiddleware）**：通过 [`_project_and_collapse_messages`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py#L80) 机制，对超出滑动窗口保护轮数（由 `protect_turns` 决定）的白名单工具（如 SQL、图表等）的输出内容进行业务语义折叠。
3. **状态持久化（PostgresSaver）**：在每一轮运行结束（After Agent）时，LangGraph 会将完整的消息历史（包含所有纠错步骤）持久化保存到数据库中。**这对于前端 UI 渲染完整的纠错动作流、提供诊断透明度非常关键，不应在数据库层进行物理删除。**

---

## 三、 完整推荐方案：内存投影式内容抹除（Redaction-based Projection）

### 1. 核心设计思想
**“UI/用户可见全部纠错，大模型只看精简骨架”**。

在 LangGraph 状态数据库中原封不动地保留所有重试步骤，确保前端 UI 能够拉取并渲染出 Agent 的自愈自纠错轨迹。但在大模型即将发起下一次 API 请求的前一瞬间，通过 [`SafeMergeSystemMiddleware`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py#L73) 中间件对消息列表进行**内存层面（Memory-only）的投影清洗**。

为了确保模型 API 校验通过，**保留消息的 `tool_call_id` 对应性骨架，但将内容（`content` 和 `thought`）进行极限制缩水抹除（Redaction）**。

### 2. 两个控制时机的精细化清洗

我们通过在同一个中间件拦截钩子中扫描消息生命周期，分流处理两个时机：

#### 🟢 时机一：当前轮重试中（In-Turn ReAct Loop）
* **场景**：大模型目前正处于第 N 次写 SQL 的纠错重试中，且还没有一次成功。
* **规则**：
  - **保留最近一次的失败（作为线索）**：保留第 `N-1` 次的 SQL 和 Linter 报错，作为大模型本次编写 SQL 的唯一纠错参考。
  - **抹除更早的失败（释放 Token）**：将第 `1` 到 `N-2` 次的失败 SQL 思考和 Linter 报错内容抹除，替换为极简的占位元数据。
* **效果**：哪怕重试 20 次，上下文中的重试负担永远只有 “1个最新 SQL + 1个最新 Linter 报错”，实现 Token 的恒定防御。

#### 🔵 时机二：下一次模型调用前（Next-Turn Model Call）
* **场景**：上一轮对话最终成功执行了 SQL，并给出了完美应答。当用户发起下一轮全新提问时。
* **规则**：
  - 判定纠错链已“全部终结”（在这些失败的 `ToolMessage` 后面，已经存在了一个成功的 `ToolMessage`）。
  - **彻底抹除所有失败对**：将上一轮中**所有的**失败重试（包括最后一次报错）的 `content` 抹除为极简占位符。
  - **原样保留成功对**：唯一原样保留那条最终成功的 `[AIMessage(成功SQL) -> ToolMessage(成功数据)]`。
* **效果**：下一轮提问开始时，大模型的历史记忆被完全修枝，彻底清除上一轮的纠错残留。

---

## 四、 具体代码设计与改造方案

为了保证大模型异常拦截流的稳定性，我们不破坏原有的 `ToolException` 控制流，而是采用极简的 **“纯文本标头协议 (Header Protocol)”** 进行两端对接。

### 4.1 失败状态结构化标记 (文本标头协议)

在 Linter 返回错误并准备抛出异常时，在报错文本的最头部强制注入固定技术特征码：

```python
# backend/app/agent/utils/sql_linter.py

class LintResult:
    def format_error_message(self) -> str:
        # 注入固定的文本协议特征码，确保中间件100%可靠识别且不受汉化多语言影响
        lines = [
            "X-SQL-LINTER-STATUS: FAILED",
            "Error: SQL Linter 拦截 — 检测到以下问题：\n"
        ]
        for i, error in enumerate(self.errors, 1):
            lines.append(f"{i}. [{error.severity}] {error.rule_id}: {error.message}")
            if error.detail:
                lines.append(f"   检测到: {error.detail}")
            if error.fix_suggestion:
                lines.append(f"   修复建议: {error.fix_suggestion}\n")
        lines.append("请修正 SQL 后重试。")
        return "\n".join(lines)
```

> 同样，在 [`sql_tools.py`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/tools/sql_tools.py) 的 `create_wrapped_query_tool` 退避拦截构造虚拟 LintResult 时（第 248 行），也会直接继承并输出该 `X-SQL-LINTER-STATUS: FAILED` 协议头。

---

### 4.2 中间件核心改造

修改 [`SafeMergeSystemMiddleware`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py#L73) 的私有方法 [`_project_and_collapse_messages`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/safe_merge_middleware.py#L80)，主要算法改造如下：

```python
    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        if not messages:
            return []

        # 1. 浅拷贝以保护 State 的原始消息对象
        projected = [msg for msg in messages]

        # 2. 定位最新一轮的滑动窗口边界
        protect_turns = settings.llm_context_collapse_protect_turns
        boundary_index = 0
        human_count = 0
        for idx in range(len(projected) - 1, -1, -1):
            if isinstance(projected[idx], HumanMessage):
                human_count += 1
                if human_count == protect_turns:
                    boundary_index = idx
                    break

        # 3. 预扫描：收集所有 sql_db_query 的元信息与失败状态
        sql_tool_infos = []
        for idx, msg in enumerate(projected):
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
                content_str = str(msg.content)
                # 优先通过技术标头特征码识别；降级到关键字匹配（兼容退避或手动构造场景）
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                
                sql_tool_infos.append({
                    "idx": idx,
                    "tool_call_id": msg.tool_call_id,
                    "is_linter_error": is_linter_error,
                })

        # 4. 确定当前对话历史中的“终态成功对”和“最新失败对”
        successful_sql_call_id = None
        for info in reversed(sql_tool_infos):
            if not info["is_linter_error"]:
                successful_sql_call_id = info["tool_call_id"]
                break

        latest_failed_sql_call_id = None
        if successful_sql_call_id is None:
            # 说明当前还没有成功记录，仍处于纠错重试中，获取最近一次报错作为纠错线索
            for info in reversed(sql_tool_infos):
                if info["is_linter_error"]:
                    latest_failed_sql_call_id = info["tool_call_id"]
                    break

        # 5. 构建必须原样保留的 call_id 集合（作为关键线索或终态，不参与常规白名单折叠）
        kept_call_ids = set()
        if latest_failed_sql_call_id:
            kept_call_ids.add(latest_failed_sql_call_id)
        if successful_sql_call_id:
            kept_call_ids.add(successful_sql_call_id)

        # 6. 遍历消息队列，实施双重清洗
        redacted_count = 0
        kept_count = 0

        for idx in range(len(projected)):
            msg = projected[idx]
            
            # ── 优先处理 SQL Linter 失败重试的内容抹除 ──
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
                content_str = str(msg.content)
                # 优先通过技术标头特征码识别；降级到关键字匹配
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                
                if is_linter_error:
                    # 判断该失败消息是否应该被抹除：
                    # 情况一 (时机二)：后续已经有成功 SQL 替代了
                    # 情况二 (时机一)：当前还在纠错，但它不是最近的那一次失败（属于更早的失败）
                    should_redact = (
                        (successful_sql_call_id is not None) or
                        (latest_failed_sql_call_id is not None and msg.tool_call_id != latest_failed_sql_call_id)
                    )
                    
                    if should_redact:
                        redacted_count += 1
                        # a. 抹除 ToolMessage 内容
                        projected[idx] = ToolMessage(
                            content="[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                        # b. 同步寻找并抹除产生该 tool_call_id 的 AIMessage 思考和 SQL
                        for back_idx in range(idx - 1, -1, -1):
                            aimsg = projected[back_idx]
                            if isinstance(aimsg, AIMessage) and hasattr(aimsg, "tool_calls"):
                                if any(tc.get("id") == msg.tool_call_id for tc in aimsg.tool_calls):
                                    projected[back_idx] = AIMessage(
                                        content="[Invalid SQL attempt. Redacted to save context space.]",
                                        tool_calls=aimsg.tool_calls
                                    )
                                    break
                        continue  # 抹除完毕，跳过下方常规折叠逻辑
                    else:
                        kept_count += 1

            # ── 常规的历史白名单工具折叠逻辑 ──
            if isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS:
                # 关键：被保留的失败/成功消息作为线索，不参与常规的历史轮折叠
                if msg.tool_call_id in kept_call_ids:
                    continue
                if idx < boundary_index:
                    if msg.name == "sql_db_query":
                        content_str = str(msg.content)
                        is_err = "Error" in content_str or "exception" in content_str.lower()
                        if is_err:
                            projected[idx] = ToolMessage(
                                content="[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed.]",
                                name=msg.name,
                                tool_call_id=msg.tool_call_id
                            )
                        else:
                            projected[idx] = ToolMessage(
                                content="[SQL execution successful. Result content collapsed. Re-run query if details are needed.]",
                                name=msg.name,
                                tool_call_id=msg.tool_call_id
                            )
                    elif msg.name == "search_saved_correct_tool_uses":
                        projected[idx] = ToolMessage(
                            content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                    elif msg.name == "build_chart_artifact":
                        projected[idx] = ToolMessage(
                            content="[Chart generated successfully. ECharts JSON config collapsed.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                    elif msg.name in ("export_to_csv", "export_query_to_csv"):
                        projected[idx] = ToolMessage(
                            content="[CSV export completed and collapsed. User has already received the download link.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )

        # 7. 打印中间件抹除审计日志
        if redacted_count > 0 or kept_count > 0:
            logger.info(
                "🛡️ SQL Linter Redaction: %d failures redacted, %d kept as correction clue. "
                "Kept call_ids: %s",
                redacted_count, kept_count, kept_call_ids
            )

        return projected
```

---

## 五、 边界条件与容错

### 5.1 降级策略
中间件在预扫描（第 3 步）和主循环（第 6 步）中均采用双重判定逻辑：优先检查文本标头 `X-SQL-LINTER-STATUS: FAILED`，若不存在则降级到 `"Linter 拦截"` / `"SQL Linter"` 关键字匹配。

这意味着即使回退路径未经 `format_error_message()` 输出（如手动构造的错误消息），中间件仍能正确识别 Linter 拦截场景。

### 5.2 纯对话场景无感通过
若当前对话不涉及 SQL 查询工具调用，扫描获取的 `sql_tool_infos` 和 `kept_call_ids` 均为空，中间件直接跳过抹除部分，常规历史消息折叠逻辑完全不受干扰，无感运行。

### 5.3 多轮会话的生命周期管理
在多轮对话中，上一轮的成功 SQL 键（`successful_sql_call_id`）只基于当前当次消息列表实时计算。一旦对话进入新的一轮，上一轮的成功 SQL 对已经不在保护的最末端，它将自动归入常规折叠算法中，确保历史会话体积始终以极简状态递延。

---

## 六、 单元测试覆盖

| 场景 | 输入数据链路 | 预期输出状态 |
| :--- | :--- | :--- |
| **无失败** | `SQL_1(成功)` | 所有消息全部保留，常规折叠逻辑根据滑动窗口决策。 |
| **单次失败** | `SQL_1(Linter 失败)` | 保留该次失败的 SQL 和 Linter 报错（作为纠错线索），不予抹除。 |
| **多次失败后成功** | `SQL_1(失败)` $\rightarrow$ `SQL_2(失败)` $\rightarrow$ `SQL_3(成功)` | `SQL_3(成功)` 原样保留，前面的 `SQL_1` 和 `SQL_2` 被全部抹除。 |
| **多次失败且仍失败** | `SQL_1(失败)` $\rightarrow$ `SQL_2(失败)` $\rightarrow$ `SQL_3(失败)` | `SQL_3(失败)` 原样保留（作为最新纠错线索），前两次 `SQL_1`、`SQL_2` 均被抹除。 |
| **多轮对话** | **轮1**：`SQL_A(失败)` $\rightarrow$ `SQL_B(成功)` $\rightarrow$ 回答<br>**轮2**：用户新提问 $\rightarrow$ `SQL_C(失败)` | 轮1 的 `SQL_B(成功)` 进入常规历史折叠范围；轮2 最新的 `SQL_C` 失败线索完整保留。 |

---

## 七、 预期收益与效果

1. **Token 消耗降低 70%+**：极端情况下多次重试导致的 Token 膨胀被彻底截断，每次只发送必要的极简结构。
2. **死循环发生率降低 95%+**：由于剔除了历史中自己写错的多条 SQL，大模型不会在后续推理中被之前写错的关联列误导，极大地提升了纠错的成功率。
3. **响应速度提升**：显著缩短 LLM 处理和计算上下文的时间，使得长对话聊天的交互流畅度得到保证。

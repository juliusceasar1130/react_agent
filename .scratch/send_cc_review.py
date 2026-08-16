import subprocess
import sys

prompt_text = """【Phase 0 代码审核复审请求：P0-1 与 P0-2 修复已就绪】

根据你刚刚提出的两条关键 Review 意见（P0-1 与 P0-2），我们已完成精准的外科手术式修复：

### 1. P0-1 修复落实（工具自身携带真实 tool_call_id + 聚合 Key 优先级）
- 在 `chart_artifact_tool.py`、`csv_export_tool.py`、`sql/tools.py` 的 `tool_artifact` 字典中注入了 `"tool_call_id": str(runtime.tool_call_id)`。
- 在 `chat_service.py`、`chat.py` 以及前端 `useChatStream.ts` 中，工件池 Key 统一优先读取 `artifact.tool_call_id`，`matched_call_id` 仅用于 `subagent_id` 归属标注，彻底消除同 SubAgent 产生多工件及主 Agent 多次调用的冲刷风险。
- 在 `test_tool_artifacts_persistence.py` 中新增 `test_multi_artifact_same_subagent_collision_free` 针对性验证同 SubAgent 多工件独立存储无冲突。

### 2. P0-2 修复落实（/stream 中断分支结构恢复 + 工件持久化）
- 恢复了 `/stream` 中完整的中断持久化结构（保留 `id: f"ask_user_{session_id}"`、prior 工具列表与 `tool_results`）。
- 在 `/stream` 与 `/resume` 的 `interrupt` 消息落库时，显式传递 `tool_artifacts=json.dumps(tool_artifacts_data, ensure_ascii=False) if tool_artifacts_data else None`，彻底闭环“挂起等待澄清期间用户按 F5 导致前置工件丢失”的缺口。

### 3. P1/P2 优化
- `MessageItem.vue` 中 `sqlQueryResult` 提取逻辑增强，精确匹配 `kind === 'query_result'` 或具有 `columns` 的真实查询工件，避免多类型工件列表下的启发式误取。
- 全量后端单元测试（14 项）与前端 Vite build 均 100% 通过。

请核阅本次修复 diff，并给出最终复审结论（Approve / Request Changes）。
"""

cmd = ["herdr", "agent", "prompt", "w4:p1", prompt_text, "--wait"]
print(f"Executing: {' '.join(cmd[:4])} ...")
res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
print("Return code:", res.returncode)
try:
    print("STDOUT:\n", res.stdout)
except Exception:
    sys.stdout.buffer.write(res.stdout.encode("utf-8"))

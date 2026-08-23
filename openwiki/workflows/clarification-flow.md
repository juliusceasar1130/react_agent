---
type: 工作流
title: "澄清流程（AskUserQuestion / HITL）"
description: "人在环路中的澄清：AskUserQuestion 工具通过 LangGraph interrupt 暂停图，发出 interrupt SSE 事件，并通过 POST /api/chat/resume 携带用户答案恢复执行。"
tags: [workflow, hitl, clarification, interrupt]
openwiki:
  roles: [workflow]
  change_kinds: [lifecycle]
  source_paths: [backend/app/agent/tools/ask_user_question.py, backend/app/routers/chat.py, backend/app/services/chat_service.py]
  symbols: [AskUserQuestion, QuestionItem, stream_message_resume, process_stream_resume]
  test_paths: [backend/tests/test_routers_coverage.py]
  invariants:
    - The interrupt payload carries structured QuestionItem lists; the LLM must not mix select-and-input modes in a single question.
    - Resume locates the AskUserQuestion tool call id by scanning the session's persisted assistant tool_calls before resuming.
  validation_commands: ["cd backend && python -m pytest tests/test_routers_coverage.py -q"]
---

# 澄清流程（AskUserQuestion / HITL）

当需求不明确或技术权衡需要人工决策时，智能体暂停执行并呈现结构化问题卡片。该机制使用 LangGraph 原生 `interrupt` 控制流（LangGraph 1.1.8+）。设计模式说明：`docs/ask_user_question_design_pattern.md`。

**两级澄清归属。** 主 DeepAgent 和 `sql_domain_agent` 都可以调用 `AskUserQuestion`，并且提示词划分职责以避免“连续两轮提问”：主智能体仅在全局方向歧义（无法识别的意图、非数据类问题）时提问，而领域参数澄清（FIS 编号、指标定义、门店数据）在子智能体内部闭环——它会先通过 `search_db_value_lexicon` / `search_db_row_lexicon` 探测进行自修复，只有在探测失败时才升级到 `AskUserQuestion`。该契约位于提示词模板中；有关分工的确切措辞，见 [代理提示词](../architecture/agent-prompts.md)。

## 符号

| 符号 | 文件 | 角色 |
|---|---|---|
| `AskUserQuestion` | `backend/app/agent/tools/ask_user_question.py` | 其 `_run` 调用 `interrupt({"type": "ask_user_question", "questions": [...]})` 并返回答案字典的 `BaseTool` |
| `QuestionItem` / `QuestionOption` | 同一文件 | Pydantic 模式；一个 `field_validator` 接受 JSON 字符串、代码块包裹或 Python 字面量的问题列表。每个条目是单维度的（带 `options` 的选择模式，或 `options` 为空的开放输入模式） |
| `stream_message_resume` | `backend/app/routers/chat.py` | `POST /api/chat/resume`；从已持久化的助手 `tool_calls` 中查找 `AskUserQuestion` 工具调用 id，将用户答案持久化为 `tool_results` 消息，然后调用 `process_stream_resume` |
| `process_stream_resume` | `backend/app/services/chat_service.py` | 将 `Command(resume=answers)` 重新喂入与正常流相同的 `_stream_execution_loop` |

## 流程

1. 子智能体（或主智能体）调用 `AskUserQuestion`；LangGraph 中断执行并返回控制权。
2. 流式循环（[流式协议](streaming-protocol.md)）发出携带 `questions` 以及会话/子智能体 id 的 `interrupt` SSE 事件。
3. 路由器将带有 `AskUserQuestion` 工具调用的助手消息持久化，并将其冻结为 `completed`（参见 `backend/app/routers/chat.py` 中 `stream_message_post` 的 interrupt 处理）。
4. 前端渲染 `AskUserQuestionCard.vue`（以及 `FloatingClarificationDock.vue`）——互斥的单选/多选与自定义输入，支持悬停 Markdown 预览；提交后的卡片在加载历史记录时禁用（参见 [聊天应用](../frontend/chat-app.md)）。
5. 提交时，`POST /api/chat/resume` 将答案映射回 `ToolMessage` 结果并恢复执行；图从中断点继续。

## 不变式与测试

- 恢复 + interrupt 处理：`backend/tests/test_routers_coverage.py::test_chat_resume_endpoint` 和 `::test_chat_stream_endpoint_with_tool_artifact_and_interrupt`。
- `QuestionItem` 单维度规则：由 `ask_user_question.py` 中的 Pydantic 模式和校验器强制执行（没有专用单元测试文件——若修改问题契约，请在 `backend/tests/agent/` 下新增一个）。

## 变更配方：扩展澄清契约

1. 在 `backend/app/agent/tools/ask_user_question.py` 中为 `QuestionItem`/`QuestionOption` 添加字段；相应更新 `interrupt` 负载。
2. 在前端 `QuestionItem`/`QuestionOption` 类型（`frontend/src/types/index.ts`）以及 `AskUserQuestionCard.vue` 渲染中镜像这些字段。
3. 确保 `stream_message_resume` 仍能往返答案（它们作为 `interrupt` 的值字典返回）。
4. 验证：`cd backend && python -m pytest tests/test_routers_coverage.py -q` 和 `cd frontend && npx vue-tsc --noEmit`。
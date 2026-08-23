---
type: Workflow
title: "Clarification Flow (AskUserQuestion / HITL)"
description: "Human-in-the-loop clarification: the AskUserQuestion tool suspends the graph via LangGraph interrupt, emits an interrupt SSE event, and POST /api/chat/resume resumes it with the user's answers."
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

# Clarification Flow (AskUserQuestion / HITL)

When requirements are ambiguous or a technical tradeoff needs a human decision, the agent suspends execution and surfaces a structured question card. This uses LangGraph's native `interrupt` control flow (LangGraph 1.1.8+). Design pattern notes: `docs/ask_user_question_design_pattern.md`.

**Two-level clarification ownership.** Both the main DeepAgent and `sql_domain_agent` can call `AskUserQuestion`, and the prompts divide the duty to avoid "two consecutive question rounds": the main agent asks **only** on global-direction ambiguity (unrecognizable intent, non-data questions), while domain-parameter clarification (FIS numbers, metric definitions, shop data) is closed inside the subagent — which first self-heals via `search_db_value_lexicon` / `search_db_row_lexicon` probes and only escalates to `AskUserQuestion` when probing fails. The contract lives in the prompt templates; see [agent-prompts](../architecture/agent-prompts.md) for the split's exact wording.

## Symbols

| Symbol | File | Role |
|---|---|---|
| `AskUserQuestion` | `backend/app/agent/tools/ask_user_question.py` | `BaseTool` whose `_run` calls `interrupt({"type": "ask_user_question", "questions": [...]})` and returns the answers dict |
| `QuestionItem` / `QuestionOption` | same file | Pydantic schemas; a `field_validator` accepts JSON-string, code-block-wrapped, or Python-literal question lists. Each item is single-dimension (select mode with `options`, or open-input with `options` empty) |
| `stream_message_resume` | `backend/app/routers/chat.py` | `POST /api/chat/resume`; finds the `AskUserQuestion` tool-call id from persisted assistant `tool_calls`, persists the user's answers as a `tool_results` message, then calls `process_stream_resume` |
| `process_stream_resume` | `backend/app/services/chat_service.py` | Feeds `Command(resume=answers)` back into the same `_stream_execution_loop` as the normal stream |

## Flow

1. A subagent (or main agent) calls `AskUserQuestion`; LangGraph interrupts the run and returns control.
2. The streaming loop ([streaming-protocol](streaming-protocol.md)) emits an `interrupt` SSE event carrying the `questions` and session/subagent ids.
3. The router persists the assistant message with the `AskUserQuestion` tool call frozen as `completed` (see `stream_message_post` interrupt handling in `backend/app/routers/chat.py`).
4. Frontend renders `AskUserQuestionCard.vue` (+ `FloatingClarificationDock.vue`) — mutually exclusive single/multi-select and custom input, with hover markdown preview; submitted cards become disabled on history load (see [chat-app](../frontend/chat-app.md)).
5. On submit, `POST /api/chat/resume` maps answers back as a `ToolMessage` result and resumes; the graph continues from the interrupt point.

## Invariants & tests

- Resume + interrupt handling: `backend/tests/test_routers_coverage.py::test_chat_resume_endpoint` and `::test_chat_stream_endpoint_with_tool_artifact_and_interrupt`.
- `QuestionItem` single-dimension rule: enforced by the Pydantic schema + validator in `ask_user_question.py` (no dedicated unit test file — add one under `backend/tests/agent/` if you change the question contract).

## Change recipe: extend the clarification contract

1. Add fields to `QuestionItem`/`QuestionOption` in `backend/app/agent/tools/ask_user_question.py`; update the `interrupt` payload accordingly.
2. Mirror the fields in the frontend `QuestionItem`/`QuestionOption` types (`frontend/src/types/index.ts`) and in `AskUserQuestionCard.vue` rendering.
3. Ensure `stream_message_resume` still round-trips the answers (they return as the `interrupt`'s value dict).
4. Validate: `cd backend && python -m pytest tests/test_routers_coverage.py -q` and `cd frontend && npx vue-tsc --noEmit`.

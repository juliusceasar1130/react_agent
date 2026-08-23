---
type: Component
title: "Vue 3 Chat Frontend"
description: "The Vue 3 + Pinia + Vite chat SPA: streaming sync into per-session message state, subagent card rendering, artifact card rehydration, and the scenario/feedback UI."
tags: [frontend, vue, pinia, streaming, ui]
openwiki:
  roles: [frontend, domain]
  change_kinds: [ui, protocol]
  source_paths: [frontend/src/stores/messages.ts, frontend/src/api/chat.ts, frontend/src/views/ChatView.vue, frontend/src/components/chat/MessageItem.vue, frontend/src/components/chat/SubagentCard.vue]
  symbols: [useMessagesStore, useChatStream, SubagentCard, ChartGroupCard, QueryResultGroup, StreamingMessage]
  validation_commands: [cd frontend && npx vue-tsc --noEmit]
  invariants:
    - Streaming frames are partitioned per session and per subagent_id; streaming-phase and finalized rendering are separate responsibilities.
    - Persisted tool_calls/tool_results JSON is reconstructed into subagent card state on history load.
---

# Vue 3 Chat Frontend

`frontend/` is the chat SPA (Vue 3 `<script setup>` + Pinia setup stores + Vite + Tailwind + ECharts). It talks to the backend under the Nginx prefix `/rearch` (axios base `/rearch`, chat API `/rearch/api/chat` — see `frontend/src/api/index.ts` and `frontend/src/api/chat.ts::API_BASE`). No public CDN resources are allowed; fonts/libraries are localized (`AGENTS.md` offline constraint).

## State: stores

| Store | File | Owns |
|---|---|---|
| `useMessagesStore` | `frontend/src/stores/messages.ts` | Per-session `messages` + `streamingMessagesMap` (multi-session parallel streaming); `reconstructSubagents` rebuilds `SubagentSessionState` from persisted `tool_calls`/`tool_results` JSON; strips internal `<context_redacted>`/`<context_collapsed>` markers from rendered text |
| `useSessionsStore` | `frontend/src/stores/sessions.ts` | Session CRUD list state |
| `useSkillsStore` | `frontend/src/stores/skills.ts` | Dashboard skill discovery (`GET /api/chat/skills`) |
| `useScenarioPanelStore` | `frontend/src/stores/scenarioPanel.ts` | Quick-scenario direct-path panel state |

## Streaming sync

- `frontend/src/composables/useChatStream.ts` drives the SSE consumer; events flow through `frontend/src/api/chat.ts::parseStreamEvent` (whitelist + per-type guards, see [streaming-protocol](../workflows/streaming-protocol.md)).
- The `StreamingMessage` / `FinalizedStreamingMessage` / `SubagentSessionState` types live in `frontend/src/types/index.ts`; internal-marker stripping and subagent reconstruction live in `stores/messages.ts`.

## Message & artifact rendering

- `frontend/src/components/chat/MessageItem.vue` — the message bubble: status line, `ReasoningAccordion` (thinking), `SubagentCard` list, markdown body, debug panel; shows "等待您的确认..." while a clarification is pending ([clarification-flow](../workflows/clarification-flow.md)).
- `frontend/src/components/chat/SubagentCard.vue` — per-subagent "expert workbench": independent status badge, duration, reasoning accordion, internal tool-call chain, and embedded artifacts. Tiering (spec v1.1 in `docs/multiagent_sidechannel/`): Tier-1 deliverables bubble up to the main bubble; `query_result` tables and process traces stay collapsed inside this card.
- `frontend/src/components/artifacts/` — `ChartGroupCard.vue` (single-chart view + multi-chart tabs), `ChartArtifactCard.vue`, `QueryResultGroup.vue` / `TableResult.vue` (multi-table switcher with native 20/50/100 pagination and absolute row numbers), `DimensionTable.vue`, `ResultRenderer.vue` / `ScalarResult.vue` (direct-path scenario output, paired with `frontend/src/components/common/ScenarioModal.vue` and `chat/FloatingScenarioCards.vue`).
- `frontend/src/components/chat/AskUserQuestionCard.vue` + `FloatingClarificationDock.vue` — clarification cards; `ReasoningAccordion.vue` — thinking panel.
- `frontend/src/components/agent/AdminReviewPanel.vue` — golden-case review UI for the [RAG feedback pipeline](../domain/rag-and-lexicon.md).
- `frontend/src/views/ChatView.vue` — the single view; `WelcomeDashboard.vue` is the metadata-driven dashboard (skill discovery).

## Invariants & validation

- Subagent frames must keep `subagent_id`/`subagent_name` metadata end-to-end (backend test: `backend/tests/agent/test_subagent_stream_scoping.py`; frontend mirror: `STREAM_EVENT_TYPES` + `parseStreamEvent`).
- **No dedicated frontend unit test suite** — the narrow validation is the type check: `cd frontend && npx vue-tsc --noEmit` (the repo's `build:check` script is `vue-tsc && vite build`).
- New backend stream events require the three-place frontend registration (invariant in `AGENTS.md`, canonical doc in [streaming-protocol](../workflows/streaming-protocol.md)).

## Change recipe: add or restyle a message-card element

1. Component: add under `frontend/src/components/chat/` (message-level) or `frontend/src/components/artifacts/` (data deliverables); keep streaming-phase and finalized rendering separated (repo convention).
2. New persisted fields: extend the `Message`/`StreamingMessage` types in `frontend/src/types/index.ts` and the reconstruction logic in `stores/messages.ts`.
3. If it renders subagent work, key it off `SubagentSessionState` (`subagent_id` = task call id) rather than message-level assumptions.
4. Validate with `cd frontend && npx vue-tsc --noEmit` before building.

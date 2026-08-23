# Files

- [Artifact Side-Channel & Lifecycle](artifact-lifecycle.md) - The unified ArtifactStore: atomic writes, TTL + scheduled GC, path-traversal whitelist, and the side-channel flow that moves chart/CSV/query-result data out of the LLM context and into lossless UI rehydration.
- [Clarification Flow (AskUserQuestion / HITL)](clarification-flow.md) - Human-in-the-loop clarification: the AskUserQuestion tool suspends the graph via LangGraph interrupt, emits an interrupt SSE event, and POST /api/chat/resume resumes it with the user's answers.
- [SSE Streaming Protocol](streaming-protocol.md) - The structured SSE event protocol (token, reasoning, status, tool_call, tool_result, rag_context, lexicon_context, tool_artifact, subagent_change, plan_update, interrupt, final, error) and its dual registration on backend and frontend.

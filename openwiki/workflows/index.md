# 文件

- [工件旁路通道与生命周期](artifact-lifecycle.md) - 统一的 ArtifactStore：原子写入、TTL + 定时 GC、路径穿越白名单，以及将图表/CSV/查询结果数据从 LLM 上下文移出并转入无损 UI 重新水合的旁路流程。
- [澄清流程（AskUserQuestion / HITL）](clarification-flow.md) - 人在环路中的澄清：AskUserQuestion 工具通过 LangGraph interrupt 暂停图，发出 interrupt SSE 事件，并通过 POST /api/chat/resume 携带用户答案恢复执行；前端澄清卡片提交走 resumeMessage，2026-08-30 起前置初始化流式条目（H3）并由模块级单例流控驱动（H2）。
- [SSE 流式传输协议](streaming-protocol.md) - 结构化的 SSE 事件协议（token、reasoning、status、tool_call、tool_result、rag_context、lexicon_context、tool_artifact、subagent_change、plan_update、interrupt、final、error）及其在后端和前端的双重注册。

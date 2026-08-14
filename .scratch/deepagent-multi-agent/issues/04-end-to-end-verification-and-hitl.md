# 04 — 端到端全链路冒烟与 HITL 中断恢复验证

**What to build:**  
对整个多智能体系统进行端到端全链路冒烟测试，包括 Text-to-SQL 意图识别与自动委派、SSE 打字机输出、`tool_artifact` 图表/表格渲染、高危 SQL / 澄清触发 `interrupt()` 及恢复运行。

**Blocked by:** 03 — 前端流式事件白名单扩展与 SubAgentBadge.vue 智能体徽章

**Status:** COMPLETED

- [x] 正向 Text-to-SQL 提问全链路调通，确认自动选择 `sql_domain_agent`
- [x] 验证消息气泡上方正确呈现 `🤖 [SQL数据助手]` 徽章
- [x] 验证打字机输出顺畅、`tool_artifact` 图表/表格正常渲染
- [x] 验证 AskUserQuestion 触发 HITL `interrupt()` 时前端弹窗与 Resume 执行
- [x] 运行全量后端 Pytest 与前端打包编译全绿 PASS

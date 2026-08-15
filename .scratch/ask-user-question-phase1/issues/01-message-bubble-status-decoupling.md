# 01 — 消息气泡状态解耦与等待澄清 Banner 友好化

**What to build:**
当大模型（主智能体或子智能体）调用 `AskUserQuestion` 挂起时，消息气泡（`MessageItem.vue`）彻底消除生硬的“已停止生成”黄色警告，转而渲染温和的“⏳ 等待您的确认”柔和微光条；严格区分“等待提问输入”与“用户主动点击停止生成”，解决顶端提示与底部问卷之间的逻辑与视觉冲突。

**Blocked by:** None — can start immediately

**Status:** done

- [x] 在 `MessageItem.vue` 中解耦 `isInterruptedMessage` 与 `hasQuestions` 的判断，区分 `isAwaitingClarification`（挂起等待澄清）与真正的中断终止
- [x] 挂起等待澄清时，顶部不展示“已停止生成”，展示“⏳ 等待您的确认”或柔和呼吸提示
- [x] 用户主动 Abort 或未带 questions 的中断时，依然保持展示“已停止生成”
- [x] 确保前端类型与计算属性在流式挂起态与完成态下均能正确计算

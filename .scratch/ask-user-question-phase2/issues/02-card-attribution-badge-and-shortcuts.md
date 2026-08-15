# 02 — 澄清卡片专属智能体角色徽章与键盘快捷键交互

**What to build:**
`AskUserQuestionCard.vue` 头部根据提问者身份渲染专属徽章（如：带有机器人图标的【🤖 SQL数据专家 发起澄清】），让用户直观知晓提问上下文；输入框支持 `Ctrl+Enter` / `Cmd+Enter` 快速提交表单，支持全键盘流畅操作。

**Blocked by:** 01 — 后端中断协议身份透传与前端 Store 角色上下文打通

**Status:** done

- [x] 在 `MessageItem.vue` 中将提问者身份信息传递给 `AskUserQuestionCard.vue`
- [x] 在 `AskUserQuestionCard.vue` 中渲染角色徽章与来源提示
- [x] 在 `AskUserQuestionCard.vue` 的 textarea 输入框绑定 `@keydown.ctrl.enter` 和 `@keydown.meta.enter` 快捷提交

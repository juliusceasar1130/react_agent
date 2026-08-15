# 代码审核请求：主子智能体 AskUserQuestion 交互体验与状态解耦（第一阶段与第二阶段）

请对本次实现的主子智能体 `AskUserQuestion` 交互体验与状态解耦改动进行代码审查（Code Review）。

## 变更文件列表

### 1. 后端
- `backend/app/schemas.py`: `InterruptStreamEvent` 增加 `subagent_id`, `subagent_name`, `subagent_title` 可选字段。
- `backend/app/services/chat_service.py`: 在捕获 `AskUserQuestion` 中断挂起时，自适应解析当前活跃的子智能体身份（如 `sql_domain_agent` -> `SQL数据专家`）并注入 `InterruptStreamEvent`。

### 2. 前端
- `frontend/src/types/index.ts`: `StreamEvent` 的 `interrupt` 分支及 `StreamingMessage` 接口增加 `subagent_id`, `subagent_name`, `subagent_title`。
- `frontend/src/api/chat.ts`: `parseStreamEvent` 的 `case 'interrupt':` 解析中完整透传 `subagent_id`, `subagent_name`, `subagent_title`。
- `frontend/src/stores/messages.ts`: `setStreamingInterrupt` 支持接收并保存提问者元数据。
- `frontend/src/composables/useChatStream.ts`: 消费 `interrupt` 事件时向 store 传递提问者元数据。
- `frontend/src/components/chat/MessageItem.vue`:
  - 增加 `isAwaitingClarification` 计算属性，彻底消除有提问时的“已停止生成”误报，转为“⏳ 等待您的确认...”呼吸引导条；
  - 计算 `questionAskerTitle` 与 `questionAskerName` 并透传给 `AskUserQuestionCard`。
- `frontend/src/components/chat/SubagentCard.vue`:
  - 增加 `isAwaitingClarification` 计算属性，等待期状态标签升级为“等待确认”（搭配蓝色微光点），工具链显示“等待用户确认...”；
  - 展开面板增加引导条与“定位到表单”按钮，点击平滑滚动并自动聚焦输入框（`scrollToClarificationCard`）。
- `frontend/src/components/chat/AskUserQuestionCard.vue`:
  - 头部增加提问者身份专属徽章（如【🤖 SQL数据专家 发起澄清提问】）；
  - 输入框支持 `Ctrl+Enter` / `Cmd+Enter` 快速提交并附带快捷键提示。

## 验证情况
- 前端 `npm run build:check`（`vue-tsc` 严格类型检查 + Vite 生产构建）已 100% 验证通过。
- 后端中间件单元测试 `pytest` 全部通过。

请从代码规范、边界防御、状态一致性、Vue3/TypeScript 最佳实践以及潜在回归风险进行全面 Review。

# Spec: 主子智能体 AskUserQuestion 角色归属、聚焦联动与快捷交互优化（第二阶段）

Triage Label: `ready-for-agent`

## Problem Statement

在完成了第一阶段的状态解耦后，主智能体与子智能体在触发澄清问答时的状态表现已恢复平稳，但用户在深度使用多智能体协同查询时仍面临以下三方面的**交互体验与上下文割裂**痛点：

1. **提问来源与角色归属感缺失**：
   - 澄清卡片（`AskUserQuestionCard`）头部仅展示通用的“问题 1/2”和业务分类（如“参数确认”），用户无法直观看出提问是来自于“主调度助手”还是底层的“SQL数据专家”。当出现专业数据库字段澄清时，用户容易产生困惑，缺乏明确的智能体角色上下文。
2. **长日志与底部表单之间的视线/滚动割裂**：
   - 当子智能体卡片展开较长或工具链繁多时，用户的视线停留在子智能体面板中，无法第一时间察觉到底部生成了需要填写的澄清卡片，且没有直接锚定定位到操作区的快捷路径。
3. **操作效率与键盘交互缺失**：
   - 业务人员在输入框中输入完车身号或参数后，必须移开键盘、使用鼠标滑到底部点击“确认并恢复生成”按钮，无法通过 `Ctrl + Enter` 等标准化快捷键一键提交。

---

## Solution

在后端流式协议、前端状态机与交互组件层实现**角色透传、视线联动与键盘效率增强**：

1. **后端透传提问者身份元数据（Agent Attribution）**：
   - 后端在发射 `type: "interrupt"` SSE 流式事件时，附带发起提问的智能体身份字段（`subagent_id`、`subagent_name`、`subagent_title`）。
   - 前端接收并保存在当前消息的提问上下文中。
2. **澄清卡片专属角色徽章展示**：
   - `AskUserQuestionCard` 头部根据提问者身份渲染专属徽章（如：带有机器人图标的 **【🤖 SQL数据专家 发起澄清】** 或 **【💬 数据编排助手 提问】**），赋予用户清晰的提问角色认知。
3. **子智能体面板与底部表单的平滑聚焦联动**：
   - 在 `SubagentCard` 的工具调用列表末尾，当处于等待澄清态时，展示高辨识度的柔和提示条：“正在等待您在下方卡片中确认参数...”，并提供 **【👇 定位到表单】** 按钮，点击后页面平滑滚动并将视线与焦点锚定到底部卡片。
4. **键盘快捷键与高效交互支持**：
   - `AskUserQuestionCard` 内的所有输入框支持 `Ctrl+Enter` / `Cmd+Enter` 快捷提交表单；
   - 在单选题场景下支持快捷键盘回车确认。

---

## User Stories

1. As a 业务分析人员, I want 在澄清卡片顶部看到提问是由“SQL数据专家”还是“主助手”发起的徽章, so that 我能清晰理解问题的上下文背景与专业意图。
2. As a 业务分析人员, I want 在查看子智能体长日志时，能够点击“定位到表单”按钮一键滑动到底部问卷, so that 我无需手动滑动长页面即可直接开始输入。
3. As a 业务分析人员, I want 在输入完车身号后直接按 `Ctrl + Enter` 提交答案, so that 我可以保持全键盘操作，显著提高多轮问答效率。
4. As a 开发者, I want 后端 `interrupt` 事件规范化携带提问者角色元数据, so that 前端组件和遥测系统能够精准归因人机交互的发起方。
5. As a 开发者, I want 聚焦锚点具备安全的 DOM 查找与防抖平滑滚动, so that 在复杂嵌套组件和动态高度渲染下不会发生页面抖动或报错。

---

## Implementation Decisions

1. **后端流式中断事件契约扩展**
   - 在 `InterruptStreamEvent` 中新增可选的提问者元数据字段：
     ```python
     subagent_id: Optional[str] = None
     subagent_name: Optional[str] = None
     subagent_title: Optional[str] = None
     ```
   - 后端在检测到 `AskUserQuestion` 挂起时，根据当前活跃的子图命名空间（如 `tools:<call_id>`）自动提取所属子智能体名称与标题并注入事件中。
2. **前端流式解析与 Store 透传**
   - 前端 `StreamEvent` 联合类型与 `api/chat.ts` 解析白名单同步扩展 `subagent_id` / `subagent_name` / `subagent_title`；
   - `messagesStore` 在记录 `setStreamingInterrupt` 时将提问者元数据存入当前流式消息中。
3. **`AskUserQuestionCard.vue` 角色徽章渲染**
   - 卡片顶部接收 `asker` / `subagentName` prop；
   - 渲染带有品牌色彩与图标的专属智能体角色标识。
4. **`SubagentCard.vue` 锚点联动机制**
   - 当检测到自身处于等待澄清态时，在底部渲染引导条并挂载点击事件；
   - 点击时调用 `scrollIntoView({ behavior: 'smooth', block: 'center' })` 聚焦到对应的 `AskUserQuestionCard`，并触发首个输入框的 `focus()`。
5. **快捷键事件监听机制**
   - 在 `AskUserQuestionCard` 的 textarea / input 上绑定 `@keydown.ctrl.enter` 及 `@keydown.meta.enter` 事件直接触发 `handleSubmit`。

---

## Testing Decisions

### 良好测试的标准
- 验证后端发射的 `interrupt` 事件是否正确包含 `subagent_name` 等元数据；
- 验证前端卡片在接收到不同提问者（主 Agent vs SQL Agent）时准确渲染对应的身份标识文本与徽章；
- 验证快捷键触发时表单校验与提交回调是否被正确调用。

### 重点测试范围
- `schemas.py` & `chat_service.py`：验证 `interrupt` 事件序列化包含子智能体身份；
- `AskUserQuestionCard.vue`：测试提问者徽章渲染与 `Ctrl+Enter` 按键响应；
- `SubagentCard.vue`：测试定位按钮的渲染与点击事件。

---

## Out of Scope

1. **数据库 Message 表持久化新增 `questions` 字段**（留待 P3 阶段评估）。
2. **卡片内复杂交互式表格编辑**（保持结构化问答与自定义补充文本）。

---

## Further Notes

- 第二阶段贯穿前后端微调：后端仅在已有的 `interrupt` 事件推送处注入命名空间对应的身份（零破坏性改动），前端增量丰富角色徽章、锚点滚动与快捷键，整体改动紧凑内聚。

# Chat UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变功能和逻辑的前提下，将 `frontend` 聊天界面升级为现代、简洁明快、友好的响应式聊天工作台。

**Architecture:** 以现有 Vue 组件结构为基础，优先通过主题 token、布局类名和少量本地 UI 状态完成改造。桌面端维持双栏，移动端新增会话抽屉；消息、会话与输入区样式统一到同一套视觉体系中。

**Tech Stack:** Vue 3, TypeScript, Pinia, Tailwind CSS, Vite

---

### Task 1: 固定设计边界并恢复可验证基线

**Files:**
- Modify: `frontend/src/composables/useChatStream.ts`

- [ ] **Step 1: 修正阻塞构建的类型断言**

```ts
if (event.source === 'context_warning' && event.detail) {
  contextWarning.value = event.detail as unknown as ContextWarningPayload
  return
}
```

- [ ] **Step 2: 运行构建检查确认前端重新可验证**

Run: `npm run build:check`  
Expected: 类型检查和打包通过

### Task 2: 统一主题 token 与全局基础样式

**Files:**
- Modify: `frontend/src/style.css`
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: 更新颜色、阴影、背景和组件 token**
- [ ] **Step 2: 调整全局按钮、输入框、卡片与 Markdown 样式**
- [ ] **Step 3: 增加移动端和 reduced-motion 相关基础支持**

### Task 3: 重组主聊天布局与移动端抽屉

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: 增加移动端会话抽屉的本地显隐状态**
- [ ] **Step 2: 重组桌面端 / 移动端布局骨架**
- [ ] **Step 3: 优化顶部栏、上下文预警和输入区结构**

### Task 4: 优化会话列表与消息展示组件

**Files:**
- Modify: `frontend/src/components/SessionList.vue`
- Modify: `frontend/src/components/SessionItem.vue`
- Modify: `frontend/src/components/MessageList.vue`
- Modify: `frontend/src/components/MessageItem.vue`
- Modify: `frontend/src/components/EmptyState.vue`
- Modify: `frontend/src/components/ToggleSwitch.vue`

- [ ] **Step 1: 调整会话列表与会话项层级、密度和状态**
- [ ] **Step 2: 调整消息区容器、空状态和消息气泡样式**
- [ ] **Step 3: 统一流式、错误、中断、工具结果和附件卡片视觉**

### Task 5: 记录变更并完成最终验证

**Files:**
- Modify: `changelog.md`

- [ ] **Step 1: 记录本次 UI 优化与验证说明**
- [ ] **Step 2: 运行 `npm run build:check` 做最终验证**

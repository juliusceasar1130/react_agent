# Frontend Paper Editorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在独立 worktree 中把 `frontend` 从明亮 SaaS 工作台改造成淡暖棕 `Paper Editorial` 聊天界面，同时保持现有聊天功能、信息结构和交互路径不变。

**Architecture:** 继续沿用当前 Vue 组件拆分和双栏聊天工作台结构，不新增依赖，也不调整 API / store / 流式逻辑。实现重点放在三层：主题 token 重建、主聊天框架杂志化、组件局部样式统一，并通过阶段性构建检查和手动响应式检查保证可回退、可验证。

**Tech Stack:** Vue 3, TypeScript, Pinia, Tailwind CSS, Vite

---

### Task 1: 创建独立 worktree 并确认当前基线

**Files:**
- Modify: 无

- [ ] **Step 1: 从当前 `feature/agent` worktree 派生一个新的前端美化 worktree**

```powershell
git worktree add '..\paper-editorial' -b 'feature/frontend-paper-editorial' feature/agent
```

- [ ] **Step 2: 进入新 worktree 并确认 Git 指向正确分支**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial'
git branch --show-current
git worktree list
```

Expected:
- `git branch --show-current` 输出 `feature/frontend-paper-editorial`
- `git worktree list` 中出现 `...\paper-editorial`

- [ ] **Step 3: 在新 worktree 中检查前端构建基线**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run build:check
```

Expected:
- 理想情况：`vue-tsc && vite build` 通过
- 如果只出现 `spawn EPERM`，将其记为当前终端/沙箱环境限制，不作为前端代码回归处理

- [ ] **Step 4: 提交 worktree 建立与基线确认结果到执行日志**

```markdown
- worktree path: F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial
- branch: feature/frontend-paper-editorial
- baseline build: pass / blocked by spawn EPERM
```

### Task 2: 重建暖棕 Paper Editorial 主题 token

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: 在 `frontend/tailwind.config.js` 中替换蓝青色板和阴影为暖棕体系**

```js
colors: {
  primary: {
    DEFAULT: '#8A5A3B',
    hover: '#72452A',
    light: '#C7A98E',
  },
  secondary: '#D8C2AE',
  accent: '#B78B63',
  background: '#F5EFE6',
  surface: '#FFFCF7',
  text: '#2E241E',
  neutral: {
    50: '#FCF8F2',
    100: '#F3EADF',
    200: '#E5D6C5',
    300: '#D3BEA6',
    400: '#A88D76',
    500: '#836A58',
    600: '#654F43',
    700: '#4B392F',
    800: '#372922',
    900: '#241A15',
  },
},
boxShadow: {
  soft: '0 18px 36px -28px rgb(61 43 33 / 0.28)',
  glow: '0 16px 32px -24px rgb(138 90 59 / 0.28)',
},
```

- [ ] **Step 2: 在 `frontend/src/style.css` 中重写根变量和基础背景**

```css
:root {
  --color-primary: #8a5a3b;
  --color-primary-hover: #72452a;
  --color-secondary: #d8c2ae;
  --color-accent: #b78b63;

  --color-bg: #f5efe6;
  --color-bg-alt: #efe5d9;
  --color-surface: #fffaf3;
  --color-text: #2e241e;
  --color-text-muted: #766457;

  --shadow-sm: 0 10px 22px -16px rgb(46 36 30 / 0.14);
  --shadow-md: 0 22px 42px -30px rgb(46 36 30 / 0.18);
  --shadow-lg: 0 32px 56px -36px rgb(46 36 30 / 0.22);
  --shadow-xl: 0 42px 78px -42px rgb(46 36 30 / 0.26);
}

body {
  font-family: 'Iowan Old Style', 'Palatino Linotype', 'Noto Serif SC', 'Source Han Serif SC', serif;
  background:
    radial-gradient(circle at top left, rgb(215 193 169 / 0.24), transparent 28%),
    linear-gradient(180deg, #f8f3eb 0%, #f5efe6 48%, #eee4d6 100%);
  color: var(--color-text);
}
```

- [ ] **Step 3: 把基础组件类从科技感改成纸面感**

```css
.panel {
  @apply rounded-[28px] bg-surface/95 shadow-soft backdrop-blur-sm;
  border: 1px solid rgb(130 103 82 / 0.12);
}

.btn-primary {
  @apply rounded-2xl bg-primary px-5 py-2.5 font-medium text-white;
  @apply transition-all duration-200 ease-out hover:bg-primary-hover hover:shadow-glow;
  @apply active:scale-[0.98];
}

.input {
  @apply w-full rounded-[26px] border bg-white/92 px-4 py-3.5 text-text;
  border-color: rgb(140 111 90 / 0.18);
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.8);
}
```

- [ ] **Step 4: 运行构建检查，确认 token 调整未破坏样式编译**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run build:check
```

Expected:
- 构建通过，或仍仅受 `spawn EPERM` 影响

- [ ] **Step 5: 提交主题 token 阶段结果**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial'
git add -- 'frontend/tailwind.config.js' 'frontend/src/style.css'
git commit -m "style: establish paper editorial design tokens"
```

### Task 3: 改造主聊天框架与顶部/底部视觉层级

**Files:**
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/components/ToggleSwitch.vue`

- [ ] **Step 1: 将 `ChatView.vue` 的页头从工作台状态栏改成栏目式标题区**

```vue
<template v-if="currentSession">
  <p class="text-[11px] font-semibold uppercase tracking-[0.3em] text-neutral-400">
    Paper Editorial Workspace
  </p>
  <div class="mt-1 flex items-center gap-2">
    <span class="inline-flex h-2 w-2 rounded-full bg-accent"></span>
    <h3 class="truncate text-[clamp(1.05rem,1.5vw,1.45rem)] font-semibold text-text">
      {{ currentSession.title }}
    </h3>
  </div>
  <p class="mt-1 truncate text-sm text-neutral-500">
    {{ streamHeaderText }}
  </p>
</template>
```

- [ ] **Step 2: 调整主背景、预警条和输入区容器的类名**

```vue
<main class="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-[linear-gradient(180deg,rgba(255,252,247,0.88),rgba(245,239,230,0.92))]">
  <div
    v-if="currentSession && contextWarning"
    class="mx-auto mb-3 w-full max-w-4xl rounded-[24px] border border-amber-300/60 bg-[#fbf3e4] px-4 py-3 text-sm text-[#7a5638] shadow-sm"
  >
```

```vue
<div class="mx-auto w-full max-w-4xl panel border border-neutral-200/70 bg-[#fffaf3]/95 p-2.5 sm:p-3">
```

- [ ] **Step 3: 将 `ToggleSwitch.vue` 从明亮 SaaS 滑块改成更安静的编辑器工具条样式**

```vue
<label class="group inline-flex cursor-pointer items-center gap-3 rounded-full border border-neutral-200/80 bg-[#f7efe5]/90 px-3 py-2">
  <div
    class="relative h-6 w-11 rounded-full transition-all duration-300 ease-out peer-focus:ring-2 peer-focus:ring-primary/30"
    :class="modelValue ? 'bg-primary/85' : 'bg-[#d6c3b1]'"
  >
```

```vue
<span
  v-if="label"
  class="select-none text-[13px] font-medium"
  :class="modelValue ? 'text-text' : 'text-neutral-600'"
>
  {{ label }}
</span>
```

- [ ] **Step 4: 运行构建检查**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run build:check
```

- [ ] **Step 5: 提交聊天框架与开关样式阶段结果**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial'
git add -- 'frontend/src/views/ChatView.vue' 'frontend/src/components/ToggleSwitch.vue'
git commit -m "style: shift chat shell to paper editorial layout"
```

### Task 4: 改造左侧会话栏与欢迎态为目录风格

**Files:**
- Modify: `frontend/src/components/SessionList.vue`
- Modify: `frontend/src/components/SessionItem.vue`
- Modify: `frontend/src/components/EmptyState.vue`

- [ ] **Step 1: 调整 `SessionList.vue` 空状态和列表容器为目录页语气**

```vue
<div v-if="sessions.length === 0" class="panel border border-neutral-200/70 px-5 py-8 text-center">
  <p class="text-[11px] font-semibold uppercase tracking-[0.26em] text-neutral-400">Index</p>
  <p class="mt-3 text-sm font-semibold text-text">暂无会话目录</p>
  <p class="mt-1 text-xs leading-5 text-neutral-500">点击上方“新建”创建新的专题对话。</p>
</div>
```

- [ ] **Step 2: 调整 `SessionItem.vue` 选中态、时间信息和删除按钮**

```vue
<div
  class="group relative cursor-pointer rounded-[20px] border px-4 py-3.5 transition-all duration-200"
  :class="isActive
    ? 'border-[#c9b29b] bg-[#f7efe6] shadow-sm'
    : 'border-transparent bg-white/55 hover:border-neutral-200 hover:bg-white/88'"
>
```

```vue
<h4 class="truncate text-sm font-semibold" :class="isActive ? 'text-[#6f462d]' : 'text-neutral-700'">
  {{ session.title }}
</h4>
```

```vue
<button
  @click.stop="handleDelete"
  class="rounded-xl p-2 text-neutral-400 transition-all duration-200 hover:bg-[#f6e8dc] hover:text-[#8a5a3b]"
>
```

- [ ] **Step 3: 把 `EmptyState.vue` 改成刊物首页导语风格**

```vue
<p class="text-[11px] font-semibold uppercase tracking-[0.32em] text-neutral-400">Paper Editorial</p>
<h2 class="mb-2 mt-3 text-[clamp(1.7rem,3vw,2.4rem)] font-semibold text-text">欢迎进入对话专栏</h2>
<p class="mx-auto max-w-md text-sm leading-7 text-neutral-500">
  在左侧创建新会话或进入已有主题，让 AI 助手围绕一个清晰专题持续展开。
</p>
```

- [ ] **Step 4: 运行构建检查**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run build:check
```

- [ ] **Step 5: 提交左栏与空状态阶段结果**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial'
git add -- 'frontend/src/components/SessionList.vue' 'frontend/src/components/SessionItem.vue' 'frontend/src/components/EmptyState.vue'
git commit -m "style: restyle sidebar and empty state as editorial index"
```

### Task 5: 改造消息阅读区、Markdown 和附件卡片

**Files:**
- Modify: `frontend/src/components/MessageList.vue`
- Modify: `frontend/src/components/MessageItem.vue`
- Modify: `frontend/src/components/ChartArtifactCard.vue`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: 在 `MessageList.vue` 中进一步收束版心和列表留白**

```vue
<div v-else class="mx-auto flex w-full max-w-[52rem] flex-col gap-6 px-1 py-4 sm:px-0">
  <MessageItem
    v-for="message in messages"
    :key="message.id"
    :message="message"
  />
</div>
```

- [ ] **Step 2: 在 `MessageItem.vue` 中把用户/AI/错误/中断气泡统一到纸面层级**

```ts
const messageWrapperClass = computed(() => {
  if (isUser.value) {
    return 'border border-[#d7c2ad] bg-[#efe2d4] shadow-sm'
  }
  if (errorText.value) {
    return 'border border-red-200 bg-[#fff4f1]'
  }
  if (isInterruptedMessage.value) {
    return 'border border-amber-200 bg-[#fbf2e4]'
  }
  if (streamingState.value) {
    return 'border border-[#e3d3c4] bg-[#f9f2ea]'
  }
  return 'border border-neutral-200/80 bg-[#fffaf3] shadow-sm'
})
```

```ts
const textClass = computed(() => {
  if (isUser.value) return 'font-medium text-[#3d2b21]'
  if (errorText.value) return 'text-red-700'
  if (isInterruptedMessage.value) return 'text-[#7a5638]'
  return 'text-text'
})
```

```vue
<div
  v-for="artifact in exportArtifacts"
  :key="artifact.file_id"
  class="rounded-[22px] border border-[#dcc7b4] bg-[#f8efe5] px-4 py-3 shadow-sm"
>
```

- [ ] **Step 3: 在 `style.css` 中把 Markdown 呈现改成正文阅读风格**

```css
.message-markdown p {
  line-height: 1.9;
  color: var(--color-text);
}

.message-markdown p:has(> strong:only-child) {
  margin-bottom: 0.8rem;
  border-left: 3px solid rgb(138 90 59 / 0.55);
  padding-left: 0.85rem;
  font-size: 1rem;
  font-weight: 700;
}

.message-markdown blockquote {
  border-left: 3px solid rgb(183 139 99 / 0.4);
  background: linear-gradient(180deg, rgb(245 233 220 / 0.9), rgb(255 250 243 / 0.95));
  color: rgb(101 79 67);
}
```

- [ ] **Step 4: 在 `ChartArtifactCard.vue` 中去掉蓝色图表卡片基调**

```vue
<div class="rounded-[24px] border border-neutral-200 bg-[#fbf4eb] px-4 py-3 shadow-sm">
  <div class="text-sm font-semibold text-[#5e3f2b]">{{ artifact?.title ?? artifactRef.title }}</div>
  <div v-if="artifact?.description" class="mt-1 text-xs leading-5 text-[#7a624f]">
    {{ artifact.description }}
  </div>
</div>
```

- [ ] **Step 5: 运行构建检查**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run build:check
```

- [ ] **Step 6: 启动本地开发环境做手动视觉检查**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run dev
```

Manual checklist:
- 桌面端 `1440px` 下侧栏像目录栏、消息区像正文版面
- 平板宽度 `768px` 下头部、输入区和消息留白不拥挤
- 手机宽度 `390px` 下会话抽屉、输入区、发送按钮均可正常使用
- 流式消息、错误消息、中断消息、CSV 卡片、图表卡片均已融入暖棕视觉

- [ ] **Step 7: 提交消息区与附件卡片阶段结果**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial'
git add -- 'frontend/src/components/MessageList.vue' 'frontend/src/components/MessageItem.vue' 'frontend/src/components/ChartArtifactCard.vue' 'frontend/src/style.css'
git commit -m "style: unify message reading area under paper editorial theme"
```

### Task 6: 记录变更并完成收尾验证

**Files:**
- Modify: `changelog.md`

- [ ] **Step 1: 在 `changelog.md` 顶部新增本次前端美化记录**

```md
## 2026-04-23 21:11 +08:00 - 前端切换为 Paper Editorial 暖棕杂志风

### 概述
- 在不改变聊天结构和交互逻辑的前提下，将前端整体视觉从蓝青 SaaS 风格调整为淡暖棕 Paper Editorial 风格。

### 变更内容

#### frontend/tailwind.config.js / frontend/src/style.css
- 重建暖棕主题 token、背景、阴影、输入框、按钮和 Markdown 呈现。

#### frontend/src/views/ChatView.vue / frontend/src/components/*
- 保留双栏聊天结构，重做页头、侧栏、消息区、欢迎态、图表卡片和开关的视觉层级。

### 验证
- 执行 `npm run build:check`
- 手动检查桌面端、平板端和移动端显示效果
```

- [ ] **Step 2: 做最终构建检查**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial\frontend'
npm run build:check
```

- [ ] **Step 3: 查看最终工作区状态并创建收尾提交**

```powershell
Set-Location 'F:\000_dev\Python\workplace\rearch_agent\.tree\features\paper-editorial'
git status --short
git add -- 'changelog.md'
git commit -m "docs: record paper editorial frontend refresh"
```

- [ ] **Step 4: 输出最终交付摘要**

```markdown
- worktree: feature/frontend-paper-editorial
- final verification: build:check pass / blocked by spawn EPERM
- manual QA: desktop / tablet / mobile checked
- files touched: frontend theme shell, sidebar, messages, artifacts, changelog
```

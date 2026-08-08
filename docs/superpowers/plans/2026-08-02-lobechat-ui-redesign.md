# LobeChat Style Unified Canvas & Floating Input Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the main chat view layout from a 3-tier bordered layout (Header / Middle / Footer) into a seamless LobeChat-style unified canvas with a transparent floating sticky header, Lucide panel-left toggle icon, max-w-4xl aligned message area, and a bottom floating card input panel with integrated controls.

**Architecture:** Remove physical divider borders (`border-b` on header, `border-t` on footer) and fixed background bands. Transform the header into a `sticky top-0` borderless bar with a minimal `panel-left-close` toggle button. Restructure the bottom input bar into a `max-w-4xl` centered floating card (`sticky bottom-6 rounded-3xl shadow-xl`) with an inner bottom toolbar containing the `ToggleSwitch` controls and send button. Ensure full mobile responsiveness (`sm:` breakpoints for bottom-0 flat cards on mobile).

**Tech Stack:** Vue 3 `<script setup>`, Tailwind CSS, TypeScript.

---

### Task 1: Redesign Sidebar Toggle Icon Button in ChatView.vue

**Files:**
- Modify: `frontend/src/views/ChatView.vue:37-45`

- [ ] **Step 1: Replace bulky double-arrow button with LobeChat Lucide panel-left SVG icon button**

In `frontend/src/views/ChatView.vue`, update the sidebar toggle button from:

```html
<button
  class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-neutral-200/90 bg-white text-neutral-600 shadow-sm transition hover:border-neutral-300 hover:text-text"
  @click="isSidebarOpen = !isSidebarOpen"
  :title="isSidebarOpen ? '收起侧边栏' : '展开侧边栏'"
>
  <svg class="h-5 w-5 transition-transform duration-300" :class="isSidebarOpen ? '' : 'rotate-180'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M11 19l-7-7 7-7M20 19l-7-7 7-7" />
  </svg>
</button>
```

To:

```html
<button
  @click="isSidebarOpen = !isSidebarOpen"
  class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
  :title="isSidebarOpen ? '收起侧边栏' : '展开侧边栏'"
>
  <svg v-if="isSidebarOpen" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect width="18" height="18" x="3" y="3" rx="2.5"/>
    <path d="M9 3v18"/>
    <path d="m14 9-3 3 3 3"/>
  </svg>
  <svg v-else class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect width="18" height="18" x="3" y="3" rx="2.5"/>
    <path d="M9 3v18"/>
    <path d="m13 15 3-3-3-3"/>
  </svg>
</button>
```

- [ ] **Step 2: Verify visually in dev server**

Check that hovering the button highlights smoothly with no heavy white border or drop-shadow.

---

### Task 2: Refactor Sticky Floating Header in ChatView.vue

**Files:**
- Modify: `frontend/src/views/ChatView.vue:35-94`

- [ ] **Step 1: Remove border-b divider line and heavy background blur from Header**

In `frontend/src/views/ChatView.vue`, change header container classes from:

```html
<header class="relative z-10 border-b border-neutral-200/70 bg-white/70 backdrop-blur-xl">
```

To:

```html
<header class="sticky top-0 z-20 w-full bg-background/80 backdrop-blur-md transition-colors">
```

- [ ] **Step 2: Align Header content container with main content max-width (max-w-4xl)**

Update inner container:

```html
<div class="mx-auto flex w-full max-w-4xl items-center gap-3 px-4 py-3">
```

- [ ] **Step 3: Verify all header elements are intact**

Verify session title, `streamHeaderClass`, `isSending` status pill, `关于` button, `数据字典看板` button, and `审核终端` button remain rendered correctly.

---

### Task 3: Transform Bottom Input Panel into Centered Floating Card & Inner Toolbar

**Files:**
- Modify: `frontend/src/views/ChatView.vue:115-190`

- [ ] **Step 1: Restructure Footer from full-width border-t bar to floating max-w-4xl card**

In `frontend/src/views/ChatView.vue`, change the bottom input container from:

```html
<div
  v-if="currentSession"
  class="relative z-10 border-t border-neutral-200/70 bg-white/70 px-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.5rem)] pt-2 backdrop-blur-xl sm:px-5 lg:px-8 lg:pt-3"
>
  <div class="mx-auto w-full max-w-5xl panel p-2.5 sm:p-3">
    <!-- Switches and TextArea -->
  </div>
</div>
```

To:

```html
<div
  v-if="currentSession"
  class="sticky bottom-0 sm:bottom-4 z-20 mx-auto w-full max-w-4xl px-0 sm:px-4 pointer-events-none mb-0 sm:mb-2"
>
  <div class="pointer-events-auto panel !rounded-none sm:!rounded-3xl border-t sm:border border-neutral-200/90 bg-white/95 shadow-lg sm:shadow-xl backdrop-blur-xl p-3 transition-all duration-200">
    <div class="flex flex-col gap-2">
      <!-- Input Textarea -->
      <div class="relative">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          @keydown.enter.exact.prevent="handleSendMessage"
          @keydown.enter.shift="inputText += '\n'"
          placeholder="从任何想法开始... (Enter 发送，Shift+Enter 换行)"
          class="w-full bg-transparent border-0 focus:ring-0 focus:outline-none min-h-[52px] max-h-[200px] resize-none text-sm sm:text-base text-text placeholder:text-neutral-400 pr-16 py-1"
          rows="1"
          :disabled="isSending"
        />
        <div
          v-if="inputText.length > 0"
          class="absolute top-1 right-2 rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] text-neutral-500"
        >
          {{ inputText.length }} 字符
        </div>
      </div>

      <!-- Integrated Inner Bottom Toolbar -->
      <div class="flex items-center justify-between pt-2 border-t border-neutral-100">
        <div class="flex items-center gap-2">
          <ToggleSwitch
            v-model="streamMode"
            label="流式输出"
            :show-status="true"
            on-label="实时显示"
            off-label="等待完整"
          />
          <div class="h-3.5 w-px bg-neutral-200 mx-0.5"></div>
          <ToggleSwitch
            v-model="enableThinking"
            label="深度思考"
            :show-status="true"
            on-label="已开启"
            off-label="已关闭"
          />
        </div>

        <button
          @click="isSending && streamMode ? handleStopStreaming() : handleSendMessage()"
          :disabled="!isSending && !inputText.trim()"
          class="flex h-9 items-center justify-center gap-1.5 rounded-full px-4 text-xs sm:text-sm font-semibold transition-all duration-200"
          :class="isSending && streamMode
            ? 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200 active:scale-[0.98]'
            : 'btn-primary'"
        >
          <svg v-if="!isSending" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
          <svg v-else-if="streamMode" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M7 7h10v10H7z" />
          </svg>
          <span>{{ isSending ? (streamMode ? '停止' : '发送中') : '发送' }}</span>
        </button>
      </div>
    </div>
  </div>
</div>
```

---

### Task 4: Align Message List & Canvas Layout Structure

**Files:**
- Modify: `frontend/src/views/ChatView.vue:96-113`
- Modify: `frontend/src/components/VariantB.vue:560-580`

- [ ] **Step 1: Update ChatView message container max-width to max-w-4xl**

In `frontend/src/views/ChatView.vue`, update line 96 message container:

```html
<div class="relative flex min-h-0 flex-1 flex-col mx-auto w-full max-w-4xl px-4 py-4">
```

- [ ] **Step 2: Check VariantB canvas area background**

Ensure `#main-chat-area` container in `VariantB.vue` has uniform `bg-background` background without extra card margins or artificial dividers.

---

### Task 5: End-to-End Verification & Desktop/Mobile Layout Checks

**Files:**
- Verify: `frontend/src/views/ChatView.vue`
- Verify: `frontend/src/components/VariantB.vue`

- [ ] **Step 1: Check desktop rendering (`>= 1024px`)**
  - Verify Header has no bottom border line.
  - Verify collapse button uses new Lucide `panel-left` icon.
  - Verify message list and floating input card align vertically at `max-w-4xl`.
  - Verify floating input card sits floating above the canvas with rounded-3xl and drop shadow.

- [ ] **Step 2: Check mobile/small screen rendering (`< 640px`)**
  - Verify floating input card adapts smoothly to bottom flat panel without horizontal scrollbars.
  - Verify sidebar collapse/drawer mask opens smoothly.

# Phase 3 & 4: 前端 SSE 思考事件处理与深度思考折叠面板组件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `reasoning` SSE stream events into frontend state, register in 3-point event whitelist to prevent dropping, and render an expandable `<ReasoningAccordion>` component inside chat messages with streaming typewriter effect and timer.

**Architecture:** Extend TypeScript interfaces (`types/index.ts`), add `reasoning` event parser and whitelist (`api/chat.ts`), update `useChatStream.ts` to aggregate `reasoningText` onto streaming assistant message, build `ReasoningAccordion.vue` component, and embed it into `MessageItem.vue`.

**Tech Stack:** Vue 3 Composition API (`<script setup>`), TypeScript, Tailwind CSS, Vite (`npm run build`).

---

### File Structure & Responsibilities

- Modify: `frontend/src/types/index.ts`
  - Add `reasoningText?: string` to `Message` interface.
  - Add `{ type: 'reasoning'; text: string; node?: string }` to `StreamEvent` union.
- Modify: `frontend/src/api/chat.ts`
  - Add `'reasoning'` to `STREAM_EVENT_TYPES` whitelist Set.
  - Add `case 'reasoning':` parser branch in `parseStreamEvent()`.
- Modify: `frontend/src/composables/useChatStream.ts`
  - In `handleEvent(event)`, handle `case 'reasoning':` by appending `event.text` to `currentAssistantMessage.value.reasoningText`.
- Create: `frontend/src/components/ReasoningAccordion.vue`
  - Render collapsible panel with brain icon 🧠, dynamic timer, streaming cursor, and scrollable monospace text block.
- Modify: `frontend/src/components/MessageItem.vue`
  - Embed `<ReasoningAccordion>` above the message content when `message.reasoningText` exists and message is from assistant.

---

### Task 1: Register Reasoning Stream Event in Types & API Whitelist

**Files:**
- Modify: `frontend/src/types/index.ts:38-66` & `frontend/src/types/index.ts:147-200`
- Modify: `frontend/src/api/chat.ts:61-75` & `frontend/src/api/chat.ts:100-130`
- Test: `npm run build` (Typecheck and compilation)

- [x] **Step 1: Update `frontend/src/types/index.ts`**

Add `reasoningText?: string` to `Message` interface:

```typescript
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  reasoningText?: string
  session_id: string
  created_at: string
  ...
}
```

Add `reasoning` event to `StreamEvent` union:

```typescript
export type StreamEvent =
  | {
      type: 'token'
      text: string
      node?: string
    }
  | {
      type: 'reasoning'
      text: string
      node?: string
    }
  | ...
```

- [x] **Step 2: Update `frontend/src/api/chat.ts` Whitelist & Parser**

Add `'reasoning'` to `STREAM_EVENT_TYPES`:

```typescript
const STREAM_EVENT_TYPES = new Set<StreamEvent['type']>([
  'token',
  'reasoning',
  'status',
  'tool_call',
  'tool_result',
  'final',
  'error',
  'interrupt',
  'rag_context',
  'lexicon_context',
  'tool_artifact',
])
```

Add `case 'reasoning':` to `parseStreamEvent()` switch:

```typescript
    case 'reasoning': {
      if (typeof parsed.text !== 'string') return null
      return {
        type: 'reasoning',
        text: parsed.text,
        ...(typeof parsed.node === 'string' ? { node: parsed.node } : {}),
      }
    }
```

- [x] **Step 3: Run build to verify type checking**

Run: `cd frontend; npm run build`  
Expected: PASS (Zero TypeScript errors)

- [x] **Step 4: Commit changes**

```bash
git add frontend/src/types/index.ts frontend/src/api/chat.ts
git commit -m "feat: register reasoning stream event in types and API whitelist"
```

---

### Task 2: Aggregate Reasoning Text in Composable

**Files:**
- Modify: `frontend/src/composables/useChatStream.ts:146-220`
- Test: `npm run build`

- [x] **Step 1: Update `useChatStream.ts` Event Handler**

In `useChatStream.ts`, update `handleEvent(event: StreamEvent)` to process `reasoning` events:

```typescript
      case 'reasoning': {
        if (currentAssistantMessage.value) {
          currentAssistantMessage.value.reasoningText = (currentAssistantMessage.value.reasoningText || '') + event.text
        }
        break
      }
```

- [x] **Step 2: Run build to verify type checking**

Run: `cd frontend; npm run build`  
Expected: PASS

- [x] **Step 3: Commit changes**

```bash
git add frontend/src/composables/useChatStream.ts
git commit -m "feat: accumulate reasoning stream text in useChatStream composable"
```

---

### Task 3: Build ReasoningAccordion Component & Integrate into MessageItem

**Files:**
- Create: `frontend/src/components/ReasoningAccordion.vue`
- Modify: `frontend/src/components/MessageItem.vue`
- Test: `npm run build`

- [x] **Step 1: Create `frontend/src/components/ReasoningAccordion.vue`**

```vue
<template>
  <div v-if="reasoningText" class="mb-3 overflow-hidden rounded-xl border border-neutral-200/70 bg-neutral-50/60 dark:border-neutral-800 dark:bg-neutral-900/40">
    <button
      @click="isExpanded = !isExpanded"
      class="flex w-full items-center justify-between px-3.5 py-2 text-left text-xs font-medium text-neutral-600 transition-colors hover:bg-neutral-100/50 dark:text-neutral-400 dark:hover:bg-neutral-800/50"
    >
      <div class="flex items-center gap-2">
        <span class="flex h-4 w-4 items-center justify-center rounded-full bg-primary/10 text-[10px] text-primary">🧠</span>
        <span class="font-semibold">深度思考过程</span>
        <span v-if="isStreaming" class="flex items-center gap-1 text-[11px] text-primary">
          <span class="h-1.5 w-1.5 animate-ping rounded-full bg-primary"></span>
          思考中...
        </span>
        <span v-else-if="durationText" class="text-[11px] text-neutral-400">
          ({{ durationText }})
        </span>
      </div>
      <svg
        class="h-4 w-4 transition-transform duration-200 text-neutral-400"
        :class="{ 'rotate-180': isExpanded }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <div v-show="isExpanded" class="border-t border-neutral-200/50 px-3.5 py-3 dark:border-neutral-800">
      <div class="max-h-60 overflow-y-auto whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-neutral-600 dark:text-neutral-300">
        {{ reasoningText }}
        <span v-if="isStreaming" class="inline-block h-3 w-1.5 animate-pulse bg-primary/70 ml-0.5"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  reasoningText?: string
  isStreaming?: boolean
}>()

const isExpanded = ref(true)
const startTime = ref<number | null>(null)
const elapsedTime = ref<number>(0)
let timerId: any = null

onMounted(() => {
  if (props.isStreaming) {
    startTime.value = Date.now()
    timerId = setInterval(() => {
      if (startTime.value) {
        elapsedTime.value = Math.floor((Date.now() - startTime.value) / 100) / 10
      }
    }, 100)
  }
})

watch(() => props.isStreaming, (newVal) => {
  if (!newVal && timerId) {
    clearInterval(timerId)
    timerId = null
  }
})

onUnmounted(() => {
  if (timerId) clearInterval(timerId)
})

const durationText = computed(() => {
  if (elapsedTime.value > 0) {
    return `已思考 ${elapsedTime.value.toFixed(1)}s`
  }
  return ''
})
</script>
```

- [x] **Step 2: Integrate `<ReasoningAccordion>` into `MessageItem.vue`**

In `frontend/src/components/MessageItem.vue`:
- Import `ReasoningAccordion` from `@/components/ReasoningAccordion.vue`.
- Insert `<ReasoningAccordion :reasoning-text="message.reasoningText" :is-streaming="isStreamingActive" />` directly above the message content paragraph (`<p v-if="...">`).

- [x] **Step 3: Run `npm run build` to verify end-to-end compilation**

Run: `cd frontend; npm run build`  
Expected: PASS (`✓ built in ...s`)

- [x] **Step 4: Commit changes**

```bash
git add frontend/src/components/ReasoningAccordion.vue frontend/src/components/MessageItem.vue
git commit -m "feat: add ReasoningAccordion component to MessageItem"
```

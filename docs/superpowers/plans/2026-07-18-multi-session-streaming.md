# Multi-Session Concurrent Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable seamless concurrent background streaming across multiple sessions without freezing the interface, polluting messages, or leaking text bubbles, accompanied by real-time status indicators in the session list.

**Architecture:** Map-based state isolation per `session_id` in both the message Pinia store and the streaming composable. Active streams use isolated AbortControllers and local computed indicators, displaying visual Siri-like waveforms next to active sessions.

**Tech Stack:** Vue 3, Pinia (Setup Store), TypeScript, Tailwind CSS, EventStream (SSE)

---

## Proposed Changes

### Task 1: Refactor `messages.ts` Store for Map-based Isolation

**Files:**
- Modify: [messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/stores/messages.ts)

- [ ] **Step 1.1: Redefine state as session-keyed Record Maps**
  Change `streamingMessage` from `ref<StreamingMessage | null>` to `streamingMessagesMap: ref<Record<string, StreamingMessage>>({})`.
  Provide backward-compatible computeds `streamingMessage` and `isStreaming` for the current session.
  ```typescript
  const streamingMessagesMap = ref<Record<string, StreamingMessage>>({})
  
  const streamingMessage = computed(() =>
    latestRequestedSessionId.value
      ? streamingMessagesMap.value[latestRequestedSessionId.value] ?? null
      : null
  )
  const isStreaming = computed(() => !!streamingMessage.value)
  const isSessionStreaming = (sessionId: string) => !!streamingMessagesMap.value[sessionId]
  ```

- [ ] **Step 1.2: Refactor actions to accept `sessionId` parameters**
  Update all stream lifecycle actions (`startStreamingMessage`, `appendStreamingContent`, `updateStreamingStatus`, `upsertStreamingToolCall`, `setStreamingToolResult`, `setStreamingError`, `setStreamingInterrupt`, `clearStreamingMessage`) to retrieve and mutate the message in `streamingMessagesMap.value[sessionId]` instead of a single global ref.
  Add `clearStreamingForSession(sessionId)` to delete a session's entry when the session is deleted.

- [ ] **Step 1.3: Apply strict Session ID validation to finalization actions**
  In `completeStreamingMessage`, `finalizeStreamingError`, and `finalizeStreamingInterrupted`, clean up the map entry first: `delete streamingMessagesMap.value[sessionId]`.
  Only `push` the final message onto `messages.value` if `sessionId === latestRequestedSessionId.value`.
  Ensure RAG and lexicon contexts are still cached in `memoryRagMap` and `memoryLexiconMap` by the final message ID.

- [ ] **Step 1.4: Run typecheck to verify**
  Run: `npx vue-tsc --noEmit` in frontend.
  Expected: PASS.

---

### Task 2: Refactor `useChatStream.ts` Composable

**Files:**
- Modify: [useChatStream.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/composables/useChatStream.ts)

- [ ] **Step 2.1: Map-out controller and status references**
  Replace `activeStreamController` and `isSending` with session-keyed reactive objects:
  ```typescript
  const activeStreamControllersMap = ref<Record<string, AbortController>>({})
  const sendingSessionsMap = ref<Record<string, boolean>>({})
  const contextWarningsMap = ref<Record<string, ContextWarningPayload | null>>({})
  
  const isSending = computed(() =>
    sessionsStore.currentSessionId
      ? !!sendingSessionsMap.value[sessionsStore.currentSessionId]
      : false
  )
  ```
  Remove the watch that resets `contextWarning` on session change.

- [ ] **Step 2.2: Implement session-specific cancellation**
  Modify `stopStreaming` to accept an optional `sessionId` and abort only that session's controller:
  ```typescript
  const stopStreaming = (sessionId?: string) => {
    const sid = sessionId ?? sessionsStore.currentSessionId
    if (sid) {
      activeStreamControllersMap.value[sid]?.abort()
    }
  }
  ```

- [ ] **Step 2.3: Pass `sessionId` through all SSE event handlers**
  Update `sendMessage` and `resumeMessage` to populate `sendingSessionsMap` and register `AbortController` in `activeStreamControllersMap` under the active session's ID.
  Pass the active `sessionId` to all `messagesStore` actions in `handleEvent` so that updates are routed to the correct session's Map entry.
  Ensure clean-up in `finally` blocks deletes the controllers and sending state from the maps.

- [ ] **Step 2.4: Run typecheck to verify**
  Run: `npx vue-tsc --noEmit` in frontend.
  Expected: PASS.

---

### Task 3: Integrate Siri Waveform Status Indicator in `SessionItem.vue`

**Files:**
- Modify: [SessionItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/SessionItem.vue)

- [ ] **Step 3.1: Add streaming indicator computed**
  Import `useMessagesStore` and define `isStreaming` based on the session ID:
  ```typescript
  import { useMessagesStore } from '@/stores/messages'
  const messagesStore = useMessagesStore()
  const isStreaming = computed(() => messagesStore.isSessionStreaming(props.session.id))
  ```

- [ ] **Step 3.2: Render waveform indicator in template**
  For the expanded state, render three bar spans on the right. For the collapsed (`isSlim`) state, overlay a small pulse badge:
  ```html
  <!-- Expanded state -->
  <div v-if="isStreaming && !isSlim" class="flex items-center gap-0.5 ml-2" title="正在生成回答...">
    <span class="stream-bar bar-1"></span>
    <span class="stream-bar bar-2"></span>
    <span class="stream-bar bar-3"></span>
  </div>
  <!-- Collapsed state -->
  <span v-if="isStreaming && isSlim" class="absolute bottom-0.5 right-0.5 h-2.5 w-2.5 rounded-full bg-primary border-2 border-white animate-pulse" title="正在生成..."></span>
  ```

- [ ] **Step 3.3: Write stylesheet keyframes and animations**
  Add styles to animate the columns in Siri style:
  ```css
  .stream-bar {
    display: inline-block;
    width: 2px;
    height: 8px;
    background-color: var(--color-primary, #3b82f6);
    border-radius: 1px;
    animation: bar-bounce 0.8s ease-in-out infinite alternate;
  }
  .bar-1 { animation-delay: 0.1s; }
  .bar-2 { animation-delay: 0.3s; height: 12px; }
  .bar-3 { animation-delay: 0.5s; }
  @keyframes bar-bounce {
    from { transform: scaleY(0.4); }
    to { transform: scaleY(1.2); }
  }
  ```

- [ ] **Step 3.4: Run typecheck to verify**
  Run: `npx vue-tsc --noEmit` in frontend.
  Expected: PASS.

---

## Verification Plan

### Automated Tests
- Run: `npx vue-tsc --noEmit` in frontend to ensure zero compilation or template type errors.

### Manual Verification
1. **Concurrency Check**: Ask a question in Session A. While it is generating, quickly click Session B in the sidebar. Verify:
   - Session B's history is loaded clean.
   - Session B's input field is enabled and you can send a new message.
   - Session A in the sidebar displays the bouncing Siri waveform indicator.
2. **Background Completion**: Let Session A finish generating in the background. Verify:
   - The indicator for Session A turns off.
   - Switch back to Session A and verify the fully generated response is displayed perfectly.
3. **Cancellation Isolation**: While both A and B are generating concurrently, click "Stop generating" in Session B. Verify Session B stops, while Session A continues generating in the background.

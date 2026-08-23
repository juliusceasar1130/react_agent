# 聊天问题刻度线导航 (Question Rail) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在对话主页右侧增加用户问题刻度线导览组件（Question Rail），支持常态极简刻度线、悬浮展开毛玻璃问题卡片、双向视口滚动动态点亮、点击平滑定位与微光呼吸反馈。

**Architecture:** 
- 抽取 `useScrollSpy.ts` Composable 负责视口相对位移计算、`requestAnimationFrame` 节流、`ResizeObserver` 动态监听与资源释放；
- 创建 `QuestionRail.vue` 独立组件负责刻度线渲染、悬浮卡片过渡动画与无障碍交互；
- 在 `MessageItem.vue` 中绑定用户消息 DOM 锚点及高亮动效，在 `MessageList.vue` 中装配组件并暴露定位接口。

**Tech Stack:** Vue 3 (`<script setup>`), TypeScript, Tailwind CSS, Pinia

## Global Constraints

- **Minimal Changes**: 仅修改必要的组件，不改动无关样式与后端接口。
- **Git Commit Constraint**: 严格遵循项目规则，未获用户显式允许前不得自主提交 git commit。
- **Changelog & Documentation**: 新特性与改动需在 `changelog.md` 顶部附带时间与摘要，并在 `README.md` 中同步更新。
- **No External CDN**: 禁止引入外部 CDN 资源，完全使用本地现有 Tailwind 及 Vue 依赖。

---

### Task 1: 编写视口监听与定位 Composable (`useScrollSpy.ts`)

**Files:**
- Create: `frontend/src/composables/useScrollSpy.ts`

**Interfaces:**
- Produces:
  ```ts
  export interface UserQuestionItem {
    id: string
    content: string
    index: number
  }

  export function useScrollSpy(
    containerRef: Ref<HTMLElement | null>,
    userQuestions: Ref<UserQuestionItem[]>
  ): {
    activeId: Ref<string | null>
    scrollToMessage: (messageId: string) => void
    calculateActiveMessage: () => void
  }
  ```

- [ ] **Step 1: 创建 `frontend/src/composables/useScrollSpy.ts`**

```ts
import { ref, watch, onMounted, onUnmounted, type Ref } from 'vue'

export interface UserQuestionItem {
  id: string
  content: string
  index: number
}

const ACTIVATION_OFFSET_TOP = 120 // 视口判定顶部偏移阈值 (px)

export function useScrollSpy(
  containerRef: Ref<HTMLElement | null>,
  userQuestions: Ref<UserQuestionItem[]>
) {
  const activeId = ref<string | null>(null)
  let rafId: number | null = null
  let resizeObserver: ResizeObserver | null = null

  const calculateActiveMessage = () => {
    const container = containerRef.value
    if (!container || userQuestions.value.length === 0) {
      activeId.value = null
      return
    }

    const containerRect = container.getBoundingClientRect()
    const isBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 40

    if (isBottom) {
      activeId.value = userQuestions.value[userQuestions.value.length - 1].id
      return
    }

    let matchedId: string | null = null
    for (const q of userQuestions.value) {
      const el = document.getElementById(`msg-${q.id}`)
      if (!el) continue
      const rect = el.getBoundingClientRect()
      const relativeTop = rect.top - containerRect.top
      if (relativeTop <= ACTIVATION_OFFSET_TOP) {
        matchedId = q.id
      } else {
        break
      }
    }

    activeId.value = matchedId || userQuestions.value[0]?.id || null
  }

  const handleScroll = () => {
    if (rafId !== null) cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      calculateActiveMessage()
      rafId = null
    })
  }

  const scrollToMessage = (messageId: string) => {
    const container = containerRef.value
    const el = document.getElementById(`msg-${messageId}`)
    if (!container || !el) return

    const containerRect = container.getBoundingClientRect()
    const elRect = el.getBoundingClientRect()
    const targetScrollTop = elRect.top - containerRect.top + container.scrollTop - 16

    container.scrollTo({
      top: Math.max(0, targetScrollTop),
      behavior: 'smooth'
    })

    // 触发气泡微光呼吸反馈
    el.classList.remove('highlight-pulse')
    void el.offsetWidth // 触发重绘以重启动画
    el.classList.add('highlight-pulse')
    setTimeout(() => {
      el.classList.remove('highlight-pulse')
    }, 1200)
  }

  watch(userQuestions, () => {
    calculateActiveMessage()
  }, { deep: true })

  onMounted(() => {
    const container = containerRef.value
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true })
      resizeObserver = new ResizeObserver(() => {
        calculateActiveMessage()
      })
      resizeObserver.observe(container)
    }
  })

  onUnmounted(() => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    const container = containerRef.value
    if (container) {
      container.removeEventListener('scroll', handleScroll)
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  })

  return {
    activeId,
    scrollToMessage,
    calculateActiveMessage
  }
}
```

- [ ] **Step 2: 验证 TypeScript 类型合规**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 成功无类型报错。

---

### Task 2: 编写右侧导航刻度线组件 (`QuestionRail.vue`)

**Files:**
- Create: `frontend/src/components/chat/QuestionRail.vue`

**Interfaces:**
- Consumes: `UserQuestionItem` from `@/composables/useScrollSpy`
- Props:
  - `questions: UserQuestionItem[]`
  - `activeId: string | null`
  - `loading: boolean`
- Emits:
  - `select: (id: string) => void`

- [ ] **Step 1: 创建 `frontend/src/components/chat/QuestionRail.vue`**

```vue
<!-- 2026-08-23 Asia/Shanghai - 用户问题刻度线导航浮层组件 -->
<template>
  <div
    v-if="questions.length >= 2 && !loading"
    class="absolute right-2 sm:right-4 top-1/2 -translate-y-1/2 z-30 hidden md:flex items-center select-none"
    role="navigation"
    aria-label="用户问题导航"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <!-- 常态：极简竖向刻度线列 -->
    <Transition name="fade">
      <div
        v-if="!isHovered"
        class="flex flex-col items-end gap-3 py-3 px-1.5 cursor-pointer"
        aria-hidden="true"
      >
        <div
          v-for="q in questions"
          :key="q.id"
          v-memo="[q.id, activeId === q.id]"
          class="rounded-full transition-all duration-200"
          :class="[
            activeId === q.id
              ? 'w-5 h-[3px] bg-neutral-900 shadow-xs'
              : 'w-3.5 h-[2px] bg-neutral-300 hover:bg-neutral-500'
          ]"
        />
      </div>
    </Transition>

    <!-- 悬停态：毛玻璃展开卡片 -->
    <Transition name="rail-expand">
      <div
        v-if="isHovered"
        class="flex flex-col gap-1 rounded-2xl border border-neutral-200/80 bg-white/95 p-2.5 shadow-xl backdrop-blur-xl w-64 max-h-[70vh] overflow-y-auto overscroll-contain animate-fade-in"
      >
        <div class="px-2 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
          问题导览 ({{ questions.length }})
        </div>
        <button
          v-for="q in questions"
          :key="q.id"
          v-memo="[q.id, activeId === q.id]"
          type="button"
          class="group flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left transition-all duration-150 cursor-pointer"
          :class="[
            activeId === q.id
              ? 'bg-neutral-100/90 text-neutral-900 font-semibold'
              : 'text-neutral-600 hover:bg-neutral-100/70 hover:text-neutral-900'
          ]"
          :aria-current="activeId === q.id ? 'location' : undefined"
          @click="handleSelect(q.id)"
        >
          <span class="truncate text-xs leading-relaxed flex-1">
            {{ formatQuestion(q.content) }}
          </span>
          <span
            class="rounded-full shrink-0 transition-all duration-200"
            :class="[
              activeId === q.id
                ? 'w-4 h-[3px] bg-neutral-900'
                : 'w-3 h-[2px] bg-neutral-300 group-hover:bg-neutral-700'
            ]"
          />
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { UserQuestionItem } from '@/composables/useScrollSpy'

const props = defineProps<{
  questions: UserQuestionItem[]
  activeId: string | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
}>()

const isHovered = ref(false)

function formatQuestion(content: string): string {
  if (!content) return ''
  return content.replace(/[\r\n]+/g, ' ').trim()
}

function handleSelect(id: string) {
  emit('select', id)
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.rail-expand-enter-active,
.rail-expand-leave-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.rail-expand-enter-from,
.rail-expand-leave-to {
  opacity: 0;
  transform: translateX(8px) scale(0.98);
}
</style>
```

- [ ] **Step 2: 验证编译合规**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 编译通过，无类型错误。

---

### Task 3: 更新 `MessageItem.vue` 注入 DOM 锚点与高亮动画

**Files:**
- Modify: `frontend/src/components/chat/MessageItem.vue`

- [ ] **Step 1: 在根元素绑定 `id` 并增加微光呼吸动画**

在 `MessageItem.vue` 模板最外层添加 `:id="isUser ? 'msg-' + message.id : undefined"`，并在 `<style scoped>` 中追加 `.highlight-pulse` 关键帧动画：

```vue
<!-- 修改 template 根节点 -->
<div
  :id="isUser ? `msg-${message.id}` : undefined"
  class="flex animate-slide-up transition-all duration-300"
  :class="isUser ? 'justify-end' : 'justify-start'"
>
```

```css
/* 添加到 style scoped 底部 */
:deep(.highlight-pulse),
&.highlight-pulse > div {
  animation: message-highlight-pulse 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes message-highlight-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
    transform: scale(1);
  }
  30% {
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.35);
    transform: scale(1.008);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
    transform: scale(1);
  }
}
```

- [ ] **Step 2: 验证编译合规**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 编译通过。

---

### Task 4: 在 `MessageList.vue` 中集成 QuestionRail 与 useScrollSpy

**Files:**
- Modify: `frontend/src/components/chat/MessageList.vue`

- [ ] **Step 1: 在 `MessageList.vue` 中装配 Composable 与组件**

1. 计算 `userQuestions`:
   ```ts
   const userQuestions = computed<UserQuestionItem[]>(() => {
     return messages.value
       .filter((msg) => msg.role === 'user')
       .map((msg, index) => ({
         id: msg.id,
         content: msg.content,
         index: index + 1
       }))
   })
   ```
2. 接入 `useScrollSpy`:
   ```ts
   const { activeId: activeMessageId, scrollToMessage } = useScrollSpy(containerRef, userQuestions)
   ```
3. 更新 `defineExpose`:
   ```ts
   defineExpose({
     scrollToBottom,
     scrollToMessage,
   })
   ```
4. 在模板中渲染 `<QuestionRail :questions="userQuestions" :active-id="activeMessageId" :loading="messagesStore.loading" @select="scrollToMessage" />`。

- [ ] **Step 2: 验证编译合规**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 编译通过。

---

### Task 5: 整体构建验证与文档同步

**Files:**
- Modify: `changelog.md`
- Modify: `README.md`

- [ ] **Step 1: 运行全量前端构建检查**

Run: `cd frontend && npm run build:check`
Expected: TypeScript 类型检查与 Vite 打包全绿通过。

- [ ] **Step 2: 更新 `changelog.md` 与 `README.md`**

在 `changelog.md` 头部新增记录：
- 记录优化时间（2026-08-23）与简要概括；
- 记录 QuestionRail 刻度线导览组件、useScrollSpy 视口动态感知、点击平滑定位与微光呼吸动效。
在 `README.md` 中补充聊天交互特性。

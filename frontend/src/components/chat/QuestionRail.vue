<!-- 2026-08-23 Asia/Shanghai - 用户问题刻度线导航浮层组件 -->
<template>
  <nav
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
        class="flex flex-col items-end gap-2.5 py-3 px-1.5 cursor-pointer"
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
        class="flex flex-col gap-1 rounded-2xl border border-neutral-200/80 bg-white/95 p-2.5 shadow-xl backdrop-blur-xl w-[270px] max-h-[70vh] overflow-y-auto overscroll-contain animate-fade-in"
      >
        <div class="px-2 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
          问题导览 ({{ questions.length }})
        </div>
        <button
          v-for="q in questions"
          :key="q.id"
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
  </nav>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { UserQuestionItem } from '@/composables/useScrollSpy'

defineProps<{
  questions: UserQuestionItem[]
  activeId: string | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
}>()

const isHovered = ref(false)

function formatQuestion(content: string): string {
  if (!content) return '(空提问)'
  return content.replace(/[\r\n]+/g, ' ').trim() || '(空提问)'
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

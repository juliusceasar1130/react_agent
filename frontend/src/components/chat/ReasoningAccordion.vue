<!-- 2026-07-31 23:05 Asia/Shanghai - 深度思考折叠面板组件：支持实时流式打字机效果与耗时计时器 -->
<template>
  <div v-if="reasoningText" class="mb-3 overflow-hidden rounded-xl border border-neutral-200/70 bg-neutral-50/60 dark:border-neutral-800 dark:bg-neutral-900/40">
    <button
      type="button"
      @click="toggleExpand"
      class="flex w-full items-center justify-between px-3.5 py-2 text-left text-xs font-medium text-neutral-600 transition-colors hover:bg-neutral-100/50 dark:text-neutral-400 dark:hover:bg-neutral-800/50"
    >
      <div class="flex items-center gap-2">
        <svg class="h-3.5 w-3.5 text-primary/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
        <span class="font-semibold text-neutral-700 dark:text-neutral-200">深度思考</span>
        <span v-if="isStreaming" class="flex items-center gap-1.5 text-[11px] font-medium text-primary">
          <span class="relative flex h-2 w-2">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/70 opacity-75"></span>
            <span class="relative inline-flex h-2 w-2 rounded-full bg-primary"></span>
          </span>
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
      <div ref="contentRef" class="max-h-60 overflow-y-auto whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-neutral-600 dark:text-neutral-300">
        {{ reasoningText }}
        <span v-if="isStreaming" class="inline-block h-3 w-1.5 animate-pulse bg-primary/70 ml-0.5 align-middle"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'

const props = defineProps<{
  reasoningText?: string
  isStreaming?: boolean
  duration?: number
}>()

const isExpanded = ref(Boolean(props.isStreaming))
const isUserToggled = ref(false)
const startTime = ref<number | null>(null)
const elapsedTime = ref<number>(0)
const contentRef = ref<HTMLDivElement | null>(null)
let timerId: ReturnType<typeof setInterval> | null = null

const toggleExpand = () => {
  isUserToggled.value = true
  isExpanded.value = !isExpanded.value
}

const startTimer = () => {
  if (timerId) clearInterval(timerId)
  if (!startTime.value) {
    startTime.value = Date.now()
  }
  timerId = setInterval(() => {
    if (startTime.value) {
      elapsedTime.value = Math.floor((Date.now() - startTime.value) / 100) / 10
    }
  }, 100)
}

const stopTimer = () => {
  if (timerId) {
    clearInterval(timerId)
    timerId = null
  }
}

watch(
  () => props.isStreaming,
  (newVal, oldVal) => {
    if (newVal) {
      startTimer()
      if (!isUserToggled.value) {
        isExpanded.value = true
      }
    } else {
      stopTimer()
      if (!isUserToggled.value && oldVal !== undefined) {
        isExpanded.value = false
      }
    }
  },
  { immediate: true }
)

watch(
  () => props.reasoningText,
  async () => {
    if (props.isStreaming && isExpanded.value) {
      await nextTick()
      if (contentRef.value) {
        contentRef.value.scrollTop = contentRef.value.scrollHeight
      }
    }
  }
)

onUnmounted(() => {
  stopTimer()
})

const durationText = computed(() => {
  if (props.isStreaming) {
    if (elapsedTime.value > 0) {
      return `已思考 ${elapsedTime.value.toFixed(1)}s`
    }
    return ''
  }

  const finalDuration = (props.duration != null && props.duration >= 0)
    ? props.duration
    : (elapsedTime.value > 0 ? elapsedTime.value : null)

  if (finalDuration !== null) {
    return `已思考 ${finalDuration.toFixed(1)}s`
  }

  if (props.reasoningText && props.reasoningText.trim().length > 0) {
    // 估算显示：大约 20 字符/秒，最低 0.5s
    const estimatedSec = Math.max(0.5, Math.round(props.reasoningText.trim().length / 20 * 10) / 10)
    return `已思考 ${estimatedSec.toFixed(1)}s`
  }

  return ''
})
</script>

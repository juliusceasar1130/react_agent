<!-- 2026-08-02 22:11 Asia/Shanghai - 会话项重构：100% 功能保留下的 LobeChat 极简高透风格 -->
<template>
  <div
    class="group relative cursor-pointer transition-all duration-150"
    :class="[
      isSlim 
        ? (isActive ? 'bg-primary/10 border-primary/20 scale-105 shadow-2xs rounded-full p-1.5' : 'bg-transparent border-transparent hover:bg-neutral-100 rounded-full p-1.5')
        : (isActive ? 'border-neutral-200/80 bg-neutral-200/60 shadow-2xs rounded-lg border px-3 py-2' : 'border-transparent bg-transparent hover:bg-neutral-100/80 hover:border-neutral-200/60 rounded-lg border px-3 py-2')
    ]"
    @click="handleClick"
    :title="isSlim ? session.title : ''"
  >
    <!-- 极简微缩折叠展示状态 -->
    <div v-if="isSlim" class="flex items-center justify-center">
      <div class="relative">
        <div
          class="h-9 w-9 rounded-full flex items-center justify-center font-bold text-xs transition-all duration-200 border shadow-2xs select-none"
          :class="isActive 
            ? 'bg-neutral-800 text-white border-transparent scale-105' 
            : 'bg-white text-neutral-600 border-neutral-200/80 hover:bg-neutral-50 hover:text-neutral-900'"
        >
          {{ session.title ? session.title.trim().charAt(0) : '会' }}
        </div>
        <!-- 折叠态运行状态指示器 -->
        <span
          v-if="isStreaming"
          class="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-white dark:border-neutral-900 animate-pulse shadow-2xs"
          title="正在生成回答..."
        ></span>
      </div>
    </div>

    <!-- 正常展开展示状态 (100% 保留所有字段与功能) -->
    <div v-else class="flex items-center justify-between gap-2">
      <div class="min-w-0 flex-1">
        <!-- 标题与流式生成动画 -->
        <div class="flex items-center gap-1.5">
          <svg
            class="h-3.5 w-3.5 shrink-0 transition-colors duration-150"
            :class="isActive ? 'text-primary' : 'text-neutral-400 group-hover:text-neutral-600'"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <h4 class="truncate text-xs sm:text-sm tracking-tight" :class="isActive ? 'font-semibold text-neutral-900' : 'font-medium text-neutral-700 group-hover:text-neutral-900'">
            {{ session.title }}
          </h4>
          <!-- 展开态运行状态指示器 -->
          <div v-if="isStreaming" class="flex items-center gap-0.5 shrink-0 ml-1" title="正在生成回答...">
            <span class="stream-bar bar-1"></span>
            <span class="stream-bar bar-2"></span>
            <span class="stream-bar bar-3"></span>
          </div>
        </div>

        <!-- 100% 留存元数据：单行优雅收拢排布 -->
        <div class="mt-0.5 flex items-center gap-1.5 text-[11px] text-neutral-400 font-normal">
          <span>{{ formattedUpdatedAt }}</span>
          <span class="text-neutral-300">·</span>
          <span>{{ session.message_count }} 条消息</span>
        </div>
      </div>

      <!-- 删除按键 -->
      <button
        @click.stop="handleDelete"
        class="rounded-md p-1 text-neutral-400 transition-all duration-150 hover:bg-red-50 hover:text-red-500 opacity-0 group-hover:opacity-100 shrink-0"
        title="删除会话"
      >
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Session } from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'
import { useConfirmation } from '@/composables/useConfirmation'
import { useMessagesStore } from '@/stores/messages'

interface Props {
  session: Session
  isActive: boolean
  isSlim?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSlim: false
})

const emit = defineEmits<{
  select: [sessionId: string]
  delete: [sessionId: string]
}>()

const messagesStore = useMessagesStore()
const isStreaming = computed(() => messagesStore.isSessionStreaming(props.session.id))

const { formatFullDateTime, parseServerDate } = useDateFormat()
const { confirm } = useConfirmation()

const formattedUpdatedAt = computed(() => {
  const date = parseServerDate(props.session.updated_at)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffDays < 7) return `${diffDays} 天前`
  return formatFullDateTime(props.session.updated_at)
})

const handleClick = () => {
  emit('select', props.session.id)
}

const handleDelete = async () => {
  const confirmed = await confirm('确定要删除这个会话吗？')
  if (confirmed) {
    emit('delete', props.session.id)
  }
}
</script>

<style scoped>
.stream-bar {
  display: inline-block;
  width: 2px;
  height: 8px;
  background-color: var(--color-primary, #2563eb);
  border-radius: 1px;
  animation: bar-bounce 0.8s ease-in-out infinite alternate;
}
.bar-1 {
  animation-delay: 0.1s;
}
.bar-2 {
  animation-delay: 0.3s;
  height: 12px;
}
.bar-3 {
  animation-delay: 0.5s;
}

@keyframes bar-bounce {
  from {
    transform: scaleY(0.4);
  }
  to {
    transform: scaleY(1.2);
  }
}
</style>

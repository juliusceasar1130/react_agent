<!-- 2026-04-19 23:40 Asia/Shanghai - 会话项更新：轻量卡片层级与清晰选中态 -->
<template>
  <div
    class="group relative cursor-pointer rounded-[22px] border px-4 py-3.5 transition-all duration-200"
    :class="isActive ? 'border-primary/20 bg-gradient-to-r from-primary/10 via-white to-accent/10 shadow-soft' : 'border-transparent bg-white/60 hover:border-neutral-200 hover:bg-white/90'"
    @click="handleClick"
  >
    <div
      class="absolute inset-y-3 left-0 w-1 rounded-full transition-all duration-200"
      :class="isActive ? 'bg-primary' : 'bg-transparent group-hover:bg-neutral-200'"
    ></div>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <div
            class="h-2.5 w-2.5 rounded-full transition-colors duration-200"
            :class="isActive ? 'bg-primary shadow-glow' : 'bg-neutral-300'"
          ></div>
          <h4 class="truncate text-sm font-semibold" :class="isActive ? 'text-primary' : 'text-neutral-700'">
            {{ session.title }}
          </h4>
        </div>
        <div class="mt-2 space-y-1.5 text-xs" :class="isActive ? 'text-primary/70' : 'text-neutral-500'">
          <p class="flex items-center gap-1.5">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {{ formattedUpdatedAt }}
          </p>
          <p class="flex items-center gap-1.5">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            {{ session.message_count }} 条消息
          </p>
        </div>
      </div>
      <button
        @click.stop="handleDelete"
        class="rounded-xl p-2 text-neutral-400 transition-all duration-200 hover:bg-red-50 hover:text-red-500 opacity-100 lg:opacity-0 lg:group-hover:opacity-100"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
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

interface Props {
  session: Session
  isActive: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [sessionId: string]
  delete: [sessionId: string]
}>()

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

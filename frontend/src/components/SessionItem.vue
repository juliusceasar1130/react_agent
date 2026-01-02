<template>
  <div
    class="px-4 py-3 cursor-pointer transition hover:bg-gray-50"
    :class="{ 'bg-blue-50': isActive }"
    @click="handleClick"
  >
    <div class="flex justify-between items-start">
      <div class="flex-1 min-w-0">
        <h4 class="text-sm font-medium text-gray-800 truncate">
          {{ session.title }}
        </h4>
        <!-- 显示详细信息 - 2025-01-01 -->
        <div class="text-xs text-gray-400 mt-1 space-y-0.5">
          <p>创建于：{{ formattedCreatedAt }}</p>
          <p>更新于：{{ formattedUpdatedAt }}</p>
          <p>消息数：{{ session.message_count }} 条</p>
        </div>
      </div>
      <button
        @click.stop="handleDelete"
        class="ml-2 text-gray-400 hover:text-red-500 transition"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

const { formatFullDateTime } = useDateFormat()
const { confirm } = useConfirmation()

// 格式化创建时间（年月日小时分钟）- 2025-01-01
const formattedCreatedAt = computed(() => formatFullDateTime(props.session.created_at))

// 格式化更新时间（年月日小时分钟）- 2025-01-01
const formattedUpdatedAt = computed(() => formatFullDateTime(props.session.updated_at))

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

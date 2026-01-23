<!-- 2025-01-07 - 会话列表美化：优雅滚动与空状态 -->
<template>
  <div class="flex-1 overflow-y-auto">
    <div v-if="sessions.length === 0" class="p-6 text-center">
      <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-neutral-100 mb-3">
        <svg class="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </div>
      <p class="text-neutral-400 text-sm">暂无会话</p>
      <p class="text-neutral-500 text-xs mt-1">点击上方"新建"创建对话</p>
    </div>
    <div v-else class="divide-y divide-neutral-100">
      <SessionItem
        v-for="session in sessions"
        :key="session.id"
        :session="session"
        :is-active="session.id === currentSessionId"
        @select="handleSelectSession"
        @delete="handleDeleteSession"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import SessionItem from './SessionItem.vue'

const sessionsStore = useSessionsStore()

const sessions = computed(() => sessionsStore.sessions)
const currentSessionId = computed(() => sessionsStore.currentSessionId)

const handleSelectSession = (sessionId: string) => {
  sessionsStore.setCurrentSession(sessionId)
}

const handleDeleteSession = async (sessionId: string) => {
  await sessionsStore.deleteSession(sessionId)
}

onMounted(() => {
  sessionsStore.fetchSessions()
})
</script>

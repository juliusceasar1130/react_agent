<template>
  <div class="flex-1 overflow-y-auto">
    <div v-if="sessions.length === 0" class="p-4 text-center text-gray-400">
      暂无会话
    </div>
    <div v-else class="divide-y divide-gray-100">
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

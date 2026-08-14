<!-- 2026-04-19 23:40 Asia/Shanghai - 会话列表更新：更轻的导航面板与移动端联动 -->
<template>
  <div class="flex-1 overflow-y-auto transition-all duration-300" :class="isSlim ? 'px-2 py-3' : 'px-3 py-3 sm:px-4'">
    <div v-if="sessions.length === 0" class="panel px-5 py-8 text-center">
      <div class="mb-3 inline-flex h-16 w-16 items-center justify-center rounded-[22px] bg-gradient-to-br from-primary/10 via-white to-accent/10">
        <svg class="h-8 w-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </div>
      <p class="text-sm font-semibold text-text" v-if="!isSlim">暂无会话</p>
      <p class="mt-1 text-xs leading-5 text-neutral-500" v-if="!isSlim">点击上方“新建”创建对话，开始新的聊天主题。</p>
    </div>
    <div v-else class="space-y-2">
      <SessionItem
        v-for="session in sessions"
        :key="session.id"
        :session="session"
        :is-active="session.id === currentSessionId"
        :is-slim="isSlim"
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

withDefaults(defineProps<{
  isSlim?: boolean
}>(), {
  isSlim: false
})

const sessionsStore = useSessionsStore()

const emit = defineEmits<{
  selected: []
}>()

const sessions = computed(() => sessionsStore.sessions)
const currentSessionId = computed(() => sessionsStore.currentSessionId)

const handleSelectSession = (sessionId: string) => {
  sessionsStore.setCurrentSession(sessionId)
  emit('selected')
}

const handleDeleteSession = async (sessionId: string) => {
  await sessionsStore.deleteSession(sessionId)
}

onMounted(() => {
  sessionsStore.fetchSessions()
})
</script>

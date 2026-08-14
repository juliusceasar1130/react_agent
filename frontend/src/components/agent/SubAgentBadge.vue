<!-- 2026-04-10 Asia/Shanghai - 子智能体角色动态切换 Badge (支持通用/SQL/规划器等角色标识) -->
<template>
  <div
    v-if="subagent"
    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium tracking-wide transition-all duration-300 select-none shadow-2xs border"
    :class="badgeClasses"
  >
    <span class="relative flex h-2 w-2">
      <span
        v-if="isStreaming"
        class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
        :class="dotPingClass"
      ></span>
      <span
        class="relative inline-flex rounded-full h-2 w-2"
        :class="dotClass"
      ></span>
    </span>

    <svg
      v-if="subagent === 'sql_domain_agent'"
      class="w-3.5 h-3.5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
      ></path>
    </svg>

    <svg
      v-else
      class="w-3.5 h-3.5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
      ></path>
    </svg>

    <span>{{ badgeLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    subagent?: string | null
    displayName?: string | null
    isStreaming?: boolean
  }>(),
  {
    subagent: null,
    displayName: null,
    isStreaming: false,
  }
)

const badgeLabel = computed(() => {
  if (props.displayName) return props.displayName
  if (props.subagent === 'sql_domain_agent') return 'SQL数据助手'
  return '通用助手'
})

const badgeClasses = computed(() => {
  if (props.subagent === 'sql_domain_agent') {
    return 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 hover:bg-blue-500/15'
  }
  return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/15'
})

const dotClass = computed(() => {
  if (props.subagent === 'sql_domain_agent') return 'bg-blue-500'
  return 'bg-emerald-500'
})

const dotPingClass = computed(() => {
  if (props.subagent === 'sql_domain_agent') return 'bg-blue-400'
  return 'bg-emerald-400'
})
</script>

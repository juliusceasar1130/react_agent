<!-- frontend/src/components/ScalarResult.vue -->
<template>
  <div class="flex flex-col items-center justify-center p-8 bg-gradient-to-br from-white via-neutral-50 to-primary/5 rounded-2xl border border-neutral-200/80 shadow-sm space-y-2">
    <span class="text-xs font-semibold text-neutral-500 uppercase tracking-wider">{{ label || '查询指标' }}</span>
    <span class="text-4xl font-extrabold text-primary tracking-tight font-mono">
      {{ value }}
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  value: string | number
  label?: string
}>()
</script>

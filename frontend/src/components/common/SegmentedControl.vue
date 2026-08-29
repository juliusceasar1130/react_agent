<!-- 2026-08-28 Asia/Shanghai - Phase 3: 四档分段选择器，替换 ToggleSwitch -->
<template>
  <div class="inline-flex items-center rounded-lg bg-neutral-100/80 dark:bg-neutral-800/80 p-0.5 gap-0.5">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="px-2.5 py-1 text-[11px] font-medium rounded-md transition-all duration-200"
      :class="modelValue === opt.value
        ? 'bg-white dark:bg-neutral-700 text-primary shadow-sm'
        : 'text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200'"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
interface Option {
  label: string
  value: string
}

defineProps<{
  modelValue: string
  options: Option[]
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

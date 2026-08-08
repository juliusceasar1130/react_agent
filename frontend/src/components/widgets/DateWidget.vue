<!-- frontend/src/components/widgets/DateWidget.vue -->
<template>
  <div class="relative">
    <input
      :type="paramDef?.widget === 'daterange' ? 'text' : 'date'"
      :value="modelValue"
      :placeholder="paramDef?.widget === 'daterange' ? 'YYYY-MM-DD 至 YYYY-MM-DD' : '选择日期'"
      class="w-full px-3 py-2 bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-xl text-xs text-neutral-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-200"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </div>
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

defineProps<{
  modelValue: any
  paramDef: ParameterDef
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: any): void
}>()
</script>

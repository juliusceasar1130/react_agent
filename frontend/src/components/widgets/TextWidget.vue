<!-- frontend/src/components/widgets/TextWidget.vue -->
<template>
  <input
    type="text"
    :value="modelValue"
    :placeholder="paramDef.description || '请输入文本'"
    class="w-full px-3 py-2 bg-white border border-neutral-200 rounded-xl text-xs text-neutral-800 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all placeholder-neutral-400 shadow-sm"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

defineProps<{
  modelValue: string
  paramDef: ParameterDef
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>

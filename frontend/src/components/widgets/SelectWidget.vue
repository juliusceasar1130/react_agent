<!-- frontend/src/components/widgets/SelectWidget.vue -->
<template>
  <select
    :value="modelValue"
    class="w-full px-3 py-2 bg-white border border-neutral-200 rounded-xl text-xs text-neutral-800 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all cursor-pointer shadow-sm"
    @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
  >
    <option
      v-for="opt in paramDef.options"
      :key="opt.value"
      :value="opt.value"
    >
      {{ opt.label }}
    </option>
  </select>
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

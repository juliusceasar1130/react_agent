<!-- frontend/src/components/widgets/MultiSelectWidget.vue -->
<template>
  <div class="flex flex-wrap gap-1.5">
    <button
      v-for="opt in paramDef.options"
      :key="opt.value"
      type="button"
      :class="[
        'px-2.5 py-1 text-xs rounded-lg border transition-all cursor-pointer shadow-xs',
        isSelected(opt.value)
          ? 'bg-primary border-primary text-white font-medium shadow-glow'
          : 'bg-white border-neutral-200 text-neutral-600 hover:border-neutral-300 hover:text-neutral-900'
      ]"
      @click="toggleValue(opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

const props = defineProps<{
  modelValue: string[] | string
  paramDef: ParameterDef
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

function currentArray(): string[] {
  if (Array.isArray(props.modelValue)) return props.modelValue
  if (typeof props.modelValue === 'string' && props.modelValue) return props.modelValue.split(',')
  return []
}

function isSelected(val: string): boolean {
  return currentArray().includes(val)
}

function toggleValue(val: string) {
  const arr = [...currentArray()]
  const idx = arr.indexOf(val)
  if (idx >= 0) {
    arr.splice(idx, 1)
  } else {
    arr.push(val)
  }
  emit('update:modelValue', arr)
}
</script>

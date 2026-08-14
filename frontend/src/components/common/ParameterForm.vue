<!-- frontend/src/components/ParameterForm.vue -->
<template>
  <form class="flex flex-col sm:flex-row sm:items-end justify-between gap-3" @submit.prevent="$emit('submit')">
    <!-- 动态部件自适应横向网格 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 flex-1 min-w-0">
      <div
        v-for="(pDef, pKey) in parameters"
        :key="pKey"
        class="flex flex-col space-y-1 min-w-0"
      >
        <label class="text-[11px] font-semibold text-neutral-600 flex items-center justify-between truncate">
          <span class="truncate">{{ pDef.description || pKey }}</span>
        </label>

        <!-- 动态部件分发 -->
        <component
          :is="getWidgetComponent(pDef.widget)"
          :model-value="values[pKey] ?? ''"
          :param-def="pDef"
          @update:model-value="onValueChange(pKey as string, $event)"
        />
      </div>
    </div>

    <!-- 提交按钮区（行内右对齐） -->
    <div class="shrink-0 pt-1 sm:pt-0">
      <button
        type="submit"
        :disabled="loading"
        class="w-full sm:w-auto px-4 py-2 bg-primary hover:bg-primary-hover disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all duration-200 shadow-glow flex items-center justify-center space-x-1.5 cursor-pointer active:scale-98 whitespace-nowrap"
      >
        <span v-if="loading" class="animate-spin text-xs">🌀</span>
        <span>查询</span>
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'
import TextWidget from '@/components/widgets/TextWidget.vue'
import NumberWidget from '@/components/widgets/NumberWidget.vue'
import SelectWidget from '@/components/widgets/SelectWidget.vue'
import MultiSelectWidget from '@/components/widgets/MultiSelectWidget.vue'

import DateWidget from '@/components/widgets/DateWidget.vue'

const props = defineProps<{
  parameters: Record<string, ParameterDef>
  values: Record<string, any>
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:values', values: Record<string, any>): void
  (e: 'submit'): void
}>()

function getWidgetComponent(widget: string) {
  switch (widget) {
    case 'number':
      return NumberWidget
    case 'select':
      return SelectWidget
    case 'multiselect':
      return MultiSelectWidget
    case 'date':
    case 'daterange':
      return DateWidget
    case 'text':
    default:
      return TextWidget
  }
}

function onValueChange(key: string, val: any) {
  const updated = { ...props.values, [key]: val }
  emit('update:values', updated)
}
</script>

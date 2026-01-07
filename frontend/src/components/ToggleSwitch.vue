<!-- 创建日期: 2025-01-07 - 可复用的开关组件 -->
<template>
  <label class="inline-flex items-center gap-2.5 cursor-pointer group">
    <!-- 隐藏的 checkbox input -->
    <input
      :modelValue="modelValue"
      @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
      type="checkbox"
      class="sr-only peer"
    />

    <!-- 开关轨道 -->
    <div
      class="relative w-11 h-6 rounded-full transition-all duration-300 ease-out peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-indigo-500/50"
      :class="modelValue ? 'bg-indigo-500 shadow-md shadow-indigo-500/30' : 'bg-warm-300'"
    >
      <!-- 开关滑块 -->
      <div
        class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-all duration-300 ease-out flex items-center justify-center"
        :class="modelValue ? 'translate-x-5' : 'translate-x-0'"
      >
        <!-- 开启状态图标 -->
        <svg v-if="modelValue" class="w-3 h-3 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
        </svg>
        <!-- 关闭状态图标 -->
        <svg v-else class="w-3 h-3 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </div>
    </div>

    <!-- 标签文字 -->
    <span
      v-if="label"
      class="text-sm font-medium transition-colors duration-200 select-none"
      :class="modelValue ? 'text-indigo-600' : 'text-warm-600 group-hover:text-warm-800'"
    >
      {{ label }}
    </span>

    <!-- 状态文字 -->
    <span
      v-if="showStatus"
      class="text-xs transition-colors duration-200 select-none"
      :class="modelValue ? 'text-indigo-400' : 'text-warm-400'"
    >
      {{ modelValue ? onLabel : offLabel }}
    </span>
  </label>
</template>

<script setup lang="ts">
interface Props {
  modelValue: boolean
  label?: string
  showStatus?: boolean
  onLabel?: string
  offLabel?: string
}

withDefaults(defineProps<Props>(), {
  showStatus: false,
  onLabel: '已开启',
  offLabel: '已关闭'
})

defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

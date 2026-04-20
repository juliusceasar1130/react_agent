<!-- 2026-04-19 23:40 Asia/Shanghai - 开关组件更新：适配明亮卡片式主题 -->
<template>
  <label class="group inline-flex cursor-pointer items-center gap-2.5">
    <input
      :checked="modelValue"
      @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
      type="checkbox"
      class="sr-only peer"
    />

    <div
      class="relative h-6 w-11 rounded-full transition-all duration-300 ease-out peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary/50"
      :class="modelValue ? 'bg-primary shadow-md shadow-primary/20' : 'bg-neutral-300'"
    >
      <div
        class="absolute left-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-sm transition-all duration-300 ease-out"
        :class="modelValue ? 'translate-x-5' : 'translate-x-0'"
      >
        <svg v-if="modelValue" class="h-3 w-3 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
        </svg>
        <svg v-else class="h-3 w-3 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <span
        v-if="label"
        class="select-none text-[13px] font-medium transition-colors duration-200"
        :class="modelValue ? 'text-primary' : 'text-neutral-600 group-hover:text-text'"
      >
        {{ label }}
      </span>

      <span
        v-if="showStatus"
        class="select-none text-[11px] transition-colors duration-200"
        :class="modelValue ? 'text-primary/80' : 'text-neutral-400'"
      >
        {{ modelValue ? onLabel : offLabel }}
      </span>
    </div>
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

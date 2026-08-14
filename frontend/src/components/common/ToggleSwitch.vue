<!-- 2026-04-19 23:40 Asia/Shanghai - 开关组件更新：适配明亮卡片式主题 -->
<template>
  <label class="group inline-flex cursor-pointer items-center gap-2">
    <input
      :checked="modelValue"
      @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
      type="checkbox"
      class="sr-only peer"
    />

    <div
      class="relative h-5 w-9 rounded-full transition-all duration-200 ease-out peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary/15"
      :class="modelValue ? 'bg-primary/10 border border-primary/25 dark:bg-primary/20 dark:border-primary/30' : 'bg-neutral-200/80 border border-neutral-300/60 dark:bg-neutral-700/80 dark:border-neutral-600/60'"
    >
      <div
        class="absolute left-0.5 top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full transition-all duration-200 ease-out shadow-sm"
        :class="modelValue ? 'translate-x-4 bg-primary/30 border border-primary/40 text-primary dark:bg-primary/40' : 'translate-x-0 bg-white text-neutral-400 dark:bg-neutral-300'"
      >
        <svg v-if="modelValue" class="h-2.5 w-2.5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
        </svg>
        <svg v-else class="h-2.5 w-2.5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </div>
    </div>

    <div class="flex items-center gap-1.5">
      <span
        v-if="label"
        class="select-none text-[12px] font-medium transition-colors duration-200"
        :class="modelValue ? 'text-neutral-700 dark:text-neutral-200' : 'text-neutral-500 group-hover:text-neutral-700 dark:text-neutral-400'"
      >
        {{ label }}
      </span>

      <span
        v-if="showStatus"
        class="select-none text-[11px] transition-colors duration-200"
        :class="modelValue ? 'text-neutral-400 dark:text-neutral-400' : 'text-neutral-400 dark:text-neutral-500'"
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

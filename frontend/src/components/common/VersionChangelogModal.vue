<!-- Path: frontend/src/components/VersionChangelogModal.vue -->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

import defaultChangelogData from '@/config/changelog.json'

export interface ChangelogItem {
  version: string;
  date: string;
  type: 'latest' | 'major' | 'regular';
  summary?: string;
  content: {
    features?: string[];
    improvements?: string[];
    fixes?: string[];
  };
}

const props = withDefaults(
  defineProps<{
    show: boolean;
    data?: ChangelogItem[];
  }>(),
  {
    show: false
  }
)

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void;
}>()

const defaultChangelog = defaultChangelogData as ChangelogItem[]

const changelogData = computed(() => props.data || defaultChangelog)
const activeIndex = ref(0)
const activeItem = computed(() => changelogData.value[activeIndex.value] || null)

const closeModal = () => {
  emit('update:show', false)
}

// Prevent scroll leak when modal is open
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      document.body.classList.add('overflow-hidden')
    } else {
      document.body.classList.remove('overflow-hidden')
    }
  }
)

// Handle ESC key press
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.show) {
    closeModal()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  document.body.classList.remove('overflow-hidden')
})
</script>

<template>
  <Transition name="modal-fade">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      <!-- Overlay Mask -->
      <div
        class="fixed inset-0 bg-neutral-900/40 backdrop-blur-md transition-opacity"
        @click="closeModal"
      ></div>

      <!-- Modal Container -->
      <div
        class="relative w-full max-w-4xl h-[600px] flex flex-col md:flex-row rounded-[28px] bg-white/95 dark:bg-neutral-900/95 border border-neutral-200/50 dark:border-neutral-800 shadow-2xl overflow-hidden backdrop-blur-2xl transition-all duration-300 z-10"
      >
        <!-- Close button -->
        <button
          @click="closeModal"
          class="absolute top-4 right-4 z-20 flex h-8 w-8 items-center justify-center rounded-full text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
          title="关闭说明"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <!-- Left Column: Timeline Navigation -->
        <div class="w-full md:w-[280px] shrink-0 border-b md:border-b-0 md:border-r border-neutral-200/60 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-950/20 flex flex-col min-h-0">
          <!-- Left Header -->
          <div class="p-6 border-b border-neutral-200/60 dark:border-neutral-800 shrink-0">
            <h3 class="text-lg font-bold text-text dark:text-neutral-100 flex items-center gap-2">
              <span>ℹ️</span>
              <span>关于系统</span>
            </h3>
            <p class="text-xs text-neutral-500 mt-1">了解系统最新的升级与改动</p>
          </div>

          <!-- List -->
          <div class="flex-1 overflow-y-auto px-4 py-6 space-y-1 relative">
            <!-- Central Timeline line -->
            <div class="absolute left-8 top-8 bottom-8 w-[1px] bg-neutral-200 dark:bg-neutral-800 z-0"></div>

            <button
              v-for="(item, idx) in changelogData"
              :key="item.version"
              @click="activeIndex = idx"
              class="w-full text-left flex items-start gap-4 px-4 py-3 rounded-2xl transition-all duration-200 relative z-10"
              :class="activeIndex === idx
                ? 'bg-primary/5 dark:bg-primary/10 border-l-2 border-primary text-primary font-semibold'
                : 'hover:bg-neutral-100/60 dark:hover:bg-neutral-800/40 text-neutral-600 dark:text-neutral-400 border-l-2 border-transparent'"
            >
              <!-- Status indicator bullet -->
              <div class="mt-1 flex items-center justify-center shrink-0">
                <span
                  class="h-2.5 w-2.5 rounded-full"
                  :class="[
                    item.type === 'latest' ? 'bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]' : '',
                    item.type === 'major' ? 'bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]' : '',
                    item.type === 'regular' ? 'bg-neutral-400 dark:bg-neutral-600' : ''
                  ]"
                ></span>
              </div>

              <div class="min-w-0">
                <div class="text-sm font-medium flex items-center gap-1.5">
                  <span :class="activeIndex === idx ? 'text-primary' : 'text-neutral-800 dark:text-neutral-200'">{{ item.version }}</span>
                  <span
                    v-if="item.type === 'latest'"
                    class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  >
                    当前
                  </span>
                </div>
                <div class="text-[11px] text-neutral-400 mt-0.5">{{ item.date }}</div>
              </div>
            </button>
          </div>
        </div>

        <!-- Right Column: Changelog Details -->
        <div class="flex-1 min-h-0 flex flex-col bg-white dark:bg-neutral-900">
          <Transition name="slide-fade" mode="out-in">
            <div
              v-if="activeItem"
              :key="activeItem.version"
              class="flex-1 overflow-y-auto p-6 sm:p-8 space-y-6"
            >
              <!-- Header of right column -->
              <div class="border-b border-neutral-100 dark:border-neutral-800 pb-4">
                <div class="flex items-center gap-3">
                  <h2 class="text-2xl font-black text-neutral-900 dark:text-neutral-100">{{ activeItem.version }}</h2>
                  <span class="text-sm text-neutral-400">{{ activeItem.date }}</span>
                </div>
                <p v-if="activeItem.summary" class="mt-2 text-sm text-neutral-600 dark:text-neutral-300 leading-relaxed font-medium">
                  {{ activeItem.summary }}
                </p>
              </div>

              <!-- Categorized Cards -->
              <div class="space-y-4">
                <!-- Features -->
                <div
                  v-if="activeItem.content.features && activeItem.content.features.length > 0"
                  class="rounded-2xl p-5 border bg-gradient-to-br from-emerald-50/40 to-white/40 dark:from-emerald-950/10 dark:to-neutral-900/40 border-emerald-100/80 dark:border-emerald-900/40 shadow-sm"
                >
                  <h4 class="text-sm font-bold text-emerald-800 dark:text-emerald-400 flex items-center gap-2 mb-3">
                    <span>🎉</span>
                    <span>新特性 Features</span>
                  </h4>
                  <ul class="space-y-2 text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed list-disc list-inside">
                    <li v-for="feat in activeItem.content.features" :key="feat">{{ feat }}</li>
                  </ul>
                </div>

                <!-- Improvements -->
                <div
                  v-if="activeItem.content.improvements && activeItem.content.improvements.length > 0"
                  class="rounded-2xl p-5 border bg-gradient-to-br from-amber-50/40 to-white/40 dark:from-amber-950/10 dark:to-neutral-900/40 border-amber-100/80 dark:border-amber-900/40 shadow-sm"
                >
                  <h4 class="text-sm font-bold text-amber-800 dark:text-amber-400 flex items-center gap-2 mb-3">
                    <span>⚡</span>
                    <span>性能与优化 Improvements</span>
                  </h4>
                  <ul class="space-y-2 text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed list-disc list-inside">
                    <li v-for="imp in activeItem.content.improvements" :key="imp">{{ imp }}</li>
                  </ul>
                </div>

                <!-- Bug Fixes -->
                <div
                  v-if="activeItem.content.fixes && activeItem.content.fixes.length > 0"
                  class="rounded-2xl p-5 border bg-gradient-to-br from-rose-50/40 to-white/40 dark:from-rose-950/10 dark:to-neutral-900/40 border-rose-100/80 dark:border-rose-900/40 shadow-sm"
                >
                  <h4 class="text-sm font-bold text-rose-800 dark:text-rose-400 flex items-center gap-2 mb-3">
                    <span>🐛</span>
                    <span>修复缺陷 Bug Fixes</span>
                  </h4>
                  <ul class="space-y-2 text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed list-disc list-inside">
                    <li v-for="fix in activeItem.content.fixes" :key="fix">{{ fix }}</li>
                  </ul>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Transition for modal fade */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* Transition for right column switch */
.slide-fade-enter-active {
  transition: all 0.22s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.12s ease-in;
}
.slide-fade-enter-from {
  transform: translateY(8px);
  opacity: 0;
}
.slide-fade-leave-to {
  transform: translateY(-8px);
  opacity: 0;
}
</style>

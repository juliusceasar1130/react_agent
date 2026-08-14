<!-- frontend/src/components/ScenarioModal.vue -->
<template>
  <Transition name="modal-fade">
    <div
      v-if="store.visible"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8"
    >
      <!-- 弹窗背景遮罩 -->
      <div
        class="absolute inset-0 bg-neutral-900/40 backdrop-blur-[3px]"
        @click="store.close()"
      ></div>

      <!-- 弹窗主体容器 -->
      <div
        class="relative z-10 flex h-[88vh] w-full max-w-5xl flex-col rounded-3xl border border-neutral-200/80 bg-white/95 p-5 shadow-2xl backdrop-blur-xl animate-scale-up"
      >
        <!-- 极简单行头部栏 -->
        <div class="mb-3 flex items-center justify-between pb-3 border-b border-neutral-200/80 shrink-0">
          <div class="flex items-center space-x-2.5 min-w-0">
            <span class="flex h-7 w-7 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 border border-amber-500/20 shrink-0">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </span>
            <h2 class="text-lg font-bold text-neutral-800 tracking-tight truncate">
              {{ store.currentScenarioTitle }}
            </h2>
          </div>

          <div class="flex items-center space-x-2 shrink-0">
            <button
              type="button"
              class="h-8 px-2.5 rounded-xl border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-all text-xs font-semibold flex items-center space-x-1.5 cursor-pointer active:scale-95 shadow-xs"
              title="刷新查询"
              @click="store.refresh()"
            >
              <svg class="h-3.5 w-3.5 text-neutral-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
                <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                <path d="M16 16h5v5" />
              </svg>
              <span>刷新</span>
            </button>
            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-xl border border-neutral-200 bg-white text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800 transition-all cursor-pointer active:scale-95 shadow-xs"
              title="关闭弹窗"
              @click="store.close()"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <!-- 模板 Tab 切换条（如多模板） -->
        <div
          v-if="store.paramsMeta?.templates && store.paramsMeta.templates.length > 1"
          class="mb-3 flex p-1 bg-neutral-100/90 rounded-2xl border border-neutral-200/60 shrink-0"
        >
          <button
            v-for="tpl in store.paramsMeta.templates"
            :key="tpl.name"
            type="button"
            :class="[
              'flex-1 py-1.5 px-3 text-xs font-bold rounded-xl transition-all cursor-pointer truncate',
              store.activeTemplate === tpl.name
                ? 'bg-white text-primary shadow-sm'
                : 'text-neutral-500 hover:text-neutral-900'
            ]"
            :title="tpl.label"
            @click="store.switchTemplate(tpl.name)"
          >
            {{ tpl.label }}
          </button>
        </div>

        <!-- 主体垂直伸缩区域 -->
        <div class="flex-1 min-h-0 flex flex-col space-y-3">
          <!-- 紧凑横向参数配置区 -->
          <div v-if="store.paramsMeta?.parameters" class="p-3 bg-neutral-50/70 rounded-2xl border border-neutral-200/80 shadow-2xs shrink-0">
            <ParameterForm
              :parameters="store.paramsMeta.parameters"
              :values="store.currentParamValues"
              :loading="store.isQueryLoading"
              @update:values="store.updateParamValues($event)"
              @submit="store.executeQuery()"
            />
          </div>

          <!-- 全量铺开直通结果呈现区 (单层平铺显示) -->
          <div class="flex-1 min-h-0 flex flex-col">
            <ResultRenderer
              :result="store.queryResult"
              :loading="store.isQueryLoading"
              :error="store.queryError"
              class="h-full"
              @retry="store.executeQuery()"
              @change-page="store.changePage($event)"
              @change-page-size="store.changePageSize($event)"
            />
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { useScenarioPanelStore } from '@/stores/scenarioPanel'
import ParameterForm from './ParameterForm.vue'
import ResultRenderer from './ResultRenderer.vue'

const store = useScenarioPanelStore()
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.25s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active :deep(.animate-scale-up) {
  animation: scale-up 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-fade-leave-active :deep(.animate-scale-up) {
  animation: scale-down 0.2s ease-in;
}

@keyframes scale-up {
  from {
    transform: scale(0.95);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes scale-down {
  from {
    transform: scale(1);
    opacity: 1;
  }
  to {
    transform: scale(0.95);
    opacity: 0;
  }
}
</style>

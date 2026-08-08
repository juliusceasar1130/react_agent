<!-- frontend/src/components/FloatingScenarioCards.vue -->
<template>
  <div
    v-if="directScenarios.length > 0"
    class="fixed right-4 sm:right-6 top-20 z-30 flex flex-col items-end space-y-2 pointer-events-none"
    :style="{ transform: `translate3d(${dragOffset.x}px, ${dragOffset.y}px, 0)` }"
  >
    <!-- 折叠/展开 掌控微按钮 (支持按住自由拖拽) -->
    <button
      v-if="directScenarios.length > 1"
      type="button"
      @mousedown="onPointerDown"
      @touchstart="onPointerDown"
      @click="handleToggleExpand"
      class="pointer-events-auto flex items-center space-x-1.5 rounded-lg border border-neutral-200/80 bg-white/85 px-3 py-1.5 text-xs font-medium text-neutral-700 shadow-2xs backdrop-blur-md transition-all hover:bg-white hover:border-neutral-300 active:scale-95 cursor-grab active:cursor-grabbing select-none"
      :title="isExpanded ? '按住拖动 / 点击收起' : '按住拖动 / 点击展开'"
    >
      <svg class="h-3.5 w-3.5 text-primary shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      <span class="text-xs">快捷直通 ({{ directScenarios.length }})</span>
      <svg
        class="h-3 w-3 text-neutral-400 transition-transform duration-200"
        :class="isExpanded ? 'rotate-180' : ''"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- 极简高透 IDE 下拉菜单面板 -->
    <Transition name="card-stack">
      <div
        v-if="isExpanded"
        class="pointer-events-auto flex flex-col space-y-1 rounded-lg border border-neutral-200/80 bg-neutral-50/90 p-1.5 shadow-md backdrop-blur-md transition-all min-w-[130px]"
      >
        <div
          v-for="item in directScenarios"
          :key="`${item.domain}/${item.scenario.name}`"
          class="flex items-center space-x-2 rounded-md px-2.5 py-1.5 text-xs font-medium text-neutral-700 transition-all duration-150 hover:bg-white hover:text-primary hover:shadow-2xs group cursor-pointer"
          @click="handleOpenScenario(item.domain, item.scenario.name)"
          :title="item.scenario.description || item.scenario.title"
        >
          <!-- 极简单色矢量 Icon -->
          <svg v-if="getScenarioIconType(item.scenario.name, item.scenario.title) === 'car'" class="h-3.5 w-3.5 text-neutral-500 group-hover:text-primary transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 16H9m10 0h3v-3.15a1 1 0 00-.84-.99L16 11l-2.7-3.6a1 1 0 00-.8-.4H7.5a1 1 0 00-.8.4L4 11l-2.16.86A1 1 0 001 12.85V16h3"/>
            <circle cx="6.5" cy="16.5" r="2.5"/>
            <circle cx="16.5" cy="16.5" r="2.5"/>
          </svg>
          <svg v-else-if="getScenarioIconType(item.scenario.name, item.scenario.title) === 'lightning'" class="h-3.5 w-3.5 text-neutral-500 group-hover:text-primary transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
          <svg v-else-if="getScenarioIconType(item.scenario.name, item.scenario.title) === 'chart'" class="h-3.5 w-3.5 text-neutral-500 group-hover:text-primary transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 20V10M12 20V4M6 20v-6" />
          </svg>
          <svg v-else-if="getScenarioIconType(item.scenario.name, item.scenario.title) === 'target'" class="h-3.5 w-3.5 text-neutral-500 group-hover:text-primary transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="6" />
            <circle cx="12" cy="12" r="2" />
          </svg>
          <svg v-else-if="getScenarioIconType(item.scenario.name, item.scenario.title) === 'search'" class="h-3.5 w-3.5 text-neutral-500 group-hover:text-primary transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <svg v-else class="h-3.5 w-3.5 text-neutral-500 group-hover:text-primary transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
          <span class="whitespace-nowrap">{{ item.scenario.title }}</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useScenarioPanelStore } from '@/stores/scenarioPanel'
import { useDrag } from '@/composables/useDrag'
import type { ScenarioSummary } from '@/api/scenarios'

const store = useScenarioPanelStore()
const isExpanded = ref(true)

// 拖拽手势（鼠标 + 触摸支持）
const { position: dragOffset, onPointerDown, hasMoved } = useDrag()

function handleToggleExpand() {
  if (hasMoved.value) return
  isExpanded.value = !isExpanded.value
}



function getScenarioIconType(scenarioName: string, title: string): 'car' | 'lightning' | 'chart' | 'target' | 'search' | 'layers' {
  const name = (scenarioName || '').toLowerCase()
  const t = title || ''
  if (name.includes('vehicle') || t.includes('项目车') || (t.includes('车') && !t.includes('滞留'))) {
    return 'car'
  }
  if (name.includes('stranded') || name.includes('quick') || t.includes('滞留') || t.includes('快捷')) {
    return 'lightning'
  }
  if (name.includes('chart') || name.includes('stat') || t.includes('统计') || t.includes('分析')) {
    return 'chart'
  }
  if (name.includes('target') || name.includes('monitor') || t.includes('检测') || t.includes('监控')) {
    return 'target'
  }
  if (name.includes('search') || t.includes('查询') || t.includes('搜索')) {
    return 'search'
  }
  return 'layers'
}

onMounted(() => {
  if (store.domains.length === 0) {
    store.fetchDomainTree()
  }
})


// 过滤出具备直通能力的场景
const directScenarios = computed(() => {
  const list: { domain: string; domainTitle: string; scenario: ScenarioSummary }[] = []
  for (const domain of store.domains) {
    for (const scenario of domain.scenarios) {
      if (scenario.direct_path_enabled !== false) {
        list.push({
          domain: domain.domain,
          domainTitle: domain.domain_title,
          scenario,
        })
      }
    }
  }
  return list
})

function handleOpenScenario(domain: string, scenarioName: string) {
  store.open(domain, scenarioName)
}
</script>

<style scoped>
.card-stack-enter-active,
.card-stack-leave-active {
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.card-stack-enter-from,
.card-stack-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.96);
}
</style>

<!-- frontend/src/components/artifacts/ChartGroupCard.vue -->
<template>
  <div v-if="charts && charts.length > 0" class="w-full space-y-2 text-left animate-fade-in">
    <!-- 多图表：Tab 选项卡切换容器 -->
    <div
      v-if="charts.length > 1"
      class="rounded-2xl border border-[#D8E2EE] bg-white/95 shadow-sm overflow-hidden"
    >
      <!-- 头部 Tab 导航栏 -->
      <div class="flex items-center justify-between border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 py-2.5">
        <div class="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
          <button
            v-for="(chart, idx) in charts"
            :key="chart.chart_id || idx"
            type="button"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150 cursor-pointer shrink-0"
            :class="[
              activeIdx === idx
                ? 'bg-primary text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-200/60 hover:text-slate-900 bg-white border border-slate-200/70'
            ]"
            @click="activeIdx = idx"
          >
            <span>{{ chart.chart_type === 'line' ? '📈' : '📊' }}</span>
            <span class="max-w-[140px] truncate">{{ chart.title || `图表 ${idx + 1}` }}</span>
          </button>
        </div>

        <div class="flex items-center gap-2 pl-3 text-xs text-slate-500 font-medium shrink-0">
          <span class="rounded-lg bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
            共 {{ charts.length }} 张图表
          </span>
        </div>
      </div>

      <!-- 当前选中图表展示区 -->
      <div class="p-3 bg-[#F6F9FC]/40">
        <ChartArtifactCard
          v-if="currentChart"
          :key="currentChart.chart_id || activeIdx"
          :chart-payload="currentChart"
        />
      </div>
    </div>

    <!-- 单图表：直接渲染独立卡片 -->
    <div v-else class="w-full">
      <ChartArtifactCard
        :key="charts[0].chart_id || 0"
        :chart-payload="charts[0]"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ChartArtifactCard from '@/components/artifacts/ChartArtifactCard.vue'
import type { ChartArtifact } from '@/types'

const props = defineProps<{
  charts: ChartArtifact[]
}>()

const activeIdx = ref(0)

// 当图表列表变动或缩减时重置索引
watch(
  () => props.charts.length,
  (newLen) => {
    if (activeIdx.value >= newLen) {
      activeIdx.value = Math.max(0, newLen - 1)
    }
  },
)

const currentChart = computed<ChartArtifact | null>(() => {
  if (!props.charts || props.charts.length === 0) return null
  return props.charts[activeIdx.value] || props.charts[0]
})
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>

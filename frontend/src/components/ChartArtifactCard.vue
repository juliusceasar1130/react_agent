<template>
  <div class="rounded-2xl border border-sky-200 bg-gradient-to-br from-sky-50 to-white px-4 py-3 shadow-sm">
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="text-sm font-semibold text-sky-900">{{ artifact?.title ?? artifactRef.title }}</div>
        <div
          v-if="artifact?.description"
          class="mt-1 text-xs leading-5 text-sky-700/90"
        >
          {{ artifact.description }}
        </div>
        <div class="mt-1 text-xs leading-5 text-sky-700/80">
          {{ artifactRef.chart_type === 'line' ? '折线图' : '柱状图' }} · {{ artifactRef.point_count }} 个点
        </div>
        <div
          v-if="artifactRef.expires_at"
          class="mt-1 text-xs leading-5 text-sky-700/70"
        >
          有效期至：{{ formatDateTime(artifactRef.expires_at) }}
        </div>
      </div>
    </div>

    <div v-if="loading" class="mt-3 rounded-xl border border-sky-100 bg-white/80 px-3 py-6 text-sm text-sky-700">
      正在加载图表...
    </div>
    <div v-else-if="error" class="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-600">
      {{ error }}
    </div>
    <div v-else ref="chartRef" class="mt-3 h-72 w-full"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { getChartArtifactApi } from '@/api/charts'
import { useDateFormat } from '@/composables/useDateFormat'
import type { ChartArtifact, ChartArtifactRef, ChartArtifactSeries } from '@/types'

interface Props {
  artifactRef: ChartArtifactRef
}

const props = defineProps<Props>()

const chartRef = ref<HTMLDivElement | null>(null)
const artifact = ref<ChartArtifact | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const { parseServerDate } = useDateFormat()
let chartInstance: echarts.ECharts | null = null

const toKey = (value: string | number | null | undefined) => String(value ?? '')

const buildXData = (rows: ChartArtifact['rows'], xField: string) => {
  return Array.from(new Set(rows.map((row) => row[xField] ?? '')))
}

const buildSeriesData = (
  rows: ChartArtifact['rows'],
  xField: string,
  seriesItem: ChartArtifactSeries,
  xData: Array<string | number | null>,
) => {
  const scopedRows = seriesItem.category_field
    ? rows.filter((row) => toKey(row[seriesItem.category_field!]) === toKey(seriesItem.category_value))
    : rows

  const valueByX = new Map<string, string | number | null>()
  for (const row of scopedRows) {
    valueByX.set(toKey(row[xField]), row[seriesItem.field] ?? null)
  }

  return xData.map((xValue) => valueByX.get(toKey(xValue)) ?? null)
}

const option = computed<echarts.EChartsOption | null>(() => {
  if (!artifact.value) return null

  const rows = artifact.value.rows
  const xData = buildXData(rows, artifact.value.x_field)
  const rightSeries = artifact.value.series.filter((item) => item.y_axis === 'right')

  return {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      top: 0,
    },
    grid: {
      left: 48,
      right: rightSeries.length > 0 ? 48 : 24,
      top: 36,
      bottom: 24,
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: {
        color: '#334155',
      },
    },
    yAxis: [
      {
        type: 'value' as const,
        axisLabel: { color: '#334155' },
      },
      ...(rightSeries.length > 0
        ? [
            {
              type: 'value' as const,
              axisLabel: { color: '#334155' },
            },
          ]
        : []),
    ],
    series: artifact.value.series.map((seriesItem) => ({
      name: seriesItem.name,
      type: artifact.value!.chart_type,
      yAxisIndex: seriesItem.y_axis === 'right' ? 1 : 0,
      smooth: artifact.value!.chart_type === 'line',
      data: buildSeriesData(rows, artifact.value!.x_field, seriesItem, xData),
      ...(seriesItem.color
        ? {
            color: seriesItem.color,
            lineStyle: { color: seriesItem.color },
            itemStyle: { color: seriesItem.color },
          }
        : {}),
    })),
  } as echarts.EChartsOption
})

const formatDateTime = (value: string) => {
  const date = parseServerDate(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value || !option.value || loading.value || error.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(option.value, true)
  chartInstance.resize()
}

const loadArtifact = async () => {
  chartInstance?.dispose()
  chartInstance = null
  artifact.value = null
  loading.value = true
  error.value = null
  try {
    artifact.value = await getChartArtifactApi(props.artifactRef.chart_id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '图表加载失败'
  } finally {
    loading.value = false
  }
  await renderChart()
}

watch(() => props.artifactRef.chart_id, () => {
  void loadArtifact()
})

watch(option, () => {
  void renderChart()
})

onMounted(() => {
  void loadArtifact()
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
})
</script>

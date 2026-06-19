<template>
  <div class="rounded-2xl border border-[#D8E2EE] bg-[#F6F9FC] px-4 py-3 shadow-sm">
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="text-sm font-semibold text-slate-900">{{ artifact?.title ?? artifactRef.title }}</div>
        <div
          v-if="artifact?.description"
          class="mt-1 text-xs leading-5 text-slate-600"
        >
          {{ artifact.description }}
        </div>
        <div class="mt-1 text-xs leading-5 text-slate-600">
          {{ artifactRef.chart_type === 'line' ? '折线图' : '柱状图' }} · {{ artifactRef.point_count }} 个点
        </div>
        <div
          v-if="artifactRef.expires_at"
          class="mt-1 text-xs leading-5 text-slate-500"
        >
          有效期至：{{ formatDateTime(artifactRef.expires_at) }}
        </div>
      </div>
    </div>

    <div v-if="loading" class="mt-3 rounded-xl border border-[#D8E2EE] bg-white/85 px-3 py-6 text-sm text-slate-600">
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
    let val = row[seriesItem.field] ?? null
    if (typeof val === 'number') {
      val = Number(val.toFixed(2))
    }
    valueByX.set(toKey(row[xField]), val)
  }

  return xData.map((xValue) => valueByX.get(toKey(xValue)) ?? null)
}

const option = computed<echarts.EChartsOption | null>(() => {
  if (!artifact.value) return null

  const rows = artifact.value.rows
  const xData = buildXData(rows, artifact.value.x_field)
  const rightSeries = artifact.value.series.filter((item) => item.y_axis === 'right')

  // 智能计算图表的数据密度（X轴点数 * 序列数量）
  const totalPoints = xData.length * artifact.value.series.length
  // 当总数据点少于 25 个时，自适应开启数据标签，否则关闭以防重叠拥挤
  const showLabelAdaptively = totalPoints < 25

  return {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      type: 'scroll',
      top: 0,
      itemGap: 16,
      textStyle: {
        color: '#475569'
      }
    },
    grid: {
      left: 16,
      right: 16,
      top: 48,
      bottom: 12,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: {
        color: '#334155',
        interval: 0,           // 强制显示所有 X 轴标签，不进行自动隐藏
        hideOverlap: true,     // 若在窄屏下发生真实重叠，自适应隐藏碰撞的字
        overflow: 'truncate',  // 超出宽度时自动省略号
      },
    },
    yAxis: [
      {
        type: 'value' as const,
        boundaryGap: [0, '15%'] as any, // 顶部预留 15% 空间，防止顶部标签数字被截断
        axisLabel: {
          color: '#334155',
          formatter: (value: number) => Number(value.toFixed(2))
        },
      },
      ...(rightSeries.length > 0
        ? [
            {
              type: 'value' as const,
              boundaryGap: [0, '15%'] as any, // 右轴也同样留出 15% 安全空间
              axisLabel: {
                color: '#334155',
                formatter: (value: number) => Number(value.toFixed(2))
              },
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
      label: {
        show: showLabelAdaptively,
        position: 'top',
        formatter: '{c}', // 显示原始数值
        color: '#475569',
        fontSize: 10,
        fontWeight: '600'
      },
      labelLayout: {
        hideOverlap: true // 折线图重叠时，自动隐去碰撞标签，防止交叉拥挤
      },
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

import api from './index'
import type { ChartArtifact } from '@/types'

export const getChartArtifactApi = (chartId: string): Promise<ChartArtifact> =>
  api.get(`/api/chat/charts/${encodeURIComponent(chartId)}`)

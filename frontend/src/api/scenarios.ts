// frontend/src/api/scenarios.ts
import api from './index'

export interface ScenarioItemSummary {
  name: string
  title: string
  description: string
  direct_path_enabled?: boolean
}

export type ScenarioSummary = ScenarioItemSummary

export interface ScenarioDomainSummary {
  domain: string
  domain_title: string
  scenarios: ScenarioItemSummary[]
}

export interface ParameterOption {
  value: string
  label: string
}

export interface ParameterDef {
  type: string
  widget: string
  description: string
  required: boolean
  default: string | number | null
  options: ParameterOption[]
}

export interface TemplateInfo {
  name: string
  label: string
}

export interface ScenarioParamsMeta {
  name: string
  title: string
  output_type: string
  templates?: TemplateInfo[]
  default_template?: string
  parameters: Record<string, ParameterDef>
}

export interface TableQueryResult {
  type: 'table'
  columns: string[]
  rows: (string | number)[][]
  row_count: number
  total_count?: number
  page?: number
  page_size?: number
  total_pages?: number
  is_truncated?: boolean
}

export interface ScalarQueryResult {
  type: 'scalar'
  value: string | number
  label: string
}

export type ScenarioQueryResult = TableQueryResult | ScalarQueryResult

/**
 * 拉取全量场景领域树列表
 */
export async function getScenariosApi(): Promise<ScenarioDomainSummary[]> {
  const data = await api.get('/api/scenarios')
  return data as unknown as ScenarioDomainSummary[]
}

/**
 * 解析获取指定场景的参数定义与模板
 */
export async function getScenarioParamsApi(
  domain: string,
  scenario: string,
  templateName?: string
): Promise<ScenarioParamsMeta> {
  const params: Record<string, string> = {}
  if (templateName) {
    params.template_name = templateName
  }
  const data = await api.get(`/api/scenarios/${domain}/${scenario}/params`, { params })
  return data as unknown as ScenarioParamsMeta
}

/**
 * 执行快捷场景直通 SQL 查询
 * 2026-08-30: 直通查询为真实 SQL 执行，单独放宽超时至 60s，避免慢查询被全局 10s 超时整单中断
 */
export async function executeScenarioApi(
  domain: string,
  scenario: string,
  userParams: Record<string, any>,
  templateName?: string,
  page: number = 1,
  pageSize: number = 50
): Promise<ScenarioQueryResult> {
  const payload = {
    params: userParams,
    template_name: templateName,
    page,
    page_size: pageSize,
  }
  const data = await api.post(`/api/scenarios/${domain}/${scenario}/execute`, payload, {
    timeout: 60000,
  })
  return data as unknown as ScenarioQueryResult
}

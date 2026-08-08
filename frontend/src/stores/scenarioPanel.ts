// frontend/src/stores/scenarioPanel.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getScenariosApi,
  getScenarioParamsApi,
  executeScenarioApi,
  type ScenarioDomainSummary,
  type ScenarioParamsMeta,
  type ScenarioQueryResult,
} from '@/api/scenarios'
import { useRequestGuard } from '@/composables/useRequestGuard'

export const useScenarioPanelStore = defineStore('scenarioPanel', () => {
  // 面板显隐与视图状态 ('list' | 'detail')
  const visible = ref(false)
  const view = ref<'list' | 'detail'>('list')

  // 全量场景分类树
  const domains = ref<ScenarioDomainSummary[]>([])
  const isDomainsLoading = ref(false)
  const domainsError = ref<string | null>(null)
  const fetchGuard = useRequestGuard()  // 防竞态

  // 选中场景与模板状态
  const selectedDomain = ref<string | null>(null)
  const selectedScenario = ref<string | null>(null)
  const activeTemplate = ref<string | null>(null)

  // 当前场景元数据与参数设置
  const paramsMeta = ref<ScenarioParamsMeta | null>(null)
  const isParamsLoading = ref(false)
  const paramsError = ref<string | null>(null)

  // 参数缓存按 `${domain}/${scenario}/${template}` Key 存储
  const paramValuesCache = ref<Record<string, Record<string, any>>>({})
  const currentParamValues = ref<Record<string, any>>({})

  // 分页状态
  const currentPage = ref(1)
  const pageSize = ref(50)

  // 查询结果与状态
  const queryResult = ref<ScenarioQueryResult | null>(null)
  const isQueryLoading = ref(false)
  const queryError = ref<string | null>(null)

  // 计算属性：当前选中场景标题
  const currentScenarioTitle = computed(() => {
    return paramsMeta.value?.title || selectedScenario.value || ''
  })

  // Action: 打开面板
  function open(targetDomain?: string, targetScenario?: string) {
    visible.value = true
    if (domains.value.length === 0) {
      fetchDomainTree()
    }
    if (targetDomain && targetScenario) {
      selectScenario(targetDomain, targetScenario)
    }
  }

  // Action: 关闭面板
  function close() {
    visible.value = false
  }

  // Action: 拉取场景分类树
  async function fetchDomainTree() {
    const requestId = fetchGuard.next()
    isDomainsLoading.value = true
    domainsError.value = null
    try {
      const result = await getScenariosApi()
      if (!fetchGuard.isFresh(requestId)) return
      domains.value = result
    } catch (err: any) {
      if (!fetchGuard.isFresh(requestId)) return
      domainsError.value = err.message || '获取场景列表失败'
    } finally {
      if (fetchGuard.isFresh(requestId)) {
        isDomainsLoading.value = false
      }
    }
  }

  // Action: 选中场景并初始化参数
  async function selectScenario(domain: string, scenario: string, templateName?: string) {
    selectedDomain.value = domain
    selectedScenario.value = scenario
    view.value = 'detail'
    queryResult.value = null
    queryError.value = null
    currentPage.value = 1

    await loadScenarioParams(domain, scenario, templateName)
  }

  // Action: 加载参数元数据
  async function loadScenarioParams(domain: string, scenario: string, templateName?: string) {
    isParamsLoading.value = true
    paramsError.value = null
    try {
      const meta = await getScenarioParamsApi(domain, scenario, templateName)
      paramsMeta.value = meta
      activeTemplate.value = meta.default_template || (meta.templates?.[0]?.name ?? null)

      // 从缓存恢复或应用默认值
      const cacheKey = `${domain}/${scenario}/${activeTemplate.value || 'default'}`
      if (paramValuesCache.value[cacheKey]) {
        currentParamValues.value = { ...paramValuesCache.value[cacheKey] }
      } else {
        const initialValues: Record<string, any> = {}
        if (meta.parameters) {
          for (const [key, pDef] of Object.entries(meta.parameters)) {
            initialValues[key] = pDef.default ?? ''
          }
        }
        currentParamValues.value = initialValues
        paramValuesCache.value[cacheKey] = { ...initialValues }
      }

      // 自动发第一次直通查询 (默认第 1 页)
      await executeQuery(1)
    } catch (err: any) {
      paramsError.value = err.message || '获取场景参数失败'
    } finally {
      isParamsLoading.value = false
    }
  }

  // Action: 切换模板 Tab
  async function switchTemplate(newTemplateName: string) {
    if (!selectedDomain.value || !selectedScenario.value) return
    activeTemplate.value = newTemplateName
    currentPage.value = 1
    await loadScenarioParams(selectedDomain.value, selectedScenario.value, newTemplateName)
  }

  // Action: 更新参数值
  function updateParamValues(newValues: Record<string, any>) {
    currentParamValues.value = { ...newValues }
    currentPage.value = 1
    if (selectedDomain.value && selectedScenario.value) {
      const cacheKey = `${selectedDomain.value}/${selectedScenario.value}/${activeTemplate.value || 'default'}`
      paramValuesCache.value[cacheKey] = { ...newValues }
    }
  }

  // Action: 执行直通 SQL 查询
  async function executeQuery(targetPage: number = currentPage.value) {
    if (!selectedDomain.value || !selectedScenario.value) return
    currentPage.value = targetPage
    isQueryLoading.value = true
    queryError.value = null
    try {
      const res = await executeScenarioApi(
        selectedDomain.value,
        selectedScenario.value,
        currentParamValues.value,
        activeTemplate.value || undefined,
        currentPage.value,
        pageSize.value
      )
      queryResult.value = res
    } catch (err: any) {
      queryError.value = err.message || '直通查询执行失败'
      queryResult.value = null
    } finally {
      isQueryLoading.value = false
    }
  }

  // Action: 切换页码
  async function changePage(newPage: number) {
    if (newPage === currentPage.value) return
    await executeQuery(newPage)
  }

  // Action: 切换每页显示条数
  async function changePageSize(newSize: number) {
    if (newSize === pageSize.value) return
    pageSize.value = newSize
    await executeQuery(1)
  }

  // Action: 刷新当前查询
  async function refresh() {
    await executeQuery(currentPage.value)
  }

  return {
    visible,
    view,
    domains,
    isDomainsLoading,
    domainsError,
    selectedDomain,
    selectedScenario,
    activeTemplate,
    paramsMeta,
    isParamsLoading,
    paramsError,
    currentParamValues,
    queryResult,
    isQueryLoading,
    queryError,
    currentScenarioTitle,
    currentPage,
    pageSize,
    open,
    close,
    fetchDomainTree,
    selectScenario,
    switchTemplate,
    updateParamValues,
    executeQuery,
    changePage,
    changePageSize,
    refresh,
  }
})

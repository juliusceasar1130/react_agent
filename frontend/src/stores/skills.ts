import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'

/**
 * 技能领域数据接口
 */
export interface Scenario {
  name: string
  title: string
  description: string
  questions: string[]
}

export interface DomainSkill {
  name: string
  title: string
  description: string
  scenarios: Scenario[]
}

export const useSkillsStore = defineStore('skills', () => {
  const domains = ref<DomainSkill[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  /**
   * 从后端拉取技能列表
   */
  const fetchSkills = async () => {
    // 如果已经有数据，则不再重复请求（除非需要刷新逻辑）
    if (domains.value.length > 0) return
    
    isLoading.value = true
    error.value = null
    
    try {
      // 使用统一的 api 实例，会自动带上 /rearch 前缀并走代理
      const data = await api.get('/api/chat/skills')
      domains.value = data as unknown as DomainSkill[]
    } catch (err: any) {
      error.value = err.message || '获取技能列表失败'
      console.error('Fetch skills error:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 强制刷新技能列表（跳过缓存检查）
   */
  const refreshSkills = async () => {
    domains.value = []
    await fetchSkills()
  }

  return {
    domains,
    isLoading,
    error,
    fetchSkills,
    refreshSkills
  }
})

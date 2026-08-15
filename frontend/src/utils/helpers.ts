// 通用工具函数 — 从 MessageItem.vue 提取的可复用纯函数

/**
 * 安全解析 JSON 字符串，解析失败返回 null
 */
export const parseJson = <T,>(value?: string | null): T | null => {
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

/** 子智能体显示名统一映射（与 backend 命名约定保持一致） */
const SUBAGENT_TITLES: Record<string, string> = {
  sql_domain_agent: 'SQL数据专家',
  chart_agent: '图表助手',
  main: '主助手',
}

export const formatSubagentTitle = (name?: string | null): string =>
  (name && SUBAGENT_TITLES[name]) || name || '子智能体'

/**
 * 格式化文件大小为人类可读字符串（B / KB / MB）
 */
export const formatFileSize = (sizeBytes: number): string => {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * 复制文本到剪贴板，兼容非安全上下文（HTTP 环境）降级方案
 */
export const copyToClipboard = async (text: string): Promise<void> => {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
  } else {
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.top = '0'
    textArea.style.left = '0'
    textArea.style.position = 'fixed'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    try {
      document.execCommand('copy')
    } catch (err) {
      console.error('Fallback copy failed:', err)
      throw err
    } finally {
      document.body.removeChild(textArea)
    }
  }
}

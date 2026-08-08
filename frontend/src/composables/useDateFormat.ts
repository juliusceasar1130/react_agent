export function useDateFormat() {
  const parseServerDate = (dateString: string): Date => {
    const normalized = dateString.trim()
    const hasExplicitTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized)
    const isIsoLike = /^\d{4}-\d{2}-\d{2}T/.test(normalized)
    const parsed = new Date(!hasExplicitTimezone && isIsoLike ? `${normalized}Z` : normalized)
    return parsed
  }

  const formatTime = (dateString: string): string => {
    const date = parseServerDate(dateString)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // 完整日期时间格式（年月日小时分钟）- 2025-01-01
  const formatFullDateTime = (dateString: string): string => {
    const date = parseServerDate(dateString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:${minute}`
  }

  return {
    parseServerDate,
    formatTime,
    formatFullDateTime,
  }
}

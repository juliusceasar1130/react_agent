// 导出文件下载 API
// 修改时间: 2026-04-01 00:00 Asia/Shanghai
// 主要修改内容:
// - 新增 SQL 导出文件下载 URL 构造与触发下载能力

const EXPORT_API_BASE = '/rearch/api/chat'

export const buildExportDownloadUrl = (fileId: string): string =>
  `${EXPORT_API_BASE}/files/${encodeURIComponent(fileId)}`

export const triggerExportDownload = (fileId: string) => {
  const link = document.createElement('a')
  link.href = buildExportDownloadUrl(fileId)
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

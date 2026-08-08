// 2026-04-01 22:55 Asia/Shanghai - 统一 Markdown 展示渲染与安全清洗
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { markdownItAlert } from '@/components/chat/plugins/markdown-it-alert'

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false
})

markdown.use(markdownItAlert)

const defaultLinkOpen =
  markdown.renderer.rules.link_open
  ?? ((tokens: any, idx: number, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.link_open = (tokens: any, idx: number, options: any, env: any, self: any) => {
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

// 2026-05-23 - 表格溢出美化：为 Markdown 表格包裹一层 table-container，以便进行响应式滚动
const defaultTableOpen =
  markdown.renderer.rules.table_open
  ?? ((tokens: any, idx: number, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.table_open = (tokens: any, idx: number, options: any, env: any, self: any) => {
  return '<div class="table-container">' + defaultTableOpen(tokens, idx, options, env, self)
}

const defaultTableClose =
  markdown.renderer.rules.table_close
  ?? ((tokens: any, idx: number, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.table_close = (tokens: any, idx: number, options: any, env: any, self: any) => {
  return defaultTableClose(tokens, idx, options, env, self) + '</div>'
}

// 2026-08-02 - LobeChat 1:1 风格复刻：为 Markdown 代码块注入 IDE Header 顶栏 (小写语言标识 + 一键复制按钮)
const defaultFence =
  markdown.renderer.rules.fence
  ?? ((tokens: any, idx: number, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.fence = (tokens: any, idx: number, options: any, env: any, self: any) => {
  const token = tokens[idx]
  let lang = (token.info || '').trim().toLowerCase()
  const content = token.content || ''

  // 智能矫正 LLM 语言错标：如果错标为 sql 但代码包含 Python 标志词
  if (lang === 'sql' && (content.includes('import ') || content.includes('plt.') || content.includes('def ') || content.includes('print('))) {
    lang = 'python'
  }
  if (!lang) lang = 'code'

  const rawCodeHtml = defaultFence(tokens, idx, options, env, self)
  const encodedContent = encodeURIComponent(content)

  return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-lang">${lang}</span><button class="code-copy-btn" data-copy-content="${encodedContent}"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg><span>复制</span></button></div>${rawCodeHtml}</div>`
}

export const renderMarkdown = (source: string) => {
  if (!source.trim()) {
    return ''
  }

  // 2026-08-02 - 自动断段预处理：当 Alert/Callout 关键字 (如 📝 NOTE / 💡 TIP / > [!NOTE]) 与前文黏连在单换行时，自动补齐 \n\n 确保其分割为独立的 Block 卡片
  const alertPreprocessRe = new RegExp('([^\\n])\\s*\\n\\s*((?:[^\\w\\s]\\s*)?(?:\\[\\!)?(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\\]?(?!\\w))', 'gi')
  let processedSource = source.replace(alertPreprocessRe, '$1\n\n$2')

  const rendered = markdown.render(processedSource)
  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['data-copy-content']
  })
}

export interface MessageMetaData {
  queryTime?: string
  dataSource?: string
}

export const extractMetaData = (content: string): { cleanContent: string; meta: MessageMetaData } => {
  let cleanContent = content
  const meta: MessageMetaData = {}

  // 1. 优先提取并清除时间（方括号格式：[数据真实查询时刻: ...]）
  const bracketTimeRegex = /\[数据真实查询时刻[:：]\s*([^\]]+)\]/g
  const bracketTimeMatch = bracketTimeRegex.exec(cleanContent)
  if (bracketTimeMatch) {
    meta.queryTime = bracketTimeMatch[1].trim()
    cleanContent = cleanContent.replace(bracketTimeRegex, '')
  }

  // 2. 提取并清除普通文本时间（格式：查询时间：YYYY-MM-DD HH:MM:SS）
  const textTimeRegex = /(?:查询时间|查询时刻)[:：]\s*([0-9\-\ :]+)/g
  const textTimeMatch = textTimeRegex.exec(cleanContent)
  if (textTimeMatch) {
    if (!meta.queryTime) {
      meta.queryTime = textTimeMatch[1].trim()
    }
    cleanContent = cleanContent.replace(textTimeRegex, '')
  }

  // 3. 提取并清除数据来源（消灭时间后，抓取"数据来源:"后面的表名文本，遇句号、中括号 [ 或换行停止）
  const sourceRegex = /数据来源[:：]\s*([^。\[\n\r]+)/g
  const sourceMatch = sourceRegex.exec(cleanContent)
  if (sourceMatch) {
    let ds = sourceMatch[1].trim()
    // 清洗首尾残留的逗号、全角逗号、顿号、中文句号、英文点号或空格
    ds = ds.replace(/^[,，、。.\s\-\|]+|[,，、。.\s\-\|]+$/g, '').trim()
    meta.dataSource = ds
    cleanContent = cleanContent.replace(sourceRegex, '')
  }

  // 3.5 清理冗余的本地 file:/// 链接（支持常规超链接或图片超链接语法，容忍括号间空格或换行）
  const fileLinkRegex = /!?\[[^\]]*\]\s*\(file:\/\/\/[^\)]+\)/g
  cleanContent = cleanContent.replace(fileLinkRegex, '')

  // 4. 清理残留的多余换行与逗号等垃圾标记并收拢为标准的双换行（保持段落、表格与正文的空行隔离）
  cleanContent = cleanContent.replace(new RegExp('\\n\\s*[,，，、]\\s*\\n', 'g'), '\n\n')
  cleanContent = cleanContent.replace(new RegExp('\\n\\s*\\n', 'g'), '\n\n').trim()

  return { cleanContent, meta }
}

// 2026-04-01 22:55 Asia/Shanghai - 统一 Markdown 展示渲染与安全清洗
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false
})

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

export const renderMarkdown = (source: string) => {
  if (!source.trim()) {
    return ''
  }

  const rendered = markdown.render(source)
  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true }
  })
}

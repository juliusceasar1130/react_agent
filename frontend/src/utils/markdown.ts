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
  ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, idx, options, env, self)
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

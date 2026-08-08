// 2026-08-02 LobeChat 风格 GFM Alert (Callout) 精确匹配解析插件 (使用 (?!\\w) 替代 \\b，完美吃掉 [!NOTE] 中的 ] 字符)

const ALERT_CONFIG: Record<string, { icon: string; title: string; className: string }> = {
  NOTE: { icon: 'ℹ️', title: 'Note', className: 'markdown-alert-note' },
  TIP: { icon: '💡', title: 'Tip', className: 'markdown-alert-tip' },
  IMPORTANT: { icon: '🟣', title: 'Important', className: 'markdown-alert-important' },
  WARNING: { icon: '⚠️', title: 'Warning', className: 'markdown-alert-warning' },
  CAUTION: { icon: '🚫', title: 'Caution', className: 'markdown-alert-caution' },
}

// 统一标准正则：使用 (?!\w) 断言防止误捕获 NOTEBOOK/IMPORTANTLY，同时完整吞掉 [!NOTE] 的末尾 ] 字符
const ALERT_KEYWORD_REGEX = /^\s*(?:[^\w\s]\s*)?(?:\[\!)?(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]?(?!\w)(?:\s*[(（][^)）]+[)）])?:?\s*/i
const BLOCKQUOTE_ALERT_REGEX = /^\s*(?:&gt;|>)?\s*(?:\[\!)?(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]?(?!\w)(?:\s*[(（][^)）]+[)）])?:?\s*/i

export function markdownItAlert(md: any) {
  md.core.ruler.after('block', 'gfm_alert', (state: any) => {
    const tokens = state.tokens
    for (let i = 0; i < tokens.length; i++) {
      // 场景 1: 标准 Blockquote 内部捕获 (> [!NOTE])
      if (tokens[i].type === 'blockquote_open') {
        const openToken = tokens[i]
        let inlineTokenIdx = -1

        for (let j = i + 1; j < tokens.length; j++) {
          if (tokens[j].type === 'blockquote_close') break
          if (tokens[j].type === 'inline') {
            inlineTokenIdx = j
            break
          }
        }

        if (inlineTokenIdx !== -1) {
          const inlineToken = tokens[inlineTokenIdx]
          const rawContent = inlineToken.content || ''
          const match = rawContent.match(BLOCKQUOTE_ALERT_REGEX)

          if (match) {
            const alertType = match[1].toUpperCase()
            const config = ALERT_CONFIG[alertType] || ALERT_CONFIG.NOTE

            openToken.attrJoin('class', `markdown-alert ${config.className}`)

            const cleanText = rawContent.replace(BLOCKQUOTE_ALERT_REGEX, '').trim()
            inlineToken.content = cleanText

            if (Array.isArray(inlineToken.children)) {
              inlineToken.children = inlineToken.children.filter((child: any) => {
                if (child.type === 'code_inline' && child.content.match(/^\[\!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?!\w)/i)) return false
                if (child.type === 'text') {
                  child.content = child.content.replace(BLOCKQUOTE_ALERT_REGEX, '')
                }
                return true
              })
            }

            // 修正：将 html_block 标题节点插入在 paragraph_open 之前，消除 <p><div> 非法嵌套
            const titleToken = new state.Token('html_block', '', 0)
            titleToken.content = `<div class="markdown-alert-title"><span class="alert-icon">${config.icon}</span><span>${config.title}</span></div>`

            const paragraphOpenIdx = inlineTokenIdx - 1
            if (paragraphOpenIdx >= 0 && tokens[paragraphOpenIdx].type === 'paragraph_open') {
              tokens.splice(paragraphOpenIdx, 0, titleToken)
            } else {
              tokens.splice(inlineTokenIdx, 0, titleToken)
            }
          }
        }
      }

      // 场景 2: 智能全兼容升级 —— 普通段落匹配到 📝 NOTE (说明) 直接将 paragraph 节点改写升级为 blockquote 卡片节点
      if (tokens[i].type === 'paragraph_open') {
        const nextToken = tokens[i + 1]
        if (nextToken && nextToken.type === 'inline') {
          const rawContent = nextToken.content || ''
          const match = rawContent.match(ALERT_KEYWORD_REGEX)

          let inBlockquote = false
          for (let k = i - 1; k >= 0; k--) {
            if (tokens[k].type === 'blockquote_open') { inBlockquote = true; break; }
            if (tokens[k].type === 'blockquote_close') break;
          }

          if (match && !inBlockquote) {
            const alertType = match[1].toUpperCase()
            const fullMatchedStr = match[0]
            const config = ALERT_CONFIG[alertType] || ALERT_CONFIG.NOTE

            tokens[i].type = 'blockquote_open'
            tokens[i].tag = 'blockquote'
            tokens[i].attrJoin('class', `markdown-alert ${config.className}`)

            const cleanContent = rawContent.slice(fullMatchedStr.length).trim()
            nextToken.content = cleanContent
            if (Array.isArray(nextToken.children)) {
              nextToken.children = nextToken.children.filter((child: any) => {
                if (child.type === 'text') {
                  child.content = child.content.replace(ALERT_KEYWORD_REGEX, '').trim()
                }
                return true
              })
            }

            const titleToken = new state.Token('html_block', '', 0)
            titleToken.content = `<div class="markdown-alert-title"><span class="alert-icon">${config.icon}</span><span>${config.title}</span></div>`
            tokens.splice(i + 1, 0, titleToken)

            for (let m = i + 3; m < tokens.length; m++) {
              if (tokens[m].type === 'paragraph_close') {
                tokens[m].type = 'blockquote_close'
                tokens[m].tag = 'blockquote'
                break
              }
            }
          }
        }
      }
    }
  })
}

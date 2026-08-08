# LobeChat 风格 Vue 3 AI 消息 Markdown 渲染与排版系统落地指南

> **文档版本**：v1.0.0  
> **适用技术栈**：Vue 3 + Vite + Tailwind CSS + markdown-it  
> **离线与部署约束**：100% 本地离线合规、零外网 CDN 依赖、零黑盒第三方 UI 库依赖

---

## 目录 (Table of Contents)

- [一、 架构目标与设计原则](#一-架构目标与设计原则)
- [二、 端到端双层联动拓扑](#二-端到端双层联动拓扑)
- [三、 后端 System Prompt 结构化约束规范](#三-后端-system-prompt-结构化约束规范)
- [四、 前端 GFM Alert (Callout) 插件源码与 AST 设计](#四-前端-gfm-alert-callout-插件源码与-ast-设计)
- [五、 LobeChat 视觉设计系统与 Tailwind Reset 恢复白皮书](#五-lobechat-视觉设计系统与-tailwind-reset-恢复白皮书)
- [六、 关键注意事项与防错军规 (Critical Pitfalls & Rules)](#六-关键注意事项与防错军规-critical-pitfalls--rules)
- [七、 故障排查手册与 CheckList](#七-故障排查手册与-checklist)

---

## 一、 架构目标与设计原则

### 1. 核心目标
1. **1:1 视觉排版复刻**：完整还原 LobeChat 官方 `@lobehub/ui` 组件库中 `variant='chat'` 的紧凑缩放与优雅排版体验。
2. **纯原生 Vue 3 & 零黑盒依赖**：利用 Vue 3 的 `<script setup>` 与 `markdown-it` AST 插件机制，彻底摆脱 `veaury` 跨框架适配及 React-in-Vue 的性能开销。
3. **100% 离线合规**：封堵所有隐式公网 CDN 依赖，KaTeX 字体、代码高亮主题与矢量 Icon 全量本地打包。
4. **前端与后端双层联动**：通过 System Prompt 从源头引导 LLM 输出结构化 Markdown，前端精准渲染卡片与排版。

---

## 二、 端到端双层联动拓扑

```mermaid
graph TD
    User Prompt[用户提问 / 业务交互] --> LLM[LLM Agent 智能体]
    LLM -- 注入 § 4.5 规则集 --> OutputText[大模型原始输出<br/>包含列表 / 表格 / > [!NOTE] 语法]
    OutputText --> MarkdownIt[markdown-it 解析管线]
    MarkdownIt -- 加载 --> AlertPlugin[markdown-it-alert.ts 插件<br/>改写 AST Token 树]
    AlertPlugin --> DOMPurify[DOMPurify 安全清洗]
    DOMPurify --> MessageItem[MessageItem.vue<br/>.message-markdown 挂载]
    MessageItem -- 注入 CSS 变量与 Reset 样式 --> UserView[1:1 LobeChat 高高级感渲染界面]
```

---

## 三、 后端 System Prompt 结构化约束规范

大模型原生输出高质量结构化 Markdown 是呈现精致界面的前提。在 Agent 底层 `base_system_prompt.md` 的 **§ 4.5** 中注入以下规范：

```markdown
## 4.5 Markdown 结构化排版与 GFM Alert 约束规范 (Formatting Directives)
为确保给用户呈现最高质量、条理清晰的响应，回答时必须遵守以下 Markdown 排版规范：
1. **多要点与步骤列表**：
   - 表达有先后顺序、优先级或步骤流程时，必须使用标准的 Markdown 数字列表 `1.` `2.` `3.`；
   - 表达并列概念、分类维度或无序多项建议时，必须使用标准的无序列表 `-` 或 `+`；
   - 严禁将多个独立要点混杂在单一大段落中。
2. **小节与标题**：
   - 当回复包含多个分析维度或板块时，使用 `###` 或 `####` 划分小节标题，保持文本层级结构清晰。
3. **数据表格**：
   - 当遇到 3 项以上具备多属性对比的数据或查询统计结果时，优先使用 Markdown 居中管道表格 (`| :---: | :---: |`) 进行呈现，确保表头与数值对齐工整。
4. **重点结论与警示 Callout**：
   - 当输出重要的洞察结论、操作建议或风险提示时，必须使用标准的 GFM Callout 警示卡片语法：
     - `> [!NOTE]` 洞察结论或辅助性背景补充；
     - `> [!TIP]` 操作技巧与最佳实践建议；
     - `> [!IMPORTANT]` 核心指标与重点关注参数；
     - `> [!WARNING]` 潜在的系统性能风险与预警；
     - `> [!CAUTION]` 异常告警与危险操作提示。
```

---

## 四、 前端 GFM Alert (Callout) 插件源码与 AST 设计

`markdown-it-alert.ts` 插件在 AST Token 层拦截 `> [!NOTE]` 及 `📝 NOTE` 等变体语法，改写为符合合法 HTML DOM 树的卡片节点：

```typescript
// frontend/src/components/chat/plugins/markdown-it-alert.ts

const ALERT_CONFIG: Record<string, { icon: string; title: string; className: string }> = {
  NOTE: { icon: 'ℹ️', title: 'Note', className: 'markdown-alert-note' },
  TIP: { icon: '💡', title: 'Tip', className: 'markdown-alert-tip' },
  IMPORTANT: { icon: '🟣', title: 'Important', className: 'markdown-alert-important' },
  WARNING: { icon: '⚠️', title: 'Warning', className: 'markdown-alert-warning' },
  CAUTION: { icon: '🚫', title: 'Caution', className: 'markdown-alert-caution' },
}

// 统一标准正则：使用 [^\w\s] 兼容 Emoji，使用 (?!\w) 负向先行断言吃掉末尾 ] 字符，消除 Invalid escape
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

      // 场景 2: 智能全兼容升级 —— 普通段落匹配到 📝 NOTE 直接升级为 Blockquote 卡片
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
```

---

## 五、 LobeChat 视觉设计系统与 Tailwind Reset 恢复白皮书

以下规则集成至 `frontend/src/style.css` 的 `.message-markdown` 中：

```css
:root {
  /* LobeHub 官方 Markdown 计算变量 */
  --lobe-markdown-font-size: 14px;
  --lobe-markdown-header-multiple: 1;
  --lobe-markdown-margin-multiple: 1;
  --lobe-markdown-line-height: 1.6;
  --lobe-markdown-border-radius: 8px;
}

.message-markdown {
  font-size: var(--lobe-markdown-font-size);
  line-height: var(--lobe-markdown-line-height);
  color: inherit;
  word-break: break-word;

  /* GFM Alert 卡片样式与 5 种官方底色 */
  .markdown-alert {
    margin-block: calc(var(--lobe-markdown-margin-multiple) * 0.6em);
    padding: 0.6em 0.85em;
    border-radius: var(--lobe-markdown-border-radius);
    border-left: 4px solid var(--alert-color, #3b82f6);
    background-color: var(--alert-bg, rgba(59, 130, 246, 0.06));
    color: inherit;
  }

  .markdown-alert-title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 600;
    font-size: 0.9em;
    color: var(--alert-color, inherit);
    margin-bottom: 0.25em;

    .alert-icon { font-size: 1.1em; line-height: 1; }
  }

  .markdown-alert p:last-child { margin-bottom: 0; }

  .markdown-alert-note { --alert-color: #3b82f6; --alert-bg: rgba(59, 130, 246, 0.06); }
  .markdown-alert-tip { --alert-color: #10b981; --alert-bg: rgba(16, 185, 129, 0.06); }
  .markdown-alert-important { --alert-color: #a855f7; --alert-bg: rgba(168, 85, 247, 0.06); }
  .markdown-alert-warning { --alert-color: #f59e0b; --alert-bg: rgba(245, 158, 11, 0.06); }
  .markdown-alert-caution { --alert-color: #ef4444; --alert-bg: rgba(239, 68, 68, 0.06); }

  /* 消除首尾元素空隙 */
  > *:first-child { margin-top: 0 !important; }
  > *:last-child { margin-bottom: 0 !important; }

  /* 段落与标题 */
  p {
    margin-block: 4px;
    line-height: var(--lobe-markdown-line-height);
    letter-spacing: 0.01em;
  }

  h1, h2, h3, h4, h5, h6 {
    margin-block: max(
      calc(var(--lobe-markdown-header-multiple) * var(--lobe-markdown-margin-multiple) * 0.4em),
      var(--lobe-markdown-font-size)
    );
    font-weight: bold;
    line-height: 1.25;
    color: var(--color-title, inherit);
  }

  h1 { font-size: calc(var(--lobe-markdown-font-size) * (1 + 0.5 * var(--lobe-markdown-header-multiple))); }
  h2 { font-size: calc(var(--lobe-markdown-font-size) * (1 + 0.3 * var(--lobe-markdown-header-multiple))); }
  h3 { font-size: calc(var(--lobe-markdown-font-size) * (1 + 0.15 * var(--lobe-markdown-header-multiple))); }

  /* 列表与 Tailwind Base Reset 复原 */
  ul {
    list-style-type: disc;
    margin-block: calc(var(--lobe-markdown-margin-multiple) * 0.5em);
    padding-left: 1.4rem;
  }

  ol {
    list-style-type: decimal;
    margin-block: calc(var(--lobe-markdown-margin-multiple) * 0.5em);
    padding-left: 1.4rem;
  }

  /* 列表 Marker 降温 (Slate-400 柔灰蓝) */
  li::marker {
    color: rgb(148 163 184);
    font-weight: 500;
  }

  li + li { margin-top: 0.25rem; }

  /* 修饰标签复原 */
  del { text-decoration: line-through; opacity: 0.75; }
  em, i { font-style: italic; }
  ins, u { text-decoration: underline; text-underline-offset: 3px; }
  sub { vertical-align: sub; font-size: 0.75em; }
  sup { vertical-align: super; font-size: 0.75em; }
  hr {
    border: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgb(203 213 225 / 0.8), transparent);
    margin-block: 1.2em;
  }

  /* 降温普通 Blockquote */
  blockquote {
    margin-block: calc(var(--lobe-markdown-margin-multiple) * 0.5em);
    padding: 0.5em 1em;
    border-inline-start: solid 4px rgb(148 163 184 / 0.6);
    background-color: rgb(248 250 252);
    border-radius: 0 var(--lobe-markdown-border-radius) var(--lobe-markdown-border-radius) 0;
    color: rgb(71 85 105);
  }

  /* 行内 Code 降温与 代码块 Pre */
  code:not(pre code) {
    margin-inline: 0.2em;
    padding: 0.15em 0.35em;
    border: 1px solid rgb(226 232 240);
    border-radius: 0.25em;
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: 0.875em;
    background: rgb(241 245 249 / 0.8);
    color: rgb(51 65 85);
  }

  pre {
    margin-block: calc(var(--lobe-markdown-margin-multiple) * 0.5em);
    overflow-x: auto;
    border-radius: var(--lobe-markdown-border-radius);
    background: linear-gradient(180deg, rgb(15 23 42 / 0.96), rgb(30 41 59 / 0.96));
    padding: 0.85rem 1rem;
    color: #e2e8f0;
    font-size: calc(var(--lobe-markdown-font-size) * 0.875);
  }

  /* 表格全列强制居中 (!important 破除内联 style 压制) */
  th, td {
    min-width: 5rem;
    border-bottom: 1px solid rgb(219 229 240);
    padding: 0.65rem 0.9rem;
    text-align: center !important;
    vertical-align: middle;
    white-space: normal;
    line-height: 1.5;
  }

  th {
    font-size: 0.9rem;
    font-weight: 600;
    color: rgb(30 41 59);
    letter-spacing: 0.015em;
  }

  td {
    font-size: 0.875rem;
    color: rgb(51 65 85);
  }

  td strong {
    color: rgb(15 23 42);
    font-weight: 600;
  }

  /* 流式打字呼吸光标 */
  &.is-streaming > *:last-child::after,
  &.is-streaming > p:last-child::after,
  &.is-streaming > li:last-child::after {
    content: '▋';
    display: inline-block;
    margin-left: 3px;
    vertical-align: baseline;
    animation: lobe-caret-blink 0.8s steps(2, start) infinite;
    color: var(--color-primary, #3b82f6);
    font-weight: bold;
  }
}
```

---

## 六、 关键注意事项与防错军规 (Critical Pitfalls & Rules)

### 🚨 1. 【正则与 Unicode 编译坑】严禁使用 `\u{1F300}` 与 `/u` 标志
- **踩坑点**：在浏览器或 Vite 打包场景下，`\u{1F300}` 与普通 UTF-16 范围混用在 `[...]` 字符集内时，部分 ESbuild / Babel 编译器会引发 `SyntaxError: Invalid regular expression: Invalid escape`，导致全站 JS 执行中断而**白屏**。
- **防错军规**：统一使用非字母数字字符集 **`[^\w\s]`** 匹配所有 Emoji 与表情符号，语法干净且 100% 绝对无编译兼容隐患。

### 🚨 2. 【字符遗留坑】捕获 `[!NOTE]` 时严禁仅使用 `\b` 词边界
- **踩坑点**：在字符串 `[!NOTE]` 中，字母 `E` 与右中括号 `]` 之间恰好存在词边界。如果正则写作 `/NOTE]\b/`，匹配过程会在 `NOTE` 字母处终止，导致右中括号 **`]` 残留在正文开头**。
- **防错军规**：必须使用 **`(?!\w)` 负向先行断言**（即“后面不能跟英文字母或数字”）替代 `\b`。这样既能精准包含并吞掉 `]`，又能防止错切 `NOTEBOOK` 或 `IMPORTANTLY`。

### 🚨 3. 【HTML DOM 嵌套坑】严禁在 `<p>` 内部插入 `<div>`
- **踩坑点**：在 `markdown-it` 插件阶段，如果将 `<div class="markdown-alert-title">` 插入在 `paragraph_open` 和 `inline` 节点之间，会生成违规 HTML：`<blockquote><p><div class="markdown-alert-title">...</div>正文</p></blockquote>`。浏览器解析器会自动强制提前闭合 `<p>`，引发空白 `<p>` 间距伪影。
- **防错军规**：必须在 Token 处理阶段将 `titleToken` (`html_block`) 插入在 `paragraph_open` 节点**之前**。

### 🚨 4. 【Tailwind Base Reset 坑】必须显式声明 `list-style-type`
- **踩坑点**：Tailwind CSS 的 `@tailwind base` 默认设置了 `ul, ol { list-style: none; }`。即使生成了 `<ul><li>` 节点，列表小圆点 `•` 和数字 `1.` 也会被隐藏。
- **防错军规**：必须在 `.message-markdown ul` 和 `.message-markdown ol` 中显式指定 `list-style-type: disc` 与 `list-style-type: decimal`。

### 🚨 5. 【Scoped CSS 覆盖坑】严禁在 SFC 组件内对全局标签加 `!important`
- **踩坑点**：如果在 `MessageItem.vue` 的 `<style scoped>` 中声明了 `:deep(td) { text-align: center !important }`，它会因为 CSS Cascade Layers 机制直接压制全局 `style.css` 的表格左对齐规则。
- **防错军规**：避免在 scoped 样式内使用 `!important` 覆盖全局通用排版规则。

### 🚨 6. 【高饱和度色彩坑】全量色彩必须进行中性降温
- **踩坑点**：直接给 `li::marker` 或 `code` 施加 100% 饱和度的鲜蓝色（如 `#3b82f6`），会导致长文本正文的阅读焦点被乱切碎。
- **防错军规**：列表 Marker 统一降温为 Slate-400 (`rgb(148 163 184)`) 柔和灰蓝，行内代码降温为低调石墨浅底 (`rgb(241 245 249)` + `rgb(51 65 85)`)。

### 🚨 7. 【表格全列水平居中与权重破除双保险坑】消除 markdown-it 生成的行内样式压制
- **踩坑点**：
  1. 当 `markdown-it` 遇到 LLM 输出的默认或带靠左指示符的表格时，生成的 HTML 标签会自动挂载行内样式 `<th style="text-align:left">`，其 CSS 优先级高达 `1,0,0,0`；
  2. 若外部 CSS 写为 `.message-markdown th { text-align: center; }`（权重仅 `0,0,1,1`），会被 HTML 行内 `style="text-align:left"` 强行覆盖压制，导致表格永远死死靠左；
  3. 若给 `td strong` 配置 `color: var(--color-primary)`，大模型一旦在表格单元格加粗文本，整列文字会全变成刺眼亮蓝，破坏数据沉稳质感。
- **防错军规**：
  1. 必须使用**前端 CSS 最高权重 + 后端 Prompt 居中引导的双保险机制**：
     - 前端 CSS 加上 `!important` 破除行内样式压制：`.message-markdown th, .message-markdown td { text-align: center !important; }`
     - 后端 `base_system_prompt.md` § 4.5 显式引导：`优先使用 Markdown 居中管道表格 (| :---: | :---: |) 进行呈现`
  2. `td strong` 必须回归沉稳深石墨色 `rgb(15 23 42)`，保持表格的干净沉稳。

---

## 七、 故障排查手册与 CheckList

在部署新项目或升级排版系统时，按以下 CheckList 进行无盲区排查：

- [ ] **1. 首屏白屏检测**：刷新页面，检查 DevTools Console 是否存在 `SyntaxError: Invalid regular expression: Invalid escape`。若有，检查是否误用了 `\u{1F300}`。
- [ ] **2. 卡片字符残留检测**：输出 `> [!NOTE]` 和 `> [!TIP]`，观察卡片内部首行是否有多余的 `]` 字符。
- [ ] **3. 列表圆点与数字检测**：发送包含无序列表 `- ` 和有序列表 `1. ` 的问题，检查小圆点 `•` 和数字 `1.` 是否正常显示。
- [ ] **4. 表格对齐与滚动检测**：检查表格是否具备 `.table-container` 响应式横向滚动条，且表头与单元格为优雅的左对齐。
- [ ] **5. 英文单词隔离检测**：输入包含 `IMPORTANTLY` 或 `notebook` 的英文段落，验证是否会被误判并拆切成卡片。
- [ ] **6. 离线合规检测**：在 Chrome DevTools Network 面板中勾选 `Offline`，验证本地加载零报错。

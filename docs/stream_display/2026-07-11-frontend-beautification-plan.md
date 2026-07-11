# 前端 AI 回答消息美化实现计划 (三项美化工作)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 美化前端 AI 消息展示，包含提取脚标（查询时间、数据源）进行分离排版，优化 Markdown 二维表格的斑马纹和悬停高亮，并修饰暗色 SQL 代码框。

**Architecture:**
1. 在 `frontend/src/utils/markdown.ts` 中实现正则元数据清洗与提取函数。
2. 在 `frontend/src/components/MessageItem.vue` 中绑定元数据计算属性，优化模板渲染以在底部卡片式展现元数据。
3. 在 `MessageItem.vue` 中增加 `<style scoped>`，定义表格（th/td 边框、斑马纹、悬停背景）及 SQL 暗色代码框（含 CSS ::before 伪类 SQL 徽章）样式。

**Tech Stack:** Vue 3, Tailwind CSS, Markdown-It, Vanilla Scoped CSS, Node.js (for tool script test).

---

### Task 1: 编写单元测试与工具提取逻辑 (TDD)

**Files:**
- Create: `frontend/src/utils/test_markdown.js`
- Modify: `frontend/src/utils/markdown.ts:40-50`

- [ ] **Step 1: 创建轻量本地断言测试脚本**

创建测试脚本 `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\frontend\src\utils\test_markdown.js`，包含对元数据正则提取的预期断言：

```javascript
import assert from 'assert';
import { extractMetaData } from './markdown.js';

// 测试用例 1: 同时包含时间和数据源
const testContent1 = "这是查询结果。\n[数据真实查询时刻: 2026-07-11 14:58:26]\n数据来源：mart.mart_vehicle_quality_360";
const { cleanContent: clean1, meta: meta1 } = extractMetaData(testContent1);

assert.strictEqual(clean1, "这是查询结果。");
assert.strictEqual(meta1.queryTime, "2026-07-11 14:58:26");
assert.strictEqual(meta1.dataSource, "mart.mart_vehicle_quality_360");

// 测试用例 2: 仅包含时间
const testContent2 = "无数据来源说明\n[数据真实查询时刻: 2026-07-11 17:30:00]";
const { cleanContent: clean2, meta: meta2 } = extractMetaData(testContent2);
assert.strictEqual(clean2, "无数据来源说明");
assert.strictEqual(meta2.queryTime, "2026-07-11 17:30:00");
assert.strictEqual(meta2.dataSource, undefined);

console.log("PASS: extractMetaData test cases passed successfully!");
```

- [ ] **Step 2: 运行测试并验证其因缺少实现而报错**

在终端运行：
`node frontend/src/utils/test_markdown.js`

Expected Output:
`Cannot find module './markdown.js' or extractMetaData is not a function`

- [ ] **Step 3: 在 markdown.ts 中实现清洗与提取逻辑**

在 [markdown.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/utils/markdown.ts) 底部新增 `extractMetaData` 函数的声明与导出，清洗正文中的元数据标识：

```typescript
export interface MessageMetaData {
  queryTime?: string
  dataSource?: string
}

export const extractMetaData = (content: string): { cleanContent: string; meta: MessageMetaData } => {
  let cleanContent = content
  const meta: MessageMetaData = {}

  // 1. 提取时间后缀并从正文擦除
  const timeRegex = /\[数据真实查询时刻:\s*([^\]]+)\]/g
  const timeMatch = timeRegex.exec(content)
  if (timeMatch) {
    meta.queryTime = timeMatch[1].trim()
    cleanContent = cleanContent.replace(timeRegex, '')
  }

  // 2. 提取数据源后缀并从正文擦除
  const sourceRegex = /数据来源[:：]\s*([a-zA-Z0-9_\.]+)/g
  const sourceMatch = sourceRegex.exec(content)
  if (sourceMatch) {
    meta.dataSource = sourceMatch[1].trim()
    cleanContent = cleanContent.replace(sourceRegex, '')
  }

  // 整理换行格式并剔除首尾空字符
  cleanContent = cleanContent.replace(/\n\s*\n/g, '\n').trim()

  return { cleanContent, meta }
}
```

- [ ] **Step 4: 将 ES 模块脚本编译/运行通过**

为了能用 Node 直接执行 ES module 测试，将 `test_markdown.js` 中的导入替换为直接引用或用 CommonJS 改写，重新运行以验证：

在 `test_markdown.js` 中使用模拟逻辑导入，运行：
`node frontend/src/utils/test_markdown.js`

Expected Output:
`PASS: extractMetaData test cases passed successfully!`

---

### Task 2: 消息展示组件逻辑与模板美化 (MessageItem.vue)

**Files:**
- Modify: `frontend/src/components/MessageItem.vue`

- [ ] **Step 1: 修改 MessageItem.vue 脚本部分**

在 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue) 的 script 中，引入我们新写的 `extractMetaData` 并绑定计算属性：

在大约 269 行附近引入：
```typescript
import { renderMarkdown, extractMetaData } from '@/utils/markdown'
```

修改 320 行的 `displayContent` 和新增 `metaData`：
```typescript
const metaData = computed(() => {
  const { meta } = extractMetaData(content.value || '')
  return meta
})

const displayContent = computed(() => {
  const rawContent = content.value || ''
  const cleaned = rawContent.replace(/\[suggest_chart:(line|bar|auto)(?:\|[^\]]*)?\]/, '')
  const { cleanContent } = extractMetaData(cleaned)
  return cleanContent
})
```

- [ ] **Step 2: 修改 MessageItem.vue 模板展示**

在 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue) 的模板中，在正文渲染（第 45 行附近 `v-html="renderedContent"` 的下方），增加用于渲染独立元数据卡片的 DOM：

```html
        <!-- 数据源与查询时刻脚标独立卡片化展示 -->
        <div
          v-if="!isUser && (metaData.queryTime || metaData.dataSource)"
          class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-neutral-100/50 pt-2.5 text-[11px] text-neutral-400 font-medium"
        >
          <span v-if="metaData.dataSource" class="flex items-center gap-1">
            <svg class="h-3.5 w-3.5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
            数据源: <code class="rounded bg-neutral-100 px-1 py-0.5 text-neutral-500 font-mono">{{ metaData.dataSource }}</code>
          </span>
          <span v-if="metaData.queryTime" class="flex items-center gap-1">
            <svg class="h-3.5 w-3.5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            查询时刻: <span>{{ metaData.queryTime }}</span>
          </span>
        </div>
```

---

### Task 3: 渲染元素 scoped CSS 样式美化

**Files:**
- Modify: `frontend/src/components/MessageItem.vue`

- [ ] **Step 1: 追加 scoped style 段到组件底部**

在 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue) 底部，追加 `<style scoped>` 块，精修动态表格和 SQL 语句的高亮排版：

```html
<style scoped>
/* 2026-07-11 - Markdown 动态渲染元素美化 */
.message-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13.5px;
  line-height: 1.5;
  text-align: left;
  border-radius: 12px;
  overflow: hidden;
}

.message-markdown :deep(th) {
  background-color: #f8fafc;
  color: #334155;
  font-weight: 600;
  padding: 10px 14px;
  border-bottom: 2px solid #e2e8f0;
}

.message-markdown :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #475569;
}

.message-markdown :deep(tr:last-child td) {
  border-bottom: none;
}

.message-markdown :deep(tr:nth-child(even)) {
  background-color: rgba(248, 250, 252, 0.6);
}

.message-markdown :deep(tr:hover td) {
  background-color: rgba(241, 245, 249, 0.7);
  color: #0f172a;
}

/* SQL 代码块样式 */
.message-markdown :deep(pre) {
  position: relative;
  background-color: #0f172a;
  color: #f8fafc;
  padding: 16px;
  border-radius: 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.message-markdown :deep(pre::before) {
  content: 'SQL';
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.5px;
  background-color: #1e293b;
  padding: 2px 6px;
  border-radius: 6px;
}

.message-markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}
</style>
```

---

### Task 4: 浏览器界面视觉联调

**Files:**
- Manual verification on Dev server.

- [ ] **Step 1: 运行前端服务进行视觉验证**

运行前端开发服务器（如已自动开启的 `npm run dev`）。在聊天界面进行一次包含 SQL 结果和数据源的提问，断言：
1. 原本挤在气泡内部的 `[数据来源：...，查询时间：...]` 已被完全移出，并在底部以精致的 icon 卡片形式分离出来。
2. 表格展示具有精致的灰色边框、斑马纹和轻盈的鼠标 hover 反馈。
3. 大模型列出的 ```sql 代码块圆角高雅，右上角包含 `SQL` 金属灰徽章。

---

### Task 5: 提交记录

- [ ] **Step 1: 提请 Git 提交许可**

将本次前端三项美化代码一并合入并请求 commit 授权。

# Agent 多格式结构化输出阶段 3 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成前端双模 UI 渲染与高级表格卡片组件开发。支持对 `StructuredDataResult`（推理思考、高级 Element Plus 数据表、导出 Excel、核心洞察）和 `FreeMarkdownResult`（自由 Markdown 内容、联想表与提问）的精美卡片渲染。

**Architecture:**
1. 修改 [types/index.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts)，在 `Message`、`StreamingMessage`、`StreamEvent` 等类型定义中引入 `structured_response` 成员。
2. 在 [stores/messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/stores/messages.ts) 中，当监听到 SSE 的 `'final'` 消息且含有 `structured_response` 负载时，将其缓存至当前消息模型中，以便视图响应。
3. 创建全新的 Vue 组件 [StructuredOutputCard.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/StructuredOutputCard.vue), 封装：
   - 气泡思考框（`ReasoningSteps`）：列出思考、状态与验证建议。
   - 高级表格（`PremiumTable`）：使用 `el-table` 实现列排序和条件过滤，配备“导出 Excel”交互按钮。
   - 洞察卡片（`Insights`）：灯泡展示核心洞察列表。
4. 修改 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue)，执行条件渲染分流：如果消息含有有效的 `structured_response`，则直接渲染 `StructuredOutputCard` 组件，实现优雅的双模 UI 渲染。

**Tech Stack:** `Vue 3`, `Pinia`, `Element Plus`, `Tailwind CSS / Vanilla CSS`

---

## 任务分解清单

### Task 1: 扩展前端 TypeScript 类型定义

**Files:**
- Modify: [frontend/src/types/index.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts)

- [ ] **Step 1: 增加 `structured_response` 属性**
  
  在 [frontend/src/types/index.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts) 中的 `Message`、`FinalizedStreamingMessage`、`StreamingMessage` 接口以及 `StreamEvent` 的 `'final'` 变体中，分别插入 `structured_response` 类型：
  
  * **在 `Message` 中**：
    ```typescript
    export interface Message {
      // ... 约第 43 行后面
      refined_payload?: string | null
      structured_response?: any  // 新增
      rag_context?: Array<{
    ```
  
  * **在 `FinalizedStreamingMessage` 中**：
    ```typescript
    export interface FinalizedStreamingMessage {
      id?: string
      created_at?: string
      content?: string
      tool_calls?: string | null
      tool_results?: string | null
      structured_response?: any  // 新增
      rag_context?: Array<{
    ```

  * **在 `StreamingMessage` 中**：
    ```typescript
    export interface StreamingMessage {
      id: string
      // ... 约第 220 行后面
      feedback?: 'none' | 'like' | 'dislike' | 'collected' | 'approved'
      structured_response?: any  // 新增
      ragContext?: Array<{
    ```

  * **在 `StreamEvent` 联合类型的 `'final'` 部分中**：
    ```typescript
      | {
          type: 'final'
          content: string
          structured_response?: any  // 新增
          tool_calls?: StreamToolCall[] | null
    ```

- [ ] **Step 2: 验证编译**
  
  在 `frontend` 目录下运行 TypeScript 校验命令：
  ```powershell
  cd frontend
  npm run build -- --noEmit
  ```
  Expected: 无任何 TypeScript 语法或接口声明报错。

- [ ] **Step 3: Commit**
  ```bash
  git add frontend/src/types/index.ts
  git commit -m "types: add structured_response fields in typescript interfaces"
  ```

---

### Task 2: Pinia Store 状态处理重构

**Files:**
- Modify: [frontend/src/stores/messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/stores/messages.ts)

- [ ] **Step 1: 在 `completeStreamingMessage` 中保留 `structured_response`**
  
  定位到 [frontend/src/stores/messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/stores/messages.ts) 的 `completeStreamingMessage` 函数中（约第 258-275 行），修改为：
  ```typescript
    const completeStreamingMessage = (payload: FinalizedStreamingMessage = {}) => {
      if (!streamingMessage.value) return null
  
      const finalizedMessage: Message = {
        id: payload.id ?? streamingMessage.value.id,
        session_id: streamingMessage.value.session_id,
        role: 'assistant',
        content: payload.content ?? streamingMessage.value.content,
        created_at: payload.created_at ?? streamingMessage.value.created_at,
        structured_response: payload.structured_response ?? streamingMessage.value.structured_response, // 新增
        tool_calls: payload.tool_calls ?? (
          streamingMessage.value.toolCalls.length
            ? JSON.stringify(streamingMessage.value.toolCalls)
            : null
        ),
        tool_results: payload.tool_results ?? (
          Object.keys(streamingMessage.value.toolResults).length
            ? JSON.stringify(streamingMessage.value.toolResults)
            : null
        ),
        rag_context: payload.rag_context ?? streamingMessage.value.ragContext
      }
  ```

- [ ] **Step 2: 在 `fetchMessages` 结果中兼容 JSON 解析**
  
  在加载历史会话消息列表时，我们需要能够识别被存储在 `content` 字段中的 JSON 字符串。
  定位到 [frontend/src/stores/messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/stores/messages.ts) 的 `fetchMessages` 中获取到 `fetchedMessages` 后（约第 46 行），在赋值前进行清洗：
  ```typescript
      // 遍历解析已被序列化存储的历史结构化消息
      const cleanedMessages = fetchedMessages.map((m: any) => {
        if (m.role === 'assistant' && m.content.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(m.content)
            if (parsed && (parsed.tables || parsed.response_type)) {
              return {
                ...m,
                structured_response: parsed
              }
            }
          } catch (e) {
            // 解析失败时保持原样
          }
        }
        return m
      })

      messages.value = cleanedMessages
  ```

- [ ] **Step 3: 运行验证**
  
  运行项目前端打包：
  ```powershell
  npm run build -- --noEmit
  ```
  Expected: 成功且无类型错误。

- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/stores/messages.ts
  git commit -m "store: parse and bind structured_response in messages store"
  ```

---

### Task 3: 封装 `StructuredOutputCard.vue` 结构化渲染组件

**Files:**
- Create: [frontend/src/components/StructuredOutputCard.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/StructuredOutputCard.vue)

- [ ] **Step 1: 新建并实现多格式混合渲染组件**
  
  创建文件并写入以下内容，支持对 `StructuredDataResult` 和 `FreeMarkdownResult` 两种数据模型的卡片渲染：
  ```html
  <!-- frontend/src/components/StructuredOutputCard.vue -->
  <template>
    <div class="structured-output-card">
      <!-- 格式一：StructuredDataResult (数据查询/报表模式) -->
      <div v-if="isStructuredData" class="data-result-container">
        <!-- 推理意图判断 -->
        <div class="judgment-banner">
          <el-icon class="icon-space"><Compass /></el-icon>
          <span>{{ data.judgment }}</span>
        </div>

        <!-- 思考思考推理过程 Reasoning Process -->
        <div v-if="data.reasoning_process && data.reasoning_process.length" class="reasoning-section">
          <el-collapse>
            <el-collapse-item name="1">
              <template #title>
                <div class="collapse-title-custom">
                  <el-icon class="icon-space"><Cpu /></el-icon>
                  <span>查看 Agent 推理决策链路 ({{ data.reasoning_process.length }} 步)</span>
                </div>
              </template>
              <div class="steps-timeline">
                <div v-for="step in data.reasoning_process" :key="step.step" class="step-item">
                  <div class="step-header">
                    <span class="step-num">步骤 {{ step.step }}</span>
                    <el-tag :type="getConfidenceTagType(step.confidence)" size="small">
                      可信度: {{ step.confidence }}
                    </el-tag>
                    <el-tag v-if="step.user_should_verify" type="danger" size="small">需人工验证</el-tag>
                  </div>
                  <div class="step-thought">{{ step.thought }}</div>
                  <div v-if="step.suggestion" class="step-suggestion">
                    <strong>建议：</strong>{{ step.suggestion }}
                  </div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 斑马纹表格列表 -->
        <div v-for="(table, tIdx) in data.tables" :key="tIdx" class="table-card">
          <div class="table-card-header">
            <h4 class="table-title">{{ table.title || '查询结果数据表' }}</h4>
            <el-button type="primary" size="small" :icon="Download" @click="exportToExcel(table)">
              导出 Excel
            </el-button>
          </div>
          
          <el-table 
            :data="getFormattedRows(table)" 
            stripe 
            border 
            style="width: 100%; margin-top: 10px;"
            max-height="400"
          >
            <el-table-column 
              v-for="col in table.headers" 
              :key="col" 
              :prop="col" 
              :label="col" 
              sortable
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <!-- 智能洞察与结论 Insights -->
        <div v-if="data.insights && data.insights.length" class="insights-section">
          <div class="insights-header">
            <el-icon class="insights-icon"><Opportunity /></el-icon>
            <span>数据洞察与核心结论</span>
          </div>
          <ul class="insights-list">
            <li v-for="(insight, insIdx) in data.insights" :key="insIdx" class="insight-item">
              <span class="insight-bullet">•</span>
              <span class="insight-text">{{ insight }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- 格式二：FreeMarkdownResult (开放式问答模式) -->
      <div v-else-if="isFreeMarkdown" class="markdown-result-container">
        <!-- 响应类型标签 -->
        <div class="response-type-header" :class="data.response_type">
          <el-tag :type="getMarkdownTagType(data.response_type)" effect="dark">
            {{ getMarkdownTagLabel(data.response_type) }}
          </el-tag>
        </div>

        <!-- Markdown 渲染主体 -->
        <div class="markdown-body-render" v-html="renderMarkdown(data.content)" />

        <!-- 联想建议表 & 问法 -->
        <div v-if="hasSuggestions" class="suggestions-area">
          <div v-if="data.suggested_tables && data.suggested_tables.length" class="suggested-tables">
            <span class="suggest-title">相关数据表：</span>
            <el-tag 
              v-for="tab in data.suggested_tables" 
              :key="tab" 
              class="suggest-tag-item"
              size="small"
              @click="onSuggestClick(tab)"
            >
              {{ tab }}
            </el-tag>
          </div>
          <div v-if="data.suggested_questions && data.suggested_questions.length" class="suggested-questions">
            <div class="suggest-title-block">您可以尝试以下问法：</div>
            <div 
              v-for="q in data.suggested_questions" 
              :key="q" 
              class="suggest-question-btn"
              @click="onQuestionClick(q)"
            >
              {{ q }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>

  <script setup lang="ts">
  import { computed } from 'vue'
  import { Compass, Cpu, Opportunity, Download } from '@element-plus/icons-vue'
  import MarkdownIt from 'markdown-it'

  const props = defineProps<{
    data: any
  }>()

  const emit = defineEmits<{
    (e: 'send-message', text: string): void
  }>()

  const md = new MarkdownIt({ html: true, linkify: true })

  const isStructuredData = computed(() => {
    return props.data && Array.isArray(props.data.tables)
  })

  const isFreeMarkdown = computed(() => {
    return props.data && props.data.content !== undefined
  })

  const hasSuggestions = computed(() => {
    return props.data && (
      (props.data.suggested_tables && props.data.suggested_tables.length) ||
      (props.data.suggested_questions && props.data.suggested_questions.length)
    )
  })

  // 整理表格行数据给 el-table
  const getFormattedRows = (table: any) => {
    return table.rows.map((row: any[]) => {
      const rowObj: Record<string, any> = {}
      table.headers.forEach((header: string, idx: number) => {
        rowObj[header] = row[idx]
      })
      return rowObj
    })
  }

  // 根据可信度决定 Tag 类型
  const getConfidenceTagType = (confidence: string) => {
    switch (confidence) {
      case 'high': return 'success'
      case 'medium': return 'warning'
      case 'low': return 'danger'
      default: return 'info'
    }
  }

  // 根据 Markdown 回复类型决定 Tag 类型
  const getMarkdownTagType = (type: string) => {
    switch (type) {
      case 'explanation': return 'success'
      case 'clarification': return 'warning'
      case 'refusal': return 'danger'
      default: return 'info'
    }
  }

  const getMarkdownTagLabel = (type: string) => {
    switch (type) {
      case 'explanation': return '解释说明'
      case 'clarification': return '需澄清'
      case 'refusal': return '拒绝执行'
      default: return '其它'
    }
  }

  const renderMarkdown = (text: string) => {
    return md.render(text || '')
  }

  // 点击建议问题
  const onQuestionClick = (question: string) => {
    emit('send-message', question)
  }

  const onSuggestClick = (table: string) => {
    emit('send-message', `查一下表 ${table}`)
  }

  // 一键导出 Excel 表格
  const exportToExcel = (table: any) => {
    let csvContent = '\uFEFF' + table.headers.join(',') + '\n'
    table.rows.forEach((row: any[]) => {
      csvContent += row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',') + '\n'
    })
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.setAttribute('download', `${table.title || 'export'}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
  </script>

  <style scoped>
  .structured-output-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    border: 1px solid #e2e8f0;
    max-width: 100%;
    overflow-x: auto;
  }
  .judgment-banner {
    display: flex;
    align-items: center;
    background: #eff6ff;
    color: #1d4ed8;
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 12px;
  }
  .icon-space {
    margin-right: 8px;
  }
  .reasoning-section {
    margin-bottom: 16px;
  }
  .collapse-title-custom {
    display: flex;
    align-items: center;
    color: #475569;
    font-size: 13px;
  }
  .steps-timeline {
    padding: 6px 12px;
    border-left: 2px solid #cbd5e1;
    margin-left: 8px;
  }
  .step-item {
    margin-bottom: 12px;
  }
  .step-header {
    display: flex;
    gap: 8px;
    margin-bottom: 4px;
  }
  .step-num {
    font-weight: bold;
    color: #334155;
    font-size: 12px;
  }
  .step-thought {
    font-size: 13px;
    color: #475569;
    background: #f1f5f9;
    padding: 6px 10px;
    border-radius: 6px;
  }
  .step-suggestion {
    font-size: 12px;
    color: #dc2626;
    margin-top: 2px;
    padding-left: 6px;
  }
  .table-card {
    background: #ffffff;
    padding: 14px;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    margin-bottom: 16px;
  }
  .table-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .table-title {
    margin: 0;
    font-size: 14px;
    color: #1e293b;
    font-weight: 600;
  }
  .insights-section {
    background: #fffdf5;
    border: 1px solid #fef08a;
    padding: 12px 14px;
    border-radius: 8px;
  }
  .insights-header {
    display: flex;
    align-items: center;
    color: #854d0e;
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 8px;
  }
  .insights-icon {
    margin-right: 6px;
    color: #ca8a04;
  }
  .insights-list {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .insight-item {
    display: flex;
    margin-bottom: 6px;
    font-size: 13px;
    color: #71717a;
  }
  .insight-bullet {
    margin-right: 6px;
    color: #eab308;
  }
  .suggest-title {
    font-weight: 600;
    color: #475569;
    font-size: 13px;
  }
  .suggest-tag-item {
    cursor: pointer;
    margin-right: 6px;
    margin-bottom: 4px;
  }
  .suggested-questions {
    margin-top: 12px;
  }
  .suggest-title-block {
    font-weight: 600;
    color: #475569;
    font-size: 13px;
    margin-bottom: 6px;
  }
  .suggest-question-btn {
    display: inline-block;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    color: #3b82f6;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    cursor: pointer;
    margin-right: 8px;
    margin-bottom: 6px;
    transition: all 0.2s;
  }
  .suggest-question-btn:hover {
    background: #eff6ff;
    border-color: #3b82f6;
  }
  </style>
  ```

- [ ] **Step 2: 验证编译**
  
  运行测试打包：
  ```powershell
  npm run build -- --noEmit
  ```
  Expected: 成功无 TypeScript 类型报错。

- [ ] **Step 3: Commit**
  ```bash
  git add frontend/src/components/StructuredOutputCard.vue
  git commit -m "feat: add StructuredOutputCard component for dual-mode display"
  ```

---

### Task 4: UI 渲染分流挂载 (MessageItem.vue)

**Files:**
- Modify: [frontend/src/components/MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue)

- [ ] **Step 1: 引入 `StructuredOutputCard` 组件**
  
  在 [frontend/src/components/MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue) 的 `<script setup>` 区域顶部（约第 25 行），引入该组件：
  ```typescript
  import StructuredOutputCard from './StructuredOutputCard.vue'
  ```

- [ ] **Step 2: 修改气泡内部渲染模板，优先条件渲染卡片**
  
  定位到 `MessageItem.vue` 中对 `message.content` 渲染的元素区（通常在 template 内部带有 `v-html="renderedContent"` 或是处理 markdown 渲染的行，大约在第 30-80 行范围内）。
  * 让我们用 `view_file` 看一下 `MessageItem.vue` 的 template 结构。
  
  * **操作**：使用 `v-if="message.structured_response"` 分支来替换普通文字渲染区：
    ```html
    <!-- 如果消息带有结构化结果，优先采用卡片进行完美渲染 -->
    <StructuredOutputCard 
      v-if="message.structured_response" 
      :data="message.structured_response" 
      @send-message="$emit('send-message', $event)" 
    />
    
    <!-- 否则采用原有的 Markdown 渲染 -->
    <div v-else class="markdown-body" v-html="renderedContent" />
    ```

- [ ] **Step 3: 运行并验证**
  
  运行前端本地构建：
  ```powershell
  npm run build
  ```
  Expected: 构建成功并在 `dist/` 生成正确的打包静态资源。

<!-- 2026-04-19 23:40 Asia/Shanghai - 消息气泡更新：统一卡片层级与现代阅读体验 -->
<template>
  <div
    class="flex animate-slide-up"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="rounded-2xl shadow-2xs transition-all duration-200"
      :class="[messageWrapperClass, isUser ? 'w-fit max-w-[80%] sm:max-w-[70%] ml-auto rounded-tr-xs' : 'w-full max-w-full']"
    >
      <div
        v-if="isAwaitingClarification && !isUser"
        class="flex items-center gap-1.5 px-5 pt-3 text-xs font-medium tracking-wide text-primary"
      >
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
          <span class="relative inline-flex h-2 w-2 rounded-full bg-primary"></span>
        </span>
        <span>等待您的确认...</span>
      </div>
      <div
        v-else-if="isInterruptedMessage && !isUser"
        class="px-5 pt-3 text-xs font-medium tracking-wide text-amber-700"
      >
        已停止生成
      </div>

      <div
        v-if="showDebugDetails && statusText && !isUser"
        class="px-5 pt-3 text-xs font-medium tracking-wide"
        :class="statusClass"
      >
        {{ statusText }}
      </div>

      <div class="px-5 py-3.5">
        <div v-if="!isUser && message.active_subagent && subagentsList.length === 0" class="mb-2.5">
          <SubAgentBadge
            :subagent="message.active_subagent"
            :display-name="message.subagent_display_name"
            :is-streaming="isStreamingActive"
          />
        </div>

        <ReasoningAccordion
          v-if="!isUser && reasoningText"
          :reasoning-text="reasoningText"
          :is-streaming="isStreamingActive"
          :duration="reasoningDuration"
        />

        <!-- 子智能体独立卡片列表 -->
        <div v-if="!isUser && subagentsList.length > 0" class="my-2.5 space-y-2">
          <SubagentCard
            v-for="sub in subagentsList"
            :key="sub.id"
            :subagent="sub"
          />
        </div>

        <p
          v-if="isUser"
          class="whitespace-pre-wrap break-words text-[15px] leading-7"
          :class="textClass"
        >
          {{ content }}
        </p>
        <div
          v-else
          class="message-markdown break-words text-[15px] leading-relaxed"
          :class="[textClass, { 'is-streaming': isStreamingActive }]"
        >
          <div v-if="isStreamingActive && !content" class="flex flex-col gap-2 w-full animate-pulse my-2">
            <span class="h-3.5 bg-neutral-200/80 rounded-md w-2/3"></span>
            <span class="h-3.5 bg-neutral-200/60 rounded-md w-1/2"></span>
          </div>
          <div v-else v-html="renderedContent"></div>
        </div>

      <div
        v-if="!isUser && sqlQueryResult"
        class="mt-3 text-left animate-fade-in"
      >
        <details class="group rounded-lg border border-neutral-200/60 bg-neutral-50/50 p-2.5 px-3.5 transition-all duration-200 hover:bg-neutral-100/50">
          <summary class="flex cursor-pointer select-none items-center justify-between text-neutral-700 list-none">
            <div class="flex items-center gap-2">
              <svg class="w-4 h-4 text-neutral-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/>
              </svg>
              <span class="text-xs font-medium text-neutral-700">
                SQL 查询数据
                <template v-if="sqlQueryResult.row_count !== undefined">
                  <span class="mx-1 text-neutral-300">·</span>
                  <span class="text-xs text-neutral-500 font-normal">
                    {{ sqlQueryResult.row_count }} 行
                    <span v-if="sqlQueryResult.truncated" class="text-amber-600 font-medium">· 已截断</span>
                  </span>
                </template>
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="sqlQueryResult.query_time" class="text-[11px] text-neutral-400 font-normal font-mono">{{ sqlQueryResult.query_time }}</span>
              <span class="text-neutral-400 transition-transform duration-200 group-open:rotate-180 text-[10px]">▼</span>
            </div>
          </summary>

          <div class="mt-2.5 border-t border-neutral-200/50 pt-2.5">
            <!-- 表格主体 -->
            <div class="overflow-x-auto rounded-lg border border-neutral-200/60 bg-white">
              <table class="min-w-full text-xs text-center border-collapse">
                <thead>
                  <tr class="bg-neutral-100/80 text-neutral-700 font-semibold border-b border-neutral-200/60">
                    <th v-for="col in sqlQueryResult.columns" :key="col" class="px-3.5 py-2 font-mono text-center">
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rIdx) in sqlQueryResult.rows" :key="rIdx" class="border-b border-neutral-100 hover:bg-neutral-50/50 transition-colors">
                    <td v-for="col in sqlQueryResult.columns" :key="col" class="px-3.5 py-2 font-mono text-neutral-600 text-center">
                      {{ row[col] !== undefined && row[col] !== null ? row[col] : '-' }}
                    </td>
                  </tr>
                  <tr v-if="!sqlQueryResult.rows || sqlQueryResult.rows.length === 0">
                    <td :colspan="sqlQueryResult.columns?.length || 1" class="px-3.5 py-6 text-center text-neutral-400 font-medium">
                      暂无数据返回
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 防御性聚合建议说明 -->
            <div v-if="sqlQueryResult.truncated" class="mt-3 flex items-start gap-1.5 rounded-xl bg-amber-50/60 p-2.5 text-[11px] leading-relaxed text-amber-800">
              <span class="text-[13px] leading-none">⚠️</span>
              <div>
                数据行数过多，页面仅承载展示前 {{ sqlQueryResult.rows?.length }} 行预览。如需获取完整分析结果，请使用 <strong>导出 CSV</strong> 或 <strong>聚合 SQL</strong> 重跑。
              </div>
            </div>
          </div>
        </details>
      </div>

      <!-- 一键生成图表的智能快捷 Banner (调整至 SQL 查询数据正下方) -->
      <div
        v-if="chartSuggestion"
        class="mt-3 flex flex-col gap-2.5 rounded-lg border border-neutral-200/60 bg-neutral-50/50 p-2.5 px-3.5 transition-all sm:flex-row sm:items-center sm:justify-between animate-fade-in"
      >
        <div class="flex items-center gap-2.5">
          <svg class="h-4 w-4 text-primary shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <div class="text-left">
            <div class="text-xs font-semibold text-neutral-800">智能图表绘制</div>
            <div class="text-[11px] text-neutral-500 mt-0.5">
              {{ chartSuggestion.desc ? `适合绘制：${chartSuggestion.desc}` : '建议将当前结果转换为图表展示' }}
            </div>
          </div>
        </div>
        <div class="flex gap-2">
          <button
            v-if="chartSuggestion.type === 'line' || chartSuggestion.type === 'auto'"
            type="button"
            class="inline-flex items-center rounded-md border border-primary/25 bg-white px-2.5 py-1 text-xs font-medium text-primary transition hover:bg-primary hover:text-white active:scale-95 whitespace-nowrap"
            @click="handleQuickChart('line')"
          >
            <svg class="w-3.5 h-3.5 mr-1 text-current shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            生成折线图
          </button>
          <button
            v-if="chartSuggestion.type === 'bar' || chartSuggestion.type === 'auto'"
            type="button"
            class="inline-flex items-center rounded-md border border-primary/25 bg-white px-2.5 py-1 text-xs font-medium text-primary transition hover:bg-primary hover:text-white active:scale-95 whitespace-nowrap"
            @click="handleQuickChart('bar')"
          >
            <svg class="w-3.5 h-3.5 mr-1 text-current shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            生成柱状图
          </button>
        </div>
      </div>

      <!-- 侧信道直达与懒加载图表卡片 (紧贴智能图表 Banner 展开) -->
      <div v-if="chartSpec" class="mt-3 animate-fade-in">
        <ChartArtifactCard :chart-payload="chartSpec" />
      </div>
      <div
        v-else-if="!isUser && chartArtifacts.length > 0"
        class="mt-3 space-y-3 animate-fade-in"
      >
        <ChartArtifactCard
          v-for="artifact in chartArtifacts"
          :key="artifact.chart_id"
          :artifact-ref="artifact"
        />
      </div>

      <!-- 问答澄清卡片区域 -->
      <div
        v-if="!isUser && hasQuestions"
        class="mt-3 pb-3 animate-fade-in"
      >
        <AskUserQuestionCard
          :questions="questions"
          :is-submitted="isQuestionSubmitted"
          :asker-title="questionAskerTitle"
          :asker-name="questionAskerName"
          @submit="handleQuestionSubmit"
        />
      </div>

      <div
        v-if="showDebugDetails && !isUser && toolCallList.length > 0"
        class="mt-3 space-y-2 pb-3"
      >
        <div
          v-for="tool in toolCallList"
          :key="tool.id"
          class="rounded-lg border border-primary/15 bg-white/70 px-3 py-2 text-xs text-neutral-600"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="font-medium text-primary">{{ tool.name }}</span>
            <span class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
              {{ toolStatusText(tool) }}
            </span>
          </div>
          <p v-if="getToolArgsText(tool)" class="mt-1 max-h-24 overflow-hidden whitespace-pre-wrap break-all text-neutral-500 font-mono">
            {{ getToolArgsText(tool) }}
          </p>
        </div>
      </div>

      <div
        v-if="showDebugDetails && !isUser && toolResultEntries.length > 0"
        class="mt-3 space-y-2 pb-3"
      >
        <details
          v-for="toolResult in toolResultEntries"
          :key="toolResult.id"
          class="rounded-lg border border-neutral-200 bg-surface/90 px-3 py-2 text-xs text-neutral-600"
        >
          <summary class="cursor-pointer select-none font-medium text-neutral-700">
            工具结果: {{ getToolNameById(toolResult.id) }} ({{ toolResult.id }})
          </summary>
          <pre class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-relaxed text-neutral-500 font-mono">{{ formatToolResultContent(toolResult.content) }}</pre>
        </details>
      </div>

      <div
        v-if="showDebugDetails && errorText && !isUser"
        class="mt-3 pb-3"
      >
        <div class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
          {{ errorText }}
        </div>
      </div>

      <!-- 反馈操作按钮与时间状态展示行 -->


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
      </div>

      <!-- 新机制：侧信道直达的 CSV 导出，无需等待打字机 (流式优先) -->
      <div v-if="fileExport" class="space-y-3 px-4 pb-3">
        <div class="rounded-[22px] border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-emerald-50/50 px-4 py-3 shadow-sm">
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-emerald-800">CSV 文件已生成</div>
              <div class="mt-1 break-all text-sm text-emerald-700">{{ fileExport.filename }}</div>
              <div class="mt-2 text-xs leading-5 text-emerald-700/90">
                <span>{{ fileExport.row_count }} 行 × {{ fileExport.col_count }} 列</span>
                <span v-if="fileExport.size_bytes"> · {{ formatFileSize(fileExport.size_bytes) }}</span>
              </div>
              <div v-if="fileExport.columns && fileExport.columns.length > 0" class="mt-1 text-xs leading-5 text-emerald-700/90">
                列名：{{ fileExport.columns.join('、') }}
              </div>
              <div v-if="fileExport.expires_at" class="mt-1 text-xs leading-5 text-emerald-700/80">
                有效期至：{{ formatDateTime(fileExport.expires_at) }}
              </div>
            </div>
            <button
              type="button"
              class="shrink-0 rounded-2xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700"
              @click="handleExportDownload(fileExport.file_id)"
            >
              下载 CSV
            </button>
          </div>
        </div>
      </div>

      <!-- 旧机制：历史消息兼容 (保留) -->
      <div
        v-else-if="!isUser && exportArtifacts.length > 0"
        class="space-y-3 px-4 pb-3"
      >
        <div
          v-for="artifact in exportArtifacts"
          :key="artifact.file_id"
          class="rounded-[22px] border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-emerald-50/50 px-4 py-3 shadow-sm"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-emerald-800">CSV 文件已生成</div>
              <div class="mt-1 break-all text-sm text-emerald-700">{{ artifact.filename }}</div>
              <div class="mt-2 text-xs leading-5 text-emerald-700/90">
                <span v-if="artifact.row_count !== undefined && artifact.col_count !== undefined">
                  {{ artifact.row_count }} 行 × {{ artifact.col_count }} 列
                </span>
                <span v-if="artifact.size_bytes !== undefined">
                  · {{ formatFileSize(artifact.size_bytes) }}
                </span>
              </div>
              <div
                v-if="artifact.columns && artifact.columns.length > 0"
                class="mt-1 text-xs leading-5 text-emerald-700/90"
              >
                列名：{{ artifact.columns.join('、') }}
              </div>
              <div
                v-if="artifact.expires_at"
                class="mt-1 text-xs leading-5 text-emerald-700/80"
              >
                有效期至：{{ formatDateTime(artifact.expires_at) }}
              </div>
            </div>

            <button
              type="button"
              class="shrink-0 rounded-2xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700"
              @click="handleExportDownload(artifact.file_id)"
            >
              下载 CSV
            </button>
          </div>
        </div>
      </div>


        <!-- 第二阶段新增：参考业务术语折叠卡片 -->
        <div v-if="!isUser && parsedRagContext.length > 0" class="mt-4 px-5 animate-fade-in text-left">
          <details class="group rounded-[20px] border border-neutral-200/80 bg-neutral-50/50 p-3.5 text-xs text-neutral-600 transition-all duration-200">
            <summary class="flex cursor-pointer select-none items-center justify-between font-semibold text-neutral-700 hover:text-primary list-none">
              <span class="flex items-center gap-2">
                <svg class="h-4 w-4 text-neutral-500 group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                <span class="text-xs font-semibold text-neutral-800">参考业务术语 ({{ parsedRagContext.length }} 条)</span>
              </span>
              <svg class="h-3.5 w-3.5 text-neutral-400 transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            <div class="mt-3 space-y-4 border-t border-neutral-200/60 pt-3">
              <div v-for="item in parsedRagContext" :key="item.title" class="space-y-1.5">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-[6px] bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                    {{ item.domain }}
                  </span>
                  <span class="font-bold text-neutral-800 text-[12px]">{{ item.title }}</span>
                  <span v-if="item.aliases && item.aliases.length" class="text-[10px] text-neutral-400 font-medium">
                    (别名: {{ item.aliases.join(', ') }})
                  </span>
                </div>
                <p class="pl-0.5 text-[11px] leading-5 text-neutral-500 whitespace-pre-line font-medium">
                  {{ item.content }}
                </p>
              </div>
            </div>
          </details>
        </div>

        <!-- 新增：参考数据库物理词典折叠卡片 -->
        <div v-if="!isUser && parsedLexiconContext && (parsedLexiconContext.tables?.length || parsedLexiconContext.values?.length || parsedLexiconContext.rows?.length)" class="mt-3 px-5 animate-fade-in text-left">
          <details class="group rounded-[20px] border border-neutral-200/80 bg-neutral-50/50 p-3.5 text-xs text-neutral-600 transition-all duration-200">
            <summary class="flex cursor-pointer select-none items-center justify-between font-semibold text-neutral-700 hover:text-primary list-none">
              <span class="flex items-center gap-2">
                <svg class="h-4 w-4 text-neutral-500 group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                </svg>
                <span class="text-xs font-semibold text-neutral-800">参考数据库物理词典 (DB Lexicon)</span>
              </span>
              <svg class="h-3.5 w-3.5 text-neutral-400 transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            
            <div class="mt-3 space-y-3.5 border-t border-neutral-200/60 pt-3">
              <!-- 1. 表结构 DDL 模块 -->
              <div v-if="parsedLexiconContext.tables && parsedLexiconContext.tables.length > 0" class="space-y-2">
                <details class="sub-group">
                  <summary class="flex cursor-pointer select-none items-center gap-1.5 font-bold text-neutral-700 hover:text-primary text-[11.5px] list-none">
                    <span class="text-neutral-400">📂</span>
                    <span>推荐的数据库表 DDL 结构 (已命中 {{ parsedLexiconContext.tables.length }} 张表)</span>
                  </summary>
                  <div class="mt-2 space-y-2.5 pl-3 border-l border-neutral-200/80">
                    <div v-for="tbl in parsedLexiconContext.tables" :key="tbl.table_name" class="space-y-1">
                      <div class="text-[11px] font-bold text-neutral-600 font-mono">{{ tbl.table_name }}</div>
                      <pre class="bg-neutral-900 text-neutral-100 p-2.5 rounded-xl text-[10.5px] overflow-x-auto max-h-48 font-mono leading-normal whitespace-pre-wrap break-all"><code class="language-sql">{{ tbl.ddl }}</code></pre>
                    </div>
                  </div>
                </details>
              </div>

              <!-- 2. 列值对照映射模块 -->
              <div v-if="parsedLexiconContext.values && parsedLexiconContext.values.length > 0" class="space-y-2">
                <details class="sub-group">
                  <summary class="flex cursor-pointer select-none items-center gap-1.5 font-bold text-neutral-700 hover:text-primary text-[11.5px] list-none">
                    <svg class="h-3.5 w-3.5 text-neutral-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                      <path d="M3 3v5h5" />
                      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                      <path d="M16 16h5v5" />
                    </svg>
                    <span>字段去重值对照参考 (已命中 {{ parsedLexiconContext.values.length }} 条)</span>
                  </summary>
                  <div class="mt-2 pl-3 border-l border-neutral-200/80 overflow-x-auto">
                    <table class="min-w-full text-[10.5px] border-collapse text-left">
                      <thead>
                        <tr class="bg-neutral-100/80 text-neutral-600 border-b border-neutral-200">
                          <th class="p-1.5 font-semibold">数据表</th>
                          <th class="p-1.5 font-semibold">目标列名</th>
                          <th class="p-1.5 font-semibold">物理字段值</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(val, idx) in parsedLexiconContext.values" :key="idx" class="border-b border-neutral-100 hover:bg-neutral-50/50">
                          <td class="p-1.5 font-mono text-neutral-500">{{ val.table_name }}</td>
                          <td class="p-1.5 font-mono text-neutral-700 font-semibold">{{ val.column_name }}</td>
                          <td class="p-1.5"><code class="bg-primary/5 text-primary px-1 py-0.5 rounded font-mono font-bold">{{ val.exact_value }}</code></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>

              <!-- 3. 行实体关联模块 -->
              <div v-if="parsedLexiconContext.rows && parsedLexiconContext.rows.length > 0" class="space-y-2">
                <details class="sub-group">
                  <summary class="flex cursor-pointer select-none items-center gap-1.5 font-bold text-neutral-700 hover:text-primary text-[11.5px] list-none">
                    <span class="text-neutral-400">🔍</span>
                    <span>实体主键与行属性参考 (已命中 {{ parsedLexiconContext.rows.length }} 条)</span>
                  </summary>
                  <div class="mt-2 pl-3 border-l border-neutral-200/80 overflow-x-auto">
                    <table class="min-w-full text-[10.5px] border-collapse text-left">
                      <thead>
                        <tr class="bg-neutral-100/80 text-neutral-600 border-b border-neutral-200">
                          <th class="p-1.5 font-semibold">数据表</th>
                          <th class="p-1.5 font-semibold">主键列 / 主键值</th>
                          <th class="p-1.5 font-semibold">关联行属性描述</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, idx) in parsedLexiconContext.rows" :key="idx" class="border-b border-neutral-100 hover:bg-neutral-50/50">
                          <td class="p-1.5 font-mono text-neutral-500">{{ row.table_name }}</td>
                          <td class="p-1.5 font-mono">
                            <span class="text-neutral-700 font-medium">{{ row.primary_key_column }}</span>
                            <span class="text-neutral-400 mx-1">:</span>
                            <code class="bg-neutral-100 text-neutral-800 px-1 py-0.5 rounded font-bold">{{ row.primary_key_val }}</code>
                          </td>
                          <td class="p-1.5 text-neutral-600 whitespace-pre-line leading-relaxed">{{ row.row_content }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>
            </div>
          </details>
        </div>

            <!-- 智能 SQL 数据预览表格模块 (防冲突修改) -->
      <div
        v-if="!isUser && !isStreamingActive && props.message.id && !props.message.id.startsWith('temp-')"
        class="flex items-center justify-between px-5 pb-3.5 pt-0 text-neutral-400 border-t border-neutral-100/50 mt-1"
      >
        <div class="flex items-center gap-4 mt-2">
          <button
            type="button"
            class="transition-colors duration-150 hover:text-primary active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            :class="{ 'text-primary !font-semibold': props.message.feedback === 'like' }"
            @click="handleFeedback('like')"
          >
            👍 <span class="hidden sm:inline">赞</span>
          </button>
          <button
            type="button"
            class="transition-colors duration-150 hover:text-rose-500 active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            :class="{ 'text-rose-500 !font-semibold': props.message.feedback === 'dislike' }"
            @click="handleFeedback('dislike')"
          >
            👎 <span class="hidden sm:inline">踩</span>
          </button>
          <button
            type="button"
            class="transition-colors duration-150 hover:text-amber-500 active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            :class="{ 'text-amber-500 !font-semibold': props.message.feedback === 'collected' || props.message.feedback === 'approved' }"
            @click="handleFeedback(props.message.feedback === 'collected' || props.message.feedback === 'approved' ? 'none' : 'collected')"
          >
            ⭐ <span class="hidden sm:inline">{{ props.message.feedback === 'collected' || props.message.feedback === 'approved' ? '已收藏' : '收藏' }}</span>
          </button>
        </div>
        <div class="flex items-center gap-4 mt-2" :class="timeClass">
          <button
            type="button"
            class="transition-colors duration-150 hover:text-primary active:scale-95 flex items-center text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            @click="handleCopy"
            :title="copied ? '已复制' : '复制消息内容'"
          >
            <svg v-if="copied" class="h-3.5 w-3.5 text-emerald-500 animate-scale-up" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
          <div class="flex items-center gap-1">
            <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-xs">{{ formattedTime }}</span>
          </div>
        </div>
      </div>
      <div
        v-else
        class="flex items-center justify-end gap-4 px-4 pb-2.5 pt-0"
        :class="timeClass"
      >
        <button
          v-if="!isStreamingActive"
          type="button"
          class="transition-colors duration-150 hover:text-primary active:scale-95 flex items-center text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
          @click="handleCopy"
          :title="copied ? '已复制' : '复制消息内容'"
        >
          <svg v-if="copied" class="h-3.5 w-3.5 text-emerald-500 animate-scale-up" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
        </button>
        <div class="flex items-center gap-1">
          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-xs">{{ formattedTime }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import SubAgentBadge from '@/components/agent/SubAgentBadge.vue'
import ChartArtifactCard from '@/components/artifacts/ChartArtifactCard.vue'
import AskUserQuestionCard from './AskUserQuestionCard.vue'
import ReasoningAccordion from './ReasoningAccordion.vue'
import SubagentCard from './SubagentCard.vue'
import { useChatStream } from '@/composables/useChatStream'
import { triggerExportDownload } from '@/api/exports'
import { CHAT_DEBUG_STREAM } from '@/config/chat'
import { useMessagesStore } from '@/stores/messages'
import type {
  ChartArtifact,
  ChartArtifactRef,
  ExportArtifact,
  Message,
  StreamToolCall,
  StreamingMessage,
  SubagentSessionState,
} from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'
import { renderMarkdown, extractMetaData } from '@/utils/markdown'
import { formatSubagentTitle } from '@/utils/helpers'
import { parseJson, formatFileSize, copyToClipboard } from '@/utils/helpers'

interface Props {
  message: Message | StreamingMessage
}

interface ToolResultEntry {
  id: string
  content: string
}

const props = defineProps<Props>()

const messagesStore = useMessagesStore()

const { formatTime, parseServerDate } = useDateFormat()

const isUser = computed(() => props.message.role === 'user')
const reasoningText = computed(() => {
  if (streamingState.value?.reasoningText) {
    return streamingState.value.reasoningText
  }
  const msgId = props.message.id
  if (msgId && messagesStore.memoryReasoningMap[msgId]) {
    return messagesStore.memoryReasoningMap[msgId]
  }
  return (props.message as Message).reasoningText ?? ''
})

const reasoningDuration = computed(() => {
  if (streamingState.value?.reasoningDuration !== undefined) {
    return streamingState.value.reasoningDuration
  }
  const msgId = props.message.id
  if (msgId && messagesStore.memoryReasoningDurationMap[msgId] !== undefined) {
    return messagesStore.memoryReasoningDurationMap[msgId]
  }
  return (props.message as Message).reasoningDuration
})

const streamingState = computed<StreamingMessage | null>(() => {
  if ('toolCalls' in props.message && 'toolResults' in props.message) {
    return props.message as StreamingMessage
  }
  return null
})

const isStreamingActive = computed(() => Boolean(streamingState.value?.isStreaming))
const showDebugDetails = CHAT_DEBUG_STREAM

const emit = defineEmits<{
  (e: 'select-scenario', prompt: string): void
}>()

const content = computed(() =>
  streamingState.value ? streamingState.value.content : props.message.content
)

const chartSuggestion = computed<{ type: 'line' | 'bar' | 'auto'; desc: string | null } | null>(() => {
  if (isUser.value || isStreamingActive.value) return null
  const rawContent = content.value || ''
  const match = rawContent.match(/\[suggest_chart:(line|bar|auto)(?:\|([^\]]+))?\]/)
  return match ? { type: match[1] as 'line' | 'bar' | 'auto', desc: match[2] || null } : null
})

const metaData = computed(() => {
  const { meta } = extractMetaData(content.value || '')
  return meta
})

const parsedRagContext = computed(() => {
  if (streamingState.value?.ragContext) {
    return streamingState.value.ragContext
  }
  const msgId = props.message.id
  if (msgId && messagesStore.memoryRagMap[msgId]) {
    return messagesStore.memoryRagMap[msgId]
  }
  return (props.message as Message).rag_context ?? []
})

const parsedLexiconContext = computed(() => {
  if (streamingState.value?.lexiconContext) {
    return streamingState.value.lexiconContext
  }
  const msgId = props.message.id
  if (msgId && messagesStore.memoryLexiconMap[msgId]) {
    return messagesStore.memoryLexiconMap[msgId]
  }
  return (props.message as Message).lexicon_context ?? { tables: [], values: [], rows: [] }
})

const queryResult = computed(() => {
  if (streamingState.value?.tool_artifact) {
    return streamingState.value.tool_artifact
  }
  const msgId = props.message.id
  if (msgId && messagesStore.memoryArtifactMap[msgId]) {
    return messagesStore.memoryArtifactMap[msgId]
  }
  return (props.message as Message).tool_artifact ?? null
})

// 判断 tool_artifact 是否为 chart_spec
const chartSpec = computed<ChartArtifact | null>(() => {
  const artifact = queryResult.value
  if (artifact && artifact.kind === 'chart_spec') {
    return artifact as unknown as ChartArtifact
  }
  return null
})

// 判断实时侧信道推送的 tool_artifact 是否为 file_export
const fileExport = computed<ExportArtifact | null>(() => {
  const artifact = queryResult.value
  if (artifact && artifact.kind === 'file_export') {
    return artifact as unknown as ExportArtifact
  }
  return null
})

// 仅在 kind === 'query_result'，或者具有 columns 时作为表格渲染数据，过滤掉图表
const sqlQueryResult = computed(() => {
  const artifact = queryResult.value
  if (artifact && (artifact.kind === 'query_result' || (!artifact.kind && artifact.columns))) {
    return artifact
  }
  return null
})

const displayContent = computed(() => {
  const rawContent = content.value || ''
  const cleaned = rawContent.replace(/\[suggest_chart:(line|bar|auto)(?:\|[^\]]*)?\]/, '')
  const { cleanContent } = extractMetaData(cleaned)
  return cleanContent
})

const renderedContent = ref('')
let renderRafId = 0

watch(displayContent, (val) => {
  if (isStreamingActive.value) {
    // 流式过程中使用 requestAnimationFrame 节流，避免每 token 都全量渲染 markdown
    if (renderRafId) cancelAnimationFrame(renderRafId)
    renderRafId = requestAnimationFrame(() => {
      renderedContent.value = renderMarkdown(val)
    })
  } else {
    // 非流式状态直接渲染（最终消息）
    if (renderRafId) {
      cancelAnimationFrame(renderRafId)
      renderRafId = 0
    }
    renderedContent.value = renderMarkdown(val)
  }
}, { immediate: true })

const handleQuickChart = (type: 'line' | 'bar' | 'auto') => {
  const promptMap = {
    line: '生成折线图',
    bar: '生成柱状图',
    auto: '生成图表',
  }
  emit('select-scenario', promptMap[type])
}

const rawToolResults = computed<Record<string, string>>(() => {
  const message = props.message as Message
  return streamingState.value?.toolResults ?? parseJson<Record<string, string>>(message.tool_results) ?? {}
})

const statusText = computed(() => streamingState.value?.statusText ?? null)
const errorText = computed(() => streamingState.value?.error ?? null)
const isInterruptedMessage = computed(() => {
  if (streamingState.value) {
    return Boolean(streamingState.value.isInterrupted)
  }
  return Boolean((props.message as Message).is_interrupted)
})

const subagentsList = computed<SubagentSessionState[]>(() => {
  if (streamingState.value?.subagents) {
    return Object.values(streamingState.value.subagents)
  }
  const msgId = props.message.id
  if (msgId && messagesStore.memorySubagentsMap[msgId]) {
    return Object.values(messagesStore.memorySubagentsMap[msgId])
  }
  const msg = props.message as Message
  if (msg.subagents) {
    return Object.values(msg.subagents)
  }
  return []
})

const toolCallList = computed<StreamToolCall[]>(() => {
  if (streamingState.value) {
    return streamingState.value.toolCalls.filter(t => !t.subagent_id)
  }
  const message = props.message as Message
  const parsed = parseJson<StreamToolCall[]>(message.tool_calls)
  return (Array.isArray(parsed) ? parsed : []).filter(t => !t.subagent_id)
})

const toolResultEntries = computed<ToolResultEntry[]>(() => {
  const mainToolIds = new Set(toolCallList.value.map(t => t.id))
  return Object.entries(rawToolResults.value)
    .filter(([id]) => mainToolIds.has(id))
    .map(([id, result]) => ({
      id,
      content: String(result)
    }))
})

const isExportArtifact = (value: unknown): value is ExportArtifact => {
  if (!value || typeof value !== 'object') return false
  const artifact = value as Record<string, unknown>
  return (
    artifact.kind === 'file_export'
    && typeof artifact.file_id === 'string'
    && typeof artifact.filename === 'string'
  )
}

const exportArtifacts = computed<ExportArtifact[]>(() => {
  const results = rawToolResults.value

  return toolCallList.value.flatMap((tool) => {
    if (tool.name !== 'export_to_csv') {
      return []
    }

    const rawResult = results[tool.id]
    if (typeof rawResult !== 'string') {
      return []
    }

    const parsed = parseJson<ExportArtifact>(rawResult)
    if (!isExportArtifact(parsed)) {
      return []
    }

    return [parsed]
  })
})

const isChartArtifactRef = (value: unknown): value is ChartArtifactRef => {
  if (!value || typeof value !== 'object') return false
  const artifact = value as Record<string, unknown>
  return (
    artifact.kind === 'chart_artifact_ref'
    && typeof artifact.chart_id === 'string'
    && typeof artifact.title === 'string'
  )
}

const chartArtifacts = computed<ChartArtifactRef[]>(() => {
  const results = rawToolResults.value

  return toolCallList.value.flatMap((tool) => {
    if (tool.name !== 'build_chart_artifact') {
      return []
    }

    const rawResult = results[tool.id]
    if (typeof rawResult !== 'string') {
      return []
    }

    const parsed = parseJson<ChartArtifactRef>(rawResult)
    if (!isChartArtifactRef(parsed)) {
      return []
    }

    return [parsed]
  })
})

const hasToolResult = (toolId: string) => toolResultEntries.value.some(item => item.id === toolId)

// 澄清卡片相关逻辑
const questions = computed(() => {
  if (streamingState.value) {
    return streamingState.value.questions || []
  }
  return (props.message as Message).questions || []
})
const hasQuestions = computed(() => questions.value.length > 0)
const isLocalSubmitted = ref(false)

// 监听澄清问题包的深度变化，一旦有新问题推入（例如下一轮的澄清卡片）自动重置本地提交锁定状态
watch(
  () => questions.value,
  (newQuestions) => {
    if (newQuestions && newQuestions.length > 0) {
      isLocalSubmitted.value = false
    }
  },
  { deep: true }
)
const isQuestionSubmitted = computed(() => {
  if (!streamingState.value) {
    return true
  }
  return isLocalSubmitted.value
})

const isAwaitingClarification = computed(() => {
  return isInterruptedMessage.value && hasQuestions.value && !isQuestionSubmitted.value
})

const questionAskerTitle = computed(() => {
  if (streamingState.value?.interrupt_subagent_title) {
    return streamingState.value.interrupt_subagent_title
  }
  if (streamingState.value?.interrupt_subagent_name && streamingState.value.interrupt_subagent_name !== 'main') {
    return formatSubagentTitle(streamingState.value.interrupt_subagent_name)
  }
  return null
})

const questionAskerName = computed(() => {
  if (streamingState.value?.interrupt_subagent_name && streamingState.value.interrupt_subagent_name !== 'main') {
    return streamingState.value.interrupt_subagent_name
  }
  return null
})
const { resumeMessage } = useChatStream()
const handleQuestionSubmit = async (answers: Record<string, string | string[]>) => {
  isLocalSubmitted.value = true
  try {
    await resumeMessage(answers)
  } catch (err) {
    isLocalSubmitted.value = false
    console.error('回复澄清失败:', err)
  }
}

const handleCopy = async () => {
  const textToCopy = displayContent.value || ''
  if (!textToCopy) return
  try {
    await copyToClipboard(textToCopy)
    copied.value = true
    if (copyTimeout) {
      clearTimeout(copyTimeout)
    }
    copyTimeout = window.setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}

const formatDateTime = (value: string) => {
  const date = parseServerDate(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

const handleExportDownload = (fileId: string) => {
  triggerExportDownload(fileId)
}

const toolStatusText = (tool: StreamToolCall) => {
  if (tool.status === 'completed' || hasToolResult(tool.id)) {
    return '已完成'
  }

  if (isAwaitingClarification.value) {
    return '等待确认'
  }

  if (isInterruptedMessage.value) {
    return '已停止'
  }

  const status = tool.status
  switch (status) {
    case 'started':
      return '已开始'
    default:
      return '执行中'
  }
}

const getToolArgsText = (tool: StreamToolCall): string => {
  if (tool.name === 'task') {
    const args = typeof tool.args === 'object' && tool.args !== null
      ? tool.args as Record<string, unknown>
      : parseJson<Record<string, unknown>>(tool.args_text || '')
    if (args && typeof args.description === 'string') {
      return `委派子任务: ${args.description}`
    }
  }
  if (tool.args_text) {
    return tool.args_text
  }
  if (tool.args) {
    if (typeof tool.args === 'object' && tool.args !== null) {
      const argsObj = tool.args as Record<string, unknown>
      if (typeof argsObj.query === 'string') {
        return argsObj.query
      }
      return JSON.stringify(tool.args, null, 2)
    }
    return String(tool.args)
  }
  return ''
}

const getToolNameById = (id: string): string => {
  const tool = toolCallList.value.find(t => t.id === id)
  if (tool?.name) {
    return tool.name
  }
  return id.startsWith('chatcmpl-') ? '工具调用' : id
}

const formatToolResultContent = (content: string): string => {
  try {
    const parsed = JSON.parse(content)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return content
  }
}

const messageWrapperClass = computed(() => {
  if (isUser.value) {
    return 'border border-neutral-200/80 bg-neutral-100/90 text-neutral-800 shadow-2xs'
  }
  if (errorText.value) {
    return 'border border-red-200 bg-gradient-to-br from-red-50 to-white'
  }
  if (isAwaitingClarification.value) {
    return 'border border-blue-200/80 bg-gradient-to-br from-blue-50/30 via-white to-white shadow-sm'
  }
  if (isInterruptedMessage.value) {
    return 'border border-amber-200 bg-gradient-to-br from-amber-50 to-white'
  }
  if (streamingState.value) {
    return 'border border-[#DDEBFA] bg-[#F3F8FF] shadow-sm'
  }
  return 'border border-neutral-200/90 bg-white/95 shadow-sm'
})

const textClass = computed(() => {
  if (isUser.value) {
    return 'font-medium text-neutral-800'
  }
  if (errorText.value) {
    return 'text-red-700'
  }
  if (isAwaitingClarification.value) {
    return 'text-neutral-800'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-800'
  }
  return 'text-text'
})

const statusClass = computed(() => {
  if (errorText.value) {
    return 'text-red-500'
  }
  if (isAwaitingClarification.value) {
    return 'text-primary font-medium'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-600'
  }
  return 'text-primary'
})

const timeClass = computed(() => {
  if (isUser.value) {
    return 'text-[#7A8C9E]'
  }
  if (errorText.value) {
    return 'text-red-400'
  }
  if (isAwaitingClarification.value) {
    return 'text-neutral-500'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-500'
  }
  return 'text-neutral-500'
})

const formattedTime = computed(() => {
  if (isStreamingActive.value) return '正在生成...'
  return formatTime(props.message.created_at)
})

const handleFeedback = async (feedbackType: 'none' | 'like' | 'dislike' | 'collected' | 'approved') => {
  if (!props.message.id) return
  try {
    await messagesStore.submitMessageFeedback(props.message.id, feedbackType)
  } catch (err) {
    console.error('Submit feedback failed:', err)
  }
}

const copied = ref(false)
let copyTimeout: number | null = null
</script>

<style scoped>
/* 2026-07-11 - Markdown 动态渲染元素与代码框美化 */
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

.message-markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}
</style>
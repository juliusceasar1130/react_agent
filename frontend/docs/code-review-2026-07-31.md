# 前端代码检查报告（2026-07-31）

> 检查范围：`frontend/src` 全部 49 个源文件（约 7700 行，含 style.css），并顺带核对 vite.config.ts / tailwind.config.js / package.json / tsconfig.json。
>
> 检查方式：code-reviewer 子代理逐维度审查 + 关键发现人工复核 + WebSearch 核对依赖最新版本（npm registry 直连不通）。
>
> 路径简写：`R = frontend/src`

---

## 一、总体结论

| 维度 | 结论 |
|---|---|
| Vue 3 废弃 API / Vue 2 遗留写法 | ✅ 干净，无任何命中 |
| 废弃依赖用法 | ✅ 干净，markdown-it/pinia/vite/tailwind 用法均与声明版本匹配 |
| TODO/FIXME / 注释代码块 | ✅ 干净，零命中 |
| 死代码 | ⚠️ 有问题：8 处死代码 + 1 处组件重复实例化 |
| 类型安全 | ⚠️ 有问题：`str` 类型笔误（阻塞构建）+ any/双重断言/非空断言若干 |
| 调试/UI 残留 | ⚠️ 零星：`v-if="false"` 隐藏 UI、`[diagnose]` 日志、无条件 console.debug |
| 依赖版本 | ⚠️ 部分落后：pinia/echarts/tailwind/vite/vue-tsc 均有新大版本 |

整体判断：代码的 Vue 3 现代化程度高，无 Vue 2 遗留、无废弃 API 用法；主要"不干净"集中在**死代码**与**类型漏洞**；依赖方面 lockfile 冻结在旧版本。

---

## 二、干净维度（详细）

### 1. Vue 3 废弃 API / Vue 2 遗留写法 — 干净

- 无 `filters:`、`$on/$off`、`Vue.set`、`.sync`、`slot="..."`、`slot-scope`、`$listeners/$scopedSlots/$children`、`beforeDestroy`、`new Vue(`、options API 混用（`export default { data() {...} }` 零命中）
- 生命周期全部使用 `onMounted/onUnmounted`
- v-model 全部为新版 `modelValue/update:modelValue`（如 `R\components\ToggleSwitch.vue:63-65`、`R\views\ChatView.vue:203` 的 `v-model:show`）

### 2. 废弃/已移除的依赖用法 — 干净

- markdown-it ^14：`R\utils\markdown.ts:5-38` 的 `new MarkdownIt({html, linkify, breaks, typographer})`、`markdown.renderer.rules.*` 覆写、`token.attrSet` 均为 v14 现行 API
- dompurify ^3：`R\utils\markdown.ts:46-48` `sanitize(rendered, { USE_PROFILES })` 现行
- pinia 2.x：5 个 store 全部是 setup store（`defineStore('id', () => {...})`），无 pinia 1.x options 语法
- vite ^5：`frontend/vite.config.ts` 无 vite 4 及以下过时配置项（proxy/alias/plugins 均现行写法；`:16` 的 `extensions` 数组为冗余默认值，非过时）
- tailwind ^3：`frontend/tailwind.config.js` 为 ESM `export default`（与 package.json `"type": "module"` 匹配），`content` 数组正确，无 tailwind 2 的 `purge` 语法
- 注意：`package.json` 未装 `@types/markdown-it`，导致用本地 any shim 兜底（见维度五）

### 3. TODO/FIXME / 注释代码 / 调试残留

- 无 TODO/FIXME/XXX/HACK；未发现被注释掉的代码块（`//` 前缀代码行与 `/* */` 代码块均零命中）

---

## 三、死代码（维度 3）

以下符号全项目 grep 无任何引用方（定义与导出之外零命中）：

| 位置 | 内容 |
|---|---|
| `R\api\messages.ts:8-10` | `getMessageApi` 导出后无人调用 |
| `R\api\sessions.ts:12-14` | `getSessionApi` 导出后无人调用 |
| `R\stores\messages.ts:211-217` | action `setStreamingError`，无调用方 |
| `R\stores\messages.ts:338-340` | action `clearStreamingForSession`，无调用方（注释自诩"🆕 新增清理 action"，实际从未接线） |
| `R\stores\scenarioPanel.ts:68-70`（导出于 :211） | `backToList` 无任何调用方 |
| `R\composables\useDateFormat.ts:10-28` | `formatDate` 导出后无消费者（三个使用方 MessageItem/SessionItem/ChartArtifactCard 只解构了 `formatTime`/`formatFullDateTime`/`parseServerDate`） |
| `R\types\index.ts:145-148` | `StreamToolResult` 接口导出后无任何 import |
| `R\utils\test_markdown.js`（整文件 56 行） | 残留在 src 下的 Node 脚本：用正则从 `markdown.ts` 抽取源码 + `eval()` 跑"单元测试"（:20-21），未接入 package.json 任何 script，无引用。属于遗留测试/调试文件混入生产源码目录 |

次要：

- `R\stores\skills.ts:25,42,52` — `error` 状态有写入无读取

### 3.1 组件重复实例化（已人工确认，实际 bug）

- `R\views\ChatView.vue:201` 与 `R\components\VariantB.vue:456` 各自渲染一个 `<ScenarioModal>`
- 两个实例读取同一个 pinia store（`useScenarioPanelStore().visible`），双击单元格事件（`dblclick-cell`）会同时触发两个弹窗实例打开
- ChatView.vue:9 又监听 VariantB 转发上来的 `dblclick-cell` → 同一事件可能走两条路径
- 属组件重复实例化遗留，建议确认后删除其中一个

---

## 四、调试/UI 残留（维度 4）

| 位置 | 内容 |
|---|---|
| `R\views\ChatView.vue:130` | `<ToggleSwitch v-if="false" v-model="enableThinking" ...>`：用 `v-if="false"` 永久禁用"思考模式"开关，等价于注释掉的 UI（`enableThinking` 仍透传到 `R\composables\useChatStream.ts:235,259` 的请求体，开关却永远不可见） |
| `R\composables\useChatStream.ts:121,392` | `console.error('[diagnose] 流式请求异常类型: ...')` / `console.error('[diagnose] 恢复流式异常: ...')`：带 `[diagnose]` 前缀的调试日志残留，无开关控制 |
| `R\api\chat.ts`（8 处） | `console.debug`（:305、:321、:333、:346、:401、:418、:430、:443）无条件执行。项目已有 `CHAT_DEBUG_STREAM` 开关（`R\config\chat.ts:6`），但只被 `R\components\MessageItem.vue:597` 使用，api/chat.ts 的 debug 日志未接入，生产构建仍输出 |
| `R\stores\messages.ts:370,390,393` | 注释中的 "🆕 新增" 标记残留 |
| `R\components\AskUserQuestionCard.vue:206-208` | `onTextAreaInput` 是空实现 stub（模板 :87 仍绑定，函数体只有注释"不做操作"） |

其余 11 处 `console.error/warn`（如 `R\components\MessageItem.vue:827,961,983,1004`、`R\stores\messages.ts:115`、`R\api\chat.ts:328,337`）属于正常错误处理，不列为残留。

---

## 五、类型安全（维度 5）

### 严重：未定义类型 `str`（阻塞构建）

- `R\api\scenarios.ts:24` — `description: str`，`str` 是未定义类型（笔误，应为 `string`）
- 该类型是 `ParameterDef` 的字段，被 `ParameterForm.vue` 与 5 个 widgets 正在使用，属活代码上的类型漏洞
- 在 `strict: true` + include src 的 tsconfig 下，`npm run build:check`（vue-tsc）会直接报 TS 编译错误；当前仅 vite dev 不查类型所以未暴露

### 统计

- **`any`：34 处**，分布在 16 个文件。典型：
  - `R\api\chat.ts:172` — `lexicon_context: parsed.lexicon_context as any`（:167 已有 `isRecord` 校验，本可安全收窄）
  - `R\types\index.ts:60,212,256` — `rows?: any[]`、`artifact: any`
  - `R\utils\markdown.ts:12-37` — 6 个 renderer 规则签名全是 `tokens: any, idx: number, options: any, env: any, self: any`（根因是缺 `@types/markdown-it`）
  - `R\markdown-it.d.ts:2` — `declare module 'markdown-it' { const MarkdownIt: any }` 全 any shim
  - `R\components\widgets\DateWidget.vue:18,23` — `modelValue: any`
  - `R\stores\scenarioPanel.ts:34-35,111,139` — `Record<string, any>`（参数缓存/值）
  - `R\views\ChatView.vue:278`、`R\components\DimensionTable.vue:173` — `let toastTimer: any = null`
  - `catch (err: any)`：`R\stores\skills.ts:41`、`R\stores\scenarioPanel.ts:78,123,164`、`R\components\VariantB.vue:516`
- **`as unknown as` 双重断言：6 处** — `R\api\scenarios.ts:69,85,106`、`R\stores\skills.ts:40`、`R\composables\useChatStream.ts:157,305`
- **非空断言 `!`：4 处**，全部集中在 `R\components\ChartArtifactCard.vue`（:74 `category_field!`、:154-157 `artifact.value!.chart_type` 等）

---

## 六、依赖版本对比（维度 6）

npm registry 直连不通（ECONNRESET），无法运行 `npm outdated`；以下最新版本来自 WebSearch 核对。

| 依赖 | 声明范围 | 已安装（lockfile） | 最新版（2026-07） | 差距 | 升级注意 |
|---|---|---|---|---|---|
| vue | ^3.4.0 | 3.5.26 | 3.5.40 | 同线内 patch，**不算过时** | 重新 `npm install` 即可收敛 |
| axios | ^1.6.0 | 1.13.2 | ~1.x 最新 | 正常 | — |
| dompurify | ^3.3.3 | 3.3.3 | 3.x | 正常 | — |
| markdown-it | ^14.1.1 | 14.1.1 | 14.x | 正常 | — |
| pinia | ^2.1.7 | 2.3.1 | 3.0.4 | 落后 1 个大版本 | v3 升级"通常零代码改动"，移除 `defineStore({id})` 语法，要求 TS 5+；本项目已用 setup store，兼容 |
| echarts | ^5.6.0 | 5.6.0 | 6.1.0 | 落后 1 个大版本 | v6 有 breaking：默认主题变更（需 `echarts/theme/v5.js` 恢复）、API/类型定义变化，需看迁移指南 |
| tailwindcss | ^3.4.0 | 3.4.19 | 4.3 | 落后 1 个大版本 | v4 是重写：`@import "tailwindcss"` 取代三指令、CSS-first 配置（`@theme` 取代 config）、自动 content 检测、border 默认色变更等，breaking 较多 |
| vite | ^5.0.0 | 5.4.21 | 7.3.3 | 落后 2 个大版本 | 要求 Node 20.19+/22.12+；5→7 通常零配置迁移；v8 将改用 Rolldown |
| vue-tsc | ^1.8.0 | 1.8.27 | 3.3.7 | 落后较多 | 项目 TS 固定 5.4.5 也限制了 vue-tsc 升级（新版要求更高 TS）；需同步升 TS |
| typescript | 5.4.5（固定） | 5.4.5 | 5.9+ | 落后 | 与 vue-tsc 升级联动 |
| @vitejs/plugin-vue | ^5.0.0 | 5.2.4 | ~5.x | 与 vite 5 匹配，升 vite 时同步 | — |
| postcss / autoprefixer | ^8.4 / ^10.4 | 8.5.6 / 10.4.23 | 正常 | — | — |

---

## 七、处理建议（按优先级）

1. **修复 `api/scenarios.ts:24` 的 `str` 类型笔误**（阻塞型类型检查错误，`npm run build:check` 直接失败）
2. **删除 3 个死 store action 与 2 个死 API 函数**（`setStreamingError` / `clearStreamingForSession` / `backToList` / `getMessageApi` / `getSessionApi`）
3. **清理 `test_markdown.js`** 与 `[diagnose]` 日志、接入 `CHAT_DEBUG_STREAM` 开关
4. **处理 ScenarioModal 重复实例化**（确认后删除 ChatView.vue:201 或 VariantB.vue:456 其中之一）
5. **依赖升级**：低风险先做（pinia 3 / vue patch）；echarts 6、tailwind 4、vite 7 属 breaking 升级，建议单独排期并验证 UI 回归

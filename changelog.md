# Changelog

## 2026-04-25 17:52:00 +08:00 - AI 生成中增加滚动到底部按钮

### 概述
- 在 AI 流式生成过程中，当用户滚动离开消息底部时，显示一个向下按钮，方便一键回到底部查看最新生成内容。

### 变更内容

#### frontend/src/components/MessageList.vue
- 新增消息滚动位置判断，识别当前是否接近底部。
- 新增仅在 `isStreaming` 且不在底部时显示的浮动向下按钮。
- 复用现有 `scrollToBottom()` 能力，按钮点击后平滑滚动到底部，不改聊天数据流和接口。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:43:23 +08:00 - 增强图表卡片与消息背景区分

### 概述
- 将图表卡片从纯白底调整为浅中性冷灰蓝底，使其在助手回复白色消息气泡中有更明确的区域边界。

### 变更内容

#### frontend/src/components/ChartArtifactCard.vue
- 将图表卡片背景从 `bg-white` 调整为 `#F6F9FC`，边框调整为 `#D8E2EE`。
- 同步调整图表加载态的边框和背景透明度，保持卡片内层状态一致。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:28:18 +08:00 - 加深用户消息气泡背景

### 概述
- 加深用户消息气泡的浅蓝背景，使用户输入与 AI 生成中状态、AI 最终回复形成更清楚的视觉对比。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 将用户消息气泡从 `#EEF6FF` 背景与 `#D9EAFB` 边框调整为 `#DBECFF` 背景与 `#B8D7F3` 边框。
- 保持文字、布局、业务逻辑和消息结构不变。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:25:26 +08:00 - 区分 AI 生成中与最终回复气泡

### 概述
- 将 AI 正在生成、尚未形成最终回复时的助手气泡改为轻微蓝白状态色，避免与最终白底回复混在一起。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 将 `streamingState` 对应的助手气泡从接近白色调整为 `#F3F8FF` 背景与 `#DDEBFA` 边框。
- 保持最终助手回复仍为白底卡片，用户输入气泡仍为上一版浅蓝方案。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:17:38 +08:00 - 前端聊天界面视觉样式克制优化

### 概述
- 基于现有前端配色方向做最小范围视觉优化，降低整体泛蓝感，同时保留品牌蓝用于主按钮、当前状态和关键强调。
- 优化会话选中态、图表卡片、辅助文字、底部输入区和用户消息气泡的视觉层级。

### 变更内容

#### frontend/src/style.css / frontend/tailwind.config.js
- 将全局背景从偏蓝浅色调整为更中性的浅灰蓝，并减弱背景径向蓝色光感。
- 收敛阴影中的品牌蓝占比，提高辅助文字 token 对比度。
- 调整输入框和通用 panel 的边框、背景和阴影，使底部输入区域更轻。

#### frontend/src/views/ChatView.vue
- 减弱侧栏、顶部栏和底部输入栏的白色叠加与边框层级。
- 将部分辅助说明文字从较浅灰色加深为更易读的中性灰。

#### frontend/src/components/SessionItem.vue
- 当前会话选中态从蓝绿渐变改为更克制的白底弱阴影，保留品牌蓝标识当前状态。
- 移除选中状态圆点的发光阴影，提升列表整体安静度。

#### frontend/src/components/MessageItem.vue
- 用户消息气泡调整为 `#EEF6FF` 背景与 `#D9EAFB` 边框，增强与页面背景的区分但保持柔和。
- 将流式助手气泡改为更接近白色的低干扰背景，并加深时间辅助文字。

#### frontend/src/components/ChartArtifactCard.vue
- 图表卡片从 sky 蓝渐变改为白底中性边框，使图表区域更突出、减少蓝色干扰。
- 图表描述、点数和有效期文字改为中性 slate 色，提高普通显示器上的可读性。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 13:22:30 +08:00 - 会话标题自动取首条用户问题

### 概述
- 优化聊天会话标题生成逻辑：新建会话后，当首条用户消息进入该会话时，自动将会话标题更新为这条问题的清洗截断文本，不再长期停留在 `新对话`。
- 保持最小改动：数据库结构不变，前端继续使用现有会话同步链路收敛标题展示。

### 变更内容

#### backend/app/crud.py
- 新增会话占位标题识别逻辑，兼容 `新对话`、`新会话` 和空标题。
- 新增基于首条用户消息生成标题的轻量清洗与截断逻辑：压缩空白、去除多余换行、超长追加省略号。
- 在 `create_message()` 中，当检测到当前消息是该会话首条用户消息且会话标题仍为占位值时，自动回写 `chat_sessions.title`。

#### backend/app/models.py
- 将 `ChatSession.title` 的默认值统一为 `新对话`，与前端创建会话时的默认文案保持一致。

#### backend/app/test_session_title_generation.py
- 新增回归测试，覆盖首条用户消息自动生成标题、后续消息不覆盖标题、兼容旧占位值与多行长消息清洗截断三种场景。

#### 验证
- `conda activate py312_agent; pytest backend/app/test_session_title_generation.py -q`：`3 passed`

## 2026-04-20 00:43 +08:00 - 默认开启流式输出

### 概述
- 将前端聊天界面的流式输出开关默认值调整为开启，进入会话后默认使用流式响应。

### 变更内容

#### frontend/src/composables/useChatStream.ts
- 将 `streamMode` 的初始值从 `false` 调整为 `true`。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:37 +08:00 - 切换开关恢复为原先滑块式样

### 概述
- 将底部流式开关从整块胶囊包裹样式调整回更接近原先的滑块式表现，提升观感并保持紧凑布局。

### 变更内容

#### frontend/src/components/ToggleSwitch.vue
- 移除整块外层胶囊容器，恢复“独立滑块 + 文案”的结构。
- 保留较紧凑的字号与间距，但把滑块尺寸恢复到更自然的视觉比例。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:31 +08:00 - 压缩底部输入区高度以释放更多展示空间

### 概述
- 将聊天底部 composer 调整为更紧凑的布局，减少对消息展示区域的垂直占用。
- 输入框高度缩小约三分之一，同时收紧流式开关、状态标签和发送按钮。

### 变更内容

#### frontend/src/views/ChatView.vue
- 收紧底部区域外边距与内边距。
- 将消息输入框高度从三行压缩到两行，并减小最小高度。
- 缩小发送按钮高度和最小宽度。
- 收紧字数标签与流式状态标签的占位。

#### frontend/src/components/ToggleSwitch.vue
- 缩小开关容器、轨道、滑块与标签字号，匹配新的紧凑底部布局。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:24 +08:00 - 修复前端时间显示与上海时区相差 8 小时

### 概述
- 修复会话列表、消息时间和图表附件时间在前端显示时与上海时区相差 `8 小时` 的问题。
- 根因是前端直接用 `new Date(dateString)` 解析服务端返回的无时区 ISO 时间串，浏览器会把它当作本地时间处理；而这些时间实际表示的是 UTC。

### 变更内容

#### frontend/src/composables/useDateFormat.ts
- 新增统一的 `parseServerDate()` 解析函数。
- 对“无时区后缀的 ISO 时间串”按 UTC 处理，再转换为本地时间显示。

#### frontend/src/components/SessionItem.vue / MessageItem.vue / ChartArtifactCard.vue
- 统一改为使用 `parseServerDate()` 解析服务端时间。
- 修复相对时间、消息气泡时间和图表卡片到期时间的 8 小时偏差。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:15 +08:00 - 调整用户消息与过程输出气泡配色

### 概述
- 将用户消息气泡从深蓝强对比样式调整为更柔和的浅蓝纯色卡片，降低突兀感。
- 将过程输出气泡从淡渐变背景调整为淡色纯色背景，与最终答案白底卡片形成更稳定的层级区分。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 用户消息改为浅蓝纯色背景 + 深色文字。
- 流式过程输出改为浅色纯色背景，不再使用渐变。
- 同步调整用户消息时间文字颜色，匹配新的柔和气泡风格。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:08 +08:00 - 修复新建对话后输入区被挤出视口

### 概述
- 修复聊天界面升级后，在“新建对话且暂无消息”场景下，底部输入区未显示的问题。
- 根因是根容器使用 `min-height` 而子布局依赖 `h-full`，导致主内容区高度约束不稳定，消息区会把 composer 挤出当前视口。

### 变更内容

#### frontend/src/App.vue / frontend/src/style.css
- 将根容器高度链路从 `min-height` 收紧为稳定的 `100dvh` 高度。
- 保留 `min-height` 作为兜底，同时显式设置 `#app` 的 `height: 100dvh`，确保聊天主布局、空状态和输入区都能正确占满视口。

#### 验证
- `npm run build:check`：通过

## 2026-04-19 23:55 +08:00 - 前端聊天界面升级为明亮卡片式响应式工作台

### 概述
- 将 `frontend` 聊天界面升级为更现代、简洁明快、友好的 `方案 A` 风格，保持现有功能与逻辑不变。
- 桌面端继续采用双栏布局，移动端新增会话抽屉，提升小屏场景下的可用性。
- 一并修复一个阻塞前端类型检查的现有类型断言问题，保证界面改造后可继续进行构建验证。

### 变更内容

#### frontend/src/views/ChatView.vue
- 重组主界面布局，强化顶部栏、消息区与输入区层级。
- 新增移动端会话抽屉和遮罩交互。
- 优化上下文预警条与底部输入 composer 的视觉表现。

#### frontend/src/style.css / frontend/tailwind.config.js / frontend/src/App.vue
- 将主题调整为浅冷白 + 蓝青点缀的明亮卡片式工作台风格。
- 统一按钮、输入框、卡片、阴影与 Markdown 展示样式。
- 优化全局背景、滚动条、动效与 reduced-motion 基础支持。

#### frontend/src/components/SessionList.vue / SessionItem.vue
- 将会话区改为更轻的导航面板样式。
- 优化会话项选中态、信息层级与移动端可点击体验。
- 新增选中会话后关闭移动端抽屉的联动。

#### frontend/src/components/MessageList.vue / MessageItem.vue / EmptyState.vue / ToggleSwitch.vue
- 调整消息阅读宽度、空状态、用户与 AI 气泡样式。
- 统一流式中、错误、中断、工具结果和导出卡片的视觉体系。
- 细化流式开关组件样式，与新主题保持一致。

#### frontend/src/composables/useChatStream.ts
- 将 `context_warning` 的流式事件详情断言改为更安全的 `unknown` 中转，修复 `vue-tsc` 阻塞问题。

#### 验证
- `npx vue-tsc --noEmit`：通过
- `npm run build:check`：受当前环境 `esbuild spawn EPERM` 限制，未能在沙箱内完成 Vite 构建

## 2026-04-19 18:45 +08:00 - 恢复 context_warning 为正式 CustomState

### 概述
- 在升级 `langchain/langgraph` 后，恢复 `context_warning` 作为正式 `CustomState` 字段。
- `ContextWarningMiddleware` 改为通过 `ExtendedModelResponse + Command(update=...)` 写回 graph state，不再依赖临时 `request.state`。
- 恢复非流式 `ChatResponse.context_warning` 与流式 `final.context_warning` 透传，同时保留 custom `status` 告警事件。

### 变更内容

#### backend/app/agent/state.py
- 恢复 `context_warning` 字段。
- 为 `context_warning` 增加 `last wins` reducer，支持 payload 与 `None` 的动态覆盖。

#### backend/app/agent/middleware/context_warning_middleware.py
- 引入 `ExtendedModelResponse` 与 `Command(update=...)`。
- `wrap_model_call()` / `awrap_model_call()` 现在会把 `context_warning` 正式写回 agent state。
- 继续保留 token 估算、结构化日志和 `emit_stream_status(...)` 提醒。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 恢复非流式 `process_message()` / `ChatResponse` 的 `context_warning` 透传。
- 恢复流式 `updates` 读取与 `final.context_warning` 输出。
- 修复 custom status 与 updates state 双通道下的重复 warning 问题。

#### frontend/src/types/index.ts / frontend/src/composables/useChatStream.ts
- 恢复非流式 `response.context_warning` 的前端消费。
- 保持流式 `status.detail` 预警消费不变。

#### 测试与验证
- 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_services.py`
- 更新 `backend/app/test_chart_api.py`
- `pytest`：21 passed
- `npm run build`：通过

## 2026-04-19 18:20 +08:00 - 清理 context_warning 伪状态链路

### 概述
- 移除 `context_warning` 作为 `CustomState` 的字段定义，避免把仅用于流式提醒的临时数据误当成正式 graph state。
- 收口后端与前端中依赖 `context_warning` state 透传的冗余逻辑，统一保留当前已工作的 custom `status` 事件提醒路径。

### 变更内容

#### backend/app/agent/state.py
- 删除 `context_warning` 字段与对应说明。

#### backend/app/agent/middleware/context_warning_middleware.py
- 不再向 `request.state` 写入 `context_warning`。
- 保留 token 估算、观测日志和 `emit_stream_status(...)` 预警事件。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 删除依赖 `context_warning` 作为正式 state / 非流式响应字段的冗余透传逻辑。
- 流式链路继续通过 `status` 事件向前端发送预警。

#### frontend/src/composables/useChatStream.ts / frontend/src/types/index.ts
- 移除非流式 `ChatResponse.context_warning` 的消费与类型定义。
- 保留流式 `status.detail` 告警消费逻辑。

#### 测试
- 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_chart_api.py`

## 2026-04-19 17:49 +08:00 - 优化 llama.cpp 上下文预警透传与观测日志

### 概述
- 修复上下文预警在 LangChain 当前中间件实现下“估算已执行但前端收不到提示”的问题。
- 新增固定格式观测日志，直接打印预警开关、阈值、当前估算值和是否触发，便于本地调试。

### 变更内容

#### backend/app/agent/middleware/context_warning_middleware.py
- 保持基于最终 `ModelRequest` 做 token 估算。
- 触发预警时，直接通过 custom stream 发出 `status` 事件，而不再只依赖 `request.state` 透传。
- 新增 `context warning check: ...` 结构化日志，打印 `enabled`、`estimated_input_tokens`、`warn_tokens`、`context_window`、`safety_buffer`、`triggered`、`message_count`、`tool_count`。

#### backend/app/test_context_warning_middleware.py
- 新增触发告警时 custom stream 事件与日志输出的测试。
- 调整未触发和关闭开关场景下的状态断言。

#### backend/app/test_services.py
- 新增流式链路透传 `context_warning` custom status 事件的回归测试。

## 2026-04-19 16:56 +08:00 - 修复流式上下文告警未命中时的作用域错误

### 概述
- 修复流式 SSE 链路在 `context_warning` 未出现时，最终 `final` 事件构造阶段抛出 `UnboundLocalError` 的问题。
- 补充回归测试，确保普通流式回答即使没有任何上下文告警，也能正常落定为 `final` 事件。

### 变更内容

#### backend/app/services.py
- 为 `process_stream()` 内部 `_produce_events()` 补充 `nonlocal context_warning`，保持闭包读写同一外层变量。

#### backend/app/test_services.py
- 新增 `test_process_stream_emits_final_event_without_context_warning`，覆盖“无 warning 的正常流式完成”场景。

#### backend/app/test_llama_cpp_token_estimator.py
- 调整配置测试的环境隔离方式，显式设置预期环境变量并重新加载配置模块，避免受当前进程环境污染。

## 2026-04-19 16:10 +08:00 - 完成 llama.cpp 上下文预警端到端接入

### 概述
- 完成面向 OpenAI-compatible `llama.cpp` 的调用前上下文预警能力。在单次模型调用接近安全阈值时，后端会基于 `/tokenize` 估算输入上下文并透传统一 `context_warning` payload，前端展示轻量提醒条，提示用户建议新建对话。
- 整套逻辑受 `LLM_CONTEXT_WARNING_ENABLED` 开关控制，关闭时不会影响其他模型接入，也不会触发自动压缩、自动摘要或请求阻断。

### 变更内容

#### backend/app/config.py
- 新增 `LLM_CONTEXT_WARNING_ENABLED`、`LLM_CONTEXT_WINDOW`、`LLM_CONTEXT_WARN_TOKENS`、`LLM_CONTEXT_SAFETY_BUFFER`、`LLAMA_CPP_TOKENIZE_BASE_URL`、`LLM_CONTEXT_TOKENIZER_TIMEOUT` 配置项。

#### backend/app/agent/utils/llama_cpp_token_estimator.py
- 新增 `LlamaCppTokenEstimator`，优先调用 `llama.cpp /tokenize` 统计文本和 JSON-like 输入 token，接口异常时回退到保守估算。

#### backend/app/agent/middleware/context_warning_middleware.py
- 新增 `ContextWarningMiddleware`，在最终 `ModelRequest` 上估算 `system_message`、`messages`、`tools` 的输入 token。
- 预警 payload 纳入 `safety_buffer`，并写入 `state["context_warning"]`。

#### backend/app/agent/service.py
- 在 Agent 初始化链路中注册 `ContextWarningMiddleware`，保持其位于 `SkillMiddleware` 之后，确保基于最终请求内容预警。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 非流式 `ChatResponse` 新增 `context_warning` 字段。
- 流式链路在 `status.detail` 中透传 `context_warning`，并复用现有 `status` 事件协议，不新增 SSE 事件类型。

#### frontend/src/types/index.ts
- 新增 `ContextWarningPayload` 类型，并扩展 `ChatResponse`。

#### frontend/src/composables/useChatStream.ts
- 新增 `contextWarning` 状态。
- 流式模式消费 `source === "context_warning"` 的 `status` 事件；非流式模式消费 `ChatResponse.context_warning`。
- 切换会话和新一轮发送前自动清空旧 warning。

#### frontend/src/views/ChatView.vue
- 在聊天区域新增轻量预警条，展示估算输入 token、预警线与模型上下文窗口。

#### 测试与验证
- 新增 / 更新 `backend/app/test_llama_cpp_token_estimator.py`
- 新增 / 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- 更新 `backend/app/test_chart_api.py`
- 后端相关测试 `17 passed`
- 前端 `npm run build` 通过
- 说明：Vite 构建仍有现存的大 bundle warning，但不影响本次功能上线


## 2026-04-19 15:18 - 新增 ContextWarningMiddleware 上下文告警透传

### 概述
- 新增 `ContextWarningMiddleware`，在最终 `ModelRequest` 上估算 `system_message`、`messages`、`tools` 的输入 token，并在达到阈值时把统一 warning payload 写入 `state`，供后续 API / 前端链路透传。

### 变更内容

#### backend/app/agent/middleware/context_warning_middleware.py
- 新增 `ContextWarningMiddleware(AgentMiddleware[CustomState])`。
- 支持 `enabled`、`context_window`、`warn_tokens`、`output_reserve`、`safety_buffer` 参数。
- 当 token 估算达到阈值时，生成统一 `context_warning` payload 并写入 `request.state`。
- 保持只读行为，不裁剪请求、不阻断请求、不触发摘要。

#### backend/app/agent/state.py
- 为 `CustomState` 增加 `context_warning` 字段，作为 warning 透传载体。

#### backend/app/agent/middleware/__init__.py
- 导出 `ContextWarningMiddleware`，便于统一引用。

## 2026-04-19 09:45 - 为 development-guide-synthesizer 技能补充长文档目录要求

### 概述
- 将“中长篇开发指南默认增加目录”正式纳入 `development-guide-synthesizer` 技能要求，提升长篇开发文档的导航与复用体验。

### 变更内容

#### .agents/skills/development-guide-synthesizer/SKILL.md
- 在技能说明、输出结构和推荐风格中明确：中长篇开发指南默认增加目录，除非用户明确要求不加。

#### .agents/skills/development-guide-synthesizer/references/guide-template.md
- 在模板中新增“目录”章节说明与示例，统一目录放置位置和适用边界。

## 2026-04-18 14:40 - 修复结构化图表工具调用缺少 ToolRuntime 时单车型作图失败

### 概述
- 修复 `build_chart_artifact` 在 LangChain 结构化调用路径下未注入 `ToolRuntime` 时直接抛错的问题，恢复单车型图表生成。

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py
- 将 `build_chart_artifact` 的 `runtime` 参数改为可选，兼容 `tool.invoke(...)` 与实际 Agent 结构化调用路径。
- 当未注入 `ToolRuntime` 时跳过 `skills_loaded` 状态校验，并记录调试日志；其余 SQL 安全限制、序列 schema 校验和数值列校验保持不变。

## 2026-04-18 15:20 - 修复 ToolNode 注入 runtime 后被图表 args_schema 拦截的问题

### 概述
- 修复 `build_chart_artifact` 在真实 LangGraph `ToolNode` 执行链中被自动注入 `runtime` 后，因 `args_schema` 顶层 `extra=\"forbid\"` 提前校验失败的问题。该问题会导致图表工具在进入函数体之前就报 `Error invoking tool ...`，尤其体现在单车型趋势图这类最常见场景。

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py
- 将 `BuildChartArtifactInput` 顶层额外字段策略调整为“只允许注入的 `runtime`，继续拒绝其他未知字段”。
- 保持 `series` 结构化 schema、数值列校验和多分类拆线校验不变。

#### backend/app/test_chart_artifact_tool.py
- 新增覆盖 `ToolNode` 注入 `runtime` 语义的回归测试。
- 新增顶层未知字段仍会被拒绝的校验测试，避免为了兼容 runtime 注入而放松整体参数约束。

## 2026-04-18 13:20 - 强化图表工具入参 schema 与错误参数拦截
### 概述
围绕 `build_chart_artifact` 在多系列图表场景下容易被 LLM 填错参数的问题，进一步把 `series` 入参从宽松的 `list[dict[str, Any]]` 收紧为明确的结构化 schema，并在工具内部新增数值列校验、未知键拦截和分类拆线配对校验。这样即使模型继续传入 `metric`、`label`、`type` 等未支持字段，或把 `field` 错填成分类列，也会被明确拒绝，而不会再悄悄生成错误图表。
### 变更内容
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/test_chart_artifact_tool.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- `build_chart_artifact` 现在使用明确的 `BuildChartArtifactInput / ChartSeriesInput` schema
- 强制 `series.field` 必须是数值列
- 拒绝 `metric`、`label`、`type`、`axis` 等未支持键
- 强制 `category_field/category_value` 成对出现，并继续支持从系列名称自动推断分类值

## 2026-04-18 13:04 - 收紧多系列对比图的 LLM 参数生成约束
### 概述
在补齐前后端“按分类拆线”能力后，继续收紧主 Agent 的系统提示词与图表工具说明，避免模型在多车型/多类别对比图里继续只重复同一个数值字段，遗漏分类拆线元数据。现在当同一指标需要按车型、缺陷类型等分类拆成多条系列时，模型会被明确要求提供 `category_field/category_value`，或至少在系列名称中包含可识别的分类值，便于工具自动推断。
### 变更内容
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- 明确禁止仅通过重复 `field` 生成多条对比系列
- 明确要求多分类对比图补充 `category_field/category_value` 或可识别分类值

## 2026-04-18 13:05 - 修复同一指标按多分类拆线时图表系列重合的问题
### 概述
首版图表能力原本只稳定支持“多个不同数值字段并列展示”，还不真正支持“同一个数值字段按车型/类别拆成多条线”。因此像 `A7` 与 `TiguanL` 这种对比图里，如果多个系列都引用同一个数值列，前端会直接复用同一组数据，导致系列重合。此次修复后，图表工具会为系列补齐分类拆线元数据，前端也会按分类字段和值真正拆分数据。
### 变更内容
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/schemas.py`
- 更新 `frontend/src/types/index.ts`
- 更新 `frontend/src/components/ChartArtifactCard.vue`
- 更新 `backend/app/test_chart_artifact_tool.py`
- 支持图表系列携带 `category_field`、`category_value` 与可选 `color`
- 当同一数值字段被拆成多个系列时，后端可从系列名中自动推断分类值
- 前端按 `category_field/category_value` 过滤行数据，避免多系列直接叠成同一条线

## 2026-04-18 12:42 - 优化 LLM 对图表能力的主动引导文案
### 概述
针对查询结果已经明显适合可视化、但助手仍然只用“是否需要进一步分析”收尾的问题，收紧主 Agent 的系统提示词约束。现在当结果属于时间趋势、分类对比、Top N 排名或双指标对比时，模型在用户尚未明确要求作图的情况下，也必须明确提醒“可以生成图表”，并给出可直接触发的示例话术。
### 变更内容
- 更新 `backend/app/agent/service.py`
- 新增 `backend/app/test_agent_service_prompt.py`
- 明确要求助手在合适场景下引导用户回复“生成图表”“生成趋势图”或“生成柱状图”
- 禁止仅使用“是否需要进一步分析”这类泛化收尾替代图表提醒

## 2026-04-18 11:55 - 修复聊天图表卡片已取到数据但未实际渲染的问题
### 概述
首版聊天图表能力接入后，前端已经能正确拿到 `chart_artifact` 并展示标题、说明与点数，但图表区域为空白。根因是 `ChartArtifactCard` 在 `loading=true` 时就调用了 `renderChart()`，此时真正的图表容器仍被 `v-if/v-else` 隐藏，ECharts 没有可初始化的 DOM 节点，因此不会报错但也不会出图。
### 变更内容
- 更新 `frontend/src/components/ChartArtifactCard.vue`
- 将图表实例创建与 `setOption` 延后到 `loading` 结束之后
- 在重新加载 artifact 时先销毁旧实例，避免复用旧容器状态
- 补充 `resize()`，保证容器切换后尺寸同步

## 2026-04-18 15:35 - 新增聊天内嵌图表 artifact 能力
### 概述
为聊天式 SQL Agent 增加“用户明确要求后再生成图表”的首版能力。此次实现采用 chart artifact 引用机制：LLM 只负责判断是否需要作图和图表基本元数据，后端工具重新执行聚合 SQL、存储完整图表配置，并只向模型返回轻量 `chart_artifact_ref`，避免大结果再次进入上下文。前端收到 `chart_id` 后再拉取完整 `chart_spec`，在消息卡片内渲染折线图或柱状图。
### 变更内容
- 新增 `backend/app/chart_artifacts.py`
- 新增 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/config.py`
- 更新 `backend/app/schemas.py`
- 更新 `backend/app/api.py`
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/agent/tools/__init__.py`
- 新增 `backend/app/test_chart_artifacts.py`
- 新增 `backend/app/test_chart_artifact_tool.py`
- 新增 `backend/app/test_chart_api.py`
- 新增 `frontend/src/api/charts.ts`
- 新增 `frontend/src/components/ChartArtifactCard.vue`
- 更新 `frontend/src/components/MessageItem.vue`
- 更新 `frontend/src/types/index.ts`
- 新增聊天图表环境变量：`CHART_ARTIFACT_DIR`、`CHART_ARTIFACT_TTL_HOURS`、`CHART_ARTIFACT_MAX_POINTS`
- 前端引入 `echarts`，并将 `typescript` 固定在与当前 `vue-tsc` 校验兼容的 `5.4.5` 版本区间

## 2026-04-18 09:37 - 调整车型缺陷趋势场景为检测次数与平均缺陷数口径
### 概述
根据当前业务使用口径，将 `model_defect_trend` 场景的输出从“检测次数 + 缺陷总数”调整为“检测次数 + 每次检测平均缺陷数”，避免趋势解读时被样本量放大影响。
### 变更内容
- 更新 `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/model_defect_trend/scenario.py`
- 更新 `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/model_defect_trend/sql/main.sql`
- 更新 `backend/app/test_skill_registry.py`
- 将 SQL 聚合字段由 `SUM(mq.total_defect_count)` 调整为 `AVG(mq.total_defect_count)`
- 将输出契约调整为 `detection_count` 与 `avg_defect_per_detection`

## 2026-04-16 10:31 - 优化 Windows 本地后端启动入口，修复 AsyncPostgresSaver 事件循环兼容问题
### 概述
针对 Windows 本地开发场景下 `AsyncPostgresSaver` 与 `psycopg` 异步连接池依赖 `SelectorEventLoop` 的限制，新增一个独立的 Python 启动入口，在 Uvicorn 创建事件循环前显式设置 `WindowsSelectorEventLoopPolicy`。这样可以保持现有异步 Agent 链路不回退，同时避免继续直接使用 `uvicorn backend.app.main:app` 时落回 `ProactorEventLoop` 导致启动超时。

补充说明：首次落地后进一步确认，Windows 下 `uvicorn --reload` 的 `WatchFiles` 会通过 `spawn` 方式启动子进程，子进程不会继承父进程中预设的事件循环策略。因此本地 Windows 启动入口继续调整为“默认关闭 reload”，确保 async checkpointer 稳定启动。

后续进一步定位发现，`uvicorn 0.40` 在 Windows 下默认会显式选择 `ProactorEventLoop` 作为运行 loop，而不是单纯跟随当前事件循环策略。这意味着仅在入口脚本里设置 `WindowsSelectorEventLoopPolicy` 仍然不够，必须额外为 Uvicorn 显式注入自定义 `loop factory`，强制切换到 `SelectorEventLoop`，才能真正兼容 `psycopg` 异步连接池。

补充清理：在确认最终有效修复后，进一步移除了首轮尝试留下的重复配置，仅在 Windows 下向 Uvicorn 注入自定义 `loop`，并删除批处理脚本中重复的 `UVICORN_RELOAD=false` 设置，保持启动入口更接近最小改动原则。
### 变更内容
- **新增本地启动入口**:
  - 新增 `run_backend.py`
  - 在 Windows 下启动前显式设置 `WindowsSelectorEventLoopPolicy`
  - 继续复用 `backend.app.main:app`
  - 显式为 Uvicorn 注入自定义 `loop factory`
- **新增便捷启动脚本**:
  - 新增 `start_backend.bat`
  - 自动切换到 `py312_agent` 环境并调用 `python run_backend.py`
  - Windows 下默认设置 `UVICORN_RELOAD=false`
- **异步连接池修复**:
  - 更新 `backend/app/agent/service.py`
  - 为本地 `AsyncConnectionPool` 补充 `connect_timeout=5`
  - 修复 Windows 下连接池 worker 长时间挂起后触发 `pool initialization incomplete after 30 sec`
- **文档更新**:
  - 更新 `README.md`
  - 将 Windows 本地开发推荐启动方式调整为 `python run_backend.py`
  - 明确 Windows 本地默认关闭 reload
  - 明确 Docker / Linux 部署无需同步修改启动命令

## 2026-04-12 03:15 - 新增 Agent SQL 上下文与结果返回机制说明文档
### 概述
围绕 `analytics_db` 接入后关于 `schema`、`search_path`、物化视图支持、元数据抓取、`sql_db_schema` 移除影响，以及“查询结果是否应默认带列名”的连续讨论，新增一份统一机制说明文档，帮助后续维护者快速理解哪些能力已经真正作用到 LLM，哪些仍属于底层准备能力。
### 变更内容
- **新增机制说明文档**:
  - 新增 `docs/backend/database_refactor/agent_sql_context_mechanism.md`
  - 统一解释 `schema` 与 `search_path` 的关系
  - 统一解释物化视图如何纳入 `SQLDatabase`
  - 统一解释元数据抓取在当前实现中的真实作用边界
  - 统一解释为何将 `sql_db_query` 升级为默认带列名结果

## 2026-04-12 03:00 - 优化 SQL 查询结果为带列名结构，降低 LLM 对 SELECT * 的误判风险
### 概述
将包装后的 `sql_db_query` 返回格式从“默认元组列表字符串”升级为“默认带列名的字典列表字符串”，让模型在读取结果时能直接看到列名与字段值的对应关系，降低 `SELECT *`、宽表查询和多列表结果下的理解偏差。同时保持结果限流与预览机制兼容新旧两种格式。
### 变更内容
- **查询工具增强**:
  - 更新 `backend/app/agent/tools/sql_tools.py`
  - 更新 `backend/app/agent/tools/sql_tools_local.py`
  - 查询执行优先调用底层 `db.run_no_throw(query, include_columns=True)`
  - 结果默认包含列名
- **限流兼容增强**:
  - 行数估算逻辑同时兼容元组列表与字典列表
  - 预览截断逻辑同时兼容元组列表与字典列表

## 2026-04-12 02:20 - 新增 Agent 接分析库后未实施阶段待办清单
### 概述
围绕“Agent 已接入 `analytics_db`、tracking 与 defect 两个领域已初步落地”后的下一步规划，新增一份独立的未实施阶段清单文档，用于统一记录后续还未落地的阶段、优先级、进入条件和完成标准，避免后续计划继续散落在聊天记录里。
### 变更内容
- **新增待办文档**:
  - 新增 `docs/backend/database_refactor/unimplemented_phases_todolist.md`
  - 按“阶段目标 / 主要任务 / 完成标准 / 是否建议立即做”整理未实施阶段
- **规划范围明确**:
  - 覆盖跨域质量关联领域
  - 覆盖高频主题 `mart`
  - 覆盖现有技能与场景继续优化
  - 覆盖端到端验证与灰度
  - 覆盖后续可选增强项

## 2026-04-12 02:05 - 修复 CSV 导出工具未继承 analytics_db search_path 的问题
### 概述
补齐 `export_to_csv` 与 `analytics_db` 的连接一致性。此前 Agent 已经能在查询阶段通过 `search_path` 正常访问 `mart/fct/dim/ods` 对象，但 CSV 导出工具内部自行创建数据库连接时没有继承该配置，导致无 schema 前缀的查询在导出时可能报 `relation does not exist`。本次修复后，导出工具会与主查询链路共享相同的 `engine_args`。
### 变更内容
- **导出工具修复**:
  - 更新 `backend/app/agent/tools/csv_export_tool.py`
  - 为 `create_csv_export_tool()` 增加 `engine_args` 参数
  - 导出工具内部创建 SQLAlchemy 引擎时继承 `search_path`
- **服务注入修复**:
  - 更新 `backend/app/agent/service.py`
  - 注入 `export_to_csv` 时同步传入业务库对应的 `engine_args`
  - 使查询与导出在 `analytics_db` 下使用一致的 schema 可见性

## 2026-04-12 00:10 - SQL Agent 第一阶段接入 Analytics DB
### 概述
启动“Agent 接分析库”第一阶段改造，新增 `ANALYTICS_DATABASE_URL` 配置，并把 SQL Agent 的业务库入口切换为“优先 `analytics_db`、回退 `rollerbed_tracking_db`”模式。同时补齐 PostgreSQL `search_path` 和物化视图兼容，避免 Agent 接入分析库后看不到核心 `mart` / `fct` 对象。
### 变更内容
- **配置增强**:
  - 更新 `backend/app/config.py`
  - 新增 `analytics_database_url`
  - 新增 `analytics_db_search_path`
  - 兼容 `DEBUG=release/prod` 等环境标记，避免 Settings 初始化失败
  - 更新 `.env`
  - 新增 `ANALYTICS_DATABASE_URL`
  - 新增 `ANALYTICS_DB_SEARCH_PATH`
- **SQLDatabase 能力增强**:
  - 新增 `backend/app/agent/utils/sql_database.py`
  - 增加 `MaterializedViewSQLDatabase`，支持将 PostgreSQL 物化视图纳入可用对象集合
  - 增加 `build_postgres_search_path_engine_args()`，用于将 `mart,fct,dim,ods,meta` 注入连接 `search_path`
- **元数据抓取增强**:
  - 更新 `backend/app/agent/utils/db_utils.py`
  - 支持传入 `engine_args`
  - 支持把普通视图和物化视图一并纳入表结构抓取
- **Agent 业务库入口切换**:
  - 更新 `backend/app/agent/service.py`
  - 更新 `backend/app/agent/service_llama.cpp.py`
  - 业务 SQL 连接改为优先使用 `ANALYTICS_DATABASE_URL`
  - 若未配置则回退到 `ROLLERBED_DATABASE_URL`
  - CSV 导出工具同步复用新的业务库入口

## 2026-04-12 00:25 - 更新车辆追踪领域文档为分析库查询视角
### 概述
进入“Agent 接分析库”第二阶段，先对 `paint_shop_vehicle_tracking` 的领域文档做最小改动升级：保留源表说明，同时补充 `analytics_db` 下的推荐查询入口、正式产品车/异常车/当前现场总览口径，以及当前缺陷关联分析的易错点，让 Agent 加载领域技能后能直接理解应该优先查询哪些 `mart` / `fct`。
### 变更内容
- **领域文档增强**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 新增 `analytics_db` 分析库查询入口说明
  - 新增 `mart_position_current_overview`、`mart_abnormal_vehicle_current`、`mart_vehicle_quality_360` 等推荐对象
  - 明确 `fct_vehicle_position_current` 只表示正式产品车当前事实
  - 补充“异常车不适合只按 `vehicle_id` 建模”“当前缺陷关联不是检测时位置”等易错点

## 2026-04-12 00:40 - 优化车辆追踪固定场景到分析库口径
### 概述
继续“Agent 接分析库”第二阶段，对 `paint_shop_vehicle_tracking` 下现有固定场景做最小改造：让 `daily_area_body_count` 与 `realtime_area_body_count` 优先面向 `mart_position_current_overview`，不再默认从 `rb_position_data` 直接统计，并同步收敛场景口径为“当前快照下正式产品车数量”。
### 变更内容
- **场景元数据更新**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/daily_area_body_count/scenario.py`
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count/scenario.py`
  - 补充分析库对象说明
  - 明确仅统计正式产品车
  - 将区域维度参数来源切到 `dim_process_area`
- **SQL 模板更新**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/daily_area_body_count/sql/main.sql`
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count/sql/main.sql`
  - 查询入口由 `rb_position_data` 切换为 `mart_position_current_overview`

## 2026-04-12 01:10 - 新增质量缺陷分析领域与第一批固定场景
### 概述
进入“Agent 接分析库”第三阶段，新增独立的 `paint_shop_defect_analysis` 业务领域，把质量缺陷能力从车辆追踪领域中拆出来。第一批基于 `mart_vehicle_quality_360` 落地 5 个固定场景，用于承接每日缺陷汇总、车型趋势、部位分布、tunnel/cycle 对比和黑车顶对比等高频问题。
### 变更内容
- **新增领域骨架**:
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/__init__.py`
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/meta.py`
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/domain.md`
- **新增第一批质量场景**:
  - 新增 `daily_defect_summary`
  - 新增 `model_defect_trend`
  - 新增 `defect_station_distribution`
  - 新增 `tunnel_cycle_defect_comparison`
  - 新增 `black_roof_defect_comparison`
  - 每个场景均补充 `scenario.py` 与 `sql/main.sql`
- **测试补充**:
  - 更新 `backend/app/test_skill_registry.py`
  - 补充新领域与新场景的自动发现、内容加载与兼容性断言

## 2026-04-12 00:35 - 调整车辆追踪领域文档顺序以适配 Agent 阅读
### 概述
继续第二阶段文档优化，将 `paint_shop_vehicle_tracking/domain.md` 重排为“先推荐查询入口，再业务逻辑与易错点，最后源表背景”的顺序，让 Agent 在加载领域技能后更容易优先命中 `mart/fct`，同时把 `ods` 和源表说明保留为背景知识与兜底参考。
### 变更内容
- **文档结构重排**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 将“推荐查询入口”提升到前部
  - 将“业务逻辑”和“当前易错点”前置
  - 将原“数据表”章节调整为“源表与底层数据表”

## 2026-04-12 00:45 - 补充车辆追踪领域中核心 mart/fct 的关键字段说明
### 概述
继续增强 `paint_shop_vehicle_tracking/domain.md`，在“推荐查询入口”下为核心分析对象补充轻量但高频的关键字段说明，让 Agent 在优先查询 `mart/fct` 时，不只知道应该查哪个对象，也能更快理解对象粒度和常用字段语义。
### 变更内容
- **分析对象字段说明补充**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 为 `mart_position_current_overview` 补充当前总览关键字段
  - 为 `fct_vehicle_position_current` 补充正式产品车当前事实关键字段
  - 为 `fct_position_current_all` 补充当前全部有效占位关键字段
  - 为 `mart_abnormal_vehicle_current` 补充异常车关键字段
  - 为 `mart_vehicle_quality_360` 补充缺陷关联分析关键字段
## 2026-04-11 21:20 - 新增 Analytics DB 后续待办清单与 mart 复用判断说明
### 概述
为方便后续在 `analytics_db` 基础上继续选择扩展方向，新增一份面向维护者的待办清单文档，集中整理当前已完成内容、建议下一步、可选增强项，以及“当前是否可以只依赖 `mart_vehicle_quality_360` 让 LLM 自主生成 SQL”的判断依据。
### 变更内容
- **新增待办文档**:
  - 新增 `docs/backend/database_refactor/analytics_db_todolist.md`
  - 按“已完成 / 建议下一步 / 可选增强”整理数据库后续建设路径
- **设计判断沉淀**:
  - 补充当前直接复用 `mart_vehicle_quality_360` 的适用范围
  - 补充何时需要新增 `mart_defect_daily_by_model`、`mart_defect_station_distribution` 的判断标准

## 2026-04-11 20:15 - 落地当前车辆事实分层第一阶段并同步数据库重构文档
### 概述
围绕 `analytics_db` 中“正式产品车 / 异常车 / 全量占位”混用的问题，正式落地当前车辆事实分层优化第一阶段：新增全量当前占位事实、异常车事实、异常车主题 `mart` 与当前现场总览 `mart`，同时将原有产品车当前位置事实明确收口到正式产品车，并把 `database_refactor` 文档同步到数据库真实状态。
### 变更内容
- **数据库对象新增与调整**:
  - 在 `analytics_db` 中新增 `fct.fct_position_current_all`
  - 在 `analytics_db` 中新增 `fct.fct_abnormal_vehicle_current`
  - 在 `analytics_db` 中新增 `mart.mart_abnormal_vehicle_current`
  - 在 `analytics_db` 中新增 `mart.mart_position_current_overview`
  - 重建 `fct.fct_vehicle_position_current`，明确其仅服务正式产品车
  - 重建 `mart.mart_vehicle_quality_360`，使其继续面向产品车质量分析主链路
- **维度层增强**:
  - 为 `dim.dim_vehicle_profile` 增加 `current_position_id`、`current_carrier_id`、`current_carrier_type`、`current_process_area`、`current_full_rb_code`、`current_position_updated_at`
  - 让车辆画像维度可保留正式产品车的当前绑定快照
- **刷新流程升级**:
  - 更新 `meta.refresh_analytics_all()`
  - 将新 `fct` / `mart` 对象纳入一键刷新流程
  - 刷新后自动补齐 `agent_ro` 对新增对象的 `SELECT` 权限
- **验证结果**:
  - 刷新后 `fct.fct_position_current_all = 114`
  - 刷新后 `fct.fct_vehicle_position_current = 102`
  - 刷新后 `fct.fct_abnormal_vehicle_current = 12`
  - 刷新后 `mart.mart_abnormal_vehicle_current = 12`
  - 刷新后 `mart.mart_position_current_overview = 114`
  - 异常车分类样例为 `empty_vehicle_id_with_carrier = 8`、`non_product_prefix = 4`
- **文档同步**:
  - 更新 `docs/backend/database_refactor/analytics_db_architecture.md`
  - 更新 `docs/backend/database_refactor/why_analytics_db.md`
  - 更新 `docs/backend/database_refactor/current_vehicle_fact_refactor.md`

## 2026-04-11 18:55 - 补充当前车辆事实分层重构方案文档
### 概述
围绕 `analytics_db` 当前车辆事实层在异常车、重复调试 `vehicle_id` 和 `carrier_id` 反查场景下的限制，补充一份面向后续数据库重构的专题方案文档，并同步修正现有 `database_refactor` 文档中的限制说明与演进建议，帮助后续将“正式产品车 / 异常车 / 全量占位”分层建模。
### 变更内容
- **新增专题方案文档**:
  - 新增 `docs/backend/database_refactor/current_vehicle_fact_refactor.md`
  - 说明当前 `fct_vehicle_position_current` 的局限，以及 `fct_position_current_all`、`fct_abnormal_vehicle_current`、异常车主题 `mart` 的设计方向
- **现有文档补充**:
  - 更新 `docs/backend/database_refactor/analytics_db_architecture.md`
  - 增加当前 `fct_vehicle_position_current` 对异常车与重复调试车场景的限制说明
  - 更新 `docs/backend/database_refactor/why_analytics_db.md`
  - 增加当前产品车事实与异常车事实不应长期混用的设计依据与后续演进建议

## 2026-04-11 18:36 - 新增 Analytics DB 设计动机说明文档
### 概述
在已经补齐 `analytics_db` 落地与刷新操作手册的基础上，再新增一份面向后续复用的设计说明文档，专门回答“为什么要设计 `analytics_db`、为什么不是直接查源库、为什么要分层以及当前取舍是什么”，用于统一数据库重构和 Agent 接库改造的设计认知。
### 变更内容
- **新增设计说明文档**:
  - 新增 `docs/backend/database_refactor/why_analytics_db.md`
  - 从背景、问题、分层、设计决策、已验证事实、踩坑与复用清单几个维度解释 `analytics_db` 的必要性
- **与现有手册互补**:
  - 与 `docs/backend/database_refactor/analytics_db_architecture.md` 形成“为什么这样设计”与“如何落地执行”的双文档结构

## 2026-04-11 17:20 - 修正 Analytics DB 落地与刷新操作手册为最新已验证版
### 概述
将 `docs/backend/analytics_db_architecture.md` 从偏概念性的架构说明重写为可直接执行的 `analytics_db` 落地与刷新操作手册，统一当前数据库中已经验证成功的 schema、表、物化视图、权限与刷新流程，避免后续继续沿用遗漏 `dim` 刷新和 `refresh_watermark` 更新的旧版步骤。
### 变更内容
- **文档重写**:
  - 更新 `docs/backend/analytics_db_architecture.md`
  - 补充一次性初始化、FDW 外表导入、ODS/DIM/FCT/MART 初始化与授权步骤
- **刷新流程修正**:
  - 明确当前正式版 `meta.refresh_analytics_all()` 会同时刷新 `dim.dim_process_area`、`dim.dim_vehicle_profile` 与 `meta.refresh_watermark`
  - 修正旧文档中仅刷新 `ods/fct/mart` 的过时描述
- **运维说明补充**:
  - 补充日常手工刷新、Windows 定时任务、验证 SQL 与后续项目接入步骤
  - 明确当前 `mart_vehicle_quality_360` 关联的是“缺陷检测 + 当前最新位置”，不是检测当时位置

## 2026-04-09 20:28 - 新增项目内数据库结构快照目录
### 概述
为方便后续字段分析、结构梳理和离线阅读，将 `defect_db` 中 5 张业务表的字段结构同步保存到项目根目录 `database/` 下，不再只依赖数据库内查询。
### 变更内容
- **新增本地快照目录与文件**:
  - 新增 `database/README.md`
  - 新增 `database/defect_db_schema_snapshot.json`
- **README 同步**:
  - 更新项目结构，补充 `database/` 目录说明
- **快照范围**:
  - `history`
  - `history_detail`
  - `history_extras`
  - `history_station`
  - `history_tokens`

## 2026-04-08 21:49 - 新增代码质量审查子智能体
### 概述
为项目补充一个专门用于“做代码 review、找 bug、识别回归风险、检查测试缺口”的子智能体 `code-reviewer`，帮助日常代码质量审查聚焦高风险问题与缺失测试，而不是停留在泛化风格建议。
### 变更内容
- **新增子智能体定义**:
  - 新增 `.claude/agents/code-reviewer.md`
  - 约束其聚焦代码质量问题、稳定性风险、安全隐患与测试覆盖审查
- **README 同步**:
  - 补充“代码质量审查子智能体”能力说明
  - 在项目结构中新增 `.claude/agents/code-reviewer.md` 入口
## 2026-04-07 21:18 - 同步 openspec/project.md 到当前项目上下文
### 概述
重写 `openspec/project.md` 中已经过期的 OpenSpec 项目背景说明，使其不再沿用旧版通用聊天 / arXiv Agent 视角，而是聚焦当前真实使用的 SQL Agent、Skills、RAG、结构化流式协议和双模式持久化实现，便于后续 proposal / spec 编写时获得更准确的项目上下文。
### 变更内容
- **项目定位修正**:
  - 更新 `openspec/project.md`
  - 将 Purpose 从旧版通用聊天 / 论文搜索场景，修正为当前生产数据查询型 SQL Agent 场景
- **技术与架构同步**:
  - 将技术栈更新为 LangChain/LangGraph、AsyncPostgresSaver / PostgresSaver、PGVector / Milvus Hybrid 等当前实现
  - 将架构模式更新为 `api.py -> services.py -> agent/service.py` 主链路
  - 补充结构化 SSE 事件协议和双模式持久化约定
- **约束与术语更新**:
  - 补充 `required_skill`、`export_to_csv`、BusinessRagMiddleware 等当前领域术语
  - 更新重要约束为只读 SQL、聚合优先、截断结果不可直接汇总、切换 embedding provider 后需重建向量库
  - 移除旧版固定主分支、FastAPI 测试客户端、arXiv API 等不再适合作为当前项目事实的描述

## 2026-04-07 21:04 - 同步 CLAUDE.md 到当前项目实现
### 概述
清理并重写根目录 `CLAUDE.md` 中已经过期的项目说明，使其与当前仓库中的环境约定、SQL Agent 架构、Skills/RAG 能力、结构化流式协议和双模式持久化实现保持一致，避免后续继续参考旧版 arXiv / 同步 PostgresSaver 文档造成误导。
### 变更内容
- **文档定位更新**:
  - 更新 `CLAUDE.md`
  - 明确 `AGENTS.md`、`memory.md`、`README.md`、`CLAUDE.md` 的建议优先级
  - 补充 proposal / spec / plan 场景下优先查看 `openspec/AGENTS.md` 的提示
- **环境与架构同步**:
  - 将环境说明从旧版 `py314_agent` 修正为 `py312_agent`
  - 将项目定位从旧版通用聊天 / arXiv Agent 更新为当前 SQL Agent + Skills + RAG 架构
  - 更新后端、前端主链路与关键目录说明
- **关键行为说明修正**:
  - 将流式说明更新为 `token/status/tool_call/tool_result/final/error` 结构化 SSE 事件协议
  - 将持久化说明更新为 FastAPI 本地异步 `AsyncPostgresSaver` 与 LangGraph 托管双模式
  - 补充 `required_skill` 约束、CSV 导出下载链路与当前常见误区说明

## 2026-04-06 21:22 - 重构技能场景目录与自动发现机制
### 概述
围绕后续固定场景持续增加后的维护成本问题，将业务技能系统从“场景文件 + 分散 SQL + 手工注册”升级为“场景目录聚合 + 自动发现 + scoped 资产解析”模式。这样新增一个场景时，只需要新增一个场景目录并填写模板，不再修改 `registry.py`。
### 变更内容
- **注册与发现重构**:
  - 新增 `backend/app/skills/discovery.py`
  - 更新 `backend/app/skills/registry.py`
  - 由显式 import/append 改为扫描 `domains/*/meta.py` 和 `scenarios/*/scenario.py` 自动装配
- **资产解析升级**:
  - 更新 `backend/app/skills/models.py`
  - 更新 `backend/app/skills/assets.py`
  - 更新 `backend/app/skills/renderers.py`
  - 为场景资产引入 `scope + path` 语义，支持 `scenario / shared / domain` 三类作用域
- **目录结构迁移**:
  - 迁移 `paint_shop_vehicle_tracking` 现有场景到 `scenarios/<scenario_name>/scenario.py + sql/main.sql`
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/shared/scripts/README.md`
  - 删除旧版 `scenarios/*.py`、`sql/*.sql` 与领域级脚本占位说明文件
- **验证与文档同步**:
  - 更新 `backend/app/test_skill_registry.py`，补充自动发现、shared 资产解析和失败即报错场景
  - 更新 `docs/backend/skills/README.md`
  - 更新 `docs/backend/skills/新增场景技能开发指南.md`
  - 更新 `docs/backend/skills/新增业务领域技能开发指南.md`
  - 更新 `docs/backend/skills/技能注册中心与加载机制说明.md`
  - 更新 `README.md` 的技能系统说明

## 2026-04-06 11:15 - 新增技能机制评审与优化待办文档
### 概述
将本次围绕“领域技能 / 场景技能加载机制”的评审结论整理为独立待办文档，集中记录当前问题、推荐方案与分期待办，便于后续继续按阶段推进优化，而不把讨论内容散落在聊天记录中。
### 变更内容
- **新增待办目录**:
  - 新增 `docs/todolist/`
- **新增评审文档**:
  - 新增 `docs/todolist/2026-04-06-技能机制评审与优化待办.md`
  - 归档技能上下文失配、场景资产加载不一致、场景与历史 SQL 示例优先级不清、仅展开第一份 SQL 等问题
- **目录说明同步**:
  - 更新 `README.md` 的项目结构说明，补充 `docs/todolist/` 目录用途

## 2026-04-06 10:25 - 同步 Obsidian 后端学习导航，补齐遗漏文档包装页
### 概述
扫描 `docs/` 与 `docs/obsidian/` 的对应关系后，补齐此前未纳入 Obsidian 后端学习路径的 5 篇中文文档，确保 `llama.cpp` 配置总结与 skills 专题文档也能在 Obsidian 中通过导航页顺序访问。
### 变更内容
- **导航更新**:
  - 更新 `docs/obsidian/backend-learning/00_后端开发学习导航.md`
  - 新增“本地模型与技能系统扩展”阶段，补充 22-26 号学习笔记入口
- **包装页补齐**:
  - 新增 `docs/obsidian/backend-learning/22_llama.cpp_与_LangChain_配置要点总结.md`
  - 新增 `docs/obsidian/backend-learning/23_Skills总览与文档导航.md`
  - 新增 `docs/obsidian/backend-learning/24_技能注册中心与加载机制说明.md`
  - 新增 `docs/obsidian/backend-learning/25_新增业务领域技能开发指南.md`
  - 新增 `docs/obsidian/backend-learning/26_新增场景技能开发指南.md`
- **链路修正**:
  - 更新 `docs/obsidian/backend-learning/21_Docker容器网络与外部服务访问指南.md`
  - 为原有阶段末尾补充下一篇跳转，保持学习链路连续

## 2026-04-06 10:14 - 新增 llama.cpp 与 LangChain 配置要点总结文档
### 概述
将项目内接入 `llama.cpp` OpenAI 兼容接口时的关键经验整理为独立文档，集中说明 `BASE_URL`、协议、API Key、模型名与 `max_tokens` 的配置规律，便于后续排查本地模型接入问题。
### 变更内容
- **新增文档**:
  - 新增 `docs/llama.cpp 与 LangChain 配置要点总结.md`
- **沉淀内容**:
  - 总结 `BASE_URL` 应只保留到 `/v1`
  - 补充 `http`/`https` 协议匹配要求
  - 记录 `llama.cpp` 默认不校验 API Key 的约定
  - 补充模型名、`max_tokens` 与推荐 `ChatOpenAI` 参数写法
- **维护价值**:
  - 为后续本地 GGUF 模型接入、排错与配置统一提供固定参考

## 2026-04-05 20:15 - 新增实时区域车身数量场景技能
### 概述
在 `paint_shop_vehicle_tracking` 领域下补充一个“实时各区域车身数量统计”固定场景，沉淀对应的场景 playbook 和外部 SQL 模板，让 Agent 能按场景方式加载这类高频实时统计需求。
### 变更内容
- **场景技能新增**:
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count.py`
  - 定义实时区域车身数量统计的触发问法、workflow、规则、易错点与输出契约
- **SQL 模板新增**:
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/sql/realtime_area_body_count.sql`
  - 按 `process_area` 聚合统计当前有效车身数量，并按数量降序输出
- **注册与验证补充**:
  - 更新 `backend/app/skills/registry.py`，显式注册 `realtime_area_body_count`
  - 更新 `backend/app/test_skill_registry.py`，覆盖新场景的注册与加载断言
- **文档同步**:
  - 更新 `docs/backend/skills/README.md` 的当前目录结构示例，补充新场景文件

## 2026-04-05 11:40 - 补全 skills 专题文档目录
### 概述
继续完善 `docs/backend/skills/`，将原先的单篇“新增业务领域技能开发指南”扩展为一个可导航的小型专题文档集，覆盖目录索引、场景技能扩展方式以及注册中心与加载机制说明，方便团队后续系统化维护技能系统。
### 变更内容
- **新增文档索引**:
  - 新增 `docs/backend/skills/README.md`
  - 统一收口 skills 相关文档入口和推荐阅读顺序
- **新增扩展教程**:
  - 新增 `docs/backend/skills/新增场景技能开发指南.md`
  - 新增 `docs/backend/skills/技能注册中心与加载机制说明.md`
- **README 同步**:
  - 在技术文档列表中补充 skills 专题导航和新文档入口
- **维护价值**:
  - 让 `docs/backend/skills/` 从单文档目录演进为可持续扩展的技能系统手册目录

## 2026-04-05 11:10 - 新增业务领域技能扩展教程
### 概述
围绕当前“领域 skill + 场景 skill”二级披露架构，补充一份面向维护者的可复用教程，专门说明如何新增、配置和验证一个新的业务领域，避免后续只创建目录却遗漏注册中心、场景挂载或资产路径配置。
### 变更内容
- **新增教程文档**:
  - 新增 `docs/backend/skills/新增业务领域技能开发指南.md`
  - 说明新增领域目录、`meta.py`、`domain.md`、场景定义、SQL 模板与 `registry.py` 显式注册步骤
- **文档入口补充**:
  - 更新 `README.md` 的技术文档列表，加入该教程入口
- **维护建议沉淀**:
  - 明确当前实现属于“显式注册”机制，不会自动发现新领域
  - 总结新增领域后的验证清单与常见错误，便于团队后续复用

## 2026-04-05 10:30 - 引入领域与场景二级 Skill 披露骨架
### 概述
围绕 SQL Agent 的业务技能系统，实施“领域 skill + 场景 skill”二级披露改造：保留现有 `load_skill -> required_skill -> sql_db_query` 主链路，在不引入固定报表执行器的前提下，新增场景级 playbook、外部 SQL 资产和二级加载工具，为后续模板执行器与专用 report tool 预留扩展接口。
### 变更内容
- **技能包重构**:
  - 将 `backend/app/skills.py` 升级为 `backend/app/skills/` package
  - 新增 `models.py`、`registry.py`、`renderers.py`、`loaders.py`、`assets.py`
  - 保留 `SKILLS` 兼容导出，避免现有中间件和测试脚本回归
- **二级披露链路**:
  - 新增 `load_scenario` 工具
  - 扩展 `CustomState`，增加 `scenarios_loaded`、`active_skill`、`active_scenario`
  - 更新 `SkillMiddleware` 与系统提示词，引导“先加载领域，再按需加载场景”
- **样板场景落地**:
  - 为 `paint_shop_vehicle_tracking` 新增 `daily_area_body_count` 场景元数据
  - 引入外部 SQL 模板 `daily_area_body_count.sql`
  - 场景文本新增 workflow、rules、gotchas、output contract 和模板资产引用
- **文档与测试**:
  - 更新 `README.md` 中的技能系统说明
  - 新增 `backend/app/test_skill_registry.py`，覆盖注册中心、加载器和二级加载辅助逻辑

## 2026-04-04 14:55 - 清理 Docker 环境文件中的敏感信息并补充忽略规则

### 概述
针对 GitHub Push Protection 阻止 `feature/agent` 推送的问题，先在当前工作区完成最小化安全修复：补充相关忽略规则，降低后续再次误提交本地敏感配置的风险，并为后续清理未推送提交历史做准备。

### 变更内容
- **忽略规则补充**:
  - 更新 `.gitignore`
  - 新增 `.env_docker`、`.env copy`、`env_exp` 忽略项，覆盖本次触发扫描的本地环境文件命名
- **历史清理说明**:
  - 当前变更仅处理工作区与后续防误提交保护
  - 仍需对本地未推送提交历史执行重写，才能解除 GitHub 对旧提交中 secret 的拦截

## 2026-04-03 20:00 - 整理文档目录结构并更新 Obsidian 引用

### 概述
将原先分散在 `backend/docs` 下的后端技术文档统一归档到 `docs/backend`，让项目文档入口全部收口到 `docs/` 下；同时同步修正 Obsidian 学习笔记、README 与相关说明中的旧路径引用，避免目录调整后出现断链。

### 变更内容
- **目录整合**:
  - 将 `backend/docs/` 迁移为 `docs/backend/`
  - 保留 `docs/backend/rpd/` 子目录结构
- **Obsidian 引用更新**:
  - 批量更新 `docs/obsidian/backend-learning/` 下 21 篇学习笔记的 `source_note`、原文入口与嵌入路径
  - 更新 `00_后端开发学习导航.md` 中的原文目录说明
- **说明文档同步**:
  - 更新 `README.md` 中的项目结构与技术文档入口
  - 更新 `CLAUDE.md`、`开发规范与最佳实践.md` 中的后端文档目录路径
  - 修正 `docs/backend/rpd/` 内少量旧绝对路径说明

## 2026-04-02 22:25 - 新增通用文档的 Obsidian 分类学习目录

### 概述
将 `docs/` 下 7 篇原先零散放置的通用文档，按主题整理进对应的 Obsidian 学习目录，延续 `backend-learning` 的组织规则：保留原文不动，新增导航页、编号学习页、原文入口与嵌入，方便后续在 Obsidian 中按专题学习。

### 变更内容
- **新增 Obsidian 分类目录**:
  - 新增 `docs/obsidian/agent-sql-learning/`
  - 新增 `docs/obsidian/architecture-learning/`
  - 新增 `docs/obsidian/frontend-learning/`
  - 新增 `docs/obsidian/data-quality-learning/`
- **整理范围**:
  - `agent_best_practices.md`
  - `LangChain + PostgreSQL 注释识别最佳实践.md`
  - `sql_agent.md`
  - `前后端与Nginx架构知识总结.md`
  - `前端聊天消息Markdown渲染开发指南.md`
  - `数据库日期时间记录与大模型处理分析报告.md`
  - `生产数据查询智能体需求.md`
- **README 同步**:
  - 更新 Obsidian 学习目录说明
  - 增加新的学习导航入口

## 2026-04-02 22:15 - 新增 Obsidian 后端开发学习导航与编号笔记

### 概述
为了方便系统化学习 `backend/docs` 下的后端开发文档，新增一组面向 Obsidian 的学习笔记目录。在不改动原始文档的前提下，按学习顺序重新编号，并补充导航页、前后跳转和原文嵌入入口，降低后续复习与串联成本。

### 变更内容
- **新增 Obsidian 学习目录**:
  - 新增 `docs/obsidian/backend-learning/`
  - 新增 `00_后端开发学习导航.md`
  - 新增 21 篇编号学习笔记，覆盖 `backend/docs` 与 `backend/docs/rpd` 的现有后端文档
- **组织方式**:
  - 保留原始 `backend/docs` 文档不动
  - 每篇学习笔记增加学习建议、原文入口、上下篇导航与 Obsidian 嵌入
  - 导航页按“基础认知 / Agent 与 RAG / SQL Agent / 交互观测 / 部署环境”分阶段整理
- **README 同步**:
  - 更新项目结构说明
  - 增加 Obsidian 后端学习导航入口

## 2026-04-02 13:00 - 修复 Docker 构建阶段的 Milvus 依赖版本冲突

### 概述
修复 Docker 构建 `pip install -r /app/requirements.txt` 时的依赖解析失败。根因是项目显式锁定了 `pymilvus==2.6.3`，但 `llama-index-vector-stores-milvus==1.0.0` 要求 `pymilvus>=2.6.7,<3`，导致 pip 无法完成依赖求解。

### 变更内容
- **依赖版本对齐**:
  - 更新 `requirements.txt`
  - 更新 `requirements_standard.txt`
  - 将 `pymilvus` 从 `2.6.3` 提升为 `2.6.7`
- **修复效果**:
  - 与 `llama-index-vector-stores-milvus==1.0.0` 的最低兼容版本保持一致
  - 保持改动最小，避免一次性升级到更高版本带来的额外兼容风险

## 2026-04-02 12:50 - 修复 Docker 容器启动时 backend 包导入失败

### 概述
修复 `docker-compose.yml` 启动后端容器时出现的 `ModuleNotFoundError: No module named 'backend'`。根因是镜像内的 `WORKDIR`、`PYTHONPATH` 与 Uvicorn 启动入口使用了 `app.main:app` 路径，但仓库代码实际大量采用 `backend.app...` 绝对导入，导致容器内包根路径不一致。

### 变更内容
- **镜像启动路径修复**:
  - 更新 `backend/Dockerfile`
  - `WORKDIR` 从 `/app/backend` 调整为 `/app`
  - `PYTHONPATH` 从 `/app/backend` 调整为 `/app`
  - Uvicorn 启动入口从 `app.main:app` 调整为 `backend.app.main:app`
- **修复效果**:
  - 让容器内 Python 包根路径与仓库实际导入风格保持一致
  - 避免 `export_files.py`、`services.py`、`agent/service.py` 等模块中的 `backend.app...` 绝对导入在容器中失效

## 2026-04-02 00:10 - 新增 Docker 容器网络与外部服务访问指南

### 概述
围绕本次 `backend`、PostgreSQL、Milvus 与宿主机模型服务之间的 Docker 联通排查，新增一份可复用的实施/排障手册，统一沉淀 `external network`、容器名寻址、`host.docker.internal` 使用边界以及常见易错点，方便后续继续接入新的数据库或本地 API 服务。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/Docker容器网络与外部服务访问指南.md`
- **文档内容覆盖**:
  - 容器访问容器、容器访问宿主机、本机访问本机三类地址边界
  - `savedatabase_app-network` 与 `savedatabase_app_network` 命名差异带来的真实排障经验
  - Milvus 同时接入默认网络与外部网络的设计原因
  - 后续接入新依赖服务时的标准判断步骤与检查清单
- **README 同步**:
  - 更新技术文档列表，补充 Docker 网络与外部服务访问指南入口

## 2026-04-01 23:25 - 新增前端聊天消息 Markdown 渲染开发指南

### 概述
将本次“聊天消息完成态 Markdown 渲染 + 业务报表风格样式”实现过程沉淀为一份可复用开发指南，便于后续在其他聊天结果展示、分析摘要卡片或统计报表类前端场景中继续复用。

### 变更内容
- **新增文档**:
  - 新增 `docs/前端聊天消息Markdown渲染开发指南.md`
- **文档内容覆盖**:
  - 聊天消息 Markdown 渲染的背景、目标与整体分层设计
  - `markdown-it + DOMPurify + MessageItem.vue + style.css` 的调用链与职责拆分
  - 流式纯文本 / 完成态 Markdown 的设计取舍、易错点与检查清单
  - 业务报表风格样式的复用经验、边界与后续优化方向
- **README 同步**:
  - 更新项目特性与技术文档列表，补充 Markdown 展示能力与指南入口

## 2026-04-01 23:10 - 优化聊天消息为业务报表风格展示

### 概述
继续细化聊天消息的 Markdown 呈现方式，将原先偏通用文档的样式收敛为更适合统计结果、异常说明、分析摘要等场景的“业务报表风格”，让标题层次、表格扫描效率和数字信息可读性更清晰。

### 变更内容
- **样式优化**:
  - 更新 `frontend/src/style.css`
  - 强化仅含加粗文本段落的区块标题表现，模拟报表分组标题
  - 优化表格表头背景、行间斑马纹、边框与阴影，提升企业报表观感
  - 为第二列数字内容增加右对齐与等宽数字展示，便于快速对比数量
  - 放宽说明列换行规则，减少长文本被挤压的问题

## 2026-04-01 22:55 - 前端聊天消息支持 Markdown 展示渲染

### 概述
为聊天前端新增“完成态 Markdown 渲染”能力，让助手最终回复中的粗体、列表、表格、代码块和链接能够以更舒适、更易读的样式展示；同时保留流式输出阶段的纯文本效果，避免生成过程中频繁重排。

### 变更内容
- **前端依赖**:
  - `frontend/package.json` 新增 `markdown-it` 与 `dompurify`
- **渲染能力**:
  - 新增 `frontend/src/utils/markdown.ts`
  - 统一封装 Markdown 转 HTML 与安全清洗逻辑
  - 链接默认补充新窗口打开与安全 `rel` 属性
- **消息展示**:
  - 更新 `frontend/src/components/MessageItem.vue`
  - 用户消息与流式中的助手消息继续按纯文本显示
  - 助手完成态消息切换为 Markdown HTML 渲染
- **视觉样式**:
  - 更新 `frontend/src/style.css`
  - 新增聊天消息 Markdown 样式，优化段落、列表、表格、代码块、引用和链接展示

## 2026-04-01 01:00 - 新增 development-guide-synthesizer 技能

### 概述
新增一个面向“开发经验沉淀”的项目级技能，用于根据开发实现、讨论内容、代码改动和验证结果，快速提炼出结构化开发指南手册。该技能内置清晰模板、示例、关键点和常见错误，方便后续重复使用。

### 变更内容
- **新增技能**:
  - 新增 `.agents/skills/development-guide-synthesizer/SKILL.md`
- **新增参考资料**:
  - 新增 `.agents/skills/development-guide-synthesizer/references/guide-template.md`
  - 新增 `.agents/skills/development-guide-synthesizer/references/examples.md`
- **技能能力**:
  - 支持把功能开发、调试排障、架构讨论等内容沉淀为开发指南、排障手册、实施手册或复用 playbook
  - 提供标准章节模板、调用示例、关键点维度和易错点清单
- **README 同步**:
  - 更新项目特性与目录结构，补充该技能入口

## 2026-04-01 00:30 - 新增 SQL 导出文件下载开发指南

### 概述
围绕本次“SQL 大结果导出 + 后端下载接口 + 前端下载卡片”能力，新增一份可复用的开发指南，统一沉淀从查询限流、导出工具、文件元数据、安全下载到前端消息展示的设计经验，方便后续在其他导出类场景继续复用。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/SQL导出文件下载开发指南.md`
- **文档内容覆盖**:
  - SQL 导出下载链路的整体架构与调用顺序
  - `export_to_csv`、`export_files.py`、下载接口与前端下载卡片的职责分层
  - 为什么选择“结构化 JSON 字符串 + file_id + sidecar metadata”方案
  - 文件下载安全边界、复用模板、检查清单与后续演进方向
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-04-01 00:00 - 为 SQL 导出结果新增前端可下载能力

### 概述
为 `export_to_csv` 打通“服务器落盘 -> 后端安全下载接口 -> 前端下载按钮”的完整链路。现在导出工具不会再把服务器绝对路径直接暴露给前端，而是返回结构化导出元数据，聊天消息中可直接点击下载 CSV。

### 变更内容
- **后端导出元数据管理**:
  - 新增 `backend/app/export_files.py`
  - 为每个导出文件生成 `file_id`，并使用 sidecar JSON 保存文件元数据
- **后端下载接口**:
  - `backend/app/api.py` 新增 `GET /api/chat/files/{file_id}`
  - 通过 `FileResponse` 安全返回已导出的 CSV 文件
- **导出工具返回结构升级**:
  - `backend/app/agent/tools/csv_export_tool.py` 从“返回服务器路径文本”改为“返回结构化 JSON 字符串”
  - `backend/app/config.py` 新增 `SQL_EXPORT_DIR`、`SQL_EXPORT_TTL_HOURS`
- **前端下载卡片**:
  - 新增 `frontend/src/api/exports.ts`
  - `frontend/src/components/MessageItem.vue` 自动识别 `export_to_csv` 结果并渲染“下载 CSV”按钮
  - `frontend/src/types/index.ts` 新增 `ExportArtifact` 类型

### OpenSpec
- 新增 `openspec/changes/add-sql-export-download/`，记录本次导出下载能力的 proposal / design / tasks / spec delta

## 2026-03-31 22:08 - 新增聊天取消与中断机制开发指南

### 概述
围绕本次“前端停止生成 + 后端取消渗透”优化，新增一份专门的开发指南，统一说明取消链路的分层实现、机制原理、能力边界和后续扩展方向，方便团队后续继续复用和演进这套聊天中断能力。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/聊天取消与中断机制开发指南.md`
- **文档内容覆盖**:
  - 前端 `AbortController` 的停止生成机制
  - FastAPI SSE 断连感知与服务端停止转发逻辑
  - `task.cancel()` / `CancelledError` 如何沿 LangChain / LangGraph 协程链传播
  - 本地取消与远端 provider 取消的能力边界
  - 当前产品策略与后续可选体验方案
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-31 22:15 - 停止生成后保留已生成片段并明确标记中断

### 概述
继续细化“停止生成”的产品体验。用户主动中断流式回答后，前端不再直接清空过程态，而是保留已经生成的内容，并将其落定为一条本地 assistant 消息，同时明确标记“已停止生成”，让状态更可理解。

### 变更内容
- **中断消息落定**:
  - `frontend/src/stores/messages.ts` 新增主动中断落定逻辑
  - 停止生成后保留当前文本片段、工具调用和工具结果，并转为本地正式消息
- **取消分支体验优化**:
  - `frontend/src/composables/useChatStream.ts` 在 `AbortError` 分支改为保留片段而非直接清空
  - 继续刷新会话列表，但不立即用服务端消息覆盖当前本地中断结果
- **界面提示优化**:
  - `frontend/src/components/MessageItem.vue` 为中断消息增加“已停止生成”提示和对应视觉样式
- **文档同步**:
  - 更新 `backend/docs/聊天取消与中断机制开发指南.md` 中的当前产品策略说明

## 2026-03-31 21:31 - 收敛前后端 SSE 事件 schema

### 概述
继续收敛聊天流式协议边界，减少前后端对未知事件类型的宽松兜底。后端现在会在发送 SSE 前校验事件结构，前端则移除 `type: string` 回退分支并在解析层拒绝不符合协议的 payload，从而让流式协议真正收敛为有限事件集合。

### 变更内容
- **后端事件模型收敛**:
  - `backend/app/schemas.py` 将流式事件拆分为 `token/status/tool_call/tool_result/final/error` 六类显式模型
  - 新增统一序列化入口，SSE 发送前先校验并标准化事件 payload
- **前端解析层收敛**:
  - `frontend/src/types/index.ts` 移除宽松 `type: string` 兜底事件
  - `frontend/src/api/chat.ts` 增加运行时事件校验，拒绝未知或不完整的流式事件
- **消费侧类型收敛**:
  - `frontend/src/composables/useChatStream.ts` 改为穷尽式 `switch` 处理，避免新事件类型被静默忽略
- **文档同步**:
  - 更新 `backend/docs/聊天流式输出结构化事件开发指南.md`，补充 schema 收敛原则

## 2026-03-31 21:52 - 收敛取消信号到 Agent 执行任务

### 概述
继续优化聊天链路的取消能力，让“前端停止生成 / SSE 断连”不仅停止本地转发，也尽量中断服务层正在执行的 Agent 调用。这样做不能保证远端 LLM provider 一定马上停止推理，但可以更稳定地把取消信号继续传到 LangGraph 图执行与底层模型 SDK 的 await 链路。

### 变更内容
- **非流式取消收敛**:
  - `backend/app/services.py` 将 `ainvoke()` 包装为可取消 task
  - 上层取消时显式取消并等待任务结束，避免悬挂中的 Agent 调用继续运行
- **流式取消收敛**:
  - `backend/app/services.py` 将 `astream()` 消费改为独立 producer task + queue
  - 当 SSE 消费端取消或断连时，会反向取消 producer task，并主动关闭底层 async iterator
- **边界说明**:
  - 当前优化能更早停止本地 FastAPI / LangGraph 消费链路
  - 远端 provider 是否真正中断，仍取决于对应 SDK / 模型服务是否支持请求级取消

## 2026-03-31 11:05 - 新增 LangSmith tracing 开发指南文档

### 概述
围绕本次 tracing metadata / tags 接入，新增一份面向后续开发的文档手册，统一说明其作用、当前实现、字段规范、查看方式和扩展建议，方便后续在新入口或新业务域下继续复用。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/LangSmith Tracing Metadata 与 Tags 开发指南.md`
- **文档内容覆盖**:
  - tracing metadata / tags 的作用与典型使用场景
  - 当前项目中的接入位置与字段清单
  - 如何在调用时追加业务 metadata / tags
  - 如何在 LangSmith 中查看和过滤 trace
  - 后续扩展建议与开发检查清单
- **README 同步**:
  - 在技术文档列表新增该指南入口

### 2026-03-31 11:15 Asia/Shanghai 更新补充
- 澄清 `business_domain` 应来自确定性来源，不应由 LLM 在请求开始时自由推断后注入根 trace
- 补充“运行过程中才能确定 domain 时”的三种推荐策略：首轮不注入、仅对子链路补充、持久化后下一轮再注入

### 2026-03-31 11:30 Asia/Shanghai 更新补充
- 修正 tracing 手册中的 `config` 示例，拆分为“默认安全示例”和“已确认 domain 才注入”的扩展示例

## 2026-03-31 10:20 - 后端新增 SSE 客户端断连感知

### 概述
为聊天流式接口补充服务端侧断连感知能力。当浏览器主动停止生成、关闭页面或网络中断导致 SSE 连接断开时，后端会尽早停止等待新的流式事件并关闭流式迭代器，减少无效的本地继续执行。

### 变更内容
- **SSE 断连检测**:
  - `backend/app/api.py` 的 `/stream` 路由新增 `Request` 注入
  - 在事件循环中周期性检查 `request.is_disconnected()`
- **尽早停止等待**:
  - 将下一条流式事件读取包装为可取消的 `asyncio` task
  - 检测到客户端断开后，立即取消等待中的任务并结束 SSE 生成
- **资源清理与结束标记收敛**:
  - 在 `finally` 中主动关闭流式迭代器
  - 客户端已断开时不再尝试发送 `[DONE]`

## 2026-03-31 10:45 - 新增 LangSmith tracing metadata 与 tags

### 概述
为 FastAPI 本地聊天链路补充 LangSmith trace 元数据与标签。后续可以在 LangSmith 中按会话、请求模式、RAG 后端、模型和运行环境过滤 trace，也为自托管或兼容 OpenAI 协议的模型提供更稳定的模型识别字段。

### 变更内容
- **trace metadata 补充**:
  - `backend/app/services.py` 统一为 invoke/stream 两条链路补充 `session_id`、`thread_id`、`request_mode`、`rag_backend`、`app_component`、`runtime_mode`
  - 同步补充 `ls_provider`、`ls_model_name`、`ls_temperature`、`ls_max_tokens`
- **trace tags 补充**:
  - 新增 `chat-api`、`sql-agent`、`mode:*`、`runtime:*`、`rag:*`、`provider:*`、`model:*`、`env:*` 等标签
- **配置合并策略**:
  - 保留外部传入的 `configurable / metadata / tags`
  - 新增 trace 字段时默认合并，不破坏后续按业务域继续扩展

## 2026-03-29 22:35 - 修复 P0 级流式结果聚合与非流式错误语义

### 概述
针对聊天链路中最关键的三类问题进行收敛：避免多节点流式 token 被误拼成最终回答、避免 `tool_call_chunk` 在前后 chunk 间被拆成多个工具调用、避免非流式 Agent 异常被伪装成正常 assistant 消息落库。

### 变更内容
- **流式最终内容聚合修复**:
  - `backend/app/services.py` 不再使用全量流式 token 直接生成最终 `final.content`
  - 改为优先使用最终 `AIMessage` 提取的完整内容，降低多节点 streaming 污染最终回答的风险
- **工具调用 chunk 归并修复**:
  - `backend/app/services.py` 将流式工具调用按 `chunk index` 归并，并通过原始 `tool_call_id` 回写结果映射
  - 避免同一次工具调用被拆成多个前端工具卡片
- **非流式错误语义修复**:
  - `backend/app/services.py` 的 `process_message()` 改为向上抛出异常
  - `backend/app/api.py` 在非流式路径返回标准错误响应，不再把失败文本保存为成功 assistant 消息
- **前端失败后状态同步补强**:
  - `frontend/src/composables/useChatStream.ts` 在发送失败后补一次消息同步，尽量与服务端持久化状态保持一致

## 2026-03-29 22:55 - 收敛前端会话状态同步与消息请求竞态

### 概述
继续优化聊天前端状态管理，去掉本地手工维护的会话消息计数，统一以服务端会话数据为准；同时为消息拉取增加请求序列保护，避免快速切换会话时旧请求回包覆盖当前会话消息。

### 变更内容
- **会话状态权威源收敛**:
  - `frontend/src/composables/useChatStream.ts` 不再手工累加 `message_count`
  - 在消息发送完成、流式结束和失败恢复后统一刷新服务端会话列表
- **消息同步范围收敛**:
  - 仅当当前仍停留在对应会话时，才静默刷新该会话的消息列表
  - 避免用户切换到其他会话后，旧会话的后台同步覆盖当前视图
- **消息请求竞态保护**:
  - `frontend/src/stores/messages.ts` 新增请求序号与目标会话标记
  - 旧请求回包将被忽略，降低串会话和闪屏风险

## 2026-03-29 23:10 - 新增流式取消能力与停止生成交互

### 概述
为聊天前端补充流式请求取消能力。用户在流式模式下发送问题后，可以主动停止当前生成过程；前端会中断 SSE 请求、清理过程态，并重新同步服务端消息与会话状态，避免把主动停止误判为系统错误。

### 变更内容
- **流式请求取消**:
  - `frontend/src/api/chat.ts` 为 `sendChatStream()` 增加 `AbortSignal` 支持
  - `frontend/src/composables/useChatStream.ts` 使用 `AbortController` 管理当前流式请求
- **停止生成交互**:
  - `frontend/src/views/ChatView.vue` 在流式发送中将发送按钮切换为“停止生成”
  - 用户点击后会中断当前请求，而不是弹出失败提示
- **中断后的状态收敛**:
  - 主动中断时清理流式临时消息
  - 随后重新同步当前会话消息与会话列表，尽量与服务端持久化结果保持一致

## 2026-03-27 22:12 - 聊天界面默认仅展示最终结论

### 概述
优化聊天前端展示策略，将“过程信息”和“最终答案”分层处理。普通用户在问答完成后只看到最终结论，生成过程中的状态与工具细节仅保留为轻量提示或内部调试信息，从而减少信息噪音，提升阅读效率。

### 变更内容
- **OpenSpec 提案补充**:
  - 新增 `openspec/changes/update-chat-final-only-display/`
  - 为“默认仅展示最终结论”补齐 proposal / tasks / spec delta
- **前端展示收敛**:
  - `frontend/src/components/MessageItem.vue` 默认不再展示状态文本、工具调用、工具结果和错误细节
  - 新增 `frontend/src/config/chat.ts`，通过 `VITE_CHAT_DEBUG_STREAM=true` 恢复内部调试视图
- **流式错误体验修复**:
  - `frontend/src/stores/messages.ts` 新增错误落定逻辑，失败时直接收敛为最终 assistant 消息
  - `frontend/src/composables/useChatStream.ts` 避免错误后残留半成品过程态消息
- **README 同步**:
  - 更新功能说明，强调默认用户界面仅展示最终结论

## 2026-03-27 20:55 - 新增 Milvus RAG 异步化故障排查指南

### 概述
围绕本次 Milvus RAG 检索失败事件，系统整理从故障现象、排查路径、根因分析到最终 async 化修复方案的完整经验，帮助后续快速判断“空检索结果”到底是召回失败还是初始化上下文失败。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/Milvus-RAG-异步化故障排查指南.md`
- **文档内容覆盖**:
  - 同步 `PostgresSaver`、`stream()/astream()`、Milvus lazy init 之间的因果关系
  - `ThreadPoolExecutor` 工作线程缺少 event loop 的真实触发链
  - 为什么表面上的“未检索到业务知识”其实是初始化失败后的降级结果
  - 最终为什么选择“本地 FastAPI 全链路切回 async”而不是在线程池里补 event loop
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-27 20:40 - 本地 FastAPI 切回 AsyncPostgresSaver 与异步流式执行

### 概述
将本地 FastAPI 运行链路从“同步 `PostgresSaver` + `stream()/invoke()`”切回“`AsyncPostgresSaver` + `astream()/ainvoke()`”，并增加显式 startup/shutdown 生命周期管理，解决同步 saver 限制和 Milvus 延迟初始化在线程池中缺少 event loop 的问题。

### 变更内容
- **本地异步持久化**:
  - `backend/app/agent/service.py` 新增 `AsyncConnectionPool + AsyncPostgresSaver` 初始化工厂
  - 新增 `create_local_async()` 与 `aclose()`，供 FastAPI 本地模式显式初始化和关闭
- **FastAPI 生命周期改造**:
  - `backend/app/services.py` 去掉模块级 eager `agent_service`
  - 新增 `initialize_agent_service()` / `get_agent_service()` / `shutdown_agent_service()`
  - `backend/app/main.py` 在 `lifespan` 中显式初始化与回收 Agent 资源
- **请求执行链路恢复异步**:
  - `backend/app/services.py` 的非流式和流式调用切回 `ainvoke()` / `astream()`
  - 继续保留结构化 SSE 事件协议与前端兼容逻辑
- **文档同步**:
  - 更新 `backend/docs/聊天流式输出结构化事件开发指南.md`
  - 更新 `backend/docs/延迟初始化工作流程详解.md`
  - 更新 `README.md` 中本地持久化与运行模式说明

## 2026-03-27 18:45 - 新增聊天流式输出结构化事件开发指南

### 概述
基于本次聊天流式协议升级、同步/异步 streaming 兼容处理、工具状态一致性修复和前端 SSE 重构实践，沉淀一份可复用的开发指南，方便后续在其他 Agent / Chat 场景中快速复用和学习。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/聊天流式输出结构化事件开发指南.md`
- **文档内容覆盖**:
  - 结构化流式事件协议设计
  - 后端 `messages / updates / custom` 分工建议
  - 前端 SSE buffer 解析与 streaming state 建模
  - `astream` / `stream` 与 `PostgresSaver` 兼容性踩坑
  - 工具状态“执行中/已完成”一致性处理经验
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-27 17:50 - 聊天流式协议升级为结构化事件流

### 概述
将原有“纯文本 chunk + 最终块补工具信息”的流式链路，升级为前后端协同的结构化 SSE 事件流。后端切换到 LangGraph v2 多模式 streaming，前端重写 SSE 解析与流式状态管理，使用户可以看到更稳定的实时文本、阶段状态、工具调用、工具结果和错误态。

### 变更内容
- **OpenSpec 提案补充**:
  - 新增 `openspec/changes/update-chat-streaming-protocol/`
  - 为流式协议升级补齐 proposal / tasks / spec delta
- **后端流式协议升级**:
  - `backend/app/services.py` 改为输出 `token/status/tool_call/tool_result/final/error` 结构化事件
  - 使用 `agent.astream(..., stream_mode=[\"messages\", \"updates\", \"custom\"], version=\"v2\")`
  - 新增 `backend/app/agent/utils/streaming.py`，为工具与中间件提供 custom status 事件写入 helper
  - `backend/app/api.py` 在 `final/error` 路径统一处理 assistant 消息落库，并保留 `[DONE]` 作为传输层结束标记
- **前端流式消费重构**:
  - `frontend/src/api/chat.ts` 重写 SSE buffer 解析逻辑，兼容跨 chunk JSON
  - `frontend/src/types/index.ts` 引入 `StreamEvent`、`StreamToolCall`、结构化 `StreamingMessage`
  - `frontend/src/stores/messages.ts` / `frontend/src/composables/useChatStream.ts` 改为事件驱动，采用“本地完成落定 + 后台静默同步”
  - `frontend/src/components/MessageItem.vue` / `frontend/src/views/ChatView.vue` 增强状态文案、工具执行区和错误态展示

## 2026-03-27 16:10 - 前端开发环境代理到本地后端 8000

### 概述
针对当前后端服务运行在 `http://localhost:8000`、而前端仍使用 `/rearch/...` 相对路径请求的情况，在 Vite 开发环境中补充代理转发规则，避免逐个修改前端 API 文件，并保持开发环境与生产环境的路径风格一致。

### 变更内容
- **Vite 开发代理**:
  - 在 `frontend/vite.config.ts` 的 `server.proxy` 中新增 `/rearch -> http://localhost:8000`
  - 通过 `rewrite` 去掉请求前缀 `/rearch`，使后端实际接收到 `/api/chat/...`
- **兼容性说明**:
  - 保持 `frontend/src/api/index.ts` 与 `frontend/src/api/chat.ts` 现有相对路径写法不变
  - 前端开发时浏览器仍访问 `/rearch/api/...`，由 Vite 代理转发到本地 FastAPI `8000`

### 补充修正（2026-03-27 16:22）
- 将 `frontend/vite.config.ts` 的代理匹配从 `/rearch` 收窄为 `/rearch/api`
- 避免首页路由 `/rearch/` 被误代理到后端根路径 `/`，导致浏览器显示 FastAPI JSON 而不是前端页面

## 2026-03-27 15:45 - 精简 service.py 运行模式识别并补充编排注释

### 概述
在保持 FastAPI / LangGraph CLI 双模式兼容的前提下，继续收敛 `backend/app/agent/service.py` 的实现复杂度，让运行模式识别、持久化注入和 Agent 编排主干更容易阅读和维护。

### 变更内容
- **运行模式识别简化**:
  - 用更直观的 `LANGGRAPH_API_URL || PATH contains langgraph` 规则判断托管环境
  - 保留日志输出，明确区分“LangGraph API 托管环境”和“本地独立运行模式”
- **持久化注入简化**:
  - 本地模式下通过 `agent_kwargs` 显式传入 `store/checkpointer`
  - 托管模式下保持空注入，由 LangGraph 运行时自动接管
- **可读性增强**:
  - 为环境识别、持久化初始化、Agent 编排主干补充了精简注释
  - `build_agent_graph` 增加了对 LangGraph factory 参数用途的说明

## 2026-03-27 15:23 - SQL Agent 服务层整合并兼容 LangGraph CLI 双模式

### 概述
将 `backend/app/services.py` 从旧的一体化 SQL Agent 实现重构为 FastAPI 兼容适配层，底层统一复用 `backend/app/agent/service.py` 的 Agent V2 核心运行时。同时补齐 `langgraph dev` / LangGraph API 场景下的双模式兼容，支持“FastAPI 本地手动初始化 PostgresSaver”与“LangGraph 托管环境自动注入 checkpointer/store”两条运行链路。

### 变更内容
- **核心运行时重构**:
  - `backend/app/agent/service.py` 新增运行模式识别
  - `SQLAgentService` 支持注入 `checkpointer` / `store`
  - 本地独立运行模式下自动回退创建 `ConnectionPool + PostgresSaver`
  - 移除模块级 `logging.basicConfig(...)` 与导入即初始化的全局 `agent_service`
- **LangGraph 入口调整**:
  - `langgraph.json` 从模块级对象切换为工厂函数入口 `backend/app/agent/service.py:build_agent_graph`
  - 兼容 LangGraph CLI 的 `config + runtime` 工厂调用约束
- **FastAPI 兼容层重构**:
  - `backend/app/services.py` 改为兼容适配层
  - 保留 `process_message()` / `process_stream()` 与 `tool_calls/tool_results` 旧返回契约
  - API 层无需调整请求/响应结构
- **文档同步**:
  - `README.md` 更新 `services.py` 与 `agent/service.py` 的职责说明
  - 补充 FastAPI / LangGraph CLI 双模式持久化说明

## 2026-03-27 13:55 - 修正 Codex 环境中的 LangGraph 启动命令

### 概述
修正 `.codex/environments/environment.toml` 中的 LangGraph 启动配置，避免因命令名写错且未先激活 `py312_agent` 环境而导致 PowerShell 报错找不到命令。

### 变更内容
- **环境配置修正**:
  - 为 `.codex/environments/environment.toml` 补充 `setup.script = "conda activate py312_agent"`
  - 将错误的 `Langgraph dev --allow-blocking` 修正为 `langgraph dev --allow-blocking`

## 2026-03-27 13:35 - LangGraph Dev 启动补充 conda 环境切换

### 概述
为 `langgraph dev --allow-blocking` 这条本地调试命令补充明确的 conda 环境切换要求，避免未激活 `py312_agent` 时出现依赖或解释器不一致问题。

### 变更内容
- **新增启动脚本**:
  - 新增根目录 `start_langgraph_dev.bat`
  - 在执行 `langgraph dev --allow-blocking` 前自动执行 `conda activate py312_agent`
- **README 同步**:
  - 新增 LangGraph Dev 调试入口说明
  - 明确先激活 `py312_agent`，并补充 Windows CMD 下的脚本启动方式

## 2026-03-27 13:10 - 新增代码阅读与解释子智能体

### 概述
为项目补充一个专门用于“读代码、讲架构、梳流程、看调用链”的子智能体 `code-explainer`，同时提供项目级 `skill` 版本，方便在不同 Agent / CLI 场景下复用，帮助更快理解仓库结构与实现机制。

### 变更内容
- **新增子智能体定义**:
  - 新增 `.claude/agents/code-explainer.md`
  - 约束其聚焦代码阅读、架构讲解、流程拆解与调用链分析
- **新增项目级 Skill**:
  - 新增 `.agents/skills/code-explainer/SKILL.md`
  - 统一沉淀代码解释类任务的工作流、输出结构与边界
- **README 同步**:
  - 补充“代码阅读讲解子智能体”能力说明
  - 在项目结构中新增 `.claude/agents/` 与 `.agents/skills/code-explainer/` 入口

## 2026-03-24 16:35 - LangGraph 调试链路补充显式 LLM 超时与重试配置

### 概述
针对 `langgraph.json -> backend/app/agent/service.py` 这条开发调试链路，补充显式的网络 LLM 超时与重试配置，避免完全依赖底层 SDK 默认值，提升 OpenAI-compatible 远程模型调用时的可控性。

### 变更内容
- **配置增强**:
  - 在 `backend/app/config.py` 新增 `LLM_TIMEOUT` 与 `LLM_MAX_RETRIES`
  - 在根目录 `.env` 增加对应默认配置项
- **Agent 服务增强**:
  - 在 `backend/app/agent/service.py` 的 `ChatOpenAI` 初始化中显式传入 `request_timeout` 与 `max_retries`
  - 使 `langgraph.json` 调试入口下的远程模型调用具备项目级可调的超时与重试策略

## 2026-03-24 16:05 - llama.cpp + Qwen3 Embedding 实践文档重构与沉淀

### 概述
将 `backend/docs/llamacpp-qwen3-embedding-local-deployment.md` 从“本地部署操作说明”升级为“完整改造与复用实践文档”，系统整理本次 `llama.cpp + Qwen3 Embedding` 接入 Milvus Hybrid RAG 的架构、流程、接口协议、部署方式、排障经验与后续复用建议。

### 变更内容
- **文档重构**:
  - 重新组织为“背景目标、相关目录、总体架构、配置设计、建库流程、查询流程、API 格式、部署步骤、排障、最佳实践、开发心智”分层结构
  - 补充项目内关键代码落点与目录索引，方便后续快速定位
  - 明确 `query instruction`、`L2 normalize`、`provider 切换后需重建索引` 等关键约束
- **README 入口同步**:
  - 在技术文档列表中新增 `llama.cpp + Qwen3 Embedding 接入与复用最佳实践` 链接
  - 方便后续从项目首页直接跳转到该专题文档

## 2026-03-24 15:35 - README 项目结构树同步更新

### 概述
对照当前仓库实际目录结构，更新 `README.md` 中的“项目结构”章节，修正已过时的路径描述，并补充当前已经落地的 RAG / llama.cpp 相关目录入口。

### 变更内容
- 将 `requirements.txt` 与 `.env` 的位置修正为仓库根目录
- 补充 `backend/docs/`、`backend/llamaCpp/`、`backend/app/test_*.py` 等实际存在的目录 / 文件入口
- 在 `backend/app/agent/vector/` 结构中补充 `embedding_provider.py`
- 保持目录树为“精简但准确”的项目入口视图，避免 README 演变成全量文件清单

## 2026-03-24 15:20 - README 与文档入口同步修正

### 概述
对照当前仓库结构与最新 RAG / llama.cpp 接入实现，修正了 `README.md` 中已过时的环境与依赖说明，避免按旧说明执行时找不到 `.env.example` 或 `backend/requirements.txt`。

### 变更内容
- **README 修正**:
  - 将“复制 `.env.example`”改为“直接使用 / 新建根目录 `.env`”
  - 将后端依赖安装入口统一为根目录 `requirements.txt`
  - 将后端启动命令统一为从仓库根目录执行 `uvicorn backend.app.main:app`
- **文档一致性检查**:
  - 复核 `README.md` 与当前 `llama.cpp + Qwen3 Embedding` / `Milvus Hybrid` 实现是否一致
  - 保持既有历史 changelog 记录不变，仅在最新条目中补充当前有效的使用说明

## 2026-03-24 14:30 - Milvus 混合检索支持 llama.cpp + Qwen3 Embedding 切换

### 概述
在保留原有 `Ollama qwen3-embedding:0.6b` 能力的基础上，为 Milvus Hybrid RAG 新增 `llama.cpp + Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0` 的可切换嵌入方案。初始化入库与运行期检索统一复用同一个 LlamaIndex embedding provider 入口，并在 `llama.cpp` 路径下对 query 侧启用 Qwen 官方推荐的 instruction-aware embedding 格式。

### 变更内容
- **共享 Embedding Provider**:
  - 新增 `backend/app/agent/vector/embedding_provider.py`
  - 统一封装 `OllamaEmbedding` 与自定义 `LlamaCppEmbedding`
  - 新增 `QwenInstructionAwareEmbedding`，只对 query 侧拼接 `Instruct: ...\nQuery: ...`
- **Milvus 接入改造**:
  - `backend/app/agent/vector/factory.py` 改为通过共享 provider 配置 `LlamaIndex Settings.embed_model`
  - `backend/app/agent/vector/milvus_init/init_store.py` 改为复用同一 provider，保证建库与查询一致
- **配置增强**:
  - `backend/app/config.py` 新增 `EMBEDDING_PROVIDER`、`LLAMA_CPP_EMBED_*`、`QWEN_QUERY_INSTRUCTION_*` 配置项
  - `.env` 补充 `llama.cpp` embedding 的默认配置示例
- **测试补充**:
  - 新增 `backend/app/test_embedding_provider.py`
  - 修正 `backend/app/test_rag_milvus_hybrid.py` 中的延迟初始化与 mock 覆盖方式
- **文档同步**:
  - `README.md` 增补 Milvus embedding provider 切换说明与重建索引提示


## 2026-03-22 22:50 - Milvus 嵌入模型迁移至本地 Ollama (Qwen3)

### 概述
将 Milvus 混合检索所依赖的嵌入模型由原有的 NVIDIA 云端 API 迁移至本地私有化部署的 `Qwen3-Embedding-0.6B`（通过 Ollama 托管）。同时解决了本地代理环境导致的 502 请求拦截问题，保持了检索链路的完全离线化。

### 变更内容
- **模型替换**: 在 `backend/app/agent/vector/factory.py` 和 `milvus_init/init_store.py` 中，使用 `OllamaEmbedding` 替换 `NVIDIAEmbedding`。
- **配置增强**:
  - `backend/app/config.py` 新增 `ollama_embed_model` 环境变量项。
  - **网络优化**: 在全局配置中强制设置 `NO_PROXY` 环境变量，自动绕过系统代理对 `localhost` 的拦截（修复 502 错误）。
- **文档同步**: 更新了 `backend/docs/RAG架构与技术总结.md`，反映了最新的模型架构选型。
- **环境变量**: `.env` 中新增 `OLLAMA_EMBED_MODEL` 参数并完成注释。


## 2026-03-22 21:35 - 新增 RAG 架构与技术栈剖析文档

### 概述
根据现有代码库实现，整理并输出了完整的 Retrieval-Augmented Generation (RAG) 架构设计文档，详细剖析了系统目前的双引擎检索架构、核心组件与模型选型以及工作流执行逻辑。

### 变更内容
- **新增文档**: `backend/docs/RAG架构与技术总结.md`
  - 阐述了 Milvus Hybrid 和 PGVector 双引擎的实现与切换机制。
  - 整理了 Embedding 模型（NVIDIA V5、BAAI BGE-M3）及 Reranker（Mistral-4B）选型细节。
  - 总结了完整的 RAG 数据检索与合成流向。

---
## 2026-03-22 18:00 - SQL 查询结果智能限流与安全防护优化

### 概述
针对大模型处理大量 SQL 查询结果时面临的上下文溢出、推理降智、Token 成本激增等问题，实施了一套弹性限流方案。小结果集（如维度表）全量返回，大结果集自动截断并注入预警，同时新增 CSV 导出工具实现数据与 LLM 的安全隔离。

### 变更内容

#### `backend/app/config.py` + `.env`
- **新增 `sql_result_hard_limit`**：后端强制截断行数上限（默认 1000），保护内存和 LLM 上下文
- **新增 `sql_result_preview_rows`**：超限时给 LLM 展示的预览行数（默认 5）

#### `backend/app/agent/tools/sql_tools.py`
- **新增 `_estimate_row_count()`**：估算 LangChain 返回结果字符串中的行数
- **新增 `_extract_preview_rows()`**：从结果字符串中提取前 N 行作为预览
- **`sql_db_query` 增强**：新增第 5 步"智能结果限流"——判断结果行数是否超过 `hard_limit`，超限时只返回预览 + 系统截断警告（引导 LLM 建议聚合 SQL 或 CSV 导出）

#### `backend/app/agent/tools/csv_export_tool.py` [NEW]
- **新增 `export_to_csv` 工具**：使用 SQLAlchemy + CSV 模块直接从数据库导出完整数据到文件，全程不经过 LLM 上下文。包含与 `sql_db_query` 一致的安全拦截和技能校验

#### `backend/app/agent/service.py`
- **工具注册**：在 `_prepare_tools` 中注入 CSV 导出工具
- **System Prompt 优化**：新增两条规则——强制使用聚合函数进行统计分析；超限时禁止基于截断数据汇总

---

## 2026-03-21 21:01 - SQL Agent 安全审计与拦截增强 (对策 3)

### 概述
针对 SQL Agent 存在的潜在 SQL 注入及破坏性操作风险（如 `DROP`, `DELETE` 等），实施了基于正则表达式的黑名单拦截机制（代码层硬校验），确保 Agent 仅能执行只读查询。

### 变更内容

#### `backend/app/agent/tools/sql_tools.py`
- **新增 `FORBIDDEN_SQL_PATTERN`**：定义了包含 `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` 等危险关键字的正则表达式。
- **`sql_db_query`**：在执行逻辑最前端注入安全性拦截。任何匹配非法关键字的查询将被直接终止，并向 LLM 返回严重安全警告。

### 防御效果
- **防止提示词注入**：即使 LLM 被诱导产生破坏性 SQL，也会在执行前被逻辑层拦截。
- **操作审计**：拦截行为会记录到日志，方便安全审计。

---

## 2026-03-21 20:43 - SQL 工具技能精确校验优化

### 概述
参考 LangChain 官方 `skills-sql-assistant` 方案，修复了在 **Checkpointer 多轮对话**场景下，LLM 因 `skills_loaded` 状态已存在而跳过 `load_skill` 调用，直接执行跨业务域 SQL 查询的潜在问题。

### 变更内容

#### `backend/app/agent/tools/sql_tools.py`
- **`sql_db_query`**：新增 `required_skill: str` 参数，将技能校验从 `if not skills_loaded` 升级为 `if required_skill not in skills_loaded`（精确校验特定技能是否已加载，而非仅判断列表是否为空）
- **`search_saved_correct_tool_uses`**：同步新增 `required_skill: str` 参数，做相同精确校验，两个工具行为一致
- 返回值类型从 `List[dict]` 更新为 `Union[str, List[dict]]`，修复 Lint 错误

#### `backend/app/agent/service.py`
- 系统提示词的 **SQL查询规则** 章节新增说明：调用 `sql_db_query` 和 `search_saved_correct_tool_uses` 时，必须通过 `required_skill` 参数声明所依赖业务技能，切换业务域时必须重新调用 `load_skill()`

### 问题场景与修复效果

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 第1轮：涂装问题 | `skills_loaded=["paint_shop"]`，正常执行 | 同左 |
| 第2轮：焊装问题 | 由于列表非空，直接调 SQL（**幻觉风险**）| 工具返回 Error，强制 LLM 先 `load_skill("weld_shop")` |

---

## 2026-02-22 14:35 - 完善 Milvus 混合检索环境变量配置

### 概述
在 `.env` 文件中补齐了 Milvus 混合检索后端所需的全部环境变量，包括连接地址、Collection 命名、向量维度、RRF 融合系数以及数据导入路径等，并将 `RAG_BACKEND` 默认指定为 `milvus_hybrid`。

### 变更内容
#### 修改文件
- **.env**: 
  - 新增 `RAG_BACKEND='milvus_hybrid'`。
  - 新增 `MILVUS_URI`, `MILVUS_COLLECTION_NAME` 等系列配置。
  - 新增 `MILVUS_DATA_DIR` 指向默认示例数据路径。
  - 新增 `MILVUS_OVERWRITE='true'` 默认覆盖策略。

---

## 2026-02-21 15:30 - 扩展混合检索后端（LlamaIndex + Milvus）

### 概述
在现有「可插拔 RAG 架构」基础上新增了 **Milvus 混合检索**（稠密向量 + BM25 稀疏向量 + RRF 融合）后端。通过切换配置即可在 `pgvector` 和 `milvus_hybrid` 之间无感切换，同时新增了配套的数据初始化与导入模块。

### 变更内容

#### 新增检索模块
- **backend/app/agent/vector/milvus_hybrid/**: LlamaIndex + Milvus 检索实现
  - `milvus_store.py`: 封装 MilvusVectorStore 的创建、加载与 BM25 索引配置。
  - `milvus_retriever.py`: 实现 `MilvusHybridRetriever`，适配 `BaseRetriever` 接口。
- **backend/app/test_rag_milvus_hybrid.py**: 冒烟测试脚本。

#### 新增初始化模块
- **backend/app/agent/milvus_init/**: Milvus 专用数据导入脚本包（与 `vector_init` 风格一致）
  - `milvus_data_importer.py`: 支持数据转换、语义切片、Collection 初始化及批量入库逻辑。
  - `milvus_import_data.py`: CLI 入口脚本，支持 `--overwrite` 重建索引和追加导入。

#### 配置与工厂更新
- **backend/app/config.py**: 新增 `RAG_BACKEND` (默认 `pgvector`) 及 `MILVUS_*` 系列配置项。
- **backend/app/agent/vector/factory.py**: 重构工厂函数实现多后端分发逻辑。

### 初始化用法示例

```bash
conda activate py312_agent
# 首次初始化或重建索引（使用 examples 数据）
python -m backend.app.agent.milvus_init.milvus_import_data example_documentation.json --overwrite
# 追加数据
python -m backend.app.agent.milvus_init.milvus_import_data example_ddl.json
```

---

## 2026-02-18 17:45 - 集成 NVIDIA Rerank 精排层

### 概述
在现有 RAG 管道（向量检索 → score_threshold 过滤 → 注入系统消息）中插入 Rerank 精排层，使用 NVIDIA NIM 的 `rerank-qa-mistral-4b` 模型对候选文档进行二次排序，提升检索精度。

### 变更内容

#### 新增文件
- **backend/app/agent/utils/rerank_service.py**: NVIDIA NIM Rerank 服务封装
  - `NvidiaRerankService` 类，调用 NVIDIA Rerank API
  - 支持 `top_n` 截断和 `score_threshold` 阈值过滤
  - 异常时自动降级为原始排序（不影响现有功能）
- **backend/app/test_rerank.py**: Rerank 测试脚本（降级测试 + API 连通性测试）

#### 修改文件
- **backend/app/config.py**: 新增 Rerank 配置项
  - `rerank_enabled`（开关，默认 false）
  - `rerank_model`（模型，默认 `nvidia/rerank-qa-mistral-4b`）
  - `rerank_top_n`（保留数，默认 3）
  - `rerank_score_threshold`（可选阈值）
- **backend/app/agent/middleware/rag_middleware.py**: `BusinessRagMiddleware.__init__` 新增 `rerank_service` 参数；`before_model` 在向量检索后、格式化前插入 Rerank 调用
- **backend/app/agent/service.py**: 初始化 `NvidiaRerankService` 并传入 `BusinessRagMiddleware`，启用时 `doc_k` 从 5 提升到 10
- **文档更新**: `README.md` 中新增「RAG 召回与参数详解」章节，包含召回数量规则汇总表和详细的环境变量说明。
- **文档更新**: 全面翻新 `README.md`，更新项目结构树以匹配 Agent V2 模块化架构；更正过时的 Multi-Step SQL 工作流程描述为最新预加载 Schema 与中间件机制；修正环境依赖（Python 3.12+），并对齐 `.env` 中的 SQL 限流默认值。
- **配置说明**: 在环境变量章节补充了 `RAG_SIMILARITY_THRESHOLD` 和 `RERANK_SCORE_THRESHOLD` 的使用建议及其与 RRF 分数的关联。
- **代码调整**: (由用户手动执行) 将 `service.py` 中未开启精排时的默认召回数量由 3 提升至 5，增强基础召回范围。
- **.env**: 新增 `RERANK_ENABLED`、`RERANK_MODEL`、`RERANK_TOP_N` 等环境变量

### 架构变化
```
改动前：向量检索(k=5) → score_threshold 过滤 → 注入系统消息
改动后：向量检索(k=10) → score_threshold 粗筛 → Rerank 精排(Top-3) → 注入系统消息
```

### 测试结果
- 降级测试通过：无效 API Key 时正确回退
- API 连通性测试通过：L3F13 相关查询中，Rerank 正确将 L3F13 文档排到第一（score=3.0371）

### 推荐配置

为获得最佳效果，建议在 `.env` 中使用以下配置：

```bash
RERANK_ENABLED="true"
RERANK_MODEL="nvidia/rerank-qa-mistral-4b"
RERANK_TOP_N="3"
RERANK_SCORE_THRESHOLD="0.0" # 过滤掉负分结果（不相关文档）
```

---

## 2026-01-27 16:37 - 修复流式聊天 API 路径配置

### 问题
- `frontend/src/api/chat.ts` 中的流式请求硬编码了 `http://localhost:8000/api/chat`
- 导致在生产环境通过 Nginx 代理时无法正常访问后端
- 其他 API（sessions、messages）使用相对路径 `/rearch` 正常工作，但流式聊天请求失败

### 解决方案
- 修改 `API_BASE` 从 `'http://localhost:8000/api/chat'` 改为 `'/rearch/api/chat'`
- 统一所有 API 请求都通过 Nginx 代理访问后端
- 确保开发和生产环境的一致性

### 技术细节
```typescript
// 修改前
const API_BASE = 'http://localhost:8000/api/chat'

// 修改后
const API_BASE = '/rearch/api/chat'  // 使用相对路径，适配 Nginx 代理
```

---

## 2026-01-27 13:55 - Docker 容器化部署方案

### 概述
为后端FastAPI应用创建完整的Docker容器化部署方案，支持一键部署到生产服务器。

### 变更内容

#### 核心配置文件
- **backend/Dockerfile**: 创建后端镜像配置
  - 基于 `python:3.12-slim` 官方镜像
  - 安装系统依赖（gcc, postgresql-client）
  - 复制依赖并安装Python包
  - 暴露8000端口，使用uvicorn启动
  
- **backend/.dockerignore**: 排除文件列表
  - 排除Python缓存、虚拟环境、测试文件等
  - 减小Docker镜像体积

- **docker-compose.yml**: 容器编排配置（更新）
  - 新增 `backend` 服务：FastAPI应用容器
  - 保留 `postgres` 服务：PostgreSQL 17-alpine
  - 配置服务依赖：backend依赖postgres健康检查
  - 使用 `.env` 文件管理所有环境变量
  - 数据持久化卷 `pgdata`

- **.env.production**: 生产环境配置模板
  - 数据库配置（PostgreSQL）
  - LLM配置（DeepSeek/Ollama）
  - Agent配置（温度、Token限制）
  - LangSmith配置（可选）
  - 详细的注释说明

#### 部署文档
- **deploy/README.md**: 完整部署指南
  - 快速部署步骤（服务器准备、上传文件、配置、启动）
  - 常用管理命令（启停、日志、调试）
  - Nginx反向代理配置示例
  - 故障排查指南
  - 安全建议和数据备份方法

### 部署流程

```bash
# 1. 上传项目到服务器
scp -r rearch_agent/ user@server:/opt/

# 2. 配置环境变量
cd /opt/rearch_agent
cp .env.production .env
nano .env

# 3. 一键启动
docker-compose up -d --build

# 4. 验证
curl http://localhost:8000/
```

### 技术特点
- ✅ 简洁：最小化配置，只包含必要组件
- ✅ 完整：包含数据库、后端服务和详细文档
- ✅ 灵活：通过环境变量轻松切换配置
- ✅ 可靠：健康检查、自动重启、数据持久化
- ✅ 易维护：详细的操作文档和故障排查指南

---

## 2026-01-26 17:45 - 修复 PostgreSQL Checkpointer 初始化错误

### 问题
- LangGraph 的 `PostgresSaver.setup()` 使用 `CREATE INDEX CONCURRENTLY` 创建索引
- 该命令不能在事务块中运行，导致初始化失败
- 错误信息: `ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`

### 解决方案
- **backend/app/services.py**: 修改 checkpointer 初始化逻辑
  - 使用独立的 `psycopg.connect()` 连接并开启 `autocommit=True` 模式执行 `setup()`
  - setup 完成后再创建 `ConnectionPool` 用于正常操作
  - 添加详细的日志输出，便于诊断数据库连接问题

### 技术细节
```python
# 使用 autocommit 模式创建表结构
with psycopg.connect(settings.database_url, autocommit=True) as setup_conn:
    temp_checkpointer = PostgresSaver(setup_conn)
    temp_checkpointer.setup()

# 然后创建连接池用于正常操作
self.conn_pool = ConnectionPool(conninfo=settings.database_url, ...)
self.checkpointer = PostgresSaver(self.conn_pool)
```

---

## 2026-01-26 - 配置本地 llama.cpp 服务器
- **Backend 配置**: 将 LLM 从 DeepSeek API 切换到本地 llama.cpp 服务器。
  - 服务器地址: `http://172.22.44.99:8089/v1`
  - 模型: GLM-4.7-Flash-Q6_K.gguf
  - 使用 `ChatOpenAI` 客户端，兼容 OpenAI API 格式


## 2026-01-24: Agent V2 重构与架构升级

### 概述
基于 CR 反馈完成了 Agent V2 的重构工作，通过高度模块化的设计提升了代码的可维护性、可扩展性和可测试性。引入了基于技能（Skills）的动态上下文管理机制，并强化了 SQL 执行的安全性和准确性。

### 变更内容
- **模块化架构 (`backend/app/agent/`)**: 将原有的单文件服务拆分为功能独立的模块：
  - `service.py`: 核心服务编排
  - `middleware/`: 包含 `SkillMiddleware` 等中间件
  - `tools/`: 包含 `WrappedQueryTool` 等增强工具
  - `constants.py` & `utils`: 常量与通用工具函数
- **技能系统 (Skills System)**:
  - 引入 `SkillMiddleware`，支持按需加载业务领域的知识（Skills）到系统提示词。
  - 新增 `load_skill` 工具，允许 Agent 在运行时动态获取特定领域的详细文档和规则。
- **增强型 SQL 执行**:
  - **前置检查**: 集成了 SQL 语法验证器。
  - **后置处理**: 统一对查询结果进行 ISO 8601 日期格式化清洗，彻底解决时间格式不一致导致的大模型推理错误。
- **配置与日志优化**: 
  - 优化了代理（Proxy）环境变量的自动清理逻辑。
  - 统一了日志格式，支持开发模式下的详细日志输出。

---

## 2026-01-21: PostgreSQL 数据库配置扩展

### 概述
为 rollerbed tracking system 添加了独立的 PostgreSQL 数据库连接配置，保留原有 agent memory 数据库配置。

### 变更内容
- **.env**: 新增 `ROLLERBED_DATABASE_URL` 及相关连接参数
  - `ROLLERBED_POSTGRES_USER='root'`
  - `ROLLERBED_POSTGRES_PASSWORD='root'`
  - `ROLLERBED_POSTGRES_DB='rollerbed_tracking_db'`
  - `ROLLERBED_POSTGRES_HOST='localhost'`
  - `ROLLERBED_POSTGRES_PORT='5432'`
- **backend/app/config.py**: 在 `Settings` 类中添加对应的配置字段
  - `rollerbed_database_url`: 完整的数据库连接 URL
  - `rollerbed_postgres_user`, `rollerbed_postgres_password`, `rollerbed_postgres_db`, `rollerbed_postgres_host`, `rollerbed_postgres_port`: 各个连接组件

### 使用说明
```python
from backend.app.config import settings

# 使用完整 URL
db_url = settings.rollerbed_database_url

# 或者使用单独的组件
host = settings.rollerbed_postgres_host
port = settings.rollerbed_postgres_port
user = settings.rollerbed_postgres_user
password = settings.rollerbed_postgres_password
database = settings.rollerbed_postgres_db
```

---

## 2026-01-17: LangGraph 1.0+ SQL Agent 实现

### 概述
新增 `backend/app/services_graph.py`，基于官方 LangGraph SQL Agent 文档实现了一个现代化的多步骤 SQL Agent 工作流，作为原 `services.py` 的对比版本。

### 变更内容
- **backend/app/services_graph.py**: 新增 LangGraph 1.0+ 版本的 `SQLGraphService` 类。
- **模型**: 从本地 Ollama (qwen3) 切换为 DeepSeek (联网大模型)，提升 SQL 生成准确率。
- **架构**: `list_tables` → `get_schema` → `generate_query` → `check_query` → `run_query`
- **SQL 查询检查器**: 在执行前由 LLM 检查常见 SQL 错误。
- **日期格式清洗**: 策略 A - 无条件对所有查询结果进行 ISO 8601 日期格式标准化。
- **深度工具包装**: `services.py` 中对 `sql_db_query` 工具进行了包装，确保模型在中间推理步骤中看到的是清洗后的日期。

### 技术要点
- 使用 `StateGraph` + `ToolNode` (LangGraph 1.0+ API)
- 保留 `PostgresSaver` 检查点持久化
- 兼容原有 `process_message` 和 `process_stream` 接口

---

## 2026-01-17: 数据库日期时间处理分析与文档化

### 概述
完成并固化了关于 Agent 处理数据库日期时间字段的调研分析，预防大模型（LLM）在时间比较时可能产生的逻辑错误。

### 变更内容
- **docs/database_datetime_analysis.md**: 新增分析报告，详细对比了 SQL 层转换与 Python 工具层转换的优劣，并推荐在代码层进行 ISO 8601 标准化。
- **最佳实践**: 记录了 `DD/MM/YYYY` 等非标格式转换为标准 `YYYY-MM-DD` 的代码实现方案。

---


## 2026-01-16: UI/UX 全面升级与后端数据库依赖修复

### 概述
完成了全系统的 UI/UX 视觉方案升级，由原有的“暖色调”切换为现代化的“神经元色调 + AI 紫色” (Neural Tones + AI Purple) 设计。同时解决了后端在连接 MySQL 8.0+ 时由于缺少 `cryptography` 库导致的身份验证失败问题。

### 变更内容

#### Frontend (UI/UX 升级)
- **Design System**: 引入了以 Slate (Neural) 为基础、Violet (AI Purple) 为点缀的新设计系统。
- **tailwind.config.js**: 
  - 重构颜色体系，新增 `primary` (Violet 600), `secondary`, `neutral` (Slate) 调色板。
  - 定义语义化背景 `background` (#FAF5FF) 和文本颜色。
  - 优化 `boxShadow` (soft/glow) 和 `borderRadius`。
- **index.html**: 接入 Google Fonts (**Inter** 字体)。
- **style.css**: 
  - 移除旧版 `--color-warm-*` 变量，迁移至新的设计系统变量。
  - 实现毛玻璃效果 (`.glass`) 和现代化滚动条样式。
  - 重构全局组件样式 (Button, Input, Animations)。
- **Vue Components**: 重构了以下系列组件的模版和样式：
  - `App.vue`: 根布局样式调整。
  - `ChatView.vue`: 侧边栏与主区域渐变效果。
  - `SessionItem.vue` / `SessionList.vue`: 列表交互状态与空状态美化。
  - `MessageItem.vue` / `MessageList.vue`: 消息气泡渐变与打字动画优化。
  - `ToggleSwitch.vue` & `EmptyState.vue`: 视觉一致性对齐。

#### Backend (数据库连接修复)
- **requirements.txt**: 新增 `cryptography==42.0.5`。
- **Dependency Fix**: 修复了 `PyMySQL` 报错 `RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods`，支持了 MySQL 8.0 的高级加密认证。

---


## 2026-01-15: 修复 Ollama 持续时间格式与远程连接配置

### 概述
修复了 Ollama 在接收 `keep_alive` 参数时的 400 格式错误，并配置后端连接到远程服务器，同时切换为支持工具调用的模型。

### 变更内容
- **backend/app/config.py**: 将 `ollama_keep_alive` 强制转为 `int`，解决 `time: missing unit in duration` 报错。
- **.env**:
  - 更新 `OLLAMA_BASE_URL='http://172.22.44.99:11434'` 指向远程 5090 服务器。
  - 更新 `OLLAMA_MODEL='qwen3:30b'` 以支持 SQL Agent 所需的工具调用功能。
  - 更新 `OLLAMA_KEEP_ALIVE=-1` 为整数形式。

---


## 2026-01-14: 切换到 Ollama + Qwen3:30b

### 概述
将后端 LLM 从 DeepSeek API 切换到本地 Ollama 服务，使用 `qwen3:30b` 模型，充分利用 RTX 5090 显存。

### 变更内容

#### backend/app/config.py
- 新增 Ollama 配置参数：
  - `OLLAMA_BASE_URL`: Ollama 服务地址 (默认 `http://localhost:11434`)
  - `OLLAMA_MODEL`: 使用的模型 (默认 `qwen3:30b`)
  - `OLLAMA_NUM_CTX`: 上下文窗口大小 (默认 32768，32k tokens)
  - `OLLAMA_KEEP_ALIVE`: 模型驻留设置 (默认 `-1`，永久驻留)

#### backend/app/services.py
- 导入变更：`langchain_deepseek.ChatDeepSeek` → `langchain_ollama.ChatOllama`
- 移除 `httpx` 依赖及 `_no_proxy_client`（Ollama 为本地服务，无需代理处理）
- LLM 初始化更新为 `ChatOllama`，使用新的 Ollama 配置参数

### 使用前准备
```bash
# 1. 安装 langchain-ollama
pip install langchain-ollama

# 2. 拉取模型
ollama pull qwen3:30b
```

### 备注
- 原有 DeepSeek 配置保留在 `config.py` 中，可随时切换回去
- 如需使用 DeepSeek，只需将 `services.py` 中的导入和初始化改回即可


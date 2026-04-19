# llama.cpp 上下文预警开发指南

修改时间: 2026-04-19 Asia/Shanghai

主要修改内容:
- 沉淀“调用前上下文预警”能力从需求澄清、技术选型到最终落地的完整方案
- 说明为什么目标是“单次真实输入上下文控制”，而不是 session 累计 token 统计
- 总结 `llama.cpp /tokenize`、`ContextWarningMiddleware`、`CustomState.context_warning`、前端提醒条之间的完整调用链
- 补充本次实现中遇到的版本差异、状态更新机制、重复事件和 LangSmith 可见性等关键注意事项

## 目录

- [1. 背景](#1-背景)
- [2. 这套方案解决什么问题](#2-这套方案解决什么问题)
- [3. 需求边界与非目标](#3-需求边界与非目标)
- [4. 整体技术架构](#4-整体技术架构)
- [5. 核心执行链路](#5-核心执行链路)
- [6. 分层职责](#6-分层职责)
  - [6.1 配置层](#61-配置层)
  - [6.2 估算层](#62-估算层)
  - [6.3 中间件层](#63-中间件层)
  - [6.4 服务适配层](#64-服务适配层)
  - [6.5 API 与前端展示层](#65-api-与前端展示层)
- [7. 关键设计决策](#7-关键设计决策)
  - [7.1 为什么不是统计 session 累计 token](#71-为什么不是统计-session-累计-token)
  - [7.2 为什么优先用 llama.cpp `/tokenize`](#72-为什么优先用-llamacpp-tokenize)
  - [7.3 为什么保留 `SummarizationMiddleware`，只做预警](#73-为什么保留-summarizationmiddleware只做预警)
  - [7.4 为什么 `context_warning` 要成为正式 CustomState](#74-为什么-context_warning-要成为正式-customstate)
  - [7.5 为什么同时保留 state 更新和 custom `status` 事件](#75-为什么同时保留-state-更新和-custom-status-事件)
- [8. 关键文件与职责](#8-关键文件与职责)
- [9. 开发过程中踩过的坑](#9-开发过程中踩过的坑)
- [10. 注意事项](#10-注意事项)
- [11. 推荐复用步骤](#11-推荐复用步骤)
- [12. 检查清单](#12-检查清单)
- [13. 验证方式](#13-验证方式)
- [14. 后续可选优化](#14-后续可选优化)
- [15. 一句话总结](#15-一句话总结)

## 1. 背景

这次能力建设的核心目标，不是“统计聊天总共用了多少 token”，而是防止**每一次真正塞进 LLM 的输入上下文**超过预设阈值，从而避免本地 `llama.cpp` 推理时上下文过大、KV cache 过高、显存占用过高，最终导致生成不稳定或直接失败。

项目的实际运行前提是：

- 模型服务使用 OpenAI-compatible 的 `llama.cpp` API
- 聊天接口使用 `/v1/chat/completions`
- token 估算接口使用 `llama.cpp` 原生 `/tokenize`
- 项目中已经存在 `SummarizationMiddleware`
- 本次需求只要求**预警**，不要求自动压缩、自动拒绝、自动新建对话

这决定了方案必须放在“模型调用前”，而不是放在“会话统计后”。

## 2. 这套方案解决什么问题

- 在真正调用 LLM 之前，估算本次输入上下文大小
- 在输入上下文接近安全阈值时，向用户提示“建议新建对话”
- 让前端和 LangSmith 都能看到统一的 `context_warning`
- 避免把告警逻辑误建成 session 总账统计或计费统计
- 避免为了预警而破坏现有 `SummarizationMiddleware`、RAG 注入、技能注入逻辑

## 3. 需求边界与非目标

本方案解决的是：

- 单次模型调用前的输入上下文预警

本方案不解决这些事情：

- 不做自动摘要触发
- 不做主动裁剪历史
- 不做请求阻断
- 不做模型计费对账
- 不把 session 累计 token 作为主判定口径

这点非常关键。预警的主指标是：

- `estimated_input_tokens`

而不是：

- `session_total_tokens`
- `provider usage.total_tokens`

## 4. 整体技术架构

最终落地采用了 5 层结构：

1. 配置层：定义预警是否启用、窗口大小、阈值和 `/tokenize` 地址
2. 估算层：通过 `llama.cpp /tokenize` 估算 `system_message`、`messages`、`tools` 的 token 数
3. 中间件层：在最终 `ModelRequest` 上做比较，并生成统一 `context_warning`
4. 服务适配层：把 `context_warning` 从 graph state 和流式事件统一透传给 API 层
5. 前端展示层：在聊天页展示轻量提醒条，不污染 assistant 正文

整体原则是：

- 估算要尽量基于**最终请求**
- 状态要走**正式 graph state**
- 提醒要走**流式 status 事件**
- 不改变现有消息内容和推理流程

## 5. 核心执行链路

当前实现的关键链路如下：

1. 用户发送消息
2. `BusinessRagMiddleware.before_model()` 可能注入业务知识到 `messages`
3. `SummarizationMiddleware` 可能按既有规则整理历史
4. `SkillMiddleware.wrap_model_call()` 追加技能说明到 `system_message`
5. `ContextWarningMiddleware.wrap_model_call()` 基于最终 `ModelRequest` 估算输入 token
6. 如果达到阈值：
   - 记录结构化日志
   - 通过 `emit_stream_status(...)` 发出 `source="context_warning"` 的流式状态事件
   - 通过 `ExtendedModelResponse + Command(update={"context_warning": ...})` 正式写回 graph state
7. 服务层读取：
   - 流式 `custom` 事件用于即时前端提醒
   - 流式 `updates` / 非流式 `ainvoke` 结果用于保留 `context_warning` 状态
8. 前端：
   - 流式模式消费 `status.detail`
   - 非流式模式消费 `ChatResponse.context_warning`
   - 在聊天页顶部显示黄色提醒条

## 6. 分层职责

### 6.1 配置层

主要入口：

- [backend/app/config.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/config.py)
- [.env](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/.env)

核心配置包括：

- `LLM_CONTEXT_WARNING_ENABLED`
- `LLM_CONTEXT_WINDOW`
- `LLM_CONTEXT_WARN_TOKENS`
- `LLM_CONTEXT_SAFETY_BUFFER`
- `LLAMA_CPP_TOKENIZE_BASE_URL`
- `LLM_CONTEXT_TOKENIZER_TIMEOUT`

职责：

- 定义是否开启整套预警能力
- 定义 `llama.cpp` 上下文窗口和项目侧安全阈值
- 定义 `/tokenize` 根地址和超时

### 6.2 估算层

主要入口：

- [backend/app/agent/utils/llama_cpp_token_estimator.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/llama_cpp_token_estimator.py)

职责：

- 调用 `llama.cpp /tokenize`
- 统计文本和 JSON-like 输入的 token 数
- 在接口异常时回退到保守估算

当前估算对象包括：

- `system_message`
- `messages`
- `tools`
- 固定 `safety_buffer`

注意：

- 当前不是复现 provider 内部 chat template 的最终精确计数
- 它是“足够保守、可操作”的预警估算

### 6.3 中间件层

主要入口：

- [backend/app/agent/middleware/context_warning_middleware.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/context_warning_middleware.py)
- [backend/app/agent/state.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/state.py)

职责：

- 在最终 `ModelRequest` 上进行 token 估算
- 生成统一 `context_warning` payload
- 写入正式 graph state
- 向前端发送即时提醒事件
- 打印可观测日志

当前 `context_warning` 已恢复为正式 `CustomState` 字段，并通过 reducer 实现：

- 超阈值时写 payload
- 未超阈值时写 `None`

### 6.4 服务适配层

主要入口：

- [backend/app/services.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py)

职责：

- 非流式：从 `ainvoke()` 结果读取 `context_warning`
- 流式：从 `custom` / `updates` 读取 warning 并去重
- 在 `final` 事件中附带最终 `context_warning`

这一层的关键价值是：

- 把 LangGraph 的状态和事件转换成项目自己的稳定协议

### 6.5 API 与前端展示层

主要入口：

- [backend/app/api.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py)
- [backend/app/schemas.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py)
- [frontend/src/types/index.ts](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts)
- [frontend/src/composables/useChatStream.ts](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/composables/useChatStream.ts)
- [frontend/src/views/ChatView.vue](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/views/ChatView.vue)

职责：

- 定义 `ContextWarningPayload`
- 非流式响应返回 `context_warning`
- 流式 `status` 事件里返回 `detail`
- 前端展示统一提醒条

## 7. 关键设计决策

### 7.1 为什么不是统计 session 累计 token

因为 session 累计 token 和“这一次会不会把本地模型上下文顶满”不是同一个问题。

真正会影响本地显存和 KV cache 的，是：

- **单次请求最终输入给模型的上下文**

而不是历史总消耗。

所以主指标不能是：

- 本轮总 usage
- session 总 token

而必须是：

- `estimated_input_tokens`

### 7.2 为什么优先用 llama.cpp `/tokenize`

因为项目实际运行模型就是 `llama.cpp`，所以预警估算最好尽量贴近它自己的 tokenizer，而不是用通用 tokenizer 做近似。

测试已经证明：

- `/tokenize` 对英文可用
- `/tokenize` 对中文可用

这让它成为当前最可靠的预警基础。

### 7.3 为什么保留 `SummarizationMiddleware`，只做预警

因为需求已经明确：

- 只做提醒
- 不做主动压缩动作

所以正确做法不是改动 `SummarizationMiddleware` 机制，而是把预警中间件放在它之后，让它看到整理后的最终上下文。

### 7.4 为什么 `context_warning` 要成为正式 CustomState

这次开发中一个关键转折点是：

- 最初 `context_warning` 只是临时写到 `request.state`
- 结果 LangSmith 看不到，graph state 也不稳定

升级依赖后，项目终于具备了：

- `ExtendedModelResponse`
- `Command(update=...)`

因此最终恢复为正式 `CustomState` 是合理的。

这让 `context_warning` 现在具备两个作用：

- 前端提醒数据
- LangGraph / LangSmith 可观测状态

### 7.5 为什么同时保留 state 更新和 custom `status` 事件

因为二者解决的问题不同：

- `Command(update=...)`：让状态正式进入 graph state
- `emit_stream_status(...)`：让前端在流式过程中第一时间显示提醒

只保留前者，前端提示不够即时。  
只保留后者，LangSmith 看不到正式状态。

所以当前是双轨，但服务层做了去重，避免同一 warning 弹两次。

## 8. 关键文件与职责

- [backend/app/agent/state.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/state.py)
  - 定义 `CustomState`
  - 定义 `context_warning` reducer

- [backend/app/agent/middleware/context_warning_middleware.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/context_warning_middleware.py)
  - 核心预警中间件
  - 估算、比较、日志、状态更新、custom status 事件

- [backend/app/agent/utils/llama_cpp_token_estimator.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/llama_cpp_token_estimator.py)
  - `llama.cpp /tokenize` 封装

- [backend/app/agent/service.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py)
  - 注册 middleware
  - 组装 agent 初始化链路

- [backend/app/services.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py)
  - FastAPI 兼容服务层
  - 统一处理 stream/invoke 的 warning 透传

- [backend/app/api.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py)
  - 非流式接口输出 `ChatResponse.context_warning`

- [backend/app/schemas.py](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py)
  - 定义 `ContextWarningPayload`
  - 定义 `FinalStreamEvent.context_warning`

- [frontend/src/composables/useChatStream.ts](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/composables/useChatStream.ts)
  - 消费流式与非流式 warning

- [frontend/src/views/ChatView.vue](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/views/ChatView.vue)
  - 展示黄色提醒条

## 9. 开发过程中踩过的坑

### 坑 1：把 `AIMessage.usage_metadata` 当成主方案

讨论初期曾评估过 `usage_metadata`。后来确认它更适合：

- 调用后统计
- 误差校准

但不适合作为调用前预警主方案。

### 坑 2：把 session 累计 token 当主指标

这会把问题从“单次上下文安全”误导成“总账统计”，偏离了本需求。

### 坑 3：把 `request.state[...] = ...` 当成正式 state update

这是本次最典型的实现误区之一。

表现为：

- 前端有时能收到提醒
- 但 LangSmith 看不到
- `state_update.get("context_warning")` 不稳定

升级后最终用 `ExtendedModelResponse + Command(update=...)` 修正。

### 坑 4：custom 事件和 state updates 双发导致重复提醒

恢复正式 state 后，流式通道会同时从：

- custom `status`
- `updates.context_warning`

两边看到同一 warning。

最终在服务层做了归一化和去重，避免前端显示两次。

### 坑 5：把 `context_warning` 一度完全移除

在 `ExtendedModelResponse` 不可用时，移除 `context_warning` 作为 `CustomState` 是合理的临时收口。  
但升级依赖后，如果还停留在“只有 custom status”模式，就失去了 LangSmith 可观测性。

这次最终又把它恢复成正式状态字段。

## 10. 注意事项

- 这个方案依赖当前 `langchain/langgraph` 版本具备 `ExtendedModelResponse`
- 只有当 `LLM_CONTEXT_WARNING_ENABLED=true` 时，预警逻辑才会生效
- `LLAMA_CPP_TOKENIZE_BASE_URL` 必须是不带 `/v1` 的根地址
- 当前估算是保守估算，不应把它误认为 provider 计费口径
- `context_warning` 现在是最近一次模型调用的状态，不是整个 session 的历史统计
- `context_warning` 允许被更新为 `None`，这是为了清空旧告警，不是异常
- 如果未来切换到别的模型服务，不应默认继续复用 `/tokenize` 方案

## 11. 推荐复用步骤

1. 明确目标是“单次输入上下文预警”，不是 session 总账
2. 确认模型服务是否有稳定 tokenizer 接口
3. 在配置层定义：
   - 是否启用
   - 总窗口
   - 预警线
   - 安全冗余
4. 把预警逻辑放在最接近最终 `ModelRequest` 的位置
5. 如果依赖版本支持：
   - 用 `ExtendedModelResponse + Command(update=...)` 写正式 state
6. 同时发 custom `status` 事件，保证前端即时提醒
7. 服务层做去重和协议归一化
8. 前端只展示提醒，不改变正文消息

## 12. 检查清单

- [ ] 已确认模型服务支持 `/tokenize` 或等价能力
- [ ] 已确认 `LLM_CONTEXT_WARNING_ENABLED` 开关存在
- [ ] 已确认 `ContextWarningMiddleware` 位于 `SkillMiddleware` 之后
- [ ] 已确认 `context_warning` 使用正式 state update
- [ ] 已确认流式 `status` 提醒可显示
- [ ] 已确认非流式 `ChatResponse.context_warning` 可返回
- [ ] 已确认不会重复弹两次 warning
- [ ] 已确认 `SummarizationMiddleware` 未被改坏
- [ ] 已确认 LangSmith 能看到 `context_warning`

## 13. 验证方式

本次实现最终验证方式包括：

- 后端单元测试：
  - `test_llama_cpp_token_estimator.py`
  - `test_context_warning_middleware.py`
  - `test_services.py`
  - `test_chart_api.py`
  - `test_agent_service_prompt.py`

- 前端构建：
  - `npm run build`

- 手工验证：
  - 降低 `.env` 中阈值
  - 发送简单消息
  - 确认日志出现：
    - `enabled`
    - `estimated_input_tokens`
    - `warn_tokens`
    - `triggered`
  - 确认前端提示条出现
  - 确认 LangSmith 中能看到 `context_warning`

## 14. 后续可选优化

- 在日志里增加更细的分项统计：
  - `system_tokens`
  - `messages_tokens`
  - `tools_tokens`

- 用 provider 返回的 `usage_metadata.input_tokens` 做误差校准

- 如果后续需要更精细的策略，可追加：
  - soft limit
  - hard limit
  - 自动摘要建议说明

但这些都属于下一阶段，不是当前需求必需项。

## 15. 一句话总结

这套方案的核心不是“统计总共用了多少 token”，而是**在每次真正发给本地 LLM 之前，用最接近最终请求的方式估算输入上下文，并把结果同时变成可观测状态和即时用户提醒**。

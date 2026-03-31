# Changelog

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




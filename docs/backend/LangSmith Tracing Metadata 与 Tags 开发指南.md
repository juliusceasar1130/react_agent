# LangSmith Tracing Metadata 与 Tags 开发指南

修改时间: 2026-03-31 11:30 Asia/Shanghai

主要修改内容:
- 总结本项目 LangSmith tracing metadata / tags 的设计目的、作用与接入方式
- 说明当前 `backend/app/services.py` 中 tracing 字段的生成与合并策略
- 提供后续开发时的字段规范、扩展方式、查看方法与排障建议
- 修正业务域示例，区分“默认安全注入”和“已确认 domain 才注入”的使用方式

---

## 1. 背景与目标

本项目已经开启 LangSmith tracing，并在 FastAPI 聊天入口统一为 Agent 调用补充 tracing metadata / tags。

这项能力的核心目标不是给最终用户增加功能，而是给开发、测试、排障和运维提供可观测性支持：

- 可以按 `session_id` 快速定位某次会话的完整 trace
- 可以按模型、运行模式、RAG 后端过滤问题请求
- 可以对比不同模型或不同配置下的表现差异
- 可以在排查“某次回答为什么异常”时快速缩小范围

当前接入的核心位置：

- `backend/app/services.py`
  - `_build_trace_metadata()`
  - `_build_trace_tags()`
  - `_build_config()`

---

## 2. 这项功能到底有什么作用

简单理解，LangSmith trace 本来只记录“这次链路执行了什么”。加上 metadata / tags 之后，它还能记录“这次链路是在什么业务上下文里执行的”。

例如没有 metadata / tags 时，你只能看到：

- 一次 `ainvoke()` 或 `astream()` 执行
- 模型调用、工具调用、耗时等底层步骤

加上 metadata / tags 后，你还能知道：

- 这是哪个会话：`session_id`
- 这是流式还是非流式：`request_mode`
- 用的是什么模型：`ls_provider` / `ls_model_name`
- 当前使用什么 RAG 后端：`rag_backend`
- 当前运行环境是什么：`runtime_mode` / `env:*`

这对后续开发最直接的价值有四类：

### 2.1 排障

当用户说“某个会话的回答不对”时，可以直接按 `session_id` 搜到对应 trace，而不是在大量运行记录中盲找。

### 2.2 性能分析

可以按 `model:*`、`mode:*`、`rag:*` 过滤，观察不同链路的耗时差异。

### 2.3 行为对比

可以对比：

- `mode:invoke` vs `mode:stream`
- `provider:custom` vs `provider:ollama`
- `rag:milvus_hybrid` vs `rag:pgvector`

### 2.4 成本与稳定性观察

如果后续接入更多 provider 或更完整的 LangSmith 统计，可以更方便地按模型维度看错误率、响应时间和消耗。

---

## 3. 当前项目里已经补充了哪些字段

当前 `backend/app/services.py` 会在每次 `process_message()` / `process_stream()` 调用时自动补 tracing 配置。

### 3.1 Metadata

当前统一补充以下 metadata：

- `session_id`
- `thread_id`
- `request_mode`
- `app_component`
- `runtime_mode`
- `rag_backend`
- `ls_provider`
- `ls_model_name`
- `ls_temperature`
- `ls_max_tokens`

字段说明：

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `session_id` | 会话 ID，用于定位某次聊天 | `0d8a...` |
| `thread_id` | LangGraph 线程 ID，当前与 `session_id` 保持一致 | `0d8a...` |
| `request_mode` | 请求模式 | `invoke` / `stream` |
| `app_component` | 当前调用入口组件 | `fastapi_chat_api` |
| `runtime_mode` | 当前运行模式 | `fastapi_local` |
| `rag_backend` | 当前 RAG 后端 | `milvus_hybrid` |
| `ls_provider` | 模型提供方标识 | `deepseek` / `ollama` / `custom` |
| `ls_model_name` | 模型名 | `deepseek-chat` / `qwen3:30b` |
| `ls_temperature` | 当前采样温度 | `0.7` |
| `ls_max_tokens` | 当前最大输出 token 配置 | `4000` |

### 3.2 Tags

当前统一补充以下 tags：

- `chat-api`
- `sql-agent`
- `mode:invoke` / `mode:stream`
- `runtime:fastapi_local`
- `rag:<backend>`
- `provider:<provider>`
- `model:<model_name>`
- `env:debug` / `env:prod`

这些 tag 更适合在 LangSmith UI 中做快速过滤。

---

## 4. 当前实现的设计原则

### 4.1 统一在兼容层补 tracing

当前 tracing 配置放在 `backend/app/services.py`，而不是散落在各个 API 路由里。这样做有几个好处：

- `invoke` 与 `stream` 两条链路保持一致
- API 层无需重复拼装 tracing 字段
- 后续切换调用入口时，只需要在兼容层统一维护

### 4.2 优先保证稳定字段

当前先补的是稳定、低争议字段：

- 会话维度：`session_id` / `thread_id`
- 模型维度：`ls_provider` / `ls_model_name`
- 请求维度：`request_mode`
- 环境维度：`runtime_mode` / `env:*`
- 检索维度：`rag_backend`

这些字段几乎每次请求都会有，且语义稳定。

### 4.3 保留外部传入配置

当前 `_build_config()` 采用“合并而不是覆盖”的策略：

- 保留外部已有的 `configurable`
- 保留外部已有的 `metadata`
- 保留外部已有的 `tags`
- 默认 tracing 字段作为基础上下文补充进去

这意味着后续业务侧仍然可以继续加自己的 metadata / tags。

---

## 5. 后续开发如何使用这个功能

### 5.1 默认情况下，不需要额外写代码

如果你只是沿用当前的：

- `agent_service.process_message()`
- `agent_service.process_stream()`

那么 tracing metadata / tags 会自动带上，不需要再额外处理。

### 5.2 如果你想补充业务字段

更稳妥的推荐做法是：先传入**当前调用开始时已经确定的字段**。

例如大多数入口一开始只明确知道“来源页面/入口”，但并不知道最终业务域时，可以这样写：

```python
config = {
    "configurable": {"thread_id": str(session_id)},
    "metadata": {
        "entrypoint": "chat_page",
    },
    "tags": [
        "entry:chat_page",
    ],
}
```

然后继续调用：

```python
await agent_service.process_stream(message, session_id, config)
```

当前兼容层会自动把这些字段和默认 tracing 字段合并。

如果 `business_domain` 是调用开始前就**已经被外部系统明确确认**的，例如：

- 会话创建时已经绑定领域
- 路由本身就是固定业务域入口
- 上游显式传入了确定的 domain

那么才适合这样补充：

```python
confirmed_domain = "paint_shop_vehicle_tracking"

config = {
    "configurable": {"thread_id": str(session_id)},
    "metadata": {
        "business_domain": confirmed_domain,
        "entrypoint": "chat_page",
    },
    "tags": [
        f"domain:{confirmed_domain}",
        "entry:chat_page",
    ],
}
```

这里要特别注意：

- `business_domain` 适合来自**确定性来源**
- 不适合直接使用“LLM 猜出来的领域”作为根 trace metadata

推荐来源包括：

- 前端或调用方已经明确传入的业务域
- 会话初始化时绑定的 domain / tenant / skill
- 后端路由或业务配置中已经确定的领域标识

不推荐来源：

- 当前这轮请求中由 LLM 临时推断出来的 domain
- 通过 prompt 理解“猜测”出的业务域

原因是：

- LLM 推断本身可能不稳定
- 根 trace metadata 一旦在请求开始时注入，就应尽量保持稳定
- 如果一开始就写入一个可能错误的 domain，会降低 trace 过滤与统计的可靠性

### 5.3 如果业务域要在运行过程中才能确定，应该怎么做

如果项目里的 `business_domain` 只有在运行过程中才能确定，例如：

- 先由 Agent 调用 `load_skill`
- 再根据 skill 或工具参数确定当前领域

那么更推荐下面三种策略，而不是在请求一开始盲注入：

#### 策略 A：首轮不注入 domain

如果当前轮开始时没有稳定 domain，就不要给根 trace 注入 `business_domain`。

这样做的好处是：

- 不会给 LangSmith 写入不可靠字段
- 后续过滤结果更干净

#### 策略 B：在子链路里补充

如果运行中某个步骤已经明确知道 domain，可以只给对应子 run / 子链路补 metadata，而不是回头修改根 trace。

适合场景：

- skill 已加载完成
- 某个工具参数里已经有 `required_skill`
- 某个 middleware 已经确认领域

#### 策略 C：把已解析 domain 持久化到会话

如果某轮运行过程中成功确定了 `business_domain`，更推荐把它写入：

- session
- 会话上下文
- 服务端状态

这样从**下一轮请求开始**，就可以把它作为稳定字段注入根 trace。

这通常是最稳妥的长期方案。

### 5.4 推荐新增字段的优先级

后续如果要继续扩展，推荐优先增加以下字段：

#### 第一优先级

- `business_domain`
- `entrypoint`
- `feature_flag`

#### 第二优先级

- `user_id` 或匿名用户标识
- `tenant_id`
- `skill_name`

#### 第三优先级

- `request_source`
- `experiment_group`
- `prompt_version`

---

## 6. 字段命名建议

为了后续检索稳定，建议遵循下面的规则。

### 6.1 Metadata 命名

推荐：

- 使用 snake_case
- 使用稳定业务含义
- 尽量避免“同义不同名”

例如：

- `business_domain`
- `request_source`
- `prompt_version`

不推荐：

- `domainName`
- `bizDomain`
- `source1`

### 6.2 Tags 命名

推荐使用 `key:value` 形式：

- `mode:stream`
- `provider:ollama`
- `domain:paint_shop_vehicle_tracking`

这样在 LangSmith 中过滤更直观，也便于后续统一统计。

---

## 7. 如何在 LangSmith 中查看

### 7.1 按会话查

最常见做法：

1. 打开 LangSmith 的 tracing project
2. 在 Filters 中按 `metadata.session_id` 过滤
3. 查看该会话的根 trace 和子 runs

### 7.2 按模型查

可以按以下字段过滤：

- `metadata.ls_provider`
- `metadata.ls_model_name`
- `tags` 中的 `provider:*`
- `tags` 中的 `model:*`

### 7.3 按请求模式查

可以直接看：

- `metadata.request_mode`
- `tags` 中的 `mode:stream`
- `tags` 中的 `mode:invoke`

### 7.4 按 RAG 后端查

可以看：

- `metadata.rag_backend`
- `tags` 中的 `rag:*`

---

## 8. 后续开发中的推荐实践

### 8.1 先保证可过滤，再追求全面

不要一上来加过多临时字段。优先保证：

- 字段语义稳定
- 能长期复用
- 能直接帮助排障

### 8.2 不要把大文本塞进 metadata

metadata 适合放：

- ID
- 枚举值
- 模型名
- 运行模式
- 业务域

不适合放：

- 全量 prompt
- 全量用户输入
- 大段检索结果

这些内容应该继续留在 trace 本身，而不是 metadata。

### 8.3 避免敏感信息

不要把以下信息直接写进 metadata / tags：

- API Key
- 明文密码
- 连接串
- 用户敏感隐私数据

### 8.4 优先在兼容层统一补充

如果字段是所有请求都应该有的，优先加到 `backend/app/services.py`。

如果字段只属于某个特定业务入口，则只在调用该入口时通过 `config` 补充。

---

## 9. 本项目后续建议

当前 tracing 已经够支撑基本排障，但还有几个可继续增强的点：

1. 从 skill / domain 链路中提取稳定 `business_domain`
2. 在特定工具调用场景中补充 `skill_name`
3. 根据运行入口补充 `entrypoint`
4. 如果后续引入实验开关，补充 `feature_flag`

建议顺序：

1. 先补 `business_domain`
2. 再补 `entrypoint`
3. 最后再根据业务需要加实验和租户维度

---

## 10. 开发检查清单

后续如果有人继续扩 tracing，可按这份清单自查：

- 是否优先复用了已有 metadata 名称
- 是否避免写入敏感信息
- 是否采用了 `key:value` 风格 tags
- 是否保证新增字段在 LangSmith 中有明确筛选价值
- 是否保留了外部传入 `config` 的合并能力
- 是否同步更新了 `changelog.md`
- 是否补充了必要文档说明

---

## 11. 结论

LangSmith tracing metadata / tags 本质上是“给 trace 增加业务上下文”的能力。

在本项目中，它的价值主要体现在：

- 快速按 `session_id` 定位问题
- 快速按模型 / 模式 / RAG 后端过滤 trace
- 为后续性能分析、行为对比和排障提供稳定抓手

当前实现已经能满足基础使用；后续开发应继续遵循“统一入口、稳定字段、增量扩展”的原则。

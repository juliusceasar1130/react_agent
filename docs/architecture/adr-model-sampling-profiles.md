# ADR: 模型采样参数动态切换方案

## 状态

已决定 (2026-08-28)

## 背景

当前系统使用 vLLM + Qwen3.8-27B 模型，在思考模式和非思考（快答）模式下需要不同的采样参数组合：

| 参数 | 思考模式 | 快答模式 |
|------|---------|---------|
| temperature | 1.0 | 0.7 |
| top_p | 0.95 | 0.8 |
| presence_penalty | 0.0 | 1.5 |
| reasoning_effort | medium（显式指定） | 不传（模板不读取） |
| enable_thinking | true | false |

**问题**：当前采样参数在 [_create_llm()](backend/app/agent/llm.py) 初始化时从环境变量静态读取，运行时不可变。前端虽然能通过 `enable_thinking` 布尔值控制思考开关（经 [_inject_thinking_config()](backend/app/agent/middleware/prompt_compiler_middleware.py) 中间件注入 `chat_template_kwargs`），但 temperature、top_p、presence_penalty 等采样参数无法随模式切换。

## 决策

### D1. 切换位置：中间件层动态覆写

扩展现有 `_inject_thinking_config()` 中间件方法，在已有的 `enable_thinking` 注入逻辑基础上，增加采样参数的动态覆写。复用已验证的 `configurable → model_settings` 传递路径，不引入新的参数传递通道。

**被否决的方案**：
- 双 LLM 实例预构建：需要改造 agent 的 model 绑定方式，侵入性过大
- 前端传完整参数集：前端需了解后端参数语义，耦合过深

### D2. 配置来源：后端 YAML 配置文件

新建 `backend/app/agent/config/model_sampling_profiles.yaml`，定义思考/快答两档参数组合。YAML 采用显式三段结构（`top_level` / `extra_body` / `chat_template_kwargs`），与 `_create_llm()` 传输分层一一对应，loader 纯机械搬运。服务启动时一次性加载到内存（`lru_cache`），`_load_profiles()` 做 fail-fast 校验（文件存在、两 profile 齐全、无未知段，否则直接抛异常），并在 `_initialize_agent` / `_ainitialize_agent` 中主动触发一次加载校验。不热重载，调参需重启服务。

**被否决的方案**：
- 环境变量扩展（`LLM_THINKING_TEMPERATURE` 等）：参数多时极为臃肿
- 嵌入 config.py：Pydantic 扁平 env 不适合表达"参数组合"这种嵌套结构

### D3. 泛化范围：仅思考/非思考二档

仅支持 `enable_thinking=true` → thinking profile 和 `enable_thinking=false` → fast profile 的二档切换。不引入多 provider、多级别抽象。未来如需多级别，可在 YAML 中增加 `thinkingLevelMap` 并让前端传 `thinking_level` 字段。

### D4. reasoning_effort 与 enable_thinking 同时注入

两字段同时注入（均为 `chat_template_kwargs` 段模板变量）：
- 思考模式：`chat_template_kwargs.enable_thinking=true` + `chat_template_kwargs.reasoning_effort=medium`（显式指定于 YAML）
- 快答模式：`chat_template_kwargs.enable_thinking=false`（`reasoning_effort` 不传，模板不读取）

> **修正（2026-08-28）**：`reasoning_effort` 必须放在 `chat_template_kwargs` 段而非 `extra_body` 顶层。Qwen3 模板渲染时以 `chat_template_kwargs` 的键作为 Jinja2 变量读取 `reasoning_effort`；`extra_body` 顶层参数 vLLM 接受但不传给模板（行为验证：顶层 5 档无差异，模板通道 low/medium/xhigh 输出长度 1864/2338/3858 阶梯递增）。

### D5. 参数分层：复用现有约定

与 [_create_llm()](backend/app/agent/llm.py) 的传输分层完全一致，YAML 采用显式三段结构：
- **top_level**：`temperature`, `top_p`, `presence_penalty`（OpenAI 标准参数）
- **extra_body**：`top_k`, `min_p`, `repetition_penalty`（vLLM 特有参数）
- **chat_template_kwargs**：`enable_thinking`, `reasoning_effort`（Qwen3 模板变量）

loader 按段机械搬运，不做隐式分类。未来新增参数只需放入正确段即可，未识别段名会直接抛异常。

### D6. 双中间件保持现状

[PromptCompilerMiddleware](backend/app/agent/middleware/prompt_compiler_middleware.py) 和 [RagPromptInjectorMiddleware](backend/app/agent/middleware/rag_prompt_injector_middleware.py) 各自保留独立的 `_inject_thinking_config` 方法，共用配置加载模块（`profile_loader.py`）。注入逻辑幂等，重复执行无副作用。

## 后果

- **正面**：最小改动复用现有中间件机制；配置文件集中管理参数；前端无需改动（仅传布尔值）；与 `_create_llm()` 的 init-time 默认值形成 fallback 链
- **负面**：双中间件 `_inject_thinking_config` 代码重复，参数变更需同步两处（但核心逻辑在共享 loader 中，实际重复量极小）；不热重载，调参需重启
- **向后兼容**：当客户端不传 `enable_thinking` 时，中间件不做任何覆写，LLM 使用 `_create_llm()` 的 init-time 默认值，行为与当前完全一致
- **覆写语义**：当客户端传 `enable_thinking` 时，YAML profile 中的参数**全量覆写** `.env` 环境变量对应的 `model_settings` 值。即 `.env` 设置 `LLM_TOP_K=50`，若 YAML thinking profile 中 `top_k=20`，最终发送给 vLLM 的是 `20` 而非 `50`。这是设计意图（profile 作为模式切换的权威参数源），非叠加语义。`_create_llm()` 的 init-time 值仅在 `enable_thinking=None`（不覆写）时生效。

## 传递链路

```
前端 enableThinking (boolean)
  → ChatRequest.enable_thinking
    → config["configurable"]["enable_thinking"]
      → Middleware._inject_thinking_config()
        → get_sampling_profile(enable_thinking)     ← 从 YAML 加载参数组合
        → apply_profile_to_model_settings(...)      ← 按分层规则写入 model_settings
          → model_settings["temperature"] = ...     (顶层)
          → model_settings["extra_body"]["top_k"] = ...  (extra_body)
          → model_settings["extra_body"]["chat_template_kwargs"]["reasoning_effort"] = ...  (chat_template_kwargs)
          → model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] = ...  (chat_template_kwargs)
```

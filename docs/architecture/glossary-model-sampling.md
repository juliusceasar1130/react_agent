# 术语表：模型采样参数动态切换

## 采样参数组合 (Sampling Profile)

YAML 配置文件（`model_sampling_profiles.yaml`）中定义的一组完整的模型采样参数，对应一种运行模式（思考/快答）。每个 profile 包含 `temperature`、`top_p`、`top_k`、`presence_penalty`、`repetition_penalty`、`min_p`、`enable_thinking`、`reasoning_effort` 等字段。

## 思考模式 (Thinking Mode)

`enable_thinking=true` 时激活的运行模式。使用高温度（1.0）、高 top_p（0.95）、无 presence_penalty 的参数组合，`enable_thinking=true`，`reasoning_effort=medium`（YAML 中显式指定）。模型会先进行推理（输出 `<think>` 块）再输出最终答案。

## 快答模式 (Fast Mode)

`enable_thinking=false` 时激活的运行模式。使用低温度（0.7）、低 top_p（0.8）、高 presence_penalty（1.5）的参数组合，`enable_thinking=false`。模型跳过推理直接输出答案。

## 参数分层 (Parameter Layering)

采样参数按 OpenAI SDK 兼容性分为三层传输，YAML 采用显式三段结构与之对应：
- **top_level**：OpenAI 标准参数（`temperature`, `top_p`, `presence_penalty`），直接放在 `model_settings` 根级
- **extra_body**：vLLM 特有参数（`top_k`, `repetition_penalty`, `min_p`），包裹在 `model_settings["extra_body"]` 中以规避 OpenAI SDK 参数强拦截
- **chat_template_kwargs**：Qwen3 模板变量（`enable_thinking`, `reasoning_effort`），包裹在 `model_settings["extra_body"]["chat_template_kwargs"]` 中

loader 按段机械搬运，未识别段名直接抛异常，不靠隐式硬编码分类。

## enable_thinking

vLLM + Qwen3 的思考开关，通过 `chat_template_kwargs.enable_thinking` 传入，控制模型是否生成 `<think>` 推理块。布尔值，前端直接发送。

## reasoning_effort

vLLM 的推理强度控制参数，通过 `chat_template_kwargs.reasoning_effort` 传入（Qwen3 模板变量，渲染时以 `chat_template_kwargs` 的键作为 Jinja2 变量）。可选值：`low`/`medium`/`xhigh`（Qwen3 模板实际值域）。思考模式默认 `medium`。

> **修正（2026-08-28）**：早期版本描述为 `extra_body.reasoning_effort`（顶层），行为验证确认 vLLM 接受顶层参数但不传给模板，必须放入 `chat_template_kwargs` 段才生效。

## thinkingLevelMap

UI 思考级别到 vLLM `reasoning_effort` 值的映射表（`low→low`, `medium→medium`, `high→xhigh`, `max→xhigh`）。`off` 档对应 `enable_thinking=false`（快答模式，模板不读取 `reasoning_effort`）。当前二档方案不使用此映射，思考模式使用配置文件指定的默认值。未来扩展为多级别时可启用。

## _inject_thinking_config

[PromptCompilerMiddleware](backend/app/agent/middleware/prompt_compiler_middleware.py) 和 [RagPromptInjectorMiddleware](backend/app/agent/middleware/rag_prompt_injector_middleware.py) 中的方法，从 LangGraph `configurable` 中读取 `enable_thinking`，动态覆写 `ModelRequest.model_settings` 中的采样参数。在本方案中扩展为按 profile 覆写全部采样参数。

## profile_loader

[backend/app/agent/config/profile_loader.py](backend/app/agent/config/profile_loader.py) 模块，启动时一次性加载 YAML 配置。`_load_profiles()` 做 fail-fast 校验（文件存在、thinking/fast 两 profile 齐全、无未知段，否则直接抛异常），在 `_initialize_agent` / `_ainitialize_agent` 中主动触发。`get_sampling_profile` 返回 `dict(profile)` 浅拷贝防止缓存污染。提供 `get_sampling_profile(enable_thinking: bool)` 和 `apply_profile_to_model_settings(model_settings, profile)` 两个函数供中间件调用。

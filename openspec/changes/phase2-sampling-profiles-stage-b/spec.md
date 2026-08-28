# Phase 2 阶段 B: 中间件接线与 eager load（Sampling Profile Middleware Wiring）

> **分类标签**：`ready-for-agent`
> **方案标识**：`phase2-sampling-profiles-stage-b`
> **架构基准**：[Phase 2 设计方案 §5.2](docs/thinking_mode/phase2_sampling_profiles_design.md)、[ADR: 模型采样参数动态切换](docs/architecture/adr-model-sampling-profiles.md)、[术语表](docs/architecture/glossary-model-sampling.md)
> **前置**：阶段 A（配置层 loader）已完成并通过全部 12 个单元测试

---

## Problem Statement

阶段 A 已完成 `profile_loader` 模块（`get_sampling_profile` / `apply_profile_to_model_settings`），但当前没有任何代码调用它。采样参数组合的动态切换需要两个前置条件：

1. **中间件层接线**：两个中间件（`PromptCompilerMiddleware` 和 `RagPromptInjectorMiddleware`）的 `_inject_thinking_config` 方法需要从"仅注入 `enable_thinking` 布尔值"扩展为"调用 `profile_loader` 加载完整 profile 并覆写全部采样参数"——否则前端切换思考模式时，只有 `chat_template_kwargs.enable_thinking` 变化，而 `temperature`/`top_p`/`presence_penalty`/`reasoning_effort` 等参数仍使用 `_create_llm()` 的 init-time 静态值。

2. **启动时 eager load**：`_load_profiles()` 是 `lru_cache` 惰性加载，若配置有问题（如 YAML 格式错误），首次用户请求时才会暴露——应在服务启动时主动触发一次加载，fail-fast 校验前置到启动阶段。

---

## Solution

1. **扩展两个中间件的 `_inject_thinking_config`**：从 configurable 读取 `enable_thinking`，调用 `get_sampling_profile` → `apply_profile_to_model_settings` 完成 model_settings 覆写；
2. **修改 `service.py`**：在 `_initialize_agent`（同步）和 `_ainitialize_agent`（异步）两条初始化路径开头，主动调用一次 `_load_profiles()` 触发 eager load + fail-fast 校验。

---

## User Stories

1. As a 最终用户, I want 前端切换思考/快答模式时，后端不仅切换思考开关，还同时切换对应的采样参数组合, so that 思考模式模型温度更高、top_p 更大，快答模式更收敛直接。
2. As a 运维工程师, I want 配置错误（YAML 缺失、格式错误、profile 不全）在服务启动时就暴露，而非首次用户请求时才失败, so that 部署问题在上线前即被发现。
3. As a 开发人员, I want 双中间件各自独立注入采样参数，逻辑幂等且无副作用, so that 主 Agent 和 SQL 子智能体路径的行为一致。
4. As a 代码审查者, I want `enable_thinking=None` 时中间件不做任何覆写、保持向后兼容, so that 客户端不传值时的行为与当前完全一致。

---

## Implementation Decisions

### 1. 扩展 `_inject_thinking_config`（双中间件）

两个中间件各自保留独立的 `_inject_thinking_config` 方法（保持现状，D6），共享 `profile_loader` 模块：

```python
def _inject_thinking_config(self, request: ModelRequest) -> None:
    try:
        runnable_config = ensure_config()
        configurable = runnable_config.get("configurable") or {}
        client_enable_thinking = configurable.get("enable_thinking")

        if client_enable_thinking is not None:
            if request.model_settings is None:
                request.model_settings = {}

            profile = get_sampling_profile(client_enable_thinking)
            apply_profile_to_model_settings(request.model_settings, profile)

            logger.info(
                "🛡️ %s: 已注入采样参数组合 (mode=%s)",
                self.__class__.__name__,
                "thinking" if client_enable_thinking else "fast",
            )
    except Exception as e:
        logger.warning("🛡️ %s: 动态注入采样参数组合失败: %s", self.__class__.__name__, e)
```

关键行为：
- `client_enable_thinking=None` → 不做任何覆写，保持向后兼容（Phase 1 行为）；
- `client_enable_thinking=True/False` → 加载对应 profile，三段机械覆写 `model_settings`；
- 注入逻辑幂等，重复执行无副作用；
- 异常被 try/except 兜底（作为中间件层的容错保护），但正常路径在阶段 A 的 fail-fast 保证下不会进入 except。

### 2. service.py eager load（S3 修正）

在 `_initialize_agent`（同步）和 `_ainitialize_agent`（异步）两条初始化路径的开头，主动调用一次 `_load_profiles()`：

```python
from backend.app.agent.config.profile_loader import _load_profiles

# 在 _initialize_agent / _ainitialize_agent 开头：
_load_profiles()  # eager load + fail-fast 校验
```

注意：`_load_profiles` 是 `lru_cache(maxsize=1)`，重复调用无开销；首次调用触发 YAML 加载与 fail-fast 校验，若配置有问题（文件缺失、profile 不全、未知段），直接抛异常阻止服务启动。

### 3. 修改文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/app/agent/middleware/prompt_compiler_middleware.py` | 修改 | 扩展 `_inject_thinking_config` |
| `backend/app/agent/middleware/rag_prompt_injector_middleware.py` | 修改 | 扩展 `_inject_thinking_config`（逻辑与上完全一致） |
| `backend/app/agent/service.py` | 修改 | 双初始化路径开头加 eager load |

---

## Testing Decisions

### 测试 seam

**单一 seam**：中间件实例的 `_modify_request(request)` 方法（和现有 `test_rag_prompt_injector_middleware.py` 的 seam 一致）。构造 `ModelRequest`，通过 `langchain_core.runnables.config.var_child_runnable_config` 设置 `enable_thinking`，调用 `_modify_request`，断言 `model_settings` 结构。

### 测试模块与用例

`backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`（扩展）：

| 用例 | 验证点 |
|------|--------|
| 扩展 `test_rag_prompt_injector_thinking_config` | 补断言 `temperature`/`top_p`/`top_k`/`reasoning_effort` 被注入 model_settings |
| 新增 `test_thinking_false_injects_fast_profile` | `enable_thinking=False` 时注入 fast profile 参数 |
| 新增 `test_enable_thinking_none_no_override` | `enable_thinking=None` 时中间件不覆写 model_settings |

`backend/tests/agent/middleware/` — 新增 PromptCompilerMiddleware 对称测试（文件名待定）：

| 用例 | 验证点 |
|------|--------|
| 新增 `test_prompt_compiler_injects_profile` | PromptCompilerMiddleware（子智能体路径）同样注入 profile 参数 |

**关键约束**：中间件测试涉及 `ensure_config()`，需通过 `var_child_runnable_config` 模拟 LangGraph 运行时上下文（现有测试已使用此模式）。

### Prior art

- `backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`：现有 3 个用例已通过，特别是 `test_rag_prompt_injector_thinking_config` 已使用 `var_child_runnable_config` 模拟 `enable_thinking=True` 的上下文；
- `backend/tests/agent/test_sampling_profile_loader.py`：阶段 A 的 loader 测试已验证 profile_loader 行为正确，中间件测试只需验证"正确调用"而非 profile 内容本身。

---

## Out of Scope

- **端到端验收**：vLLM 请求体网络层抓包、SQL 子智能体路径验证（阶段 C）；
- **changelog.md 更新**（阶段 C 收尾）；
- **前端改动**：前端已传 `enable_thinking` 布尔值，无需修改。

---

## Further Notes

- 本阶段**不新建文件**（阶段 A 已全部新建），仅修改现有文件；
- `prompt_compiler_middleware.py` 和 `rag_prompt_injector_middleware.py` 的 `_inject_thinking_config` 代码重复是设计意图（D6），核心逻辑在共享的 `profile_loader` 中；
- 异常兜底逻辑保留：中间件层的 `try/except` 是容错保护，正常路径（YAML 配置正确时）不会进入 except；若阶段 A 的 fail-fast 和 eager load 都生效，except 分支实际上不会触发；
- service.py 的双初始化路径必须同步修改（AGENTS.md 约定"修改工具注册、中间件装配、RAG 接线时，必须同步更新两边"）。

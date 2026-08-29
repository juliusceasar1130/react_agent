# Phase 2 设计方案：模型采样参数动态切换（思考/快答二档）

> **文档创建时间**: 2026-08-28 Asia/Shanghai
> **关联模块**: `backend/app/agent/middleware/`, `backend/app/agent/llm.py`, `backend/app/agent/config/`
> **前置阶段**: [Phase 1 经验总结](phase1_lessons_learned_qwen_vllm_trace.md) — 思考链 Trace 捕获与模型适配已完成
> **关联文档**: [ADR](../architecture/adr-model-sampling-profiles.md) | [术语表](../architecture/glossary-model-sampling.md)
> **适用场景**: vLLM + Qwen3.8-27B 本地部署，前端切换思考/快答模式时动态应用不同采样参数组合

---

## 1. 需求来源

### 原始需求

用户本地部署 vLLM + Qwen3.8-27B 模型，针对思考模式和非思考（快答）模式分别配置了不同的采样参数组合：

**思考模式配置** (`vllm-192.168.3.26`)：

```json
{
  "baseUrl": "http://192.168.3.26:8089/v1",
  "api": "openai-completions",
  "apiKey": "EMPTY",
  "models": [{
    "id": "gpt-5-nano",
    "name": "Qwen3.8-27B 思考 (vLLM)",
    "contextWindow": 200000,
    "maxTokens": 16384,
    "reasoning": true,
    "thinkingLevelMap": {
      "off": "none", "minimal": "low", "low": "low",
      "medium": "medium", "high": "xhigh", "xhigh": "xhigh", "max": "xhigh"
    },
    "samplingParams": {
      "temperature": 1.0, "top_p": 0.95, "top_k": 20,
      "min_p": 0.0, "presence_penalty": 0.0, "repetition_penalty": 1.0
    }
  }]
}
```

**快答模式配置** (`vllm-192.168.3.26-fast`)：

```json
{
  "baseUrl": "http://192.168.3.26:8089/v1",
  "api": "openai-completions",
  "apiKey": "EMPTY",
  "models": [{
    "id": "gpt-5-nano",
    "name": "Qwen3.8-27B 快答 (vLLM)",
    "contextWindow": 200000,
    "maxTokens": 16384,
    "reasoning": false,
    "samplingParams": {
      "temperature": 0.7, "top_p": 0.8, "top_k": 20,
      "min_p": 0.0, "presence_penalty": 1.5, "repetition_penalty": 1.0
    }
  }]
}
```

**核心需求**：设计一个具有泛化性的方案，在前端开启思考/非思考模型时，应用不同的组合参数。

### 参数差异对比

| 参数 | 思考模式 | 快答模式 | 传输层 |
|------|---------|---------|--------|
| `temperature` | 1.0 | 0.7 | model_settings 顶层 |
| `top_p` | 0.95 | 0.8 | model_settings 顶层 |
| `presence_penalty` | 0.0 | 1.5 | model_settings 顶层 |
| `top_k` | 20 | 20 | extra_body |
| `min_p` | 0.0 | 0.0 | extra_body |
| `repetition_penalty` | 1.0 | 1.0 | extra_body |
| `reasoning_effort` | medium（显式指定） | 不传（模板不读取） | 传输位置由 `REASONING_EFFORT_TRANSPORT` 决定（见 D4 修正） |
| `enable_thinking` | true | false | extra_body.chat_template_kwargs |

---

## 2. 现状分析

### 当前传递链路（Phase 1 已实现）

Phase 1 已完成 `enable_thinking` 布尔值从前端到 vLLM 网络包的端到端传递：

```
前端 enableThinking (boolean, ref(true))
  → ChatRequest.enable_thinking (Optional[bool])
    → config["configurable"]["enable_thinking"]
      → Middleware._inject_thinking_config()
        → model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"]
          → vLLM HTTP 请求体
```

### 核心问题

当前 `_inject_thinking_config()` 只动态注入了 `enable_thinking` 一个布尔值。采样参数（`temperature`, `top_p`, `presence_penalty`, `top_k` 等）在 [_create_llm()](../../backend/app/agent/llm.py) 初始化时从环境变量**静态读取一次**，运行时不可变。

两档配置之间的温度差（1.0 vs 0.7）、`top_p` 差（0.95 vs 0.8）、`presence_penalty` 差（0.0 vs 1.5）完全无法在运行时切换。

### 已有基础设施

- 中间件 `_inject_thinking_config()` 已验证"从 `configurable` 打捞运行时参数 → 动态覆写 `model_settings`"路径可行
- 前端 `useChatStream.ts` 已有 `enableThinking` ref 和透传逻辑
- 后端路由已将 `enable_thinking` 放入 `configurable`
- 两个中间件（`PromptCompilerMiddleware` + `RagPromptInjectorMiddleware`）各自有独立的 `_inject_thinking_config` 方法

---

## 3. 设计决策矩阵

通过 grilling 访谈确认的六项核心决策：

### D1. 切换位置：中间件层动态覆写

扩展现有 `_inject_thinking_config()` 方法，在已有 `enable_thinking` 注入基础上增加采样参数动态覆写。复用已验证的 `configurable → model_settings` 传递路径。

**被否决方案**：
- 双 LLM 实例预构建：需改造 agent 的 model 绑定方式，侵入性过大
- 前端传完整参数集：前端需了解后端参数语义，耦合过深

### D2. 配置来源：后端 YAML 配置文件

新建 `backend/app/agent/config/model_sampling_profiles.yaml`，定义两档参数组合。启动时一次性加载（`lru_cache`），不热重载。

**被否决方案**：
- 环境变量扩展（`LLM_THINKING_TEMPERATURE` 等）：参数多时极为臃肿
- 嵌入 config.py：Pydantic 扁平 env 不适合表达"参数组合"嵌套结构

### D3. 泛化范围：仅思考/非思考二档

仅支持 `enable_thinking=true` → thinking profile 和 `enable_thinking=false` → fast profile 的二档切换。未来如需多级别，可在 YAML 增加 `thinkingLevelMap` 并让前端传 `thinking_level` 字段。

### D4. reasoning_effort 与 enable_thinking 同时注入

两字段同时注入（均为 `chat_template_kwargs` 段模板变量）：
- 思考模式：`chat_template_kwargs.enable_thinking=true` + `chat_template_kwargs.reasoning_effort=medium`（显式指定）
- 快答模式：`chat_template_kwargs.enable_thinking=false`（`reasoning_effort` 不传，模板不读取）

> **修正（2026-08-28）**：`reasoning_effort` 必须放在 `chat_template_kwargs` 段而非 `extra_body` 顶层。Qwen3 模板渲染时以 `chat_template_kwargs` 的键作为 Jinja2 变量读取 `reasoning_effort`；`extra_body` 顶层参数 vLLM 接受但不传给模板（行为验证：顶层 5 档无差异，模板通道 low/medium/xhigh 输出长度 1864/2338/3858 阶梯递增）。

> **修正（2026-08-29，ninfer 切换）**：上述结论仅对 vLLM 单后端成立。推理框架切为 ninfer 后，两框架约定相反（ninfer 仅接受请求体顶层 `reasoning_effort`，且对 `chat_template_kwargs` 内非白名单键直接 400；vLLM ≤0.27.1 仅 `chat_template_kwargs` 模板通道生效）。现 `reasoning_effort` 在 YAML 的 `extra_body` 段做中性声明，由 loader 按环境变量 `REASONING_EFFORT_TRANSPORT`（`top_level` 默认=ninfer / `chat_template_kwargs`=vLLM ≤0.27.1）移到实际传输位置。详见 [Phase 3 设计 §3.5](phase3_thinking_levels_design.md)。

### D5. 参数分层：复用现有约定

与 [_create_llm()](../../backend/app/agent/llm.py) 传输分层完全一致：
- **顶层**：`temperature`, `top_p`, `presence_penalty`（OpenAI 标准参数）
- **extra_body**：`top_k`, `min_p`, `repetition_penalty`（vLLM 特有参数）
- **extra_body.chat_template_kwargs**：`enable_thinking`（`reasoning_effort` 在 `extra_body` 段中性声明，由 `REASONING_EFFORT_TRANSPORT` 决定最终落点，见 D4 修正）

### D6. 双中间件保持现状

`PromptCompilerMiddleware` 和 `RagPromptInjectorMiddleware` 各自保留独立 `_inject_thinking_config` 方法，共用配置加载模块（`profile_loader.py`）。注入逻辑幂等，重复执行无副作用。

---

## 4. 术语表

| 术语 | 定义 |
|------|------|
| **采样参数组合 (Sampling Profile)** | YAML 配置文件中定义的一组完整模型采样参数，对应一种运行模式 |
| **思考模式 (Thinking Mode)** | `enable_thinking=true` 时激活，高温度(1.0)+高top_p(0.95)，模型先推理再输出 |
| **快答模式 (Fast Mode)** | `enable_thinking=false` 时激活，低温度(0.7)+低top_p(0.8)+高presence_penalty(1.5)，跳过推理直接输出 |
| **参数分层 (Parameter Layering)** | 采样参数按 OpenAI SDK 兼容性分两层传输：顶层标准参数 + extra_body vLLM 特有参数 |
| **enable_thinking** | vLLM + Qwen3 的思考开关，通过 `chat_template_kwargs.enable_thinking` 传入 |
| **reasoning_effort** | 推理强度控制参数，可选 `low`/`medium`/`xhigh`（模板实际值域），传输位置由 `REASONING_EFFORT_TRANSPORT` 决定（2026-08-29 修正，见 D4） |
| **thinkingLevelMap** | UI 思考级别到 reasoning_effort 的映射表，当前二档方案不使用，留作未来扩展 |
| **profile_loader** | `backend/app/agent/config/profile_loader.py` 模块，启动时加载 YAML，提供 profile 查询和 model_settings 覆写函数 |

---

## 5. 实施方案

### 5.1 新建文件

> **注意**：`backend/app/agent/config/` 是新包，需新建 `__init__.py`（空文件）使其成为可导入的 Python 包。

#### `backend/app/agent/config/__init__.py`

空文件，使 `config/` 成为可导入的 Python 包。

#### `backend/app/agent/config/model_sampling_profiles.yaml`

> **P4 修正**：YAML 采用显式三段结构（`top_level` / `extra_body` / `chat_template_kwargs`），与 `_create_llm()` 的传输分层一一对应。loader 纯机械搬运，不靠隐式硬编码规则分类，未来新增参数只需放入正确段即可。

```yaml
# 模型采样参数组合配置
# 根据前端 enable_thinking 开关，在中间件层动态选择对应参数组合覆写 model_settings
#
# 三段结构与 _create_llm() 的传输分层完全一致：
#   top_level: OpenAI 标准参数 (temperature, top_p, presence_penalty)
#   extra_body: vLLM 特有参数 (top_k, min_p, repetition_penalty)
#   chat_template_kwargs: 模板变量 (enable_thinking, reasoning_effort)

thinking:
  top_level:
    temperature: 1.0
    top_p: 0.95
    presence_penalty: 0.0
  extra_body:
    top_k: 20
    min_p: 0.0
    repetition_penalty: 1.0
  chat_template_kwargs:
    enable_thinking: true
    reasoning_effort: medium

fast:
  top_level:
    temperature: 0.7
    top_p: 0.8
    presence_penalty: 1.5
  extra_body:
    top_k: 20
    min_p: 0.0
    repetition_penalty: 1.0
  chat_template_kwargs:
    enable_thinking: false
```

#### `backend/app/agent/config/profile_loader.py`

> **P2 修正**：`_load_profiles` 做 fail-fast 校验（文件存在、thinking/fast 两 profile 齐全、无未知段，否则直接抛异常），在服务启动时主动调用一次（非惰性加载）。
> **P3 修正**：`get_sampling_profile` 返回 `dict(profile)` 浅拷贝，防止调用方误改全局缓存。
> **S2 修正**：YAML 路径用 `Path(__file__).resolve().parent` 解析，避免 CWD 依赖（uvicorn 与 langgraph dev 启动目录不同）。
> **P4 修正**：`apply_profile_to_model_settings` 按三段结构机械搬运，不靠隐式硬编码分类。

核心接口：
- `get_sampling_profile(enable_thinking: bool) -> dict[str, Any]`：`True` → "thinking" profile，`False` → "fast" profile
- `apply_profile_to_model_settings(model_settings: dict, profile: dict) -> None`：按三段结构机械写入 model_settings（原地修改）

```python
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Any

_YAML_PATH = Path(__file__).resolve().parent / "model_sampling_profiles.yaml"

_VALID_SECTIONS = {"top_level", "extra_body", "chat_template_kwargs"}
_REQUIRED_PROFILES = {"thinking", "fast"}


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, dict[str, Any]]:
    """启动时一次性加载 YAML 配置并缓存。

    fail-fast: 文件缺失、profile 不全、含未知段时直接抛异常。
    """
    if not _YAML_PATH.exists():
        raise FileNotFoundError(f"采样参数配置文件不存在: {_YAML_PATH}")

    with open(_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError("采样参数配置文件为空")

    missing = _REQUIRED_PROFILES - set(data.keys())
    if missing:
        raise ValueError(f"采样参数配置缺少 profile: {missing}")

    for name, profile in data.items():
        if not isinstance(profile, dict):
            raise ValueError(f"profile '{name}' 必须是 dict")
        unknown = set(profile.keys()) - _VALID_SECTIONS
        if unknown:
            raise ValueError(
                f"profile '{name}' 含未知段: {unknown}，合法段: {_VALID_SECTIONS}"
            )

    return data


def get_sampling_profile(enable_thinking: bool) -> dict[str, Any]:
    """根据 enable_thinking 布尔值返回对应的采样参数组合。

    返回 dict(profile) 浅拷贝，防止调用方误改全局缓存。
    """
    profiles = _load_profiles()
    profile = profiles["thinking" if enable_thinking else "fast"]
    return dict(profile)


def apply_profile_to_model_settings(
    model_settings: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    """将采样参数组合按三段结构机械写入 model_settings（原地修改）。"""
    # top_level → model_settings[key]
    for k, v in profile.get("top_level", {}).items():
        model_settings[k] = v

    # extra_body → model_settings["extra_body"][key]
    if "extra_body" not in model_settings:
        model_settings["extra_body"] = {}
    for k, v in profile.get("extra_body", {}).items():
        model_settings["extra_body"][k] = v

    # chat_template_kwargs → model_settings["extra_body"]["chat_template_kwargs"][key]
    ctk = profile.get("chat_template_kwargs", {})
    if ctk:
        if "chat_template_kwargs" not in model_settings["extra_body"]:
            model_settings["extra_body"]["chat_template_kwargs"] = {}
        for k, v in ctk.items():
            model_settings["extra_body"]["chat_template_kwargs"][k] = v
```

### 5.2 修改文件

#### `backend/app/agent/middleware/prompt_compiler_middleware.py`

将 `_inject_thinking_config` 从"仅注入 enable_thinking"扩展为"加载完整 profile 并覆写全部采样参数"：

```python
def _inject_thinking_config(self, request: ModelRequest) -> None:
    try:
        runnable_config = ensure_config()
        configurable = runnable_config.get("configurable") or {}
        client_enable_thinking = configurable.get("enable_thinking")

        if client_enable_thinking is not None:
            if request.model_settings is None:
                request.model_settings = {}

            # 加载采样参数组合并一次性写入 model_settings
            profile = get_sampling_profile(client_enable_thinking)
            apply_profile_to_model_settings(request.model_settings, profile)

            logger.info(
                "🛡️ PromptCompilerMiddleware: 已注入采样参数组合 (mode=%s, params=%s)",
                "thinking" if client_enable_thinking else "fast",
                {k: v for k, v in profile.items()},
            )
    except Exception as e:
        logger.warning("🛡️ PromptCompilerMiddleware: 动态注入采样参数组合失败: %s", e)
```

#### `backend/app/agent/middleware/rag_prompt_injector_middleware.py`

同步修改，逻辑与 PromptCompilerMiddleware 完全一致（保持现状，双中间件各自独立注入，幂等无副作用）。

#### `backend/app/agent/service.py`

> **S3 修正**：在 `_initialize_agent`（同步）和 `_ainitialize_agent`（异步）两条初始化路径中，主动调用一次 `_load_profiles()` 触发 YAML 加载与 fail-fast 校验。确保配置问题在服务启动时即暴露，而非首次用户请求时惰性失败。

```python
from .config.profile_loader import _load_profiles

# 在 _initialize_agent / _ainitialize_agent 开头：
_load_profiles()  # eager load + fail-fast 校验
```

### 5.3 不需要改动的文件

| 文件 | 原因 |
|------|------|
| 前端 `useChatStream.ts` | 已传 `enable_thinking` 布尔值 |
| 前端 `types/index.ts` | `ChatRequest.enable_thinking` 字段已存在 |
| 后端路由 `chat.py` | 已将 `enable_thinking` 放入 `configurable` |
| 后端 Schema `schemas.py` | `ChatRequest.enable_thinking` 字段已存在 |
| LLM 工厂 `llm.py` | `_create_llm()` 的 init-time 默认值作为 fallback |

---

## 6. 完整传递链路

```
前端 enableThinking (boolean)
  → ChatRequest.enable_thinking
    → config["configurable"]["enable_thinking"]
      → Middleware._inject_thinking_config()
        → get_sampling_profile(enable_thinking)          ← 从 YAML 加载参数组合
        → apply_profile_to_model_settings(...)           ← 按分层规则写入 model_settings
          → model_settings["temperature"] = 1.0/0.7      (顶层)
          → model_settings["top_p"] = 0.95/0.8           (顶层)
          → model_settings["presence_penalty"] = 0.0/1.5  (顶层)
          → model_settings["extra_body"]["top_k"] = 20   (extra_body)
          → model_settings["extra_body"]["reasoning_effort"] = "medium"  (thinking 档，传输位置由 REASONING_EFFORT_TRANSPORT 决定，默认顶层)
          → model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] = true/false
```

### 向后兼容

当客户端不传 `enable_thinking` 时（值为 `None`），中间件不做任何覆写，LLM 使用 `_create_llm()` 的 init-time 默认值（来自 `.env` 环境变量），行为与当前完全一致。

### 覆写语义

当客户端传 `enable_thinking` 时，YAML profile 中的参数**全量覆写** `.env` 环境变量对应的 `model_settings` 值。即 `.env` 设置 `LLM_TOP_K=50`，若 YAML thinking profile 中 `top_k=20`，最终发送给 vLLM 的是 `20` 而非 `50`。这是设计意图（profile 作为模式切换的权威参数源），非叠加语义。`_create_llm()` 的 init-time 值仅在 `enable_thinking=None`（不覆写）时生效。

---

## 7. 验证步骤

### 7.1 中间件层验证（日志）

1. 修改 YAML 中 thinking 档的 `temperature` 为 `2.0`（极端值），重启服务
2. 前端开启思考模式发送消息，检查后端日志确认 `temperature=2.0` 被注入到 model_settings
3. 前端关闭思考模式发送消息，检查后端日志确认 `temperature=0.7` 被注入（fast 档 `reasoning_effort` 不传）
4. 用 curl **不带** `enable_thinking` 字段模拟 None 路径（前端恒传值，无法测 None），确认中间件不做任何覆写，使用 `_create_llm` 的 init-time 默认值

### 7.2 网络层验证（vLLM 请求体抓取）

> **Phase 1 经验**：日志只能证明“写进了 model_settings”，不能证明“值到了 vLLM 网络包”（LangChain 合并 model_settings 是另一环节）。

5. 在 vLLM 服务端或中间网络代理抓取实际 HTTP 请求体，确认 `temperature=2.0` 出现在请求 JSON 中（fast 档 `reasoning_effort` 不传）
6. 重点关注 `extra_body` 内的 `top_k`、`reasoning_effort` 是否被 LangChain 正确合并到最终请求

### 7.3 子智能体路径验证

> `PromptCompilerMiddleware` 挂在 SQL 子智能体上（service.py:513-517），需确认 `ensure_config()` 在子图内能捞到 `configurable.enable_thinking`。

7. 触发一次 SQL 子智能体调用（如查询“表结构”），确认子智能体的模型调用日志同样注入了 profile 参数
8. 若子智能体路径未注入，检查子图调用的 config 传递链

---

## 8. 测试计划

### `backend/tests/agent/test_sampling_profile_loader.py`

| 测试用例 | 验证点 |
|---------|--------|
| `test_load_profiles_returns_both_modes` | YAML 加载后包含 thinking 和 fast 两个 profile |
| `test_get_sampling_profile_true_returns_thinking` | `enable_thinking=True` 返回 thinking profile |
| `test_get_sampling_profile_false_returns_fast` | `enable_thinking=False` 返回 fast profile |
| `test_get_sampling_profile_returns_copy` | 返回値修改不影响缓存（浅拷贝验证） |
| `test_apply_profile_writes_top_level_params` | temperature/top_p/presence_penalty 写入 model_settings 顶层 |
| `test_apply_profile_writes_extra_body_params` | top_k/repetition_penalty/min_p 写入 extra_body |
| `test_apply_profile_writes_enable_thinking` | enable_thinking / reasoning_effort 写入 extra_body.chat_template_kwargs |
| `test_apply_profile_idempotent` | 重复调用同一 profile 无副作用 |
| `test_apply_profile_overrides_existing_values` | 已有 model_settings 値被 profile 覆写 |
| `test_load_profiles_missing_file_raises` | 文件缺失时抛 FileNotFoundError |
| `test_load_profiles_missing_profile_raises` | 缺少 thinking/fast 时抛 ValueError |

> **注意**：loader 测试用例间须调用 `_load_profiles.cache_clear()` 防止 `lru_cache` 跨用例污染。

### `backend/tests/agent/middleware/` — 双中间件扩展测试

> 现有 `test_rag_prompt_injector_thinking_config` 只断言 `chat_template_kwargs.enable_thinking`，改后仍会通过但应补断言。

| 测试用例 | 验证点 |
|---------|--------|
| 扩展 `test_rag_prompt_injector_thinking_config` | 补断言 `temperature`/`top_p`/`top_k`/`reasoning_effort` 被注入 |
| 新增 `test_thinking_false_injects_fast_profile` | `enable_thinking=False` 时注入 fast profile 参数（现有测试只覆盖 True） |
| 新增 `test_enable_thinking_none_no_override` | `enable_thinking=None` 时中间件不覆写 model_settings |
| 新增 `test_prompt_compiler_injects_profile` | PromptCompilerMiddleware（子智能体路径）对称测试 |

---

## 9. 未来扩展路径

当前二档方案预留了清晰的扩展路径：

1. **多级别思考**：在 YAML 中增加 `thinkingLevelMap`，前端传 `thinking_level` 字段（medium/high 等），后端从 map 映射出具体 `reasoning_effort` 值
2. **多 provider**：YAML 结构可扩展为按 provider 分组，每个 provider 下定义多个 mode profile
3. **热重载**：将 `lru_cache` 替换为带 TTL 的缓存或通过 API 端点触发重新加载
4. **前端参数预览**：前端从后端 API 获取当前 profile 的参数值，在设置面板展示

---

## 10. changelog 更新

按 AGENTS.md 约定，实施完成后在 `changelog.md` 中记录：

```markdown
### [未发布]

- **feat**: 模型采样参数动态切换（思考/快答二档）—— 前端切换思考模式时，中间件层从 YAML 配置文件加载对应采样参数组合，动态覆写 `model_settings`，支持 temperature/top_p/presence_penalty/top_k/reasoning_effort 等参数随模式切换
```

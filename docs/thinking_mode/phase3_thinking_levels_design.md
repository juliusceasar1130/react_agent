# Phase 3 设计方案：思考强度多级控制（Thinking Level Selector）

> **文档创建时间**: 2026-08-28 Asia/Shanghai
> **关联模块**: `backend/app/agent/config/`, `backend/app/agent/middleware/`, `backend/app/schemas.py`, `frontend/src/views/ChatView.vue`
> **前置阶段**: [Phase 2 设计方案](phase2_sampling_profiles_design.md) — 模型采样参数动态切换（思考/快答二档）
> **关联文档**: [ADR](../architecture/adr-model-sampling-profiles.md) | [术语表](../architecture/glossary-model-sampling.md)
> **适用场景**: vLLM / ninfer 双后端本地部署（Qwen3.8-27B），前端在思考模式内调节推理强度；`reasoning_effort` 的传输位置由 `REASONING_EFFORT_TRANSPORT` 决定（见 §3.5）

---

## 1. 需求来源

### Phase 2 遗留问题

Phase 2 实现了"思考/快答"二档切换，但 `reasoning_effort` 被写死在 YAML 中：

- **thinking 档**: `reasoning_effort=medium`（固定）
- **fast 档**: 不传 `reasoning_effort`（模板跳过推理逻辑）

而部署的 vLLM 模型（Qwen3）通过 `thinkingLevelMap` 支持多级推理强度：

| UI 档位 | `enable_thinking` | `thinking_level` | 模板实际值 |
|---------|------------------|-----------------|-----------|
| 关闭 | `false` | 不传 | —（模板不读取） |
| 轻思考 | `true` | `low` | `low` |
| 标准思考 | `true` | `medium` | `medium` |
| 深度思考 | `true` | `high` | `xhigh` |

用户确认：
1. **仅控 reasoning_effort**：temperature/top_p 等采样参数仍由思考/快答二档决定；
2. **前端分段选择器**：将现有"深度思考"ToggleSwitch 升级为四档分段选择器。

---

## 2. 总体设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Phase 3 数据流                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐      ┌─────────────┐      ┌──────────────────┐   │
│   │  前端 UI     │─────▶│  ChatRequest │─────▶│  backend/routers │   │
│   │ 四档选择器   │      │ (REST/SSE)   │      │  /chat.py        │   │
│   └─────────────┘      └─────────────┘      └──────────────────┘   │
│                                                       │             │
│   关闭/轻思考/标准思考/深度思考                        │             │
│                                                       ▼             │
│                                              ┌──────────────────┐   │
│                                              │  config[          │   │
│                                              │   "configurable"  │   │
│                                              │    ][             │   │
│                                              │    "thinking_level"│   │
│                                              │  ]                │   │
│                                              └──────────────────┘   │
│                                                       │             │
│                                                       ▼             │
│                                              ┌──────────────────┐   │
│                                              │ 双中间件注入      │   │
│                                              │ ├─rag_prompt_... │   │
│                                              │ └─prompt_comp... │   │
│                                              │   get_sampling_   │   │
│                                              │   profile(e, tl) │   │
│                                              └──────────────────┘   │
│                                                       │             │
│                                                       ▼             │
│                                              ┌──────────────────   │
│                                              │ YAML +           │   │
│                                              │ thinking_level_  │   │
│                                              │ _map 覆写        │   │
│                                              │ reasoning_effort │   │
│                                              └──────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 后端设计

### 3.1 YAML 配置扩展

在 `backend/app/agent/config/model_sampling_profiles.yaml` 顶层新增 `thinking_level_map`：

```yaml
# UI 思考级别 → reasoning_effort 映射（Phase 3 新增）
thinking_level_map:
  low: low
  medium: medium
  high: xhigh

# thinking 档参数（Phase 2 已有，Phase 3 thinking_level 覆写 reasoning_effort）
thinking:
  top_level:
    temperature: 1.0
    top_p: 0.95
    presence_penalty: 0.0
  extra_body:
    top_k: 20
    min_p: 0.0
    repetition_penalty: 1.0
    reasoning_effort: medium   # 默认 medium；中性声明位，thinking_level 存在时覆写，
                                # loader 按 REASONING_EFFORT_TRANSPORT 移到实际传输位置
  chat_template_kwargs:
    enable_thinking: true

# fast 档参数（Phase 2 已有，Phase 3 不变）
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
    # 注意：fast 档不传 reasoning_effort（模板不读取）
```

> **修正（2026-08-29，ninfer 切换）**：`reasoning_effort` 不再固定在 `chat_template_kwargs` 段，
> 而是在 `extra_body` 段做中性声明，由 loader 按传输位置开关落位（见 §3.5）。
> `enable_thinking` 仍保留在 `chat_template_kwargs`（ninfer 白名单与 vLLM 官方通道都接受）。

### 3.2 profile_loader 扩展

**⚠️ `_load_profiles` 校验白名单**：现有校验循环遍历所有顶层 key，`thinking_level_map` 会被当作 profile 校验（键 `{low, medium, high}` 全部不在 `_VALID_SECTIONS` 中）→ 服务启动即抛 ValueError。必须同步修改 `_load_profiles`，将 `thinking_level_map` 从 profile 校验中排除：

```python
_NON_PROFILE_KEYS = {"thinking_level_map"}  # 顶层非 profile 的 key

for name, profile in data.items():
    if name in _NON_PROFILE_KEYS:
        continue  # 跳过非 profile 的顶层 key
    if not isinstance(profile, dict): ...
    unknown = set(profile.keys()) - _VALID_SECTIONS
    ...
```

`get_sampling_profile` 新增 `thinking_level` 参数：

```python
def get_sampling_profile(
    enable_thinking: bool,
    thinking_level: str | None = None,
) -> dict[str, Any]:
    """根据 enable_thinking 返回对应 profile；thinking_level 存在时覆写 reasoning_effort。

    reasoning_effort 在 YAML 中统一声明于 extra_body 段，本函数按
    REASONING_EFFORT_TRANSPORT 将其移到实际传输位置（top_level=ninfer；
    chat_template_kwargs=vLLM ≤0.27.1）。
    """
    profiles = _load_profiles()
    profile = profiles["thinking" if enable_thinking else "fast"]

    result = copy.deepcopy(profile)
    transport = _get_effort_transport()

    def _place_effort(effort: str) -> None:
        if transport == "chat_template_kwargs":
            result.setdefault("chat_template_kwargs", {})["reasoning_effort"] = effort
        else:
            result.setdefault("extra_body", {})["reasoning_effort"] = effort

    # extra_body 段声明的默认 effort 移到传输位置（top_level 时为原地 no-op）
    default_effort = result.get("extra_body", {}).pop("reasoning_effort", None)
    if default_effort is not None:
        _place_effort(default_effort)

    # thinking_level 仅对 thinking 档生效（fast 档不传 reasoning_effort，忽略传入值）
    if enable_thinking and thinking_level is not None:
        level_map = profiles.get("thinking_level_map")  # 可选：缺失时不报错，走 profile 默认值
        if level_map and thinking_level in level_map:
            _place_effort(level_map[thinking_level])
        # 若 map 缺失或缺键：跳过覆写（用 profile 默认 medium），不发警告——可选语义

    return result
```

`_get_effort_transport()` 每次读取 `REASONING_EFFORT_TRANSPORT`（默认 `top_level`），非法值直接抛 `ValueError`（fail-fast）；模块导入时打一条 INFO 日志标明当前传输位置。

**关键行为**：

| 场景 | `enable_thinking` | `thinking_level` | `reasoning_effort` |
|------|------------------|-----------------|-------------------|
| 关闭 | `false` | 任意（忽略） | 不传 |
| 轻思考 | `true` | `low` | `low` |
| 标准思考 | `true` | `None` | `medium`（Phase 2 默认） |
| 深度思考 | `true` | `high` | `xhigh` |

### 3.5 传输层与后端兼容性（2026-08-29 补充，ninfer 切换）

`reasoning_effort` 的传输位置因后端而异，两个框架的约定相反：

| 后端 | 接受的传输位置 | 错误位置的行为 |
|------|--------------|---------------|
| ninfer | **请求体顶层**（OpenAI 标准字段，合法值 `none/low/medium/xhigh`） | 放进 `chat_template_kwargs` 的非白名单键直接 400 `chat_template_option_not_supported` |
| vLLM ≤0.27.1 | **`chat_template_kwargs` 模板变量通道**（Jinja 模板只读该段） | 顶层参数接受但**不透传模板**（2026-08-28 实证：顶层 5 档无差异；ctk 通道 low/medium/xhigh 输出 1864/2338/3858 阶梯递增） |

因此单一传输位置无法同时满足两者，由环境变量 `REASONING_EFFORT_TRANSPORT` 声明：

- `top_level`（默认，ninfer）：effort 发请求体顶层；
- `chat_template_kwargs`（vLLM ≤0.27.1）：effort 发模板变量通道；
- `enable_thinking` 不受开关影响，始终在 `chat_template_kwargs`（两端都接受）；
- 切换推理框架时只改 `.env` 这一行并重启，代码/YAML/前端不动；
- 误配后果：ninfer 上误配 ctk → 首个请求 400（显性，启动日志有 transport 值可对照）；vLLM 上误配 top_level → 档位静默失效、思考开关仍正常（不报错）。

### 3.3 Schema 与路由透传

`backend/app/schemas.py`：`ChatRequest` 新增字段，使用 `Literal` 在 API 层校验枚举值（非法值 422 返回，不依赖中间件 try/except 兜底）：

```python
from typing import Literal

class ChatRequest(BaseModel):
    # ... 现有字段 ...
    enable_thinking: Optional[bool] = None
    thinking_level: Literal["low", "medium", "high"] | None = None
```

`backend/app/routers/chat.py`：`/message`（L59）和 `/stream`（L156）**两处**均需透传 `thinking_level`。`resume` 端点（L538）现状连 `enable_thinking` 都没有，不继承档位，与 Phase 1/2 限制一致。

```python
if chat_request.enable_thinking is not None:
    config["configurable"]["enable_thinking"] = chat_request.enable_thinking
if chat_request.thinking_level is not None:
    config["configurable"]["thinking_level"] = chat_request.thinking_level
```

### 3.4 双中间件扩展

`rag_prompt_injector_middleware.py` 与 `prompt_compiler_middleware.py`（对称修改）：

```python
client_enable_thinking = configurable.get("enable_thinking")
client_thinking_level = configurable.get("thinking_level")  # 新增

if client_enable_thinking is not None:
    if request.model_settings is None:
        request.model_settings = {}

    profile = get_sampling_profile(client_enable_thinking, client_thinking_level)
    apply_profile_to_model_settings(request.model_settings, profile)
```

---

## 4. 前端设计

### 4.1 类型定义

`frontend/src/types/index.ts`：

```typescript
export type ThinkingLevel = "off" | "low" | "medium" | "high"

// ChatRequest 增加:
interface ChatRequest {
  // ... 现有字段 ...
  enable_thinking?: boolean
  thinking_level?: "low" | "medium" | "high"
}
```

### 4.2 状态管理

`frontend/src/composables/useChatStream.ts`：`enableThinking` 布尔 ref 升级为 `thinkingLevel` ref（`"off" | "low" | "medium" | "high"`）。`enableThinking` 改为只读 computed 仅供 payload 使用，**不再绑定 v-model**。**两处 payload**（L291 流式 + L315 非流式）均需同步加 `thinking_level`：

```typescript
// enableThinking 布尔 ref 升级为 thinkingLevel 四档 ref
const thinkingLevel = ref<ThinkingLevel>("medium")  // 默认"标准思考"

const enableThinking = computed(() => thinkingLevel.value !== "off")
const thinkingLevelParam = computed(() =>
  thinkingLevel.value === "off" ? undefined : thinkingLevel.value
)

// 两处 payload（流式 L291 + 非流式 L315）均需同步:
const payload = {
  // ...
  enable_thinking: enableThinking.value,
  thinking_level: thinkingLevelParam.value,
}
```

### 4.3 UI 组件

`frontend/src/views/ChatView.vue`：

- **移除 L185-191 的 `enableThinking` ToggleSwitch 及其 `v-model` 绑定**
- **替换为** 四档分段选择器（关闭 / 轻思考 / 标准思考 / 深度思考），默认"标准思考"

```vue
<template>
  <div class="thinking-level-selector">
    <SegmentedControl
      v-model="thinkingLevel"
      :options="[
        { label: '关闭', value: 'off' },
        { label: '轻思考', value: 'low' },
        { label: '标准思考', value: 'medium' },
        { label: '深度思考', value: 'high' },
      ]"
    />
  </div>
</template>
```

`frontend/src/components/common/SegmentedControl.vue`：**需新建**（现有 `components/common/` 下无此组件），本地打包，符合离线约束。

**默认档位**: `medium`（标准思考），与 Phase 2 默认行为一致。

---

## 5. 测试计划

### 5.1 profile_loader 测试（扩展）

| 测试用例 | 验证点 |
|---------|--------|
| `test_get_sampling_profile_with_thinking_level_high` | thinking + high → reasoning_effort=xhigh，其余参数不变 |
| `test_get_sampling_profile_with_thinking_level_low` | thinking + low → reasoning_effort=low |
| `test_get_sampling_profile_thinking_level_none_defaults_medium` | thinking + None → reasoning_effort=medium（Phase 2 兼容） |
| `test_get_sampling_profile_fast_ignores_thinking_level` | fast + high → 不传 reasoning_effort（忽略传入值） |
| `test_get_sampling_profile_map_missing_ignores_level` | YAML 不含 map + thinking_level="high" → 不覆写，用 profile 默认 medium |
| `test_get_sampling_profile_map_key_missing_skips` | YAML 含 map 但缺键（如只留 low/medium）+ thinking_level="high" → 不覆写，用 profile 默认 medium |
| 扩展 `test_get_sampling_profile_returns_copy` | 嵌套段修改也不污染缓存（深拷贝验证） |
| `test_load_profiles_contains_thinking_level_map` | YAML 加载后含 thinking_level_map 且值正确 |

### 5.2 中间件测试（扩展）

| 测试用例 | 验证点 |
|---------|--------|
| 新增 thinking_level 透传用例 | configurable.thinking_level=high → model_settings.extra_body.reasoning_effort=xhigh（transport=top_level 默认） |
| 新增 transport=chat_template_kwargs 用例 | effort 落在 model_settings.extra_body.chat_template_kwargs.reasoning_effort，extra_body 顶层无残留（双中间件对称 + loader 层 4 用例：默认档/level 覆写/fast 不传/非法值 fail-fast） |
| 新增 thinking_level=None 兼容用例 | 不传 thinking_level → reasoning_effort=medium（Phase 2 行为） |
| 新增 fast + level 被忽略的中间件层用例 | enable_thinking=false + thinking_level=high → 不注入 reasoning_effort |
| 子智能体路径对称用例 | PromptCompilerMiddleware 挂 SQL 子智能体时 configurable.thinking_level 需在子图内验证能捞到 |

### 5.3 端到端验证

1. 启动后端，确认 YAML 加载成功（无报错）；
2. 通过 SSE `/stream` 发送请求：
   - `enable_thinking=true, thinking_level=high` → 观察输出长度/耗时显著增加（对比 medium）；
   - `enable_thinking=true, thinking_level=low` → 观察输出长度/耗时显著减少（对比 medium）；
   - `enable_thinking=false` → 确认模板跳过推理逻辑，不传 reasoning_effort。

### 5.4 loader 回归测试

| 测试用例 | 验证点 |
|---------|--------|
| unknown-section 校验回归 | 确认加了 `thinking_level_map` 白名单后，真正的未知段（如 `thinking.foo_bar`）仍会拋错 |

---

## 6. 向后兼容

| 场景 | 行为 |
|------|------|
| YAML 不含 `thinking_level_map` | `thinking_level` 参数被忽略（走 profile 默认值），不报错——map 是 thinking 档增强项而非基础设施，设为可选以避免炸掉现有 6 处存量测试 fixture |
| 旧客户端不传 `thinking_level` | 不覆写，使用 YAML thinking 档内的默认值（当前为 medium），与 Phase 2 完全一致 |
| 前端仅传 `enable_thinking`（无 `thinking_level`） | `get_sampling_profile` 的 `thinking_level=None`，走 Phase 2 默认路径 |

---

## 7. Out of Scope

- **temperature/top_p 随 level 变化**：采样参数仍由二档决定（用户确认"仅控 reasoning_effort"）；
- **多档 profile 完整参数**：YAML 不扩展为多档独立参数组；

---

## 8. 修改文件清单

| # | 文件 | 修改内容 |
|---|------|---------|
| 1 | `backend/app/agent/config/model_sampling_profiles.yaml` | 新增 `thinking_level_map` |
| 2 | `backend/app/agent/config/profile_loader.py` | `get_sampling_profile` 新增参数 + 深拷贝升级 + **`_load_profiles` 校验白名单排除 `thinking_level_map`** + `REASONING_EFFORT_TRANSPORT` 传输位置开关（2026-08-29 补充） |
| 3 | `backend/app/schemas.py` | `ChatRequest` 新增 `thinking_level`（`Literal` 约束） |
| 4 | `backend/app/routers/chat.py` | `/message` + `/stream` 两处透传 `thinking_level`（resume 不继承） |
| 5 | `backend/app/agent/middleware/prompt_compiler_middleware.py` | 读取 `thinking_level` + 传入 `get_sampling_profile` |
| 6 | `backend/app/agent/middleware/rag_prompt_injector_middleware.py` | 同上（对称修改） |
| 7 | `frontend/src/types/index.ts` | 新增 `ThinkingLevel` 类型 |
| 8 | `frontend/src/composables/useChatStream.ts` | `enableThinking` → `thinkingLevel` 升级 + 两处 payload 同步 |
| 9 | `frontend/src/views/ChatView.vue` | 移除 ToggleSwitch + 替换为四档分段选择器 |
| 10 | `frontend/src/components/common/SegmentedControl.vue` | **新建**（本地打包，离线约束） |
| 11 | `backend/tests/agent/test_sampling_profile_loader.py` | 扩展 Phase 3 用例 + 存量 fixture 补 `thinking_level_map` |
| 12 | `backend/tests/agent/middleware/`（双中间件） | 扩展 Phase 3 用例（含 transport=chat_template_kwargs 对称用例） |
| 13 | `.env` / `.env_docker` | 新增 `REASONING_EFFORT_TRANSPORT`（2026-08-29 补充） |

**共 13 个文件**。

# Phase 3: 思考强度多级控制（Thinking Level Selector）

> **分类标签**：`ready-for-agent`
> **方案标识**：`phase3-thinking-levels`
> **架构基准**：[Phase 2 设计方案 §9.1](docs/thinking_mode/phase2_sampling_profiles_design.md)、[ADR: 模型采样参数动态切换](docs/architecture/adr-model-sampling-profiles.md)、[术语表](docs/architecture/glossary-model-sampling.md)
> **前置**：Phase 2（二档切换）已完成并闭环（20 单元测试 + 端到端验证通过）

---

## Problem Statement

Phase 2 实现了"思考/快答"二档切换，但 `reasoning_effort` 被写死在 YAML 中（thinking=medium；fast 档不传 `reasoning_effort`）。而 Qwen3 模板支持多级推理强度（low/medium/xhigh），UI 思考档位经 `thinking_level_map` 映射（low→low / medium→medium / high→xhigh），思考模式内部无法调节推理强度。

用户确认需求：
1. **仅控 reasoning_effort**：temperature/top_p 等采样参数仍由思考/快答二档决定，`thinking_level` 仅覆写 `reasoning_effort`；
2. **前端分段选择器**：将现有"深度思考"ToggleSwitch 升级为四档分段选择器（关闭 / 轻思考 / 标准思考 / 深度思考）。

---

## Solution

### 1. YAML 新增 `thinking_level_map`（仅影响 reasoning_effort）

在 `backend/app/agent/config/model_sampling_profiles.yaml` 顶层新增映射表（与用户 vLLM 配置 `thinkingLevelMap` 命名一致）：

```yaml
# UI 思考级别 → reasoning_effort 映射（Phase 3 新增，Phase 2 二档不受影响）
thinking_level_map:
  low: low
  medium: medium
  high: xhigh
```

- 四档前端选择器 → 请求参数映射：
  | 前端档位 | `enable_thinking` | `thinking_level` |
  |---------|------------------|-----------------|
  | 关闭 | false | 不传 |
  | 轻思考 | true | `low` |
  | 标准思考 | true | `medium` |
  | 深度思考 | true | `high` |
- `thinking_level` 缺省（`None`）→ 使用 profile 默认 `reasoning_effort`（thinking=medium），**保持 Phase 2 行为完全兼容**。

### 2. profile_loader 扩展

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

`get_sampling_profile(enable_thinking, thinking_level=None)`：

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
        # 若 map 缺失或缺键：跳过覆写（用 profile 默认值），不抛错

    return result
```

关键行为：
- `enable_thinking=False` → 忽略 `thinking_level`（fast 档不传 `reasoning_effort`，模板跳过推理逻辑）；
- `enable_thinking=True + thinking_level=None` → 默认 medium（Phase 2 行为）；
- `enable_thinking=True + thinking_level=high` → `reasoning_effort=xhigh`；
- 非法 `thinking_level` → `raise ValueError`（fail-fast，但中间件有 try/except 兜底）。

**传输位置开关（2026-08-29 补充，ninfer 切换）**：`reasoning_effort` 在 YAML 的 `extra_body` 段做中性声明，实际传输位置由环境变量 `REASONING_EFFORT_TRANSPORT` 决定（默认 `top_level`：请求体顶层，ninfer 仅接受此位置；`chat_template_kwargs`：模板变量通道，vLLM ≤0.27.1 顶层不透传模板仅该通道生效）。`thinking_level` 覆写值同样按 transport 落位；`enable_thinking` 不受开关影响，始终在 `chat_template_kwargs`。非法 transport 值导入时 fail-fast。细节见 [design §3.5](../../docs/thinking_mode/phase3_thinking_levels_design.md)。

> ⚠️ **浅拷贝 → 深拷贝升级**：Phase 2 的 `dict(profile)` 浅拷贝无法保护嵌套 `extra_body` 段，覆写 `reasoning_effort` 会污染缓存。Phase 3 必须升级为 `copy.deepcopy`（`test_get_sampling_profile_returns_copy` 需同步扩展嵌套断言）。

### 3. 后端 Schema 与路由透传

- `backend/app/schemas.py`：`ChatRequest` 新增字段，使用 `Literal` 在 API 层校验枚举值（非法值 422 返回，不依赖中间件 try/except 兜底）
  ```python
  from typing import Literal
  thinking_level: Literal["low", "medium", "high"] | None = None
  ```
- `backend/app/routers/chat.py`：`/message`（L59）和 `/stream`（L156）**两处**均需透传 `thinking_level`。`resume` 端点（L538）现状连 `enable_thinking` 都没有，不继承档位，与 Phase 1/2 限制一致。
  ```python
  if chat_request.enable_thinking is not None:
      config["configurable"]["enable_thinking"] = chat_request.enable_thinking
  if chat_request.thinking_level is not None:
      config["configurable"]["thinking_level"] = chat_request.thinking_level
  ```

### 4. 双中间件扩展 `_inject_thinking_config`

`prompt_compiler_middleware.py` 与 `rag_prompt_injector_middleware.py`（对称修改）：

```python
client_enable_thinking = configurable.get("enable_thinking")
client_thinking_level = configurable.get("thinking_level")  # 新增

if client_enable_thinking is not None:
    if request.model_settings is None:
        request.model_settings = {}

    profile = get_sampling_profile(client_enable_thinking, client_thinking_level)
    apply_profile_to_model_settings(request.model_settings, profile)
```

### 5. 前端分段选择器

- `frontend/src/types/index.ts`：
  ```typescript
  export type ThinkingLevel = "off" | "low" | "medium" | "high"
  // ChatRequest 增加:
  thinking_level?: "low" | "medium" | "high"
  ```
- `frontend/src/composables/useChatStream.ts`：`enableThinking` 布尔 ref 升级为 `thinkingLevel` ref（`"off" | "low" | "medium" | "high"`）。`enableThinking` 改为只读 computed 仅供 payload 使用，**不再绑定 v-model**。**两处 payload**（L291 流式 + L315 非流式）均需同步加 `thinking_level`：
  ```typescript
  const thinkingLevel = ref<ThinkingLevel>("medium")
  const enableThinking = computed(() => thinkingLevel.value !== "off")
  const thinkingLevelParam = computed(() =>
    thinkingLevel.value === "off" ? undefined : thinkingLevel.value
  )
  // payload 中:
  enable_thinking: enableThinking.value,
  thinking_level: thinkingLevelParam.value,
  ```
- `frontend/src/views/ChatView.vue`：**移除 L185-191 的 `enableThinking` ToggleSwitch 及其 `v-model` 绑定**，替换为四档分段选择器（关闭 / 轻思考 / 标准思考 / 深度思考），默认"标准思考"：
  ```vue
  <SegmentedControl
    v-model="thinkingLevel"
    :options="[
      { label: '关闭', value: 'off' },
      { label: '轻思考', value: 'low' },
      { label: '标准思考', value: 'medium' },
      { label: '深度思考', value: 'high' },
    ]"
  />
  ```
- `frontend/src/components/common/SegmentedControl.vue`：**需新建**（现有 `components/common/` 下无此组件），本地打包，符合离线约束。

---

## User Stories

1. As a 最终用户, I want 在思考模式内选择轻/标准/深度思考强度, so that 复杂问题用深度思考、简单问题用轻思考，平衡质量与延迟。
2. As a 前端用户, I want 思考强度以分段选择器形式呈现, so that 操作直观且与现有 UI 风格一致。
3. As a 开发人员, I want `thinking_level` 缺省时行为与 Phase 2 完全一致, so that 旧客户端不受影响。
4. As a 运维工程师, I want 非法 thinking_level 值被拒绝, so that 配置错误不会静默注入。

---

## Implementation Decisions

### D1. thinking_level 仅作用于 thinking 档
fast 档不传 `reasoning_effort`（模板跳过推理逻辑），不受 `thinking_level` 影响。前端四档选择器中"关闭"档不传 `thinking_level`。

### D2. 沿用 `thinking_level_map` 命名
与用户 vLLM 配置 `thinkingLevelMap` 保持命名一致，映射关系一眼可读。

### D3. 深拷贝升级
`get_sampling_profile` 返回 `copy.deepcopy(profile)`，保护嵌套段不被调用方修改，同时允许安全覆写 `reasoning_effort`。

### D4. 双中间件同步修改
遵循 AGENTS.md"修改中间件装配时，必须同步更新两边"约定，两个中间件对称扩展。

---

## Testing Decisions

### 测试 seam
- `backend/tests/agent/test_sampling_profile_loader.py`（扩展）：
  | 用例 | 验证点 |
  |------|--------|
  | `test_get_sampling_profile_with_thinking_level_high` | thinking + high → reasoning_effort=xhigh，其余参数不变 |
  | `test_get_sampling_profile_with_thinking_level_low` | thinking + low → reasoning_effort=low |
  | `test_get_sampling_profile_thinking_level_none_defaults_medium` | thinking + None → reasoning_effort=medium（Phase 2 兼容） |
  | `test_get_sampling_profile_fast_ignores_thinking_level` | fast + high → 不传 reasoning_effort（忽略传入值） |
  | `test_get_sampling_profile_map_missing_ignores_level` | YAML 不含 map + thinking_level="high" → 不覆写，用 profile 默认 medium |
  | `test_get_sampling_profile_map_key_missing_skips` | YAML 含 map 但缺键（如只留 low/medium）+ thinking_level="high" → 不覆写，用 profile 默认 medium |
  | 扩展 `test_get_sampling_profile_returns_copy` | 嵌套段修改也不污染缓存（深拷贝验证） |
  | `test_load_profiles_contains_thinking_level_map` | YAML 加载后含 thinking_level_map 且值正确 |
- `backend/tests/agent/middleware/`（双中间件各扩展）：
  | 用例 | 验证点 |
  |------|--------|
  | 新增 thinking_level 透传用例 | configurable.thinking_level=high → model_settings.extra_body.reasoning_effort=xhigh（transport=top_level 默认） |
  | 新增 transport=chat_template_kwargs 用例 | effort 落在 model_settings.extra_body.chat_template_kwargs.reasoning_effort，extra_body 顶层无残留（loader 4 用例：默认档/level 覆写/fast 不传/非法值 fail-fast + 双中间件对称各 1） |
  | 新增 thinking_level=None 兼容用例 | 不传 thinking_level → reasoning_effort=medium（Phase 2 行为） |
  | 新增 fast + level 被忽略的中间件层用例 | enable_thinking=false + thinking_level=high → 不注入 reasoning_effort |
  | 子智能体路径对称用例 | PromptCompilerMiddleware 挂 SQL 子智能体时 configurable.thinking_level 需在子图内验证能捞到 |
- loader 修复后 unknown-section 校验回归：确认加了 `thinking_level_map` 白名单后，真正的未知段（如 `thinking.foo_bar`）仍会抛错。
- 前端：`frontend` 无测试框架约定，通过手动验证。

### Prior art
- `backend/tests/agent/test_sampling_profile_loader.py`：Phase 2 的 12 个 loader 测试已覆盖基本加载/覆写语义；
- `backend/tests/agent/middleware/test_prompt_compiler_middleware.py` / `test_rag_prompt_injector_middleware.py`：Phase 2 的 8 个中间件测试已覆盖 True/False/None 三态。

---

## Out of Scope

- **temperature/top_p 随 level 变化**：采样参数仍由二档决定（用户确认"仅控 reasoning_effort"）；
- **多档 profile 完整参数**：YAML 不扩展为多档独立参数组；
- **changelog.md 更新**：Phase 3 收尾时一并更新。

---

## Further Notes

- 本阶段修改文件：YAML + profile_loader（含 `_load_profiles` 校验白名单）+ schemas.py + chat.py（2 处透传）+ 双中间件 + 前端 4 文件（含新建 SegmentedControl.vue）+ 测试 2 文件，**共 12 个文件**；
- 向后兼容：`thinking_level` 缺省时不覆写，使用 YAML thinking 档内的默认值（当前为 medium），旧客户端无感知；
- 未来扩展：若需"每档独立完整采样参数"，可在 YAML 中将 thinking 拆分为多档 profile，本阶段的 `thinking_level_map` 仍可复用。

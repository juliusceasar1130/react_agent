# Phase 2 阶段 A: 模型采样参数组合配置层（Sampling Profile Loader）

> **分类标签**：`ready-for-agent`
> **方案标识**：`phase2-sampling-profiles-stage-a`
> **架构基准**：[Phase 2 设计方案 §5.1](docs/thinking_mode/phase2_sampling_profiles_design.md)（含审计 P1–P4 修正）、[ADR: 模型采样参数动态切换](docs/architecture/adr-model-sampling-profiles.md)、[术语表](docs/architecture/glossary-model-sampling.md)
> **前置**：Phase 1 已实现 `enable_thinking` 布尔值端到端传递（思考链 Trace 捕获）；本阶段是 Phase 2 三阶段实施（A 配置层 / B 中间件接线 / C 端到端验收）的第一阶段

---

## Problem Statement

系统使用 vLLM + Qwen3.8-27B 模型，思考模式与快答模式需要不同的采样参数组合（temperature 1.0 vs 0.7、presence_penalty 0.0 vs 1.5、reasoning_effort medium vs none 等）。但当前所有采样参数在 `_create_llm()` 初始化时从 `.env` 环境变量**静态读取一次**，运行时不可变——后端不存在"参数组合"这一概念，无法支撑前端思考/非思考切换时动态应用不同参数组合。

经审计确认，配置层设计必须规避三个缺陷：

1. **配置加载静默失败（P2）**：若 YAML 缺失、解析失败或不完整，加载异常被中间件 `try/except` 吞掉只打 warning，`get_sampling_profile` 的 `.get(..., {})` 返回空 dict 导致空操作——客户端传的 `enable_thinking` 也不再注入 vLLM，Phase 1 的开关**静默失效**，只在 warning 日志里留痕。
2. **缓存可变引用泄漏（P3）**：`lru_cache` 缓存 profile dict 后直接返回原始引用，任何调用方误改都会污染全局缓存。
3. **扁平结构与隐式硬编码分层（P4）**：YAML 键平铺、靠 loader 内部"哪个键去顶层/extra_body/chat_template_kwargs"的硬编码规则分类，未来新增参数（如 `frequency_penalty`）会静默放错层。

---

## Solution

新建 `backend/app/agent/config/` 包（本阶段不接线中间件，接线属阶段 B）：

1. **`model_sampling_profiles.yaml`**：显式三段结构（`top_level` / `extra_body` / `chat_template_kwargs`），与 `_create_llm()` 传输分层一一对应，定义 thinking / fast 两档参数组合；
2. **`profile_loader.py`**：提供 profile 加载与 model_settings 覆写函数，内置 fail-fast 校验、浅拷贝返回、按段机械搬运；
3. **`__init__.py`**：空文件，使 `config/` 成为可导入的 Python 包。

thinking 档 `reasoning_effort=medium` 为**显式指定**（用户已确认，非推断默认值）。

---

## User Stories

1. As a 运维工程师, I want 思考/快答两档采样参数集中在单一 YAML 文件中管理, so that 调参无需修改代码或散落的环境变量。
2. As a 开发人员, I want YAML 文件缺失、profile 不完整或必需段缺失时加载器直接抛异常, so that 配置错误在服务启动时即暴露，而非静默回归 Phase 1 功能。
3. As a 开发人员, I want 调用方修改返回的 profile 不影响全局缓存, so that 任意误改不会污染后续所有请求的参数组合。
4. As a 开发人员, I want 未来新增采样参数只需放入 YAML 对应段即可生效, so that 不依赖 loader 内部的隐式硬编码分类规则。
5. As a 开发人员, I want YAML 中出现未识别段名时立即报错, so that 拼写错误或结构漂移不会静默放错传输层。
6. As a 自动化测试工程师, I want loader 在无 agent 图、无 LLM、无 vLLM 环境下可独立单测, so that 配置层正确性秒级验证且不依赖外部服务。
7. As a 开发人员, I want profile 覆写函数按三段结构机械写入 `model_settings`, so that 与 `_create_llm()` 的传输分层语义严格一致。
8. As a 代码审查者, I want loader 测试用例间互不污染, so that `lru_cache` 不会导致跨用例的假失败或假通过。

---

## Implementation Decisions

### 1. 新包 `backend/app/agent/config/`（三文件）

- `__init__.py`：空文件（新包必须，`config/` 目录当前不存在，文档头部"关联模块"标注的模块为新建而非已有）；
- `model_sampling_profiles.yaml`：三段结构配置；
- `profile_loader.py`：加载与覆写逻辑。

### 2. YAML 显式三段结构（审计 P4 修正）

YAML 结构（决策编码于结构本身，来自已审计的方案文档）：

```yaml
thinking:
  top_level:
    temperature: 1.0
    top_p: 0.95
    presence_penalty: 0.0
  extra_body:
    top_k: 20
    min_p: 0.0
    repetition_penalty: 1.0
    reasoning_effort: medium
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level:
    temperature: 0.7
    top_p: 0.8
    presence_penalty: 1.5
  extra_body:
    top_k: 20
    min_p: 0.0
    repetition_penalty: 1.0
    reasoning_effort: none
  chat_template_kwargs:
    enable_thinking: false
```

- 段名白名单：`top_level` / `extra_body` / `chat_template_kwargs`；出现未知段名直接抛异常；
- 必需 profile：`thinking` / `fast` 两档齐全，缺失即抛异常；
- loader 按段机械搬运到 `model_settings` 对应位置，不做键级硬编码分类。

### 3. `profile_loader.py` 接口（审计 P2/P3/S2 修正）

- `_load_profiles()`（`lru_cache(maxsize=1)` 私有）：
  - fail-fast：文件不存在抛 `FileNotFoundError`；YAML 为空、缺少 thinking/fast 任一 profile、profile 非 dict、含未知段均抛 `ValueError`；
  - 路径解析用 `Path(__file__).resolve().parent / "model_sampling_profiles.yaml"`，避免 CWD 依赖（uvicorn 与 langgraph dev 启动目录不同）；
- `get_sampling_profile(enable_thinking: bool) -> dict[str, Any]`：`True` → thinking profile，`False` → fast profile；返回 `dict(profile)` **浅拷贝**，防缓存污染；
- `apply_profile_to_model_settings(model_settings: dict, profile: dict) -> None`：原地修改，三段机械搬运——`top_level` → 根级、`extra_body` → `model_settings["extra_body"]`（不存在则创建）、`chat_template_kwargs` → `model_settings["extra_body"]["chat_template_kwargs"]`。

### 4. 依赖

`PyYAML==6.0.3` 已在 `requirements.txt:67` 显式声明，**无需**新增依赖（审计 P1 确认）。

### 5. 阶段边界

本阶段**不修改**任何中间件、`service.py`、路由或前端——`profile_loader` 当前无调用方，仅提供接口与测试。中间件接线与 `service.py` eager load 属阶段 B，网络层/子智能体验证属阶段 C。

---

## Testing Decisions

### 测试 seam

**单一 seam**：`profile_loader` 模块的公共函数（`get_sampling_profile` / `apply_profile_to_model_settings` / `_load_profiles`），直接单元测试。这是最高且唯一的 seam——本阶段无中间件接线，不需要经过 `ModelRequest` 层或 LangGraph 运行时。

- 真实 YAML 走默认路径（`Path(__file__).resolve().parent` 固定，测试环境可加载真实配置断言两档齐全）；
- fail-fast 用例通过 monkeypatch 替换路径常量为 `tmp_path` 下的临时文件。

### 良好测试的标准

- 只测外部行为：返回的 profile 内容、写入后 `model_settings` 的结构与值、异常类型与信息——不测内部缓存实现细节；
- 每个用例独立可复现，无外部服务依赖。

### 测试模块与用例

`backend/tests/agent/test_sampling_profile_loader.py`（新建）：

| 用例 | 验证点 |
|------|--------|
| `test_load_profiles_returns_both_modes` | 真实 YAML 加载后包含 thinking 和 fast 两个 profile |
| `test_get_sampling_profile_true_returns_thinking` | `enable_thinking=True` 返回 thinking profile |
| `test_get_sampling_profile_false_returns_fast` | `enable_thinking=False` 返回 fast profile |
| `test_get_sampling_profile_returns_copy` | 修改返回 dict 不影响后续获取结果（浅拷贝验证） |
| `test_apply_profile_writes_top_level_params` | temperature/top_p/presence_penalty 写入 model_settings 根级 |
| `test_apply_profile_writes_extra_body_params` | top_k/repetition_penalty/min_p/reasoning_effort 写入 extra_body |
| `test_apply_profile_writes_enable_thinking` | enable_thinking 写入 extra_body.chat_template_kwargs |
| `test_apply_profile_idempotent` | 重复调用同一 profile 无副作用 |
| `test_apply_profile_overrides_existing_values` | 已有 model_settings 值被 profile 覆写 |
| `test_load_profiles_missing_file_raises` | monkeypatch 路径指向不存在文件，抛 FileNotFoundError |
| `test_load_profiles_missing_profile_raises` | YAML 只定义 thinking，抛 ValueError |
| `test_load_profiles_unknown_section_raises` | YAML 含未知段名，抛 ValueError |

**关键约束**：涉及 `_load_profiles` 的用例须在 setup/teardown 中调用 `_load_profiles.cache_clear()`，防止 `lru_cache` 跨用例污染（monkeypatch 路径后不清缓存会导致后续用例读到旧结果）。

### Prior art

- `backend/tests/agent/utils/test_system_prompt_loader.py`：`tmp_path` fixture 构造临时文件 + 缺失文件抛 `FileNotFoundError` 的既有模式；
- `backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`：中间件侧 `model_settings` 结构断言的既有风格（阶段 B 扩展测试以此为基）。

---

## Out of Scope

- **中间件接线**：扩展 `_inject_thinking_config` 调用 profile_loader（阶段 B）；
- **service.py eager load**：`_initialize_agent` / `_ainitialize_agent` 主动触发加载校验（阶段 B）；
- **双中间件对称测试**：`enable_thinking=False/None` 覆盖、PromptCompilerMiddleware 对称测试（阶段 B）；
- **端到端验收**：vLLM 请求体网络层抓包、SQL 子智能体路径验证（阶段 C）；
- **changelog.md 更新**（阶段 C 收尾）；
- **未来扩展**：多级别思考（thinkingLevelMap）、多 provider、热重载、前端参数预览。

---

## Further Notes

- 本 spec 基于已完成的方案审计（P1–P4 修正 + S1–S9 建议）与三轮 grilling 决策（D1–D6），决策链路见 [Phase 2 设计方案](docs/thinking_mode/phase2_sampling_profiles_design.md)；
- thinking 档 `reasoning_effort=medium` 为用户显式确认值；
- profile 覆写 `.env` 的"全量覆写、非叠加"语义在阶段 B 接线后生效，本阶段仅保证 loader 输出正确；
- 实施完成后需在阶段 C 更新 `changelog.md`（按 AGENTS.md 文档维护约定）。

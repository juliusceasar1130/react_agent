# Phase 2 阶段 C: 端到端验收与收尾（Sampling Profile End-to-End Validation）

> **分类标签**：`ready-for-agent`
> **方案标识**：`phase2-sampling-profiles-stage-c`
> **架构基准**：[Phase 2 设计方案 §7](docs/thinking_mode/phase2_sampling_profiles_design.md)、[ADR: 模型采样参数动态切换](docs/architecture/adr-model-sampling-profiles.md)
> **前置**：阶段 A（配置层 loader）+ 阶段 B（中间件接线）均已完成并通过全部单元测试

---

## Problem Statement

阶段 A 和 B 已完成配置层、中间件接线、service.py eager load 及全部单元测试（共 20 个测试用例全部通过）。但当前仍缺少**端到端运行时验证**——单元测试只能证明"代码逻辑正确"，无法证明：

1. **网络层实际到达**：`model_settings` 中的参数是否真正被 LangChain 合并进发往 vLLM 的 HTTP 请求体；
2. **子智能体路径贯通**：SQL 子智能体（`PromptCompilerMiddleware`）在子图运行时能否正确读取 `configurable.enable_thinking`；
3. **向后兼容**：`enable_thinking=None` 时主 Agent 和子智能体均不覆写，使用 `_create_llm()` 的 init-time 默认值。

此外，按 AGENTS.md 约定，新特性完成后需更新 `changelog.md`。

---

## Solution

### 1. 中间件层日志验证（已具备条件）

阶段 B 的中间件已输出日志：

```
🛡️ PromptCompilerMiddleware: 已注入采样参数组合 (mode=thinking)
🛡️ RagPromptInjectorMiddleware: 已注入采样参数组合 (mode=fast)
```

验证步骤：
1. 临时修改 `model_sampling_profiles.yaml`，将 thinking 档的 `temperature` 改为 `2.0`（极端值，易于辨认）
2. 重启服务，触发 eager load
3. 前端开启思考模式发送消息，检查后端日志确认 `temperature=2.0` 被注入
4. 前端关闭思考模式发送消息，检查后端日志确认 `temperature=0.7, reasoning_effort=none` 被注入

### 2. 网络层抓包验证（vLLM 请求体）

> **Phase 1 经验**：日志只能证明"写进了 model_settings"，不能证明"值到了 vLLM 网络包"（LangChain 合并 model_settings 是另一环节）。

验证步骤：
1. 在 vLLM 服务端或中间网络代理抓取实际 HTTP 请求体
2. 确认 `temperature=2.0` / `reasoning_effort=none` 出现在请求 JSON 中
3. 重点关注 `extra_body` 内的 `top_k`、`reasoning_effort` 是否被 LangChain 正确合并到最终请求

### 3. 子智能体路径验证

`PromptCompilerMiddleware` 挂在 SQL 子智能体上（service.py:513-517），需确认：
1. 触发一次 SQL 子智能体调用（如查询"表结构"）
2. 确认子智能体的模型调用日志同样注入了 profile 参数
3. 若子智能体路径未注入，检查子图调用的 config 传递链

### 4. None 路径向后兼容验证

1. 用 curl **不带** `enable_thinking` 字段模拟 None 路径（前端恒传值，无法测 None）
2. 确认中间件不做任何覆写，使用 `_create_llm` 的 init-time 默认值

### 5. changelog.md 更新

按 AGENTS.md 约定，在 `changelog.md` 中记录：

```markdown
### [未发布]

- **feat**: 模型采样参数动态切换（思考/快答二档）—— 前端切换思考模式时，中间件层从 YAML 配置文件加载对应采样参数组合，动态覆写 `model_settings`，支持 temperature/top_p/presence_penalty/top_k/reasoning_effort 等参数随模式切换
```

---

## User Stories

1. As a 最终用户, I want 前端切换思考/快答模式后，实际到达 vLLM 的参数确实发生了变化, so that 模型行为（思考深度、回答风格）真正按预期切换。
2. As a 运维工程师, I want 通过日志和抓包即可验证参数是否生效, so that 无需阅读代码就能确认部署正确。
3. As a 开发人员, I want changelog 记录本次变更, so that 版本历史可追溯。

---

## Implementation Decisions

### 无代码变更

阶段 C **不涉及代码文件修改**（阶段 A + B 已覆盖全部代码变更）。本阶段仅包含：

- 运行时验证（日志检查、抓包、子智能体调用）
- 文档更新（changelog.md）

### 验证工具建议

| 验证项 | 工具 | 方法 |
|--------|------|------|
| 中间件日志 | 后端 stdout / 日志文件 | 搜索 `已注入采样参数组合` |
| 网络层抓包 | vLLM 端 access log / 代理 | 检查 POST /v1/chat/completions 请求体 |
| 子智能体验证 | LangSmith trace / 自定义日志 | 查看 SQL 子智能体调用的 model_settings |
| None 路径 | curl / Postman | 构造不含 `enable_thinking` 的请求 |

---

## Testing Decisions

### 已完成测试（前置）

阶段 A + B 已完成的测试（全部通过）：

- `backend/tests/agent/test_sampling_profile_loader.py`：12 个 loader 单元测试
- `backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`：5 个中间件测试（含扩展）
- `backend/tests/agent/middleware/test_prompt_compiler_middleware.py`：3 个对称测试

### 本阶段新增测试

无新增代码测试（本阶段为手动/半自动运行时验证）。

---

## Out of Scope

- **自动化集成测试**：vLLM 网络层抓包难以在 CI 中稳定复现，本阶段采用手动验证
- **性能测试**：参数切换对延迟的影响未纳入本阶段
- **多模型适配**：当前仅验证 Qwen3.8-27B 单模型场景

---

## Further Notes

- 阶段 C 是 Phase 2 的**收尾阶段**，完成后整个 Phase 2 闭环
- 若网络层验证发现问题（如 LangChain 未正确合并 `extra_body`），需回退到阶段 B 修复中间件逻辑
- changelog.md 更新后，建议同步更新 README.md 的"特性"章节（若存在）

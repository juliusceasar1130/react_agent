# AGENTS.md

## Rule Priority

Follow rules in this order:

1. Safety rules
2. Working rules
3. Preferences
4. Project context from `memory.md`

## Working Rules

- 默认使用中文回复；必要时对关键术语补充英文。
- 进行代码修改时，优先保持最小改动原则（minimal change）。
- 不确定项目约定时，先查阅现有文档与代码，再实施修改。
- 如遇潜在破坏性操作，应先说明风险。
- 处理涉及项目背景、团队偏好、固定流程的问题时，同时参考 `AGENTS.md` 与 `memory.md`。
- 新增约定时，采用追加方式，不删除既有内容。

## File Change Reporting

- 修改完成后，在回复中明确说明：
  - 修改时间
  - 主要修改内容
- 若变更属于新特性或重要优化，记录到 `changelog.md`。
- 若涉及项目主要特性或项目文件结构变更，同时更新 `README.md`。
- 如果 `changelog.md` 不存在，则在项目根目录新建。
- 仅在适合的文档文件中记录变更；不要在普通代码文件中添加无关修改历史注释。

## Think Before Coding

- 明确说明假设，不要默认假设成立。
- 如果存在多种理解，不要静默选择其一，应显式说明。
- 若有更简单方案，应优先采用，并说明取舍。
- 如果需求或约定不清晰，应先指出不清晰点，再继续实施。

## Simplicity First

- 只实现当前需求，不额外扩展功能。
- 不为一次性逻辑引入不必要抽象。
- 不增加未被请求的灵活性、可配置性或复杂错误处理。
- 若实现明显过度复杂，应主动简化。

## Surgical Changes

- 仅修改完成任务所必需的内容。
- 不顺手修改无关代码、注释或格式。
- 不重构未损坏的部分，除非明确要求。
- 保持与现有代码风格一致。
- 只清理因本次修改而产生的无用导入、变量、函数。
- 若发现既有无关死代码，可以说明，但不要擅自删除。

## Goal-Driven Execution

For multi-step tasks, use a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Convert requests into verifiable outcomes whenever practical.

## Environment

- 执行项目相关命令时，使用项目环境：`conda activate py312_agent`。

## Disallowed Behaviors

- 不要重构无关代码。
- 不要无理由引入新依赖。
- 不要静默修改公共接口或既有行为。
- 不要在未说明风险的情况下进行潜在破坏性操作。

## Technology Version and Documentation Rules

- 涉及第三方框架、SDK、工具链时，优先以项目当前锁定依赖版本为准。
- 对于快速迭代的技术（如 LangChain、LangGraph、MCP 相关 SDK 等），优先参考官方文档与项目内既有实现，不默认采用网络上的最新示例。
- 未明确要求时，不主动执行 major version 升级，也不擅自引入迁移性改写。
- 若项目代码、锁定依赖版本与外部文档存在差异，应在回复中显式说明。
- 若已提供文档 MCP，则优先使用其提供的文档资源作为参考上下文。

## MCP Usage Rules

- 涉及第三方库、框架、SDK 的实现或版本差异时，优先使用相关 MCP 查询文档。
- 涉及 LangChain / LangGraph / LangSmith 时，优先使用 LangChain docs MCP。
- 涉及其他第三方库时，优先使用 Context7 MCP。
- 涉及浏览器页面、console、network、DOM、性能问题时，优先使用 chrome-devtools MCP。
- 项目依赖版本、锁文件和现有实现优先级高于 MCP 返回的最新文档。
- 未明确要求时，不因 MCP 查询结果主动做 major version 升级或大规模迁移。

## Source Priority

1. 项目代码与锁定依赖
2. 项目文档与仓库规则
3. MCP 文档与工具结果
4. 通用知识

## Agent skills

### Issue tracker

本地 Markdown。问题以文件形式存储在 `.scratch/<feature>/`。见 `docs/agents/issue-tracker.md`。

### Triage labels

已映射为中文标签。见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文布局（Single-context）。见 `docs/agents/domain.md`。

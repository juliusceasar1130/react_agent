# Domain Documentation (领域文档)

本项目遵循 **单上下文 (Single-context)** 布局来管理领域知识。

## 布局结构

- **全局上下文**: 根目录下的 `CONTEXT.md`。
- **架构决策**: `docs/adr/` 目录下的架构决策记录 (ADR)。

## 使用规则

1. **优先阅读**: `improve-codebase-architecture`、`diagnose` 和 `tdd` 等技能必须先阅读 `CONTEXT.md` 以理解业务术语。
2. **参考 ADR**: 在进行结构性改动前，检查 `docs/adr/` 以确保与过去的决策保持一致。
3. **同步更新**: 当产生新的业务术语或架构决策时，应及时更新这些文档。

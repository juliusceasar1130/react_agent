# Change: 重构技能场景目录与自动发现机制

## Why

当前业务技能系统的场景资产按 `scenarios/`、`sql/`、`scripts/` 三类目录分散管理，并依赖 `registry.py` 显式导入和挂接场景。这种结构在场景数量较少时可用，但随着固定场景持续增加，会带来三个问题：

- 阅读一个场景时需要在多个目录之间来回跳转，认知成本高
- 新增一个场景至少需要改动场景文件、SQL 文件和注册中心，步骤分散且容易遗漏
- 后续若一个场景需要多 SQL、多脚本或补充说明文件，现有目录范式会继续放大维护负担

本次变更希望把场景组织从“按资产类型分散”升级为“按场景聚合”，并把注册方式从“手工注册”升级为“约定式自动发现”，使后续新增场景时只需要新增一个场景目录并填写模板。

## What Changes

- 将领域下的场景目录重构为 `scenarios/<scenario_name>/` 场景聚合结构
- 引入领域级 `shared/` 公共资产目录，承载跨场景复用的 SQL 和脚本
- 将技能注册中心从显式导入/追加改为基于目录约定的自动发现
- 调整场景资产引用方式，支持基于 `scope + path` 的相对路径解析
- 一次性迁移现有 `paint_shop_vehicle_tracking` 场景、测试和文档到新范式

## Impact

- Affected specs: `business-skills`
- Affected code:
  - `backend/app/skills/models.py`
  - `backend/app/skills/assets.py`
  - `backend/app/skills/registry.py`
  - `backend/app/skills/renderers.py`
  - `backend/app/test_skill_registry.py`
  - `docs/backend/skills/README.md`

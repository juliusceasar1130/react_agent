## Context

当前场景技能的主要摩擦点不在运行时工具接口，而在“维护者如何新增和组织场景资产”：

- 场景元数据放在 `scenarios/*.py`
- SQL 模板放在 `sql/*.sql`
- 脚本放在 `scripts/`
- `registry.py` 通过显式 import 和 append 挂接场景

这导致维护者在新增一个场景时必须跨多个位置修改，并且很难一眼看出“一个场景到底包含哪些资产”。

## Goals / Non-Goals

- Goals:
  - 让每个场景以独立目录承载自己的元数据、SQL 和脚本
  - 新增场景时不再手改 `registry.py`
  - 保持 `load_skill()` / `load_scenario()` 等运行时调用接口不变
  - 为未来多 SQL、多脚本、多说明文件场景预留稳定组织方式
- Non-Goals:
  - 本次不引入新的专用场景执行器
  - 本次不改变领域/场景的二级披露主链路
  - 本次不实现对旧目录结构的长期双轨兼容

## Decisions

- Decision: 使用“场景目录聚合”作为唯一新增规范
  - Layout:
    - `domains/<domain>/meta.py`
    - `domains/<domain>/domain.md`
    - `domains/<domain>/scenarios/<scenario_name>/scenario.py`
    - `domains/<domain>/scenarios/<scenario_name>/sql/main.sql`
    - `domains/<domain>/scenarios/<scenario_name>/scripts/`
    - `domains/<domain>/shared/sql/`
    - `domains/<domain>/shared/scripts/`
  - Why: 一个目录对应一个场景，阅读、评审、迁移和复制模板都更直接

- Decision: 将注册中心改为“约定式自动发现”
  - Discovery rules:
    - 领域：扫描 `domains/*/meta.py`，并要求同目录存在 `domain.md`
    - 场景：扫描 `domains/<domain>/scenarios/*/scenario.py`
    - 忽略 `__pycache__` 和以下划线开头目录
  - Validation rules:
    - 场景目录名必须等于 `SCENARIO["name"]`
    - `SCENARIO["skill_name"]` 必须等于所属领域名
    - 同一领域下场景名不可重复
    - 资产路径必须可解析
  - Why: 后续新增场景不再修改注册中心，减少漏接风险

- Decision: 资产路径改为 `scope + path` 语义
  - `scope="scenario"`：相对当前场景目录
  - `scope="shared"`：相对当前领域 `shared/`
  - `scope="domain"`：相对当前领域根目录
  - Why: 避免维护者继续书写 `paint_shop_vehicle_tracking/sql/...` 这种长路径

- Decision: 保持运行时接口稳定，只重构内部装配方式
  - Stable APIs:
    - `get_skill_by_name()`
    - `list_scenarios_by_skill()`
    - `get_scenario_by_name()`
    - `load_domain_content()`
    - `load_scenario_content()`
    - `load_skill()`
    - `load_scenario()`
  - Why: 把影响收敛在“目录规范 + 注册实现 + 文档”，避免扩大回归面

- Decision: 一次性切换，不保留长期兼容层
  - Why: 用户已明确偏向一次切换；长期双轨会让文档、发现逻辑和测试复杂度翻倍

## Risks / Trade-offs

- 自动发现比显式注册更依赖目录约定，错误目录结构会在导入期暴露出来
- 一次切换要求文档、测试和现有场景同步迁移，否则容易出现短期断裂
- `shared/` 若使用边界不清，可能重新演变成新的“杂物目录”

## Migration Plan

1. 新增 `business-skills` spec delta，明确目录与发现规则
2. 重构 `models.py`、`assets.py`、`registry.py`，支持新资产语义和自动发现
3. 将 `paint_shop_vehicle_tracking` 迁移到新目录结构
4. 更新测试，覆盖自动发现与资产解析
5. 更新技能专题文档、README 和 changelog

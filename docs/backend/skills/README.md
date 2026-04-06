# Skills 总览与文档导航

修改时间：2026-04-06 21:22 Asia/Shanghai

主要修改内容：
- 将技能专题文档同步到“场景目录聚合 + 自动发现”新范式
- 补充 `discovery.py`、`scope + path` 资产解析和 `shared/` 公共资产约定
- 更新当前目录结构示例和新增场景的维护建议

## 当前机制概览

业务技能系统当前仍是“领域 skill + 场景 skill”二级披露：

1. `SkillMiddleware` 只向模型暴露领域摘要
2. 模型先按需调用 `load_skill()` 加载领域公共知识
3. 命中固定场景后，再调用 `load_scenario()` 加载场景 playbook
4. SQL 执行仍由现有工具链负责，场景主要补充 workflow、口径和模板资产

本次优化的重点不在运行时接口，而在**维护者如何组织和新增场景**：

- 场景按 `scenarios/<scenario_name>/` 聚合
- `registry.py` 不再手工 import 场景，而是通过 `discovery.py` 自动发现
- 资产引用不再写长路径，而是统一使用 `scope + path`

## 核心目录结构

```text
backend/app/skills/
  __init__.py
  assets.py
  discovery.py
  loaders.py
  models.py
  registry.py
  renderers.py
  domains/
    paint_shop_vehicle_tracking/
      domain.md
      meta.py
      scenarios/
        daily_area_body_count/
          scenario.py
          sql/
            main.sql
        realtime_area_body_count/
          scenario.py
          sql/
            main.sql
      shared/
        scripts/
          README.md
```

结构含义：

- `domain.md`
  领域公共知识、表结构说明和通用业务规则
- `scenarios/<scenario_name>/scenario.py`
  单个固定场景的 playbook 元数据
- `scenarios/<scenario_name>/sql/`
  当前场景专属 SQL 模板
- `shared/`
  同一领域下多个场景共享的公共资产

## 模块职责

### `models.py`

定义 `Skill`、`DomainSkill`、`ScenarioSkill`、`AssetRef`、`ParameterDefinition`。

本次新增的关键点：

- `AssetRef.scope`
  - `scenario`：相对当前场景目录
  - `shared`：相对当前领域的 `shared/`
  - `domain`：相对当前领域根目录

### `assets.py`

负责：

- 读取文本文件
- 解析带 `scope` 的资产路径
- 在发现阶段和渲染阶段统一校验资产存在性

### `discovery.py`

负责：

- 自动扫描 `domains/*/meta.py`
- 自动扫描 `domains/<domain>/scenarios/*/scenario.py`
- 校验场景目录名、`skill_name`、资产路径是否合法

这是本次“后续新增场景更方便”的核心模块。

### `registry.py`

负责：

- 基于 `discover_domains()` / `discover_scenarios()` 组装运行时注册表
- 生成 `DOMAIN_SKILLS`
- 生成 `SCENARIOS_BY_SKILL`
- 生成兼容旧接口的 `SKILLS`

### `renderers.py`

负责把结构化领域/场景对象渲染为给 LLM 使用的文本，并在场景文本中展示：

- 触发问法
- 输入参数与参数定义
- workflow / rules / gotchas
- 模板资产与脚本资产摘要
- 第一份主 SQL 模板正文

### `loaders.py`

对外提供：

- `load_domain_content()`
- `load_scenario_content()`

### `backend/app/agent/tools/skill_tools.py`

对外暴露：

- `load_skill()`
- `load_scenario()`

运行时接口没有因为这次目录重构而改变。

## 当前新增场景的最短路径

新增一个场景时，推荐只做下面 4 步：

1. 在 `domains/<domain>/scenarios/` 下复制一个场景目录
2. 编写 `scenario.py`
3. 编写 `sql/main.sql`
4. 运行技能相关验证，不再修改 `registry.py`

如果需要跨多个场景复用脚本或 SQL，再把公共内容放到 `shared/`。

## 设计边界

当前仍保留以下边界：

- `required_skill` 仍是领域级，而不是场景级
- `load_scenario()` 仍然是按需加载知识，不是固定报表执行器
- 命中场景后，系统仍可能结合历史 SQL 示例继续生成 SQL

所以这次优化解决的是**目录组织和维护效率**，不是“场景模板优先执行”那条后续演进路线的全部问题。

## 文档分工

1. [技能注册中心与加载机制说明](./技能注册中心与加载机制说明.md)
   适合先理解自动发现、注册装配和运行时调用链。

2. [新增业务领域技能开发指南](./新增业务领域技能开发指南.md)
   适合新增整个领域时参考。

3. [新增场景技能开发指南](./新增场景技能开发指南.md)
   适合在已有领域下新增固定统计场景时参考。

## 一句话总结

当前技能系统已经从“场景文件 + 分散 SQL + 手工注册”演进为“场景目录聚合 + 自动发现 + scoped 资产解析”的结构；后续新增场景时，应尽量把一个场景维护成一个完整目录单元。

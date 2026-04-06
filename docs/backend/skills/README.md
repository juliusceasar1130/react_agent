# Skills 总览与文档导航

修改时间：2026-04-06 Asia/Shanghai

主要修改内容：
- 将目录级 README 升级为”机制总览 + 调用链说明 + 文档导航”
- 汇总”领域 skill + 场景 skill”二级重构的核心机制、模块职责与函数调用关系
- 补充”固定场景命中后仍检索历史 SQL 示例”的潜在冲突与后续完善计划
- 同步当前目录结构示例，补充 `realtime_area_body_count` 场景与 SQL 模板
- 新增场景参数化筛选机制说明，支持 LLM 自主决定参数填充

## 重构后的核心机制

本次重构把原先单文件 `backend/app/skills.py` 升级成 `backend/app/skills/` package，并引入“领域 skill + 场景 skill”二级披露机制。

目标不是把所有知识都塞进 system prompt，而是把技能系统拆成 4 个层次：

1. 领域元数据与公共说明
2. 固定场景元数据与外部 SQL/脚本资产
3. 注册中心与文本渲染层
4. 运行时工具加载与中间件注入层

当前运行机制可以概括为：

- `SkillMiddleware` 只把领域摘要注入 system prompt
- 模型先通过 `load_skill()` 加载领域公共知识
- 若命中固定场景，再通过 `load_scenario()` 加载场景 playbook
- 最终仍然通过现有 `required_skill` 领域级约束调用 SQL 工具链

这意味着：

- 领域层负责“这个业务世界是什么”
- 场景层负责“这个固定问题该怎么做”
- SQL 工具层继续负责“按受控方式执行查询”

## 模块分层与职责

### 1. 导出层：`backend/app/skills/__init__.py`

职责：

- 对外导出兼容旧代码的 `SKILLS`
- 对外导出查询与加载接口

关键导出：

- `SKILLS`
- `DOMAIN_SKILLS`
- `SCENARIOS_BY_SKILL`
- `get_skill_by_name()`
- `list_scenarios_by_skill()`
- `get_scenario_by_name()`
- `load_domain_content()`
- `load_scenario_content()`

它的作用是把内部注册中心封装成统一入口，保证现有：

```python
from backend.app.skills import SKILLS
```

仍然可用。

### 2. 数据模型层：`models.py`

职责：

- 定义领域技能、场景技能、资产引用的数据结构
- 定义场景参数的结构化描述

核心结构：

- `Skill`
  兼容旧版 `name / description / content`
- `DomainSkill`
  领域内部运行时结构
- `ScenarioSkill`
  场景内部运行时结构
- `AssetRef`
  外部 SQL / 脚本 / 文档引用
- `ParameterDefinition`
  场景参数定义，用于指导 LLM 动态填充参数

### 3. 资产层：`assets.py`

职责：

- 解析并读取外部文本资产

关键函数：

- `resolve_asset_path()`
- `read_asset_text()`

它是 `registry.py` 和 `renderers.py` 读取 `domain.md`、`.sql` 的基础设施。

### 4. 注册中心层：`registry.py`

职责：

- 导入领域元数据
- 导入场景元数据
- 组装 `SCENARIOS_BY_SKILL`
- 组装 `DOMAIN_SKILLS`
- 最终生成兼容导出的 `SKILLS`

关键对象和函数：

- `_build_scenario_summaries()`
- `SCENARIOS_BY_SKILL`
- `DOMAIN_SKILLS`
- `SKILLS`
- `get_skill_by_name()`
- `list_scenarios_by_skill()`
- `get_scenario_by_name()`

这是整个技能系统的“装配中心”。

### 5. 渲染层：`renderers.py`

职责：

- 把结构化领域/场景对象渲染成给 LLM 的文本

关键函数：

- `render_domain_for_llm()`
- `render_scenario_for_llm()`
- `_render_asset_refs()`

其中：

- `render_domain_for_llm()` 会拼出：
  - 领域名
  - 领域公共说明
  - 场景摘要
  - 使用规则
- `render_scenario_for_llm()` 会拼出：
  - 场景描述
  - triggers
  - 输入参数
  - **参数定义**（parameters）：详细展示参数类型、说明、示例值、SQL 片段和使用方式
  - workflow
  - rules
  - gotchas
  - output contract
  - 模板资产和 SQL 示例

### 6. 加载层：`loaders.py`

职责：

- 对外提供“按名称加载领域全文 / 场景全文”的统一接口

关键函数：

- `load_domain_content()`
- `load_scenario_content()`

调用关系：

- `load_domain_content()`
  - `get_skill_by_name()`
  - `list_scenarios_by_skill()`
  - `render_domain_for_llm()`
- `load_scenario_content()`
  - `get_scenario_by_name()`
  - `render_scenario_for_llm()`

### 7. 运行时工具层：`backend/app/agent/tools/skill_tools.py`

职责：

- 把领域技能或场景技能真正写入对话上下文
- 更新运行时状态

关键函数：

- `_merge_names()`
- `_build_load_skill_command()`
- `_build_load_scenario_command()`
- `load_skill()`
- `load_scenario()`

关键状态更新：

- `load_skill()` 更新：
  - `skills_loaded`
  - `active_skill`
- `load_scenario()` 更新：
  - `scenarios_loaded`
  - `active_skill`
  - `active_scenario`

### 8. 中间件层：`backend/app/agent/middleware/skill_middleware.py`

职责：

- 在每次模型调用前注入领域摘要
- 给模型暴露 `load_skill` 和 `load_scenario`

关键函数：

- `_build_skills_prompt()`
- `_modify_request()`
- `wrap_model_call()`
- `awrap_model_call()`

重点：

- 这里只注入领域摘要，不注入场景全文
- 场景全文必须通过 `load_scenario()` 按需获取

### 9. Agent 编排层：`backend/app/agent/service.py`

职责：

- 创建 Agent
- 装配工具链、中间件和 system prompt

和技能系统最相关的部分：

- `_prepare_tools()`
  装配 SQL 工具、RAG 工具、CSV 工具
- `_build_system_prompt()`
  明确写入“先 `load_skill`，再按需 `load_scenario`”
- `SQLAgentService._initialize_agent()`
  将 `SkillMiddleware()` 挂入 Agent 中间件链

## 关键函数调用关系

## 1. 模块导入时的装配链

当代码执行：

```python
from backend.app.skills import SKILLS
```

内部调用链是：

```text
backend.app.skills.__init__
  -> registry.py 顶层装配
    -> 导入 DOMAIN_META / SCENARIO
    -> read_asset_text(domain.md)
    -> 生成 SCENARIOS_BY_SKILL
    -> 生成 DOMAIN_SKILLS
    -> render_domain_for_llm(...)
    -> 生成兼容层 SKILLS
```

注意：

- 这是模块导入时执行的装配
- 当前不是自动扫描目录，而是显式注册

## 2. 领域技能加载链

当模型调用：

```python
load_skill("paint_shop_vehicle_tracking")
```

函数调用关系是：

```text
load_skill()
  -> emit_stream_status(...)
  -> _build_load_skill_command()
    -> get_skill_by_name()
    -> load_domain_content()
      -> get_skill_by_name()
      -> list_scenarios_by_skill()
      -> render_domain_for_llm()
    -> Command(update=...)
      -> ToolMessage(content=领域全文)
      -> skills_loaded += [skill_name]
      -> active_skill = skill_name
```

结果：

- 领域公共知识进入消息上下文
- 当前领域被标记为 active

## 3. 场景技能加载链

当模型调用：

```python
load_scenario("paint_shop_vehicle_tracking", "daily_area_body_count")
```

函数调用关系是：

```text
load_scenario()
  -> emit_stream_status(...)
  -> _build_load_scenario_command()
    -> get_skill_by_name()
    -> 检查 runtime.state["skills_loaded"]
    -> get_scenario_by_name()
    -> load_scenario_content()
      -> get_scenario_by_name()
      -> render_scenario_for_llm()
        -> _render_asset_refs()
        -> read_asset_text(.sql)
    -> Command(update=...)
      -> ToolMessage(content=场景全文)
      -> scenarios_loaded += [skill.scenario]
      -> active_skill = skill_name
      -> active_scenario = scenario_name
```

结果：

- 场景 workflow、规则、易错点和模板引用进入上下文
- 当前场景被标记为 active

## 4. 模型请求前的中间件注入链

每次模型调用前：

```text
SkillMiddleware.wrap_model_call()
  -> _modify_request()
    -> _build_skills_prompt(SKILLS)
    -> 将领域摘要追加到 system_message
```

这里注入的是：

- 领域名
- 领域 description
- “固定场景要按需 `load_scenario`”的行为提示

## 5. 业务问题从提问到 SQL 的完整主链路

当前主链路可以总结为：

```text
用户问题
  -> Agent system prompt + SkillMiddleware
  -> 模型看到领域摘要
  -> 调用 load_skill(domain)
  -> 领域公共知识进入上下文
  -> 若命中固定场景，调用 load_scenario(domain, scenario)
  -> 场景 playbook 进入上下文
  -> 当前实现中，仍优先调用 search_saved_correct_tool_uses(...)
  -> 生成 SQL
  -> 调用 sql_db_query(query, required_skill=domain)
  -> SQL 工具校验领域 skill 已加载
  -> 执行查询并返回结果
```

重点边界：

- `required_skill` 仍是领域级，不是场景级
- 场景技能只补充约束，不参与 SQL 工具强校验

## 当前潜在问题：固定场景与历史 SQL 示例可能互相干扰

当前实现虽然已经支持”命中固定场景后先加载 `load_scenario()`”，但在 system prompt 的工作流里，仍然保留了”查询前优先调用 `search_saved_correct_tool_uses(...)`”这一策略。

这在普通自由查询里通常是有价值的，但对”SQL 结构基本固定、只变化参数”的场景来说，会带来潜在冲突：

1. 场景模板已经在约束模型按固定 SQL 结构思考
2. `search_saved_correct_tool_uses(...)` 又会返回另一组历史 SQL 示例
3. 如果两者写法不一致，模型会重新进入”多候选综合决策”状态
4. 这会削弱场景层原本想达到的”减少随机规划、固定 SQL 结构”的目标

换句话说：

- 如果场景只是”说明性 playbook”，查历史 SQL 仍然有帮助
- 如果场景已经接近”准模板 / 半执行器”，再查历史 SQL 就可能干扰最终决策

## 场景参数化筛选机制

### 背景

某些场景需要支持参数筛选，让 LLM 能根据用户问题自主决定是否添加 SQL 条件。例如：

- “各区域有多少车身” → 查询所有区域
- “电泳区域有多少车身” → 只查询电泳区域
- “电泳和面漆区域各有多少车身” → 只查询这两个区域

### 设计方案

采用**声明式参数定义 + SQL 模板参数化**的方案：

1. **场景元数据增强**：新增 `parameters` 字段，详细描述每个参数
2. **数据模型更新**：新增 `ParameterDefinition` 类型定义
3. **SQL 模板参数化**：在 SQL 中添加参数注释和使用示例
4. **渲染器更新**：在场景加载时展示参数定义

### 参数定义结构

```python
class ParameterDefinition(TypedDict):
    “””场景参数定义，用于指导 LLM 动态填充参数。”””
    type: str  # “array”, “string”, “integer” 等
    items_type: str  # 仅当 type=”array” 时使用
    description: str  # 参数用途说明
    required: bool  # 是否必填
    source_column: str  # 数据库列名
    source_table: str  # 可选值来源表
    example_values: list[str]  # 示例值
    usage: str  # 使用方式说明
    sql_fragment: str  # SQL 片段模板
```

### LLM 决策流程

```
用户问题 → load_scenario() → LLM 阅读参数定义
                                    ↓
                          判断是否需要筛选
                          ↓              ↓
                       需要筛选       不需要筛选
                          ↓              ↓
                   添加 WHERE 条件    保持原 SQL
```

### 示例：realtime_area_body_count

```python
“parameters”: {
    “process_area”: {
        “type”: “array”,
        “items_type”: “string”,
        “description”: “工艺区域名称列表，用于筛选特定区域的车身数量”,
        “required”: False,
        “source_column”: “process_area”,
        “source_table”: “process_areas”,
        “example_values”: [“电泳”, “面漆”, “烘干”],
        “usage”: “当用户询问特定区域时，将此参数添加到 SQL 的 WHERE 子句中”,
        “sql_fragment”: “AND rp.process_area IN ('{values}')”,
    }
}
```

渲染后 LLM 看到的内容：

```
## 参数定义
### process_area
- 类型: array (元素类型: string)
- 必填: 否
- 说明: 工艺区域名称列表，用于筛选特定区域的车身数量
- 来源表: process_areas.process_area
- 示例值: 电泳, 面漆, 烘干, 电泳烘干, 面漆烘干
- SQL 片段: AND rp.process_area IN ('{values}')
- 使用方式: 当用户询问特定区域时，将此参数添加到 SQL 的 WHERE 子句中
```

## 当前设计结论

当前阶段文档和代码里仍保留：

- `load_skill()`
- `load_scenario()`
- `search_saved_correct_tool_uses(...)`

这是因为第一阶段的场景技能还只是“二级知识披露”，不是“模板执行器”。

因此当前边界应理解为：

- **现状**：命中固定场景后，系统仍可能继续走 `search_saved_correct_tool_uses(...)`
- **风险**：当场景已经很强约束时，这会对 LLM 产生决策干扰
- **结论**：这是已知设计债，后续应按“场景模板优先、历史 SQL 回退”来收敛

## 后续完善计划

后续建议把固定场景的执行策略从“场景披露 + 历史示例优先”逐步演进为“场景模板优先”。

建议分 3 步实施：

### 第 1 步：在场景元数据中显式声明策略

为 `ScenarioSkill` 增加类似字段：

```python
query_strategy: "scenario_template_first" | "example_search_first"
```

建议默认含义：

- `scenario_template_first`
  命中固定场景后优先按场景模板生成 SQL，历史 SQL 仅作回退
- `example_search_first`
  适合场景约束较弱、仍需要大量参考历史 SQL 的问题

### 第 2 步：调整系统提示词和运行时决策顺序

固定场景命中后改成：

```text
load_skill(domain)
-> load_scenario(domain, scenario)
-> 优先按场景模板生成 SQL
-> 若模板不足或报错，再调用 search_saved_correct_tool_uses(...)
```

而非固定场景继续保留：

```text
load_skill(domain)
-> search_saved_correct_tool_uses(...)
-> 生成 SQL
```

### 第 3 步：为高频场景引入模板执行器或专用 tool

最终目标应是：

- 场景不再只是“说明文档”
- 而是逐步升级为“带参数的固定 SQL 模板入口”或“专用 report tool”

一旦这一层完成：

- 命中固定场景后就可以直接跳过 `search_saved_correct_tool_uses(...)`
- 场景真正成为最终决策源，而不是一个参考源

## 当前目录结构

当前与二级 Skill 机制直接相关的结构如下：

```text
backend/app/skills/
  __init__.py
  assets.py
  loaders.py
  models.py
  registry.py
  renderers.py
  domains/
    paint_shop_vehicle_tracking/
      domain.md
      meta.py
      scenarios/
        daily_area_body_count.py
        realtime_area_body_count.py
      sql/
        daily_area_body_count.sql
        realtime_area_body_count.sql
      scripts/
        README.md
```

## `docs/backend/skills/` 内文档分工

1. [技能注册中心与加载机制说明](./技能注册中心与加载机制说明.md)
   适合先理解注册中心、渲染层、兼容导出层的职责。

2. [新增业务领域技能开发指南](./新增业务领域技能开发指南.md)
   适合需要扩展新领域时参考。

3. [新增场景技能开发指南](./新增场景技能开发指南.md)
   适合需要在已有领域下新增固定统计场景时参考。

## 推荐阅读顺序

1. 先读本 README，建立整体机制和调用链认知
2. 再读“技能注册中心与加载机制说明”，看装配细节
3. 如需扩展新领域，读“新增业务领域技能开发指南”
4. 如需扩展场景，读“新增场景技能开发指南”

## 一句话总结

这次“领域与场景二级 Skill”重构，本质上是把业务知识从“单段文本”升级为“领域注册中心 + 场景 playbook + 外部资产 + 运行时按需加载”的分层系统；当前仍保留“场景命中后继续参考历史 SQL 示例”的过渡策略，后续应进一步收敛到“场景模板优先、历史 SQL 回退”的实现方向。

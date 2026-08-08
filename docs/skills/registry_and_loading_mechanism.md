# 技能注册中心、自动发现与动态加载机制

> **文档版本**: v1.1  
> **归档位置**: `docs/skills/registry_and_loading_mechanism.md`  
> **面向对象**: 系统架构师、后端 Agent 开发者

---

## 一、 系统架构与分层装配

技能系统底层采用 **约定优于配置 (Convention Over Configuration)** 的自动装配架构。

后端模块包含两套并行机制：
1. **智能体动态加载路径 (Agent Skill Path)**：`SkillMiddleware` -> `load_skill()` / `load_scenario()` -> LLM System Prompt 注入；
2. **快捷直通查询路径 (Direct SQL Query Path)**：REST API (`/api/scenarios/...`) -> `resolver.py` -> `executor.py` -> `formatter.py`。

```
                       backend/app/skills/
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
     discovery.py          registry.py           assets.py
   (目录自动扫描校验)     (全局运行时注册表)     (scope+path 路径解析)
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                       loaders.py / renderers.py
                       (上下文渲染与 ToolMessage 注入)
```

---

## 二、 核心对象与运行时数据结构 (`registry.py`)

### 1. `DOMAIN_SKILLS`
- 类型: `dict[str, DomainSkill]`
- 职责: 汇总全局领域定义、公共 `domain.md` 上下文与领域下辖的所有场景列表。

### 2. `SCENARIOS_BY_SKILL`
- 类型: `dict[str, dict[str, ScenarioSkill]]`
- 职责: 提供 `domain_name -> scenario_name -> ScenarioSkill` 的二级快速索引结构，为 `get_scenario_by_name()` 与直通引擎解析提供高效内存检索。

### 3. `SKILLS`
- 类型: `dict[str, Skill]`
- 职责: 保持向后兼容导出层，向 `SkillMiddleware` 提供包含描述与渲染正文的字典，供中间件向系统提示词注入领域摘要。

---

## 三、 自动发现机制 (`discovery.py`)

### 3.1 领域发现 (`discover_domains`)
系统遍历 `backend/app/skills/domains/` 下的所有一级目录：
- 校验必须包含 `meta.py` 与 `domain.md`；
- 动态导入 `meta.py` 并读取 `DOMAIN_META`；
- 校验 `DOMAIN_META["name"]` 与所在目录名完全相同。

### 3.2 场景发现 (`discover_scenarios`)
系统遍历每个领域目录下的 `scenarios/*/` 场景子目录：
- 校验必须包含 `scenario.py`；
- 支持 `SCENARIO` 或 `SCENARIO_META` 双导出别名；
- 校验 `scenario["name"]` 与场景子目录名完全相同；
- 校验 `scenario["skill_name"]` 与所属领域名完全相同；
- **自动派生输入参数**：若场景元数据未显式配置 `required_inputs` / `optional_inputs`，系统基于 `parameters` 字典中各参数的 `required` 属性进行内存自动派生防错；
- **资产路径提前校验**：调用 `assets.resolve_asset_path` 提前校验 `sql_template_refs` 与 `script_refs` 在磁盘上的物理文件存在性。

---

## 四、 资产路径解析机制 (`assets.py`)

资产引用统一采用 `scope + path` 相对路径语义：

```python
{
    "type": "sql",
    "name": "main",
    "scope": "scenario",   # 作用域: scenario | shared | domain
    "path": "sql/main.sql",# 相对路径
    "description": "主查询模板"
}
```

作用域解析规则：
- **`scenario`**：相对当前场景目录 `domains/<domain>/scenarios/<scenario>/`；
- **`shared`**：相对当前领域公共目录 `domains/<domain>/shared/`；
- **`domain`**：相对当前领域根目录 `domains/<domain>/`。

解析器强校验路径越界（防止 `../` 越界读取系统敏感文件）。

---

## 五、 运行时调用链路

### 1. 智能体问答加载链路
```text
用户提问 
  └─► SkillMiddleware (注入领域摘要与可用技能列表)
        └─► Agent 识别意图并调用 load_scenario(skill_name, scenario_name)
              └─► loaders.load_scenario_content()
                    └─► renderers.render_scenario_for_llm() (剔除纯 UI 属性)
                          └─► 返回 ToolMessage 正文给 Agent
```

### 2. 快捷直通查询链路
```text
用户点击右侧直通卡片 / ScenarioModal
  └─► POST /api/scenarios/{domain}/{scenario}/execute
        └─► resolver.resolve_params() (解析并补全下拉选项)
              └─► executor.build_executed_sql() (占位符替换与命名参数绑定)
                    └─► executor.execute_scenario() (执行查询，fetchmany 300 截断保护)
                          └─► formatter.format_result() (转为 table/scalar/chart 格式返回)
```

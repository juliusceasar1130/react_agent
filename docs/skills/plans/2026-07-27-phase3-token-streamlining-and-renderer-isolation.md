# Phase 3: Token 精简与渲染隔离 RFC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `renderers.py` 中实现纯 UI 元数据（如 `widget`、`source_table`、`source_column`）从 LLM Context 中的剥离，并在 `discovery.py` 中实现 `required_inputs`/`optional_inputs` 内存派生兜底与模块别名导出兼容，降低 50%+ 提示词 Token 消耗。

**Architecture:** 优化 LLM 场景 Prompt 渲染器 `render_scenario_for_llm`，屏蔽无意图生成帮助的前端 UI 表单参数；增强 `discovery.py` 的场景加载解析器，支持从 `parameters` 的 `required` 属性派生输入清单，并增强 `SCENARIO` / `SCENARIO_META` 双模式模块属性容错。

**Tech Stack:** Python 3.12, LangChain Prompt Formatting, Pydantic/TypedDict Metadata.

---

### User Review Required

> [!IMPORTANT]
> **Token 优化与兼容性**：本次修改剥离的仅为 Prompt 中发给 LLM 的字符串明文，前端快捷直通表单（通过 `/params` 接口调用 `resolver.py`）不受任何影响，控件下拉框依然可正常渲染。

---

### Proposed Changes & File Mapping

#### Prompt Renderer

##### [MODIFY] [renderers.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/renderers.py)
- 在 `render_scenario_for_llm` 的参数循环中，移除 `source_table` 与 `source_column` 的 Prompt 拼接输出，保留核心意图与 `sql_fragment` 说明。

#### Scenario Discovery Engine

##### [MODIFY] [discovery.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/discovery.py)
- 在 `discover_scenarios` 中，容错读取 `getattr(module, "SCENARIO", None) or getattr(module, "SCENARIO_META", None)`；
- 增加 `required_inputs` 与 `optional_inputs` 的自动派生兜底逻辑。

---

## Detailed Task Breakdown

### Task 1: Prompt 渲染剥离 - 优化 `render_scenario_for_llm` 剔除纯 UI 属性

**Files:**
- Modify: `backend/app/skills/renderers.py:75-99`

- [ ] **Step 1: 检查 `render_scenario_for_llm` 中的参数循环**

在 `backend/app/skills/renderers.py` 查看当前第 74-99 行：
```python
    if scenario.get("parameters"):
        lines.append("## 参数定义")
        for param_name, param_def in scenario["parameters"].items():
            lines.append(f"### {param_name}")
            ...
            if "source_table" in param_def or "source_column" in param_def:
                table = param_def.get("source_table", "未知表")
                col = param_def.get("source_column", "未知字段")
                lines.append(f"- 来源表: {table}.{col}")
```

- [ ] **Step 2: 剥离 `source_table` / `source_column` 纯 UI 渲染字段**

在 `backend/app/skills/renderers.py` 中更新 `render_scenario_for_llm`，精简 Prompt 输出：
```python
    # 新增：参数详细展示 (专为 LLM 提示词精简，不输出 widget/source_table 等 UI 元数据)
    if scenario.get("parameters"):
        lines.append("## 参数定义")
        for param_name, param_def in scenario["parameters"].items():
            lines.append(f"### {param_name}")
            lines.append(
                f"- 类型: {param_def['type']}"
                + (
                    f" (元素类型: {param_def['items_type']})"
                    if param_def.get("items_type")
                    else ""
                )
            )
            lines.append(f"- 必填: {'是' if param_def.get('required') else '否'}")
            lines.append(f"- 说明: {param_def.get('description', '')}")
            
            if param_def.get("example_values"):
                lines.append(f"- 示例值: {', '.join(str(v) for v in param_def['example_values'])}")
            if param_def.get("sql_fragment"):
                lines.append(f"- SQL 片段: {param_def['sql_fragment']}")
            if param_def.get("usage"):
                lines.append(f"- 使用方式: {param_def['usage']}")
            lines.append("")
```

- [ ] **Step 3: 验证渲染器输出格式**

运行 Python 命令：
```bash
python -c "from backend.app.skills.registry import reload_skills, get_scenario_by_name; reload_skills(); from backend.app.skills.renderers import render_scenario_for_llm; s = get_scenario_by_name('paint_shop_vehicle_logistics', 'stranded_vehicle_detection'); text = render_scenario_for_llm(s); print(text); assert '来源表:' not in text"
```
Expected output: 成功打印精简后的 Prompt 文本，断言 `来源表:` 不在文本中通过！

---

### Task 2: 场景发现引擎增强 - `SCENARIO_META` 别名兼容与参数自动派生

**Files:**
- Modify: `backend/app/skills/discovery.py:105-135`

- [ ] **Step 1: 定位 `discover_scenarios` 中的元数据加载点**

在 `backend/app/skills/discovery.py` 中查看第 108-135 行：
```python
        scenario = getattr(module, "SCENARIO", None)
        if not isinstance(scenario, dict):
            raise ValueError(f"场景元数据必须定义 SCENARIO: {scenario_file}")
```

- [ ] **Step 2: 实现别名容错获取与输入自动派生**

在 `backend/app/skills/discovery.py` 中将加载逻辑修改为：
```python
        scenario = getattr(module, "SCENARIO", None) or getattr(module, "SCENARIO_META", None)
        if not isinstance(scenario, dict):
            raise ValueError(f"场景元数据必须定义 SCENARIO 或 SCENARIO_META: {scenario_file}")

        scenario_name = scenario.get("name")
        if not isinstance(scenario_name, str) or not scenario_name:
            raise ValueError(f"场景元数据缺少合法 name: {scenario_file}")
        if scenario_name != scenario_dir.name:
            raise ValueError(
                "场景目录名与 SCENARIO['name'] 不一致: "
                f"{scenario_dir.name} != {scenario_name}"
            )
        if scenario.get("skill_name") != domain.name:
            raise ValueError(
                "场景 skill_name 与所属领域不一致: "
                f"{scenario.get('skill_name')} != {domain.name}"
            )
        if scenario_name in seen_names:
            raise ValueError(f"发现重复场景名: {domain.name}.{scenario_name}")

        scenario_payload = dict(scenario)
        scenario_payload.setdefault("parameters", {})
        scenario_payload.setdefault("sql_template_refs", [])
        scenario_payload.setdefault("script_refs", [])

        # 自动派生 required_inputs / optional_inputs (防护缺漏)
        params_dict = scenario_payload["parameters"]
        if "required_inputs" not in scenario_payload or "optional_inputs" not in scenario_payload:
            req_inputs = [k for k, v in params_dict.items() if v.get("required")]
            opt_inputs = [k for k, v in params_dict.items() if not v.get("required")]
            scenario_payload.setdefault("required_inputs", req_inputs)
            scenario_payload.setdefault("optional_inputs", opt_inputs)

        scenario_payload["scenario_root"] = str(scenario_dir.resolve())
        scenario_payload["domain_root"] = str(domain.domain_dir.resolve())
```

- [ ] **Step 3: 验证别名兼容与自动派生功能**

运行 Python 验证脚本：
```bash
conda run -n py312_agent python -c "from backend.app.skills.registry import reload_skills, get_scenario_by_name; reload_skills(); s = get_scenario_by_name('paint_shop_vehicle_logistics', 'stranded_vehicle_detection'); print('Required:', s.get('required_inputs')); print('Optional:', s.get('optional_inputs'))"
```
Expected output: 成功输出 `Required` 与 `Optional` 列表。

---

## Verification Plan

### Automated Verification
1. 运行全局资产路径校验：
   ```bash
   python backend/app/skills/domains/verify_assets.py
   ```
2. 运行 Prompt Token 精简与渲染测试：
   ```bash
   conda run -n py312_agent python -c "from backend.app.skills.registry import reload_skills, get_all_skills; reload_skills(); skills = get_all_skills(); total_len = sum(len(s['content']) for s in skills); print('Total prompt length:', total_len)"
   ```
   预期输出：整体 Prompt 字符串长度明显缩减。

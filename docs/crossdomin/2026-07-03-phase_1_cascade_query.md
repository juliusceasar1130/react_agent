# SQL Agent Phase 1 (级联子查询直连) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现零人工维护的跨域级联子查询直连功能，打通大模型动态自愈加载辅助表 DDL 的能力，并在新对话轮次自动完成状态清空。

**Architecture:** 
1. 扩展 `meta.py` 关联表名，提取 `db.custom_table_info` 内存缓存 DDL。
2. 重构 `load_skill` 从覆写式改为去重追加模式，激活 `skills_loaded` 列表的多值并存能力。
3. 改造 `SkillMiddleware`，拦截 `_modify_request` 分层拼装主辅 Prompt，并实现 `before_agent` 原生生命周期钩子，在新一轮消息到达前自动清空辅助列表。

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, LangGraph 1.0, LangChain, PyTest

---

### Task 1: 技能元数据注册与associated_tables声明

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py:10-14`
- Modify: `backend/app/skills/domains/paint_shop_defect_analysis/meta.py:10-14`

- [ ] **Step 1: 在物流追踪技能元数据中注册关联物理表**

```python
# 修改 backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py 中的 DOMAIN_META：
DOMAIN_META = {
    "name": "paint_shop_vehicle_logistics",
    "title": "物流追踪",
    "description": "涂装车间车身物流与追踪领域，负责查询车辆的实时位置分布、车间全局产能分布、全生命周期历史轨迹、异常车监控和滞留检测。\n\n【触发关键词】当前位置、产量、吞吐量、实时分布、历史轨迹、异常车、滞留、车身追踪、物流\n【强制调用规则】用户问题包含以上任一关键词时，Agent 必须先调用 load_skill(\"paint_shop_vehicle_logistics\") 加载领域知识，再组织 SQL。",
    "tags": ["paint_shop", "vehicle_tracking", "logistics", "throughput", "scenario_enabled"],
    "associated_tables": [
        "fct.fct_vehicle_position_current",
        "ods.carbody_history",
        "dim.carbody_registry"
    ]
}
```

- [ ] **Step 2: 在质量缺陷技能元数据中注册关联物理表**

```python
# 修改 backend/app/skills/domains/paint_shop_defect_analysis/meta.py 中的 DOMAIN_META：
DOMAIN_META = {
    "name": "paint_shop_defect_analysis",
    "title": "质量缺陷",
    "description": "涂装车间质量缺陷汇总分析领域，面向车型缺陷趋势、部位分布、tunnel/cycle 对比和黑车顶对比等问题。\n\n【触发关键词】缺陷、缺陷率、缺陷汇总、部位分布、tunnel、cycle、黑车顶、车型趋势、对比\n【强制调用规则】用户问题包含以上任一关键词时，Agent 必须先调用 load_skill(\"paint_shop_defect_analysis\") 加载领域知识，再组织 SQL。",
    "tags": ["paint_shop", "defect_analysis", "quality"],
    "associated_tables": [
        "mart_vehicle_quality_360",
        "fct_vehicle_defect_detection"
    ]
}
```

- [ ] **Step 3: 运行 Python 单元测试验证元数据装配**

运行: `pytest backend/app/skills/registry.py -v` (如果无 pytest 可直接运行 py 脚本)  
Expected: PASS, 验证 `get_domain_skills()` 包含新增的 `associated_tables` 字段。

- [ ] **Step 4: 提交代码**

```bash
git add backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py backend/app/skills/domains/paint_shop_defect_analysis/meta.py
git commit -m "feat: register associated_tables metadata in logistics and defect meta.py"
```

---

### Task 2: 编写免连接开销的 SkeletonService 服务

**Files:**
- Create: `backend/app/agent/utils/skeleton_service.py`
- Create: `backend/app/agent/utils/test_skeleton_service.py`

- [ ] **Step 1: 编写骨架 DDL 反射服务，从 db.custom_table_info 缓存中动态提取**

```python
# 创建 backend/app/agent/utils/skeleton_service.py
import re
import logging

logger = logging.getLogger(__name__)

class SkeletonService:
    def __init__(self, db):
        self.db = db

    def get_skeleton_ddl(self, skill_name: str) -> str:
        try:
            meta_module = __import__(f"backend.app.skills.domains.{skill_name}.meta", fromlist=["DOMAIN_META"])
            associated_tables = getattr(meta_module, "DOMAIN_META", {}).get("associated_tables", [])
        except Exception as err:
            logger.error(f"加载技能 {skill_name} 元数据失败: {err}")
            return ""

        if not associated_tables or not getattr(self.db, "_custom_table_info", None):
            return ""

        skeleton_blocks = []
        for full_table_name in associated_tables:
            table_name = full_table_name.split('.')[-1] if '.' in full_table_name else full_table_name
            if table_name in self.db._custom_table_info:
                ddl = self.db._custom_table_info[table_name]
                # 正则剥离尾部的样本数据行以防 Token 膨胀 (-- 1. {'vehicle_id': ...})
                clean_ddl = re.sub(r'-- \d+\. \{.*?\}', '', ddl, flags=re.DOTALL).strip()
                skeleton_blocks.append(clean_ddl)

        return "\n\n".join(skeleton_blocks)
```

- [ ] **Step 2: 编写 SkeletonService 单元测试**

```python
# 创建 backend/app/agent/utils/test_skeleton_service.py
from backend.app.agent.utils.skeleton_service import SkeletonService

class DummyDB:
    def __init__(self):
        self._custom_table_info = {
            "fct_vehicle_position_current": "CREATE TABLE fct_vehicle_position_current (\n  vehicle_id VARCHAR\n);\n-- 1. {'vehicle_id': '123'}"
        }

def test_get_skeleton_ddl():
    db = DummyDB()
    service = SkeletonService(db)
    ddl = service.get_skeleton_ddl("paint_shop_vehicle_logistics")
    
    assert "CREATE TABLE fct_vehicle_position_current" in ddl
    assert "-- 1." not in ddl  # 确认示例样本数据行已被剔除
```

- [ ] **Step 3: 运行测试**

运行: `pytest backend/app/agent/services/test_skeleton_service.py -v`  
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add backend/app/agent/services/skeleton_service.py backend/app/agent/services/test_skeleton_service.py
git commit -m "feat: implement SkeletonService with regex DDL cleanup and dummy test"
```

---

### Task 3: 重构 load_skill 工具为去重追加与防爆限制模式

**Files:**
- Modify: `backend/app/agent/tools/skill_tools.py:31-65`
- Modify: `backend/app/agent/middleware/test_skill_middleware.py:32-60`

- [ ] **Step 1: 重构 _build_load_skill_command 逻辑，追加并保留历史**

```python
# 修改 backend/app/agent/tools/skill_tools.py 里的 _build_load_skill_command：
def _build_load_skill_command(skill_name: str, runtime: ToolRuntime) -> Command:
    skill = get_skill_by_name(skill_name)
    if skill is None:
        available = ", ".join(s["name"] for s in get_all_skills())
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Skill '{skill_name}' not found. Available skills: {available}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )

    # 1. 追加并保留已加载历史
    current_loaded = runtime.state.get("skills_loaded", [])
    new_loaded = list(current_loaded)
    if skill_name not in new_loaded:
        new_loaded.append(skill_name)

    # 2. 限制辅助技能堆积上限为 3 个，超出截断最先进入的
    if len(new_loaded) > 3:
        for s in list(new_loaded):
            if s != skill_name:
                new_loaded.remove(s)
                break

    # 3. 升级新技能为 active_skill (活跃主核心)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=(
                        f"已成功将当前主技能激活为 '{skill_name}'。\n"
                        f"历史加载过的技能 {new_loaded} 仍处于内存辅助参考状态，大模型可以直接跨表关联。"
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "skills_loaded": new_loaded,
            "active_skill": skill_name,
        }
    )
```

- [ ] **Step 2: 修改单元测试，验证 load_skill 的多值追加与去重**

```python
# 修改 backend/app/agent/middleware/test_skill_middleware.py：
def test_load_skill_tool_appends_state():
    from backend.app.agent.tools.skill_tools import _build_load_skill_command
    
    class DummyState:
        def __init__(self):
            self.state = {"skills_loaded": ["paint_shop_defect_analysis"]}
            self.tool_call_id = "test_call"
            
    runtime = DummyState()
    # 第一次追加
    cmd = _build_load_skill_command("paint_shop_vehicle_logistics", runtime)
    assert cmd.update["active_skill"] == "paint_shop_vehicle_logistics"
    assert "paint_shop_defect_analysis" in cmd.update["skills_loaded"]
    assert "paint_shop_vehicle_logistics" in cmd.update["skills_loaded"]
```

- [ ] **Step 3: 运行测试**

运行: `pytest backend/app/agent/middleware/test_skill_middleware.py -v`  
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add backend/app/agent/tools/skill_tools.py backend/app/agent/middleware/test_skill_middleware.py
git commit -m "refactor: update load_skill tool command to support de-duplicated appends and limit cap"
```

---

### Task 4: 改造 SkillMiddleware 并实现 before_agent 自动重置钩子

**Files:**
- Modify: `backend/app/agent/middleware/skill_middleware.py:45-78`
- Modify: `backend/app/agent/middleware/test_skill_middleware.py:60-120`

- [ ] **Step 1: 改造 _modify_request 支持骨架反射注入，并重写 before_agent 钩子**

```python
# 物理修改 backend/app/agent/middleware/skill_middleware.py：
# 在顶部引入：
from backend.app.agent.utils.skeleton_service import SkeletonService

# 修改 SkillMiddleware 类实现：
class SkillMiddleware(AgentMiddleware[CustomState]):
    state_schema = CustomState
    tools = [load_skill, load_scenario]

    def __init__(self, db) -> None:
        """
        初始化时传入全局 db 实例，构建骨架反射器
        """
        self.skeleton_service = SkeletonService(db)

    def before_agent(self, state: CustomState, runtime) -> dict | None:
        """
        💡 框架原生周期钩子：在新一轮对话（Agent开始执行）时拦截，
        强制将 skills_loaded 收窄为当前 active_skill，擦除历史遗留，自动瘦身。
        """
        active = state.get("active_skill")
        if active:
            return {
                "skills_loaded": [active]
            }
        return None

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """将技能大纲、主技能全量 DDL 与辅助骨架 DDL 动态拼装注入"""
        skills_prompt = _build_skills_prompt(get_all_skills())
        skills_addendum = (
            f"\n\n## Available Skills\n\n{skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed domain knowledge. "
            "If the loaded domain skill shows a matching fixed scenario, use the "
            "load_scenario tool before composing SQL."
        )

        active_skill = request.state.get("active_skill") if request.state else None
        skills_loaded = request.state.get("skills_loaded", []) if request.state else []

        # 1. 主激活技能 (全量 DDL)
        active_ddl_addendum = ""
        if active_skill:
            from backend.app.skills import load_domain_content
            skill_content = load_domain_content(active_skill)
            if skill_content:
                active_ddl_addendum = (
                    f"\n\n## Active Domain Knowledge: {active_skill}\n"
                    "下列是当前激活领域的核心表结构 DDL 以及业务易错规则，请在编写 SQL 时严格遵守：\n\n"
                    f"{skill_content}\n"
                )

        # 2. 辅助参考技能 (差集过滤极简骨架)
        secondary_skills = [s for s in skills_loaded if s != active_skill]
        secondary_ddl_blocks = []
        for sec_skill in secondary_skills:
            sec_ddl = self.skeleton_service.get_skeleton_ddl(sec_skill)
            if sec_ddl:
                secondary_ddl_blocks.append(
                    f"### 辅助关联技能表结构: {sec_skill}\n"
                    f"```sql\n{sec_ddl}\n```"
                )
        secondary_prompt = "\n\n".join(secondary_ddl_blocks) if secondary_ddl_blocks else ""

        # 3. 合并组装
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        if active_ddl_addendum:
            new_content.append({"type": "text", "text": active_ddl_addendum})
        if secondary_prompt:
            new_content.append({"type": "text", "text": f"\n\n## Secondary Domain Knowledge\n{secondary_prompt}"})
            
        new_system_message = SystemMessage(content=new_content)
        return request.override(system_message=new_system_message)
```

- [ ] **Step 2: 编写 before_agent 与 _modify_request 拼装测试**

```python
# 修改 backend/app/agent/middleware/test_skill_middleware.py，增加测试用例：
def test_before_agent_resets_loaded_skills():
    db = DummyDB()
    middleware = SkillMiddleware(db)
    
    state = {
        "active_skill": "paint_shop_defect_analysis",
        "skills_loaded": ["paint_shop_defect_analysis", "paint_shop_vehicle_logistics"]
    }
    
    # 触发 before_agent 重置
    update = middleware.before_agent(state, None)
    assert update == {"skills_loaded": ["paint_shop_defect_analysis"]}
```

- [ ] **Step 3: 运行测试**

运行: `pytest backend/app/agent/middleware/test_skill_middleware.py -v`  
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add backend/app/agent/middleware/skill_middleware.py backend/app/agent/middleware/test_skill_middleware.py
git commit -m "feat: implement before_agent reset hook and cascade skeleton prompt injection"
```

---

### Task 5: 系统提示词微调与直连 SQL 规则声明

**Files:**
- Modify: `backend/app/agent/service.py:446-456`
- Modify: `backend/app/agent/test_service_prompt.py:15-30`

- [ ] **Step 1: 修改 service.py 里的 _build_system_prompt，添加 EXISTS 别名强约束**

```python
# 修改 backend/app/agent/service.py 里的 _build_system_prompt 模板：
# 覆盖 446 行开始的 "## 跨领域复合问题处理流程" 章节：
    """
    ## 跨领域复合问题处理流程 (一期子查询军规)
    1. **单 DDL 限制防范**：注意，系统对辅助技能仅提供了纯表结构骨架（排在主技能下方）。你必须以此骨架为参考，在一句 SQL 里完成跨域查询。
    2. **确定性子查询直连**：
       - 表达“存在关联”时，必须使用：`WHERE EXISTS (SELECT 1 FROM 辅助表 WHERE 关联条件)`。
       - 表达“排除/不存在”时，必须使用：`WHERE NOT EXISTS (SELECT 1 FROM 辅助表 WHERE 关联条件)`。
       - 严禁在大段 SQL 中手工拼写 `IN ('FIS001', 'FIS002')` 巨型明细列表。
    3. **避免别名同名冲突 (Ambiguous Column)**：
       - 在多表关联查询中，**每一个投影字段与条件字段必须加上显式的表别名前缀**（例如必须编写 `mq.vehicle_id = vp.vehicle_id`）。
       - 严禁在主查询、子查询或 CTE 块中使用 `SELECT *`，防范 PostgreSQL 17 抛出 ambiguous 列引用报错。
    """
```

- [ ] **Step 2: 调整测试用例验证系统提示词约束**

```python
# 修改 backend/app/agent/test_service_prompt.py，确认包含 "WHERE EXISTS" 和 "表别名前缀" 的约束断言
def test_system_prompt_rules():
    from backend.app.agent.service import _build_system_prompt
    prompt = _build_system_prompt(None) # 或者传入 Mock DB
    assert "WHERE EXISTS" in prompt
    assert "表别名前缀" in prompt
```

- [ ] **Step 3: 运行测试**

运行: `pytest backend/app/agent/test_service_prompt.py -v`  
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add backend/app/agent/service.py backend/app/agent/test_service_prompt.py
git commit -m "feat: update system prompt constraints for cross-domain EXISTS and column aliases"
```

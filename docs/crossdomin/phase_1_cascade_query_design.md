# SQL Agent Phase 1 (级联子查询直连) 详细设计方案

本方案为 **Phase 1 (一期：级联子查询直连)** 的落地实施细则。

一期旨在通过**技能清单映射**、**动态数据库结构反射**与**按需追加的提示词级联注入**，赋予大模型在一局 SQL 内直接编写跨 Schema 子查询（如 `WHERE EXISTS`）的能力。

本设计基于 **“无前置 LLM 路由、大模型动态自愈加载、用完即弃（Single-Turn Reset）”** 的极简高性能原则，确保系统具有最低的开发成本、最低的 Token 消耗与最纯净的单域上下文。

---

## 1. 业务逻辑流 (Business Logic Flow)

```
[ 用户发送跨域复合提问 ]
       │
       ▼
[ 1. 初始状态载入 ] ──> 仅载入当前活跃技能为主技能（无任何辅助骨架）
       │
       ▼
[ 2. 大模型自发 Tool 决策 ]
       ├── A. 大模型阅读问题与可用技能大纲，发现需要缺失领域的数据
       └── B. 大模型在 ReAct 中途主动调用 load_skill('新领域')
               │
               ▼
[ 3. 后端状态追加与对调 ] ──> 将新技能追加至 skills_loaded 并升级为 active_skill (原主技能自动退为辅助)
               │
               ▼
[ 4. 动态 DDL 反射拼装 ]
       ├── A. 加载新激活主技能的全量 domain.md
       ├── B. 动态反射 skills_loaded 中其余技能的极简骨架 DDL (通过 db_utils.py)
       └── C. 合并拼接为 System Message 送回大模型
               │
               ▼
[ 5. SQL 编写与执行 ] ──> 大模型看到并存的 DDL，写出 EXISTS 子查询直连数据库并输出结果
               │
               ▼
[ 6. 本轮结束单步重置 ] ──> 接口层在下一轮问题到达时，清空 skills_loaded 历史，瘦身还原为单域状态
```

---

## 2. 核心模块与类设计

### 2.1 技能定义层 (associated_tables 声明)
在各个技能目录下的 `meta.py` 中的 `DOMAIN_META` 字典增加 `associated_tables` 列表，用以声明本领域技能所涉及的物理表清单。

*   **物流技能 ([paint_shop_vehicle_logistics/meta.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py))**：
    ```python
    DOMAIN_META = {
        "name": "paint_shop_vehicle_logistics",
        "title": "物流追踪",
        "associated_tables": [
            "fct.fct_vehicle_position_current",
            "ods.carbody_history",
            "dim.carbody_registry"
        ]
    }
    ```
*   **质量技能 ([paint_shop_defect_analysis/meta.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/skills/domains/paint_shop_defect_analysis/meta.py))**：
    ```python
    DOMAIN_META = {
        "name": "paint_shop_defect_analysis",
        "title": "质量缺陷",
        "associated_tables": [
            "mart_vehicle_quality_360",
            "fct_vehicle_defect_detection"
        ]
    }
    ```

---

### 2.2 骨架反射服务 (`skeleton_service.py`)
新建 `backend/app/agent/utils/skeleton_service.py`。
为了消除任何物理数据库连接开销与高并发瓶颈，该服务**不进行物理查询**。由于项目在启动初始化时已经调用过 `fetch_table_definitions_with_comments` 并将其全部缓存在了 `db.custom_table_info` 中，该服务直接从内存读取已扫描好的 DDL，仅进行样本正则裁剪。

```python
# backend/app/agent/utils/skeleton_service.py
import re
import logging

logger = logging.getLogger(__name__)

class SkeletonService:
    def __init__(self, db):
        """
        💡 零开销复用：直接传入系统初始化好的 db 实例，读取已常驻内存的表定义缓存
        """
        self.db = db

    def get_skeleton_ddl(self, skill_name: str) -> str:
        # 1. 动态加载目标技能的 meta.py 获取关联表名
        try:
            meta_module = __import__(f"backend.app.skills.domains.{skill_name}.meta", fromlist=["DOMAIN_META"])
            associated_tables = getattr(meta_module, "DOMAIN_META", {}).get("associated_tables", [])
        except Exception as err:
            logger.error(f"加载技能 {skill_name} 的元数据失败: {err}")
            return ""

        if not associated_tables:
            logger.info(f"技能 {skill_name} 没有定义关联辅助表 associated_tables")
            return ""

        table_info = getattr(self.db, "_custom_table_info", None)
        if not table_info:
            logger.warning("数据库对象中不存在 _custom_table_info 缓存字典")
            return ""

        # 2. 直接从 db 缓存中提取 DDL 并使用正则剥离样本行以防 Token 膨胀
        skeleton_blocks = []
        for full_table_name in associated_tables:
            table_name = full_table_name.split('.')[-1] if '.' in full_table_name else full_table_name
            if table_name in table_info:
                ddl = table_info[table_name]
                # 🔴 正则剥离尾部的样本数据行 (-- 1. {'vehicle_id': ...})
                clean_ddl = re.sub(r'-- \d+\. \{.*?\}', '', ddl, flags=re.DOTALL).strip()
                # 💡 正则裁减：将 VARCHAR(50) / VARCHAR(255) 等类型长度修饰符统一还原为极简 VARCHAR
                clean_ddl = re.sub(r'VARCHAR\(\d+\)', 'VARCHAR', clean_ddl, flags=re.IGNORECASE)
                skeleton_blocks.append(clean_ddl)
                logger.info(f"💡 成功加载辅助表 DDL 骨架: {table_name}")
            else:
                logger.warning(f"⚠️ 内存缓存 _custom_table_info 中未找到辅助表: {table_name}")

        final_skeleton = "\n\n".join(skeleton_blocks)
        if final_skeleton:
            logger.info(f"✅ 技能 {skill_name} 拼装完成，共加载 {len(skeleton_blocks)} 个辅助表结构")
        return final_skeleton
```

---

### 2.3 load_skill 工具重构与状态转移 (State Toggle Logic)
重构 [backend/app/agent/tools/skill_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/tools/skill_tools.py) 的 Command 生成函数，改为**去重追加模式**：

```python
# backend/app/agent/tools/skill_tools.py (一期重写逻辑)
def _build_load_skill_command(skill_name: str, runtime: ToolRuntime) -> Command:
    skill = get_skill_by_name(skill_name)
    if skill is None:
        available = ", ".join(s["name"] for s in get_all_skills())
        return Command(update={"messages": [ToolMessage(content=f"Skill '{skill_name}' not found.", tool_call_id=runtime.tool_call_id)]})

    # 1. 追加并保留已加载历史，用以表达辅助池
    current_loaded = runtime.state.get("skills_loaded", [])
    new_loaded = list(current_loaded)
    if skill_name not in new_loaded:
        new_loaded.append(skill_name)

    # 2. 限制技能池堆积最大上限为 3 个，防范长会话溢出
    if len(new_loaded) > 3:
        for s in list(new_loaded):
            if s != skill_name:
                new_loaded.remove(s)
                break

    # 3. 升级当前被请求技能为唯一的活跃主技能
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"已成功将当前主技能激活为 '{skill_name}'。历史加载过的技能 {new_loaded} 仍作为辅助骨架并存，供跨域编写参考。",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "skills_loaded": new_loaded, # 辅助参考池
            "active_skill": skill_name,   # 活跃主核心
        }
    )
```

---

### 2.4 中间件级联拼接层 (`SkillMiddleware`)
修改 [skill_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/middleware/skill_middleware.py)，利用差集逻辑 `skills_loaded - active_skill` 判定出辅助技能，并生成 Prompt：

```python
# backend/app/agent/middleware/skill_middleware.py (一期改动)
class SkillMiddleware(AgentMiddleware[CustomState]):
    state_schema = CustomState
    tools = [load_skill, load_scenario]

    def __init__(self, db) -> None:
        """
        💡 初始化时注入 db 实例，供骨架反射服务 SkeletonService 使用
        """
        self.skeleton_service = SkeletonService(db)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """
        将技能大纲、当前主技能全量 DDL 以及关联辅助技能骨架 DDL 动态拼装入 System Prompt。
        """
        skills_prompt = _build_skills_prompt(get_all_skills())
        skills_addendum = (
            f"\n\n## Available Skills\n\n{skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed domain knowledge. "
            "If the loaded domain skill shows a matching fixed scenario, use the "
            "load_scenario tool before composing SQL."
        )

        active_skill = request.state.get("active_skill") if request.state else None
        skills_loaded = request.state.get("skills_loaded", []) if request.state else []

        # 1. 载入主激活技能 (全量 DDL 与 Gotchas 说明)
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

        # 2. 🔴 计算差集并载入关联辅助技能的极简 Schema 骨架 (免读库缓存反射)
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

        # 3. 级联拼装 SystemMessage 文本块
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

---

### 2.5 每一轮新提问开始前的单步重置 (Single-Turn Reset)
为了在用户转入非跨域的普通话题时实现自动 Prompt 瘦身，在 [backend/app/services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py) 的 `process_message` 和 `process_stream` 入口函数执行之前，主动获取当前 Checkpoint 状态并将已加载池 `skills_loaded` 还原为单技能结构：

```python
# backend/app/services.py (一期状态清空重置参考)
# 注入到 process_message (非流式入口) 与 process_stream (流式入口) 的开头：

async def process_stream(
    self, message: str, session_id: str, config: dict = None
) -> AsyncIterator[dict[str, Any]]:
    """流式处理用户消息，输出结构化事件。"""
    resolved_config = self._build_config(
        session_id,
        config,
        request_mode="stream",
    )
    
    # 💡 核心自愈重置：在新一轮流式开始前，清空历史堆积的辅助骨架，瘦身为纯净主技能
    try:
        state = await self.agent.aget_state(resolved_config)
        active = state.values.get("active_skill") if state else None
        if active:
            # 覆写状态，仅保留当前的主激活技能，多余的辅助技能直接被踢出
            await self.agent.aupdate_state(resolved_config, {"skills_loaded": [active]})
    except Exception as e:
        logger.warning(f"重置多轮辅助技能状态失败: {e}")

    logger.info("开始流式处理，消息: %s...", message[:100])
    input_data = {"messages": [HumanMessage(content=message)]}
    async for event in self._stream_execution_loop(session_id, resolved_config, input_data):
        yield event
```

---

## 3. 提示词微调模版

在 `service.py` 提示词模板中，正式写入跨域直连的别名前缀纪律：

```markdown
## 跨领域复合问题处理流程 (一期子查询军规)
1. **单 DDL 限制防范**：注意，系统对辅助技能仅提供了纯表结构骨架（排在主技能下方）。你必须以此骨架为参考，在一句 SQL 里完成跨域查询。
2. **确定性子查询直连**：
   - 表达“存在关联”时，必须使用：`WHERE EXISTS (SELECT 1 FROM 辅助表 WHERE 关联条件)`。
   - 表达“排除/不存在”时，必须使用：`WHERE NOT EXISTS (SELECT 1 FROM 辅助表 WHERE 关联条件)`。
   - 严禁在大段 SQL 中手工拼写 `IN ('FIS001', 'FIS002')` 巨型明细列表。
3. **避免别名同名冲突 (Ambiguous Column)**：
   - 在多表关联查询中，**每一个投影字段与条件字段必须加上显式的表别名前缀**（例如必须编写 `mq.vehicle_id = vp.vehicle_id`）。
   - 严禁在主查询、子查询或 CTE 块中使用 `SELECT *`，防范 PostgreSQL 17 抛出 ambiguous 列引用报错。
```

---

## 4. 阶段一验证方案

一期开发完成后，进行如下验证：

### 4.1 自动化测试断言
在 `test_service_prompt.py` 中补充测试用例：
* **DML 骨架纯净度测试**：反射出来的辅助表 DDL 不允许包含 `-- 1. {'vehicle_id': ...}` 等数据样本行。
* **重置测试**：模拟两轮提问，验证第二轮的新问题中 `skills_loaded` 自动还原为了 `[active_skill]`。
* **联合 SQL 执行测试**：在开发数据库中运行生成的 EXISTS 子查询，确保 PG17 优化器执行计划正常且无别名引用报错。

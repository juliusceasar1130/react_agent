# SQL Agent 跨领域多步查询与级联 DDL 反射技术规范书 (Specification)

本规范书定义了数据查询智能体（SQL Agent）系统在处理跨越不同业务知识领域（如物流定位、质量缺陷等）以及存在前后数据依赖的复杂查询时，所采用的**系统级暂存表管道方案**、**物理连接状态管理机制**、**基于数据库反射 (Database Reflection) 的零维护级联 DDL 方案**以及** PostgreSQL 17 的 SQL 优化编写军规**。

---

## 一、 背景与挑战 (Background)

### 1. 业务场景背景
在 120JPH 涂装车间数据分析场景中，大量用户的提问天然具有跨领域的特征。
例如：*“现在面漆储存线（PBS）有哪些车身（物流域），它们的缺陷情况如何（质量域）？”*
* **物流域（paint_shop_vehicle_logistics）**：管理“车身当前在制位置”、“通过量轨迹”。
* **质量域（paint_shop_defect_analysis）**：管理“质量检测”、“检测工位（tunnel）”、“缺陷分布”。

### 2. 现有技术局限与冲突
* **提示词 DDL 注入冲突**：为了防范上下文爆满及表结构混淆，系统采用“单技能激活机制”。同一时刻，系统提示词内只注入一个活跃技能的 DDL。这导致模型无法编写直接关联两个不同域物理表的 JOIN 语句。
* **数据中转的 Token 瓶颈**：由于无法直接 JOIN，模型被迫在第一步查出明细车身号（如 200 个 FIS 码），在应用层（Python）中转后，在第二步拼写为巨大的 `WHERE vehicle_id IN ('FIS1', ..., 'FIS200')`。这会导致大模型上下文瞬间膨胀，极易造成生成截断、括号缺失等语法失误。
* **临时表 Session 易失性与池回收**：PostgreSQL 17 的 `TEMP TABLE` 具有物理连接（DB Session）隔离性。传统的 SQLAlchemy 工具在执行完 SQL 后，会立刻将物理连接归还连接池并清理状态。如果直接在 LangGraph State 中存储连接对象，由于连接对象是不可序列化的（Non-serializable），在图状态静态序列化时会发生反序列化丢失或被 GC（垃圾回收）静默关闭，引发 `relation not exist` 报错。

---

## 二、 目标与原则 (Goals & Principles)

1. **零人工维护的骨架 Schema 生成**：放弃手工维护多套骨架 DDL 的做法，直接基于现有的 `db_utils.py` 表结构注释反射技术，零成本动态拼装带字段注释的极简 Schema 注入给大模型。
2. **会话级物理隔离与数据纯净**：数据暂存完全在 PG 服务端内存/临时盘中进行，不挤占 FastAPI 进程内存。在连接释放前显式清理会话，确保零跨会话泄漏。
3. **单技能激活兼容性**：在不破坏大模型“同一时刻只读单个技能 DDL”的设计前提下，打通跨域数据传输接力。
4. **单域场景零开销**：对 90% 以上的普通单域查询，本规范中定义的临时表工具不参与调用，确保零性能损耗与零 Token 成本。
5. **Agent 自愈与复盘重试**：大模型具备在 SQL 报错时回切前置领域技能、重新生成临时表的 Self-healing 自愈路径。
6. **分阶段演进 (Phased Staging)**：技术架构分为 Phase 1（一期：级联子查询）与 Phase 2（二期：暂存表管道）。本规范中定义的 `ConnectionRegistry` 物理连接锁（第三章第 3 节）与 `sql_db_query_to_temp` 工具（第三章第 2 节）为 Phase 2 兜底方案，Phase 1 阶段仅需落地第 1 节的骨架 DDL 动态反射并配合 `WHERE EXISTS` 子查询直连即可。

---

## 三、 系统架构级详细设计 (Architectural Details)

### 1. 骨架 DDL 反射机制 (Dynamic DDL Reflection)

我们摒弃静态编写骨架 Schema 文件的做法，直接利用项目已有的 [db_utils.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/utils/db_utils.py) 工具中的 `fetch_table_definitions_with_comments` 重构级联加载流。

#### 1.1 技能清单声明 (Skill Manifest)
在每个技能的配置文件中，开发人员仅需声明其涉及的核心物理表清单：
```json
// backend/app/skills/domains/paint_shop_vehicle_logistics/manifest.json
{
  "skill_name": "paint_shop_vehicle_logistics",
  "associated_tables": [
    "fct.fct_vehicle_position_current",
    "ods.carbody_history"
  ]
}
```

#### 1.2 物理注释规范 (COMMENT ON)
为了让大模型在辅助表结构中能够看懂业务语义，**统一强制规范数据库开发行为：必须在物理数据库上执行 `COMMENT ON` 字段注释**（Single Source of Truth 唯一事实源）。
```sql
COMMENT ON COLUMN fct.fct_vehicle_position_current.process_area IS '当前工艺区域/缓冲线名称 (如 PBS, OVEN)';
```

#### 1.3 后端程序动态压缩与提取
当该技能作为“辅助技能（Secondary Skill）”加载时，后端提取 `associated_tables` 列表，传入 `db_utils` 抓取对应的纯表 DDL。
* **数据过滤**：抓取时由 Python 自动剔除原始 DDL 中与主外键、关键连接列无关的日志字段（如操作人、修改终端IP），极力保持 Token 的高纯净度（单个辅助表 DDL Token 控制在 100 以内）。

---

### 2. 工具层：`sql_db_query_to_temp` 数据暂存工具

* **职责**：运行 SELECT 查询并将结果封装为物理临时表，仅将结构元数据返回给大模型。
* **参数设计**：
  - `query` (str): 仅允许 `SELECT` 或 `WITH` 语句。
  - `temp_table_name` (str): 匹配正则 `^[a-zA-Z0-9_]+$` 的合法表名。
  - `required_skill` (str): 安全声明，必须在 `skills_loaded` 中。
* **安全性与语法校验**：
  - **过滤只读**：后端在执行前强行过滤掉任何分号 `;` 以及 `INSERT/UPDATE/DELETE/DROP/ALTER` 关键字，防范 SQL 注入与表结构破坏。
  - **过滤 CREATE 声明**：如果 `query` 已经是 `CREATE` 或 `CREATE TEMP` 开头，后端在拼接前做前置正则校验拦截，防止 SQL 嵌套语法错误。
* **并发隔离下的表名加盐规则**：
  为避免多用户并发访问时在物理上产生同名临时表冲突，大模型传参为逻辑表名（如 `tmp_pbs_vehicles`），后端通过当前 `thread_id` 自动重写为带会话短 ID 前缀的物理临时表：`tmp_{session_short_id}_{logical_name}`（例如 `tmp_a7x9_pbs_vehicles`），且创建前如果已存在自动追加 `_v2`。
* **数据结果集限制（边界保护）**：
  后端强行限制结果集上限。若 query 结果行数超过 **100,000 行**，后端拒绝写入并返回明确的越界错误提示，防止撑爆 PG 临时表空间或引发 I/O 超时。
* **结构化 ToolMessage 输出**：
  工具直接返回该临时表的 `CREATE TABLE` 字段定义片段，方便模型在后置阶段直接复制使用。

---

### 3. 连接层：基于连接注册表 (ConnectionRegistry) 的持久化会话

为彻底解决连接对象在 SQLAlchemy 2.0 中作为上下文管理器自动释放、无法在有状态 Graph 中反序列化的问题，采用 **Memory-based Registry + State Pointer** 的设计。

```
                   [ 内存物理连接注册表 (ConnectionRegistry) ]
                  ┌──────────────────────────────────────────┐
                  │ { "thread_id_123": db_connection_obj }    │ (全局单例，线程安全)
                  └────────────────────▲─────────────────────┘
                                       │ (1. 绑定与存入 / 2. 取出与复用)
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                                                           ▼
[ sql_db_query_to_temp ]                                   [ sql_db_query ]
- 申请物理连接并执行 conn.begin()                           - 通过 thread_id 从注册表提取 db_connection_obj
- 写入注册表: Registry[thread_id] = conn                   - 直接复用该物理连接执行 SQL (临时表可见)
- 在 State 中写入: has_temp_table = True (纯布尔值，可序列化)
```

* **持久连接绑定**：
  在 `sql_db_query_to_temp` 执行时，显式从池里开启物理连接 `conn = engine.connect()` 并调用 **`conn.begin()` 保持事务处于活动状态**（防止 SQLAlchemy 2.0 自动回收连接）。
  将物理连接对象存入全局物理连接注册表：`ConnectionRegistry[thread_id] = conn`。
  State 中只存放 `has_temp_table = True` 的可序列化布尔值。
* **连接复用获取**：
  后续的 Tool 执行时，通过 `runtime.config.get("configurable", {}).get("thread_id")` 从全局注册表中提取对应的 `conn` 对象复用，无需走连接池申请。
* **多道释放与清理防线**：
  - **防线一 (正常流终点)**：在 LangGraph 的最后一个退出节点 `release_connection` 中，获取 `thread_id`，从注册表中取出并物理执行：
    ```sql
    DISCARD TEMP; -- 显式销毁当前物理会话的所有临时表，防范连接归还后跨会话数据泄漏
    ```
    随后调用 `conn.close()` 物理释放连接回池，并将注册表中的对象 `pop` 掉。
  - **防线二 (异常路径收底机制)**：在 API 调用层（`service.py`）的 `try...finally` 中，利用全局注册表做强制强力清理：
    ```python
    finally:
        conn = ConnectionRegistry.pop(current_thread_id, None)
        if conn:
            try:
                conn.execute(text("DISCARD TEMP;"))
                conn.close()
            except Exception:
                pass
    ```

---

## 四、 提示词工程与认知规划规范 (Prompt Engineering Spec)

为了让大模型在最开始就拥有长远的“全局规划”眼光，并具备自我纠错自愈能力，系统提示词中必须做出如下声明和规范引导：

### 1. 意图路由与主辅技能判定 (Metric-first Router)
当面对跨域提问时，系统通过以下原则判定哪一个是主技能（Active DDL），哪一个是辅技能（Skeleton DDL）：
* **度量指标（Metric）优先原则**：在提问中，提供“指标度量计算（SELECT count/avg/sum）”的技能应判定为**主技能**；提供“物理过滤范围（WHERE 当前位置/车身）”的技能判定为**辅助技能**。
* **示例**：*“PBS 区域的车，缺陷均值是多少？”*
  - 物流域：负责 WHERE `process_area = 'PBS'` （过滤范围）。
  - 质量域：负责 SELECT `AVG(total_defect_count)` （指标度量）。
  - **决策**：**质量域为主技能，物流域为辅助技能**。

### 2. 环境局限显式告知与正向引导
大模型在提示词中必须被告知：
> *“【重要限制提示】：受系统架构限制，你同一时刻只能激活一个业务领域的表结构（DDL）。因此你无法在单条 SQL 中直接跨域 JOIN 未激活的物理表。*
> *但你可以通过以下方式实现跨域关联：*
> *1. 使用 `sql_db_query_to_temp` 将前置领域的结果暂存为临时表。*
> *2. 切换技能后，该临时表在当前物理连接中仍然可见，你可以直接关联查询。”*

### 3. 泛化多步规划确定性规则 (Deterministic Rules)
规则严禁绑定具体的业务技能，必须采用通用变量代称进行公式化提示，并消除模型对数据量大估算的模糊性：
> *“当面对需要跨领域依赖的复合查询时，必须遵循以下确定性规则：*
> *1. 无论预估数据量大小，第一步都必须使用 `sql_db_query_to_temp` 暂存过滤结果。*
> *2. 严禁在第二步中使用 WHERE id IN ('FIS1', 'FIS2', ...) 的硬编码明细列表（唯一的例外是：若前置查询明确返回结果数 ≤5 个，大模型可以在第二步使用 IN 过滤，但临时表仍然必须作为兜底生成）。*
> *3. 第二步在编写 SQL 前，为了确保临时表列名不发生偏差，推荐使用 `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '暂存表名'` 来验证临时表的字段结构，或直接使用第一步 ToolMessage 中返回的列结构定义模板。”*

### 4. 自愈与回滚重试机制 (Self-healing Guidance)
> *“如果你在第二步（后置技能 Y）执行 SQL 遭遇报错（如字段名错误、表不存在），或者发现数据过滤结果不符合预期：*
> *1. 允许重新暂存：你可以调用 `load_skill` 重新回切到前置技能，重新执行 `sql_db_query_to_temp` （后端在创建前会自动执行 DROP TABLE IF EXISTS 覆盖旧表）。*
> *2. 修正错误后，再次切换回技能 Y 重新跑 SQL。整套重试和切换逻辑同样受到最多 3 次 Tool 迭代的全局限制。”*

---

## 五、 PostgreSQL 17 的 SQL 编写军规

为了保证生成的 SQL 在最新的 PostgreSQL 17 数据库上跑出极佳的性能，且将大模型的生成语法失误率降到最低：

### 1. 结构编排：子查询优先
在 PostgreSQL 17 环境下，单次引用的 CTE 会被自动内联（Inline），底层物理性能与子查询持平。为了降低 LLM 全局变量规划失误率，**优先推荐使用 Nested Subquery**。
* **例外情况**：当同一个中间结果集在主查询中被引用两次或以上时（例如：一次用于 JOIN，一次用于 WHERE 过滤），**推荐使用 WITH 子句 (CTE)** 以避免重复计算。

### 2. 关联语义与 NULL 陷阱防护
大模型非常容易在三值逻辑（True, False, Unknown）中掉入 NULL 值的空集灾难。
* **表达“存在关联”**：使用 `WHERE EXISTS`，尽量避免使用 `IN`（除非确认字段非空）。
* **表达“不存在关联”**：**必须且只能使用 `WHERE NOT EXISTS`**，严禁使用 `NOT IN`（防止子查询包含 NULL 导致主查询返回空集的数据黑洞）。

### 3. 全局禁用 `SELECT *`
* 任何主查询、子查询 and CTE 必须显式声明所需的投影列名，杜绝列歧义（Ambiguous column）和不必要的字段拉取。
* **拦截机制**：如果大模型生成的 SQL 包含 `SELECT *`，后端将拦截执行并抛出清晰的校验错误，逼迫其修改：
  `Ambiguous column risk: SELECT * is forbidden. Please explicitly list required columns.`

### 4. 保护索引友好性
禁止在 `DATE_EVT` 等索引字段上包裹转换函数，确保命中 PG 索引：
* **🔴 严禁（函数包裹索引列，导致全表扫描）**：
  `WHERE TO_TIMESTAMP(DATE_EVT, 'DD/MM/YYYY HH24:MI:SS.US') > '2026-07-01'`
* **🟢 推荐（字符常量直接比对，利用索引；需常量格式与字段存储完全一致）**：
  `WHERE DATE_EVT > '01/07/2026 00:00:00.000000'`
* **🟢 次选（仅转换常量侧，索引列保持裸列，利用索引）**：
  `WHERE DATE_EVT > TO_CHAR(TO_TIMESTAMP('2026-07-01', 'YYYY-MM-DD'), 'DD/MM/YYYY HH24:MI:SS.US')`

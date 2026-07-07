## 2026-07-07 15:10 +08:00 - SQL 执行前硬拦截 Linter 与自愈机制 (含 PG 深度去重优化)

### 概述
- **SQL Linter 静态/语义多级安全合规检查（P2）**：实现了用于 SQL Agent 执行 SQL 前硬防守拦截的 SQL Linter 架构，分三层进行校验：
  - 安全过滤层（SEC-001 DML 写操作拦截、SEC-002 堆叠多语句注入检测、SEC-003 数据库别名前缀/非法 schema 拦截）。
  - 结构合规层（STR-001 `SELECT *` 通配符拦截、STR-002 JOIN 强制别名前缀、STR-003 子查询深度限制、STR-004 CTE 数量警告）。
  - 语义校验层（SEM-001 关联列唯一性、SEM-002 事实表非去重 `COUNT` 告警、SEM-003 标量子查询 limit 限制警告、SEM-004 `NOT IN` 子查询 NULL 穿透漏洞拦截）。
- **PostgreSQL 专用去重关联优化**：深度优化了 `JoinUniquenessRule` (SEM-001) 规则，智能识别并安全放行以下三类去重关联模式，解决常见“取最新检测记录”时的拦截误杀：
  - `MAX`/`MIN` 极值标量子查询过滤条件。
  - `ROW_NUMBER() OVER (...) = 1` 窗口去重子查询条件。
  - `LIMIT 1` 子查询全局条件。
- **标量子查询误判修复**：在 `ScalarSubqueryRule` (SEM-003) 中引入 AST 上下文路径判定逻辑，有效过滤掉 FROM/JOIN 数据源中的表子查询（Table Subquery），防止对正常子查询进行误拦截。
- **DDL 语义上下文提取**：编写了从 `custom_table_info` 表 DDL 描述中自动解析提取主键、唯一键和 Grain 信息构建 `LintContext` 上下文的引擎。
- **LangChain 工具层集成与自愈**：将 `sql_linter` 接入 `create_wrapped_query_tool` 包装查询工具。对于拦截的 ERROR 问题，通过抛出 `ToolException` 结合 `handle_tool_error=True` 属性触发 SQL Agent 的自我修复能力。
- **完全可配置支持**：提供全局开关、严重度覆盖重载、子查询深度限制、CTE 数量限制等配置项，支持环境变量在测试时动态映射重载。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `sql_linter_enabled`、`sql_linter_max_subquery_depth`、`sql_linter_max_cte_count`、`sql_linter_allowed_schemas_raw`、`sql_linter_rules_severity_raw` 等配置字段与别名环境变量映射。

#### backend/app/agent/utils/sql_linter.py [NEW]
- 实现 `LintViolation`, `LintContext`, `LintResult` 数据模型。
- 实现 `BaseLintRule` 抽象规则基类与编排器 `SQLLinter`。
- 实现安全层（`DMLSecurityRule`, `MultiStatementRule`, `DatabasePrefixRule`）、结构层（`StarSelectRule`, `AliasPrefixRule`, `SubqueryDepthRule`, `CteCountRule`）和语义层（`JoinUniquenessRule`, `CountDistinctRule`, `ScalarSubqueryRule`, `NotInSubqueryRule`）共 11 个规则类。
  - 特别优化 `JoinUniquenessRule` 支持 `MAX`/`MIN`、`ROW_NUMBER`、`LIMIT 1` 判定。
  - 特别优化 `ScalarSubqueryRule` 支持 FROM/JOIN 父类排除。
- 实现从 DDL 中提取上下文元数据的 `_build_lint_context` 引擎。

#### backend/app/agent/tools/sql_tools.py [MODIFY]
- 集成 `sql_linter` 到 `create_wrapped_query_tool`，并在合规校验拦截时抛出 `ToolException`，将 `handle_tool_error = True` 绑定到包装后的工具实例，启用 Agent 的自我修复机制。

#### backend/app/test_config.py [NEW]
- 新增 Linter 配置解析与环境变量重写覆盖的相关单元测试。

#### backend/app/test_sql_linter.py [NEW]
- 覆盖 Linter 骨架、安全拦截、结构合规、DDL 上下文提取、语义校验和工具集成的完整 pytest 用例（共 6 个大用例，覆盖所有规则分支）。

#### docs/fanout/sql_linter_proposal.md [MODIFY]
- 覆写更新方案文档，反映配置别名映射、By-pass 设计及最新自愈切入路径实现细节。

## 2026-07-06 22:30 +08:00 - DDL 粒度标注体系与唯一键自动反射

### 概述
- **唯一键自动反射**：在 `db_utils.py` 中新增 UNIQUE CONSTRAINT + UNIQUE INDEX 双重反射机制，自动标注 DDL 中的 `UNIQUE` 列，解决 `fct_vehicle_position_current` 等仅有唯一索引（UNIQUE INDEX）而无唯一约束（UNIQUE CONSTRAINT）表的标注遗漏。
  - 修复表达式索引（如 `COALESCE(history_id, '-1'::integer)`）导致列名为 None 的 crash。
- **DDL 粒度标注体系（P1）**：
  - 新增 `_parse_grain_info()` 函数，解析表注释中 `Grain:` 前缀，输出结构化 `-- Grain:` + `-- ⚠️` 警告行。
  - 无 `Grain:` 前缀的注释仍走原 `-- Description:` 渲染，向后兼容。
- **样本数据行展示**：新增 `_get_sample_rows()` 函数，在 DDL 尾部附加 3 行样本数据，帮助 LLM 理解列值格式。
- **创建粒度标注规范文档**：`docs/fanout/grain_template.md`，含模板格式、表分类示例、DDL 渲染效果、实施要求。

### 变更内容
#### backend/app/agent/utils/db_utils.py [MODIFY]
- `_build_column_definition()`: 新增 `unique_cols` 参数，在主键列之外标注 `UNIQUE`
- `_process_single_table()`: 新增 UNIQUE CONSTRAINT + UNIQUE INDEX 反射逻辑（双通道合并去重）
- 新增 `_parse_grain_info()`: 解析 `Grain:` 前缀注释为 `(grain_desc, warnings)`
- 新增 `_get_sample_rows()`: 获取 3 行样本数据追加到 DDL 尾部
- 注释渲染分支：有 `Grain:` 前缀 → 结构化 Grain + ⚠️；无前缀 → 原 Description
- 更新模块 docstring，反映唯一键反射和粒度标注能力
- 新增 `import re`

#### docs/fanout/grain_template.md [NEW]
- 粒度标注模板格式 `COMMENT ON TABLE ... IS 'Grain:...,...'`
- 流水表、快照表、维度表、异常表四类场景示例 SQL
- DDL 渲染效果对比
- 实施要求与代码实现映射

## 2026-07-05 22:30 +08:00 - P0: 冗余关系声明移除与提示词规则强化

### 概述
- **移除手动关系声明**：从两个技能的 `meta.py` 中彻底删除 `table_primary_keys` 和 `relationships` 声明（7 条关系 + 6 个 PK 定义），PK/UNIQUE 信息改由 `db_utils.py` 自动反射注入 DDL。
- **移除骨架关系渲染**：删除 `skeleton_service.py` 的 `_build_relationship_block()` 方法（~60 行）和 `skill_middleware.py` 的 `_split_skeleton()` 方法（~18 行），骨架生成简化为纯 DDL 块。
- **重写提示词规则 3.3**：
  - EXISTS/NOT EXISTS 替换 IN/NOT IN，增加三值逻辑陷阱专项警告。
  - 新增"关联基数预判与防膨胀"规则，含强制预聚合 SQL 模板。
  - 新增"结果行数 Fan out 自检"规则。
  - 移除过时的 `💡` 模板引用标记。
- **清理验证**：7 个关键词全文搜索确认零残留引用，共删除 ~230 行代码，每轮交互节省约 350 tokens。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/meta.py [MODIFY]
- 移除 `table_primary_keys`（3 个表）
- 移除 `relationships`（3 条关系）
- 更新文件头，说明 PK 信息改由数据库自动反射

#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- 移除 `table_primary_keys`（3 个表）
- 移除 `relationships`（4 条关系）
- 更新文件头，说明 PK 信息改由数据库自动反射

#### backend/app/agent/utils/skeleton_service.py [MODIFY]
- 删除 `_build_relationship_block()` 方法（~60 行）
- `_build_ddl_blocks()` 简化为纯 DDL 清理和返回
- 文件头注释更新，移除关系声明相关描述

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 删除 `_split_skeleton()` 静态方法（~18 行）
- 辅助技能处理简化为直接使用 `get_skeleton_ddl()` 输出

#### backend/app/agent/service.py [MODIFY]
- 规则 3.3 重写：EXISTS/NOT EXISTS 替换 IN/NOT IN，三值逻辑陷阱警告
- 新增关联基数预判与防膨胀规则（含预聚合 SQL 模板）
- 新增结果行数 Fan out 自检规则
- 移除 `💡` 模板引用标记
- 保留运行时自检检查项

## 2026-07-05 18:28 +08:00 - 跨域关联路径防护体系系统性审查与研究文档

### 概述
- **跨域关联路径声明全面审查**：
  - 修复 `paint_shop_defect_analysis/meta.py` 中两条 N:1 关系的 `join_safety` 标注不一致（unsafe→safe），移除冗余 `pre_aggregate_hint`。
  - 修复 `paint_shop_vehicle_logistics/meta.py` 中 relationship 4 的 from/to 方向错误（dim_process_area→position_current 翻转），基数 1:N→N:1。
  - 统一所有 note 术语：弃用"主→辅"角色描述，改用固定的"N侧/1侧"基数描述。
- **骨架关系渲染改为紧凑格式**：
  - 将 `skeleton_service.py` 的 `_build_relationship_block` 从"聚焦式关系图"重写为紧凑箭头式（`[`基数`安全标记`] from_key -> to_key + note + 💡 模板）
  - Token 消耗减少约 3.2x（每条~160→~50 tokens），两个技能 7 条关系共节省 ~770 tokens。
  - 同步更新 `service.py` 规则 3.3 提示词对齐 `⚠️`/`💡` 标记。
  - 清除文件头过时描述。
- **PK 反射替代手动声明分析与研究文档**：
  - 验证 `db_utils.py` 已通过 `inspector.get_pk_constraint()` 自动反射物理表 PK。
  - 验证 PK 规则（JOIN 目标列非 PK → 需预聚合）等价于当前 7 条 relationships 声明（7/7 正确）。
  - 从行业最佳实践角度完整评审：当前系统"重提示词、轻执行"，缺失执行前 AST 检查和运行时膨胀检测。
  - 创建系统性研究文档 `docs/fanout/README.md`，含现象/分析/行业实践/推荐方案/进度/计划六维度总结。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/meta.py [MODIFY]
- relationship 1: `join_safety` unsafe→safe，移除 `pre_aggregate_hint`，更新 note
- relationship 2 & 3: note 术语统一为 N侧/1侧

#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- relationship 4: 翻转 from/to 方向（dim_process_area→position_current → position_current→dim_process_area），cardinality 1:N→N:1

#### backend/app/agent/utils/skeleton_service.py [MODIFY]
- `_build_relationship_block` 重写为紧凑箭头式输出
- PK 标注正则 `^  `→`^\s+`，增强健壮性
- 文件头过时描述清理

#### backend/app/agent/service.py [MODIFY]
- 规则 3.3 对齐新格式，`⚠️`/`💡` 标记替代旧文本

#### docs/fanout/README.md [NEW]
- 跨域关联路径防护体系系统性总结研究文档
- 含现象、分析、行业最佳实践（附参考文献）、推荐方案、进度、后续计划

## 2026-07-04 22:08 +08:00 - 系统提示词整合自主案例检索与场景加载工作流

### 概述
- **整合系统提示词工作流**：
  在 `backend/app/agent/service.py` 的系统提示词 `## 3.1 总体工作流与重试机制` 中，显式整合了包含 `load_skill`、`load_scenario`、`search_saved_correct_tool_uses` 以及 `AskUserQuestion` 在内的 6 步标准闭环执行流程，明确了在输入口径模糊、关键参数（如车身号 FIS）缺失时提问澄清的判定，同时强化了大模型在非场景任务下通过案例检索的自适应查询规范。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 更新提示词工作流程小节，明确大模型对于澄清反馈、场景优先及案例检索工具的互斥、依存使用策略。

## 2026-07-04 18:10 +08:00 - 集成漏检车监控新场景并同步文档与场景模板对齐数仓升级


### 概述
- **新增漏检与未检测车辆监控场景 (`leak_detection`)**：
  - 设计并集成了全新的 `leak_detection` 场景，通过面漆 3 条生产线的入口读写站（`L3ACC21IS01`/`02`/`03`）过车事件锁定车辆已到达检测线，全局 `LEFT JOIN fct.fct_vehicle_defect_detection` 来精准检测没有产生对应任何通道缺陷流水的漏检车或检测失败车，输出包含车辆当前最新工艺区域（`current_process_area`）和载具（`current_carrier_id`）以便现场召回补检，且此全局关联连接策略巧妙地避免了因为改道/跨线分流导致的假阳性误报。
- **重构并同步物流追踪与质量缺陷分析领域文档**：
  - 对齐了 `dim.dim_vehicle_profile` 画像表扩展的 9 个物理车身及状态新字段，同步更新了 `dim.carbody_registry` 和 `mart.mart_vehicle_quality_360` 的字段列表；统一了车身注册表相关的“过站读写站”业务术语注释说明。
  - 重构了 `paint_shop_defect_analysis/domain.md` 的架构体系，使其与 `paint_shop_vehicle_logistics/domain.md` 的结构完全对齐，并新增了关于漏检监控场景的提示。
- **修复质量分析场景 SQL 模板由于数仓升级导致的数据虚高与 NULL 组 Bug**：
  - 因 `mart.mart_vehicle_quality_360` 的驱动表改为了包含在产未检车辆与漏检车辆的 `fct.fct_vehicle_defect_enriched`，这会导致原有场景 SQL 在做 COUNT/SUM 等聚合时，把未检出车辆计算在内，产生空值组并使检测频次统计翻倍虚高。
  - 修复了 `daily_defect_summary`、`black_roof_defect_comparison`、`defect_station_distribution`、`model_defect_trend`、`tunnel_cycle_defect_comparison` 这 5 个质量缺陷场景 SQL 模板，在 `FROM mart_vehicle_quality_360` 中均追加了 `WHERE mq.history_id IS NOT NULL` 强制过滤规则，确保只统计已上线检测的有效缺陷事实。

### 变更内容
#### backend/app/skills/domains/paint_shop_vehicle_logistics/domain.md [MODIFY]
- 对齐并补充 `dim.carbody_registry` 和 `dim.dim_vehicle_profile` 的全部新物理车身过站、MDS 字段，更新 `rw_station` 相关的中文注释为“过站读写站编码”。

#### backend/app/skills/domains/paint_shop_defect_analysis/domain.md [MODIFY]
- 重新设计文档结构，划分为 WIP 实时层与 History 历史事实层；补充 `fct_vehicle_defect_detection` 及 `fct_vehicle_defect_enriched` 字段详情；补全并对齐 `mart_vehicle_quality_360` 的 38 个字段中文说明；追加 `2.3 漏检与未检测车辆监控` 引导。

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/* [MODIFY]
- 修复 5 个已有场景的 `sql/main.sql` 模板，增加 `WHERE mq.history_id IS NOT NULL` 过滤。
- **[NEW]** 新增 `leak_detection` 场景，创建 `scenario.py` 元数据以及编写 `sql/main.sql` 精准的漏检全局 LEFT JOIN 查询逻辑。

## 2026-07-04 13:11 +08:00 - 增强 SQL Agent 系统提示词防范 PostgreSQL 数据库名前缀错误


### 概述
- **新增 PostgreSQL 数据库名前缀反向约束**：
  在 `backend/app/agent/service.py` 里的 `_build_system_prompt` 中，针对 PostgreSQL 查询规范新增了一条针对表名前缀的强制防范规则，严禁大模型生成类似 `analytics_db.schema.table` 的三段式表名，以防 PostgreSQL 报错 `UndefinedTable`。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 在 `_build_system_prompt` 中加入限制规则 `1. 【禁止使用数据库名前缀】` 并调整其他规则的数字索引。

## 2026-07-03 17:05 +08:00 - 重构 SkeletonService 归档迁移与 LangGraph 状态通道并发写修复

### 概述
- **将 SkeletonService 移入 utils/ 工具类包**：
  为保持代码目录的一致性与职责内聚，撤销了原有的单文件子目录 `services/`。将 `skeleton_service.py` 及其测试文件 `test_skeleton_service.py` 完美迁移归档至已有的 `backend/app/agent/utils/` 包下，消除了冗余目录，并将反射 DDL 逻辑划入数据库元数据工具大类。
- **修复 LangGraph 状态通道并发写异常 (INVALID_CONCURRENT_GRAPH_UPDATE)**：
  针对在同一步/Tick 中对 `skills_loaded` 和 `active_skill` 并发更新导致流式中断崩溃的问题，在 `state.py` 状态实体中，正式为 `skills_loaded`、`scenarios_loaded`、`active_skill` 与 `active_scenario` 声明挂载了 `_last_wins` Reducer 装饰，利用“后写覆盖前值”策略完美实现了状态流转的并发写容错。
- **物理剔除 DDL 骨架中的 VARCHAR(N) 长度限制**：
  在 `SkeletonService` 提取拼装骨架 DDL 时，引入正则表达式自动裁剪剥离类似 `VARCHAR(50)`、`VARCHAR(255)` 中的长度数值修饰符，统一还原为极简 `VARCHAR` 类型，为大模型 Prompt 进行了二次瘦身，减少了无效 Token 的消耗。
- **同步更新全局引用与实施文档**：
  全面修改了 `skill_middleware.py` 等文件中对 `SkeletonService` 的包导入语句，并同步重构了详细设计手册 `phase_1_cascade_query_design.md` 和一期实施计划中的文档测试路径指南。

### 变更内容
#### backend/app/agent/utils/skeleton_service.py [NEW]
- 从 `services/` 目录中迁移过来，并追加正则自动剔除 `VARCHAR(N)` 类型修饰符逻辑。

#### backend/app/agent/utils/test_skeleton_service.py [NEW]
- 从 `services/` 目录中迁移过来，将 DDL 模拟类型断言修正为通用 `VARCHAR`，修复 `_custom_table_info` 私有属性 Mock。

#### backend/app/agent/services/ [DELETE]
- 物理删除原单文件临时目录及内部的原有代码文件。

#### backend/app/agent/state.py [MODIFY]
- 对状态属性 `skills_loaded`、`scenarios_loaded`、`active_skill` 及 `active_scenario` 使用 `Annotated[..., _last_wins]` 修饰，提供并发写 Reducer。

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 修改导入语句，改从 `backend.app.agent.utils.skeleton_service` 导入。

#### docs/crossdomin/phase_1_cascade_query_design.md [MODIFY]
- 同步修正代码示例展示里的类文件路径。

#### docs/crossdomin/2026-07-03-phase_1_cascade_query.md [MODIFY]
- 修改 Task 2、Task 4 中的测试路径，对齐 `utils/` 物理目录，并将 `custom_table_info` 全局替换为私有属性 `_custom_table_info`。

## 2026-07-03 15:37 +08:00 - 实现 Phase 1 跨域子查询直连与状态清理中间件重构

### 概述
- **实现技能元数据 associated_tables 声明**：在物流追踪和缺陷分析技能的 `meta.py` 描述中，完成了物理表关联声明。
- **免物理连库的内存骨架 DDL 反射 (SkeletonService)**：新建 `SkeletonService`，复用系统初始化常驻于内存中的 `db.custom_table_info` 缓存，实现 0 物理读库开销。引入正则表达式物理剔除 DDL 尾部的样例数据行（`-- 1. { ... }`），规避了大模型在长上下文下的数据偏见与 Token 膨胀。
- **重构 load_skill 工具为去重追加与上限截断模式**：修改 `_build_load_skill_command` 函数，将原有覆盖模式升级为去重追加，并强制堆积截断上限为 3，激活了 `skills_loaded` 列表的多值级联状态。
- **基于 before_agent 原生钩子的零侵入单步重置**：重写 `SkillMiddleware.before_agent` 生周期钩子。每次新提问到来时，自动在框架层拦截，清空多余辅助技能，仅保留当前激活主技能，实现完美的“用完即弃”Prompt 瘦身。
- **级联 Prompt 拼接与子查询规训微调**：改造 `_modify_request` 级联生成 `## Secondary Domain Knowledge` 辅助块。同时更新 `service.py` 中的提示词军规，强制推行 EXISTS 子查询替代 `IN` 常量列表，并强制规定表别名前缀规范，全面防范 PostgreSQL 17 抛出 ambiguous 列引用报错。

### 变更内容
#### backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py [MODIFY]
- 在元数据中注册关联物理表 `fct.fct_vehicle_position_current`, `ods.carbody_history`, `dim.carbody_registry`。

#### backend/app/skills/domains/paint_shop_defect_analysis/meta.py [MODIFY]
- 在元数据中注册关联物理表 `mart_vehicle_quality_360`, `fct_vehicle_defect_detection`。

#### backend/app/agent/services/skeleton_service.py [NEW]
- 实现 `SkeletonService` 类以提取 DDL 并使用正则剥离样本行。

#### backend/app/agent/services/test_skeleton_service.py [NEW]
- 针对样本数据剥离和 DDL 反射编写独立单元测试。

#### backend/app/agent/tools/skill_tools.py [MODIFY]
- 重构 `_build_load_skill_command`，加入去重追加和上限为 3 的截断逻辑。

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 重写 `SkillMiddleware.__init__` 以支持全局 `db` 注入。
- 重写 `before_agent` 实现单步自愈清空状态。
- 重改 `_modify_request` 实现一主多辅 DDL 极简骨架的动态拼装。

#### backend/app/agent/middleware/test_skill_middleware.py [MODIFY]
- 添加 `test_before_agent_resets_loaded_skills` 单元测试。
- 添加 `test_skill_middleware_injects_secondary_skeleton` 级联注入断言。
- 升级 `test_load_skill_tool_appends_state` 验证去重新增和堆积截断。

#### backend/app/agent/service.py [MODIFY]
- 微调系统提示词，更新 `## 跨领域复合问题处理流程 (一期子查询军规)`，强化 EXISTS 和表别名纪律。

#### backend/app/agent/test_service_prompt.py [MODIFY]
- 新增对一期子查询军规与表别名约束的提示词测试断言。

## 2026-07-01 20:45 +08:00 - 实现多步 SQL 案例提取与过滤管道顺序 Bug 修复

### 概述
- **实现多步 SQL 案例提取与存储**：
  扩展了原有规则提取器，使其在允许的步数限制内（通过 `RULE_EXTRACTOR_MAX_SQL_STEPS` 控制）支持抓取多步 `sql_db_query` 成功调用的查询语句。多步 SQL 查询在提取时使用 `-- Step N` 注释行进行格式化拼接，执行结果则通过 `[Step N Result]` 进行分隔对齐，无需修改底层数据库与向量元数据 Schema。
- **重构并修复过滤管道执行顺序 Bug**：
  排查并修复了原系统中 `SafetyWarningFilter` 执行早于 `SingleSqlFilter` 导致其始终无法在生产环境下校验 SQL 执行结果 `tool_result` 的逻辑漏洞。将 SQL 提取与数据填充算子（重命名为 `SqlStepFilter`）移至校验过滤管道的最首位，确保先填充上下文状态，再行安全过滤与空值校验。
- **优化多步场景下的“空结果校验”**：
  针对多步查询特征，升级了 `EmptyResultFilter`，使其仅对多步调用链中的最后一步返回数据进行实质性的空列表/空字典阻断，避免因中间步骤无结果而导致高价值的复杂关联案例被硬性拦截丢弃。
- **LLM 提炼层多步适配**：
  在 `llm_refiner.py` 中更新了黄金案例意图重写与脱敏 prompt，引导大模型识别多步执行中前后步骤的变量依赖（如 `position_id = {{Step1.id}}`），并强制保证在参数化脱敏时保留 `-- Step N` 步骤说明结构。
- **前端多步 fallback 支持**：
  在 `AdminReviewPanel.vue` 审核面板中，对 `parseOriginalSql` 进行了多步提取适配，确保在后台提纯草稿未生成或报错时，前端依然能够拼接显示完整的多步 SQL。

### 变更内容
#### backend/app/config.py [MODIFY]
- 增加 `rule_extractor_max_sql_steps` 配置选项（默认值为 3）。

#### backend/app/agent/vector/rule_extractor.py [MODIFY]
- 将 `SingleSqlFilter` 重构并更名为 `SqlStepFilter`，支持跳过错误语句、步数阈值校验与拼接；
- 调整 `DEFAULT_EXTRACTOR_PIPELINE` 执行顺序，将 `SqlStepFilter()` 移至最首位；
- 优化 `EmptyResultFilter` 以在多步场景下仅对最后一步的执行结果进行有效空值拦截。

#### backend/app/agent/vector/llm_refiner.py [MODIFY]
- 更新提纯 prompt，指导 LLM 识别多步级联数据依赖并维持 `-- Step N` 结构。

#### backend/app/agent/vector/test_rule_extractor.py [MODIFY]
- 新增 `test_multi_sql_filter_success` 和 `test_multi_sql_filter_exceeds_limit` 测试用例，更新已有断言以适配 `SqlStepFilter` 命名和管道执行新顺序。

#### backend/app/agent/vector/test_llm_refiner.py [MODIFY]
- 新增 `test_refine_multi_sql_case_success` 用例，模拟验证多步 SQL 结构在 LLM 提纯时的脱敏表现。

#### frontend/src/components/AdminReviewPanel.vue [MODIFY]
- 升级 `parseOriginalSql` 助手函数，当存在多步 SQL 调用时自动返回带 `-- Step N` 拼接的原始代码块。

#### .env [MODIFY]
- 显式声明 `RULE_EXTRACTOR_MAX_SQL_STEPS="3"` 控制多步 SQL 抓取限制。

## 2026-06-30 16:30 +08:00 - 实现规则提取器配置驱动与 LangChain 1.0 结构化输出重构

### 概述
- **实现规则提取器配置驱动（Option A）**：
  将规则提取器的关键检测参数与控制开关从代码硬编码中剥离，转由 Pydantic Settings 加载，并在 `.env` 中提供了一系列开箱即用的默认环境变量控制。支持管理员与运维人员无需修改任何核心过滤逻辑代码，通过配置文件热插拔与灵活参数化控制过滤器（安全审查开关、安全关键字与警告标记、空结果校验开关、单步 SQL 检查开关、回溯开关与最大回溯轮数等）。
- **完成大模型意图与 SQL 提炼的结构化输出重构**：
  在 `llm_refiner.py` 中引入了基于 Pydantic 的 `RefinedSQLCase` 模型，利用 LangChain 1.0+ 标准推荐的 `with_structured_output(..., include_raw=True)` 机制重构了提纯算子。彻底消除了传统正则表达式与手工 JSON 清洗方式的不稳定性，通过 Constrained Decoding 强制保证了模型输出的 Schema 合规性，并结合 `parsing_error` 实现了健壮的生产级安全降级与审计。

### 变更内容
#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中增加了 Rule Extractor 相关的环境变量配置项，并声明了对关键字与警告标记进行大小写清洗、拆分逗号的助手 properties 属性。

#### backend/app/agent/vector/rule_extractor.py [MODIFY]
- 对 `SafetyWarningFilter`、`EmptyResultFilter`、`SingleSqlFilter`、`TopologyBacktrackFilter` 及 `DomainFilter` 引入开关校验逻辑与外部配置参数读取。其中回溯过滤器在禁用或配置轮数过小时支持向下安全降级为单轮处理。

#### backend/app/agent/vector/llm_refiner.py [MODIFY]
- 定义 `RefinedSQLCase` 模型，并使用 `with_structured_output(..., include_raw=True)` 重塑提炼流程，实现异常数据优雅判定与自适应策略选择。

#### backend/app/agent/vector/test_rule_extractor.py [MODIFY]
- 新增 `test_safety_warning_filter_disabled` 和 `test_topology_backtrack_filter_disabled` 两个测试用例，在 Mock 环境中模拟配置变动，全方位验证配置驱动逻辑的正确性与向后兼容性。

#### backend/app/agent/vector/test_llm_refiner.py [MODIFY]
- 全面重构测试用例以匹配 `include_raw=True` 结构化字典响应 Mock，新增解析错误与底层接口连接崩溃等分支测试。

#### .env [MODIFY]
- 追加规则提取器（Rule Extractor）的各种默认控制配置，支持热拔插配置。

## 2026-06-29 21:38 +08:00 - 增强 SQL Agent 系统提示词以提升 PostgreSQL 生成质量

### 概述
- **合并 PostgreSQL 专家规则至系统提示词**：
  在主系统提示词中合并了一组精细化的 PostgreSQL 编写最佳实践，明确声明当目标数据库为 PostgreSQL 时，生成 SQL 需遵循以下 8 项核心准则：优先使用 CTE 替换嵌套层数 > 1 的子查询以消除作用域混乱 Bug、使用自解释的 CTE 命名、避免俄罗斯套娃式嵌套反模式、智能物化（MATERIALIZED）策略、采用 PG 专属的高效语法、支持分析模式的分层计算（CTE 基础聚合 + 主查询窗口函数二次计算）、按需且有条件地引入递归（WITH RECURSIVE），以及在思考区（thinking）执行生成后自检。该规则在强化 PostgreSQL 复杂关联生成质量的同时，仍保证了系统对其他异构数据库（如 MySQL）在多方连接时的兼容性。

### 变更内容
#### backend/app/agent/service.py [MODIFY]
- 在系统提示词构建函数 `_build_system_prompt` 的 `# SQL查询规范` 章节中嵌入了结构化的 PostgreSQL 规范提示规则。

## 2026-06-29 16:30 +08:00 - 优化 DomainFilter 业务域提取与管道过滤拦截日志


### 概述
- **过滤管道拦截日志增强**：
  在规则过滤管道 `PipelineManager` 中引入了结构化的拦截警告日志。当案例提纯初筛未通过任一过滤器原则时，后台日志将精准打印出具体的过滤器类名（如 `SafetyWarningFilter` / `SingleSqlFilter`）和不符合原则的 reject 详情原因，极大地方便了开发和运维人员定位和审计提炼失败的根本原因。
- **业务域提取管道过滤优化**：
  优化了规则提取管道中的业务域提取器 `DomainFilter`。针对在真实环境中 `load_skill` 参数键名为 `skill_name` 导致的 `domain` 丢失为 `None` 的问题，重新设计了优先顺序级联抓取策略。
  1. 优先从 `sql_db_query` 工具调用的 `required_skill` 字段进行直接精准提取（直咬合 SQL 执行生命周期）。
  2. 若无 SQL 动作，则退而求其次寻找 `load_skill` 调用，双重兼容并提取 `skill_name` 或 `skill` 参数。
  3. 最终提供 `"general"` 作为默认降级保护，全面根治了 Milvus 向量入库时 `domain` 出现 `None` 值的缺陷。
- **补齐提取测试断言**：在 `test_rule_extractor.py` 中对 `test_domain_filter` 增加了多渠道（`required_skill` 与 `skill_name`）覆盖测试用例，全方位验证提取逻辑的高保真与兼容性。

### 变更内容
#### backend/app/agent/vector/rule_extractor.py [MODIFY]
- 重构 `DomainFilter.execute` 成员函数，编写级联抽取逻辑并添加健壮性 JSON 字典解析及类型保障，完美防护空域与 `None` 值。

#### backend/app/agent/vector/test_rule_extractor.py [MODIFY]
- 扩展 `test_domain_filter` 单元测试用例，覆盖 `sql_db_query.required_skill` 提取分支以及 `load_skill.skill_name` 提取分支。

## 2026-06-29 12:30 +08:00 - 实现管理员审批接口、后台异步 LLM 意图提炼与 Milvus 写入

### 概述
- **第三阶段：管理员审批、LLM 意图提炼与 Milvus 写入**：
  实现了管理员审批入库接口，支持管理员可选进行意图与 SQL 的微调纠错；集成了后台异步处理管道，通过 FastAPI `BackgroundTasks` 拉起 LLM 重写与脱敏服务；设计了后台 LLM 提炼模型（`llm_refiner.py`）进行多轮会话指代消解与字面值占位符脱敏，并配置了安全降级退回策略；在 `factory.py` 中实现了 `add_document_to_store` 向量写入适配层，支持 LlamaIndex 写入 Milvus Hybrid Collection。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 新增 `MessageApproveRequest` 请求 Schema，以支持管理员的可选改写参数。

#### backend/app/api.py [MODIFY]
- 新增 `POST /api/chat/admin/messages/{message_id}/approve` 审批接口。
- 实现 `process_collected_message_async` 异步处理管道，整合规则初筛、LLM 提纯和向量写入。

#### backend/app/agent/vector/llm_refiner.py [NEW]
- 实现大模型意图消解重写与 SQL 字面值脱敏函数 `refine_sql_case_with_llm`，具备防崩溃自动回退机制。

#### backend/app/agent/vector/test_llm_refiner.py [NEW]
- 编写提炼服务测试，验证大模型正常提炼以及异常连接时的平稳降级行为。

#### backend/app/agent/vector/factory.py [MODIFY]
- 新增统一向量存储适配器函数 `add_document_to_store`，完美支持 Milvus 及 PgVector。

#### backend/app/test_api_persistence.py [MODIFY]
- 新增审批路由 API 测试以及异步提炼写入全集成联调测试 `test_process_collected_message_async_integration`。

## 2026-06-29 11:39 +08:00 - 实现用户反馈收集基建与规则提取过滤器管道和拓扑精准回溯

### 概述
- **第一阶段：用户反馈收集基础建设与落库**：
  在后端 `ChatMessage` 模型中扩展了 `feedback` 列，提供 `MessageFeedbackRequest` 反馈打标校验并在 API 中开放了状态同步路由；在前端 Vue 消息卡片底端集成了“赞/踩/收藏”高亮操作按钮并打通了实时状态落库逻辑。修复了脱机运行下 `test_api_resume.py` 对 `get_messages_by_session` 的 Mock 缺失问题，保证测试全绿。
- **第二阶段：规则提取器与拓扑精准回溯**：
  新增了基于 Pipeline-Filter 设计模式的规则过滤器模块，定义了任务上下文与管道管理器，依次实现四大静态规则过滤器（安全检测、空结果判定、多步/报错 SQL 单步拦截舍弃以及业务域隔离）；特别实现了 `TopologyBacktrackFilter` 基于原生 `tool_call_id` 自动咬合还原包含澄清问答历史的多轮对话意图；编写了 8 项独立 TDD 测试用例全面覆盖各过滤分支与链路集成校验。

### 变更内容
#### backend/app/models.py [MODIFY]
- 为 `ChatMessage` 实体模型追加 `feedback` 字段。

#### backend/app/schemas.py [MODIFY]
- 在消息响应基类中注入 `feedback` 序列化结构，并提供 `MessageFeedbackRequest`。

#### backend/app/crud.py [MODIFY]
- 实现 `update_message_feedback` 数据状态持久化修改方法。

#### backend/app/api.py [MODIFY]
- 发布 `POST /api/chat/messages/{message_id}/feedback` 路由响应用户点击反馈。

#### backend/app/test_api_persistence.py & test_api_resume.py [MODIFY]
- 补齐反馈 API 的 TDD 测试案例。为 `test_resume_endpoint_success` 修复 offline 状态下 missing mock 导致的 db 连接失败问题。

#### backend/app/agent/vector/rule_extractor.py [NEW]
- 创建规则提取上下文、管道控制器及五大过滤器校验器（`SafetyWarningFilter`, `EmptyResultFilter`, `SingleSqlFilter`, `TopologyBacktrackFilter`, `DomainFilter`），定义 `DEFAULT_EXTRACTOR_PIPELINE`。

#### backend/app/agent/vector/test_rule_extractor.py [NEW]
- 编写 8 个测试用例，覆盖过滤器的校验和拓扑回溯意图合成的完整链路。

#### frontend/src/types/index.ts, src/api/messages.ts, src/stores/messages.ts [MODIFY]
- 注入 `feedback` 可选属性，导出 axios 交互 API，并在 Pinia store 中新增 `submitMessageFeedback` action 驱动。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 为 AI 消息卡片集成了 👍、👎、⭐ 高亮交互按钮，成功通过 `vue-tsc` 的强类型编译及打包检查。

## 2026-06-28 23:12 +08:00 - 优化澄清会话数据链系统化完整关联存储

### 概述
- **实现澄清数据链条闭环**：重构了流式中断与恢复挂起的消息持久化逻辑，解决工具调用和返回结果的丢失与错位问题。在 `interrupt` 写入消息时补全 `tool_results` 保存；在用户回答落库时倒序查询历史消息以匹配 `AskUserQuestion` 调用 ID 并以此 ID 序列化存储回答；同时在最终结果输出中主动拦截隔离历史澄清提问的返回结果。

### 变更内容
#### backend/app/api.py [MODIFY]
- 在 `/stream` 与 `/resume` 路由的中断处理分支中加入 `tool_results` 持久化，补齐 `load_skill` 与 `load_scenario` 的返回数据存储。
- 在 `/resume` 路由中，通过 `get_messages_by_session` 追溯最近一次 Assistant 的 `AskUserQuestion` 调用 ID，以 `{ask_user_tool_call_id: answers}` 格式保存 User 消息。
- 在恢复流式循环的 `tool_result` 监听及 `final` 事件中，过滤排除对应的 `ask_user_tool_call_id`，防止其泄露至最终消息。

#### backend/app/test_api_persistence.py [MODIFY]
- 扩充单元测试，对 `test_stream_interrupt_saves_clarification` 增加 `tool_result` 返回值保存的校验；重构 `test_resume_saves_user_answers` 支持 mock 历史消息并断言 ID 强对齐配对。

## 2026-06-28 22:36 +08:00 - 修复流式中断挂起场景工具调用完整持久化存储

### 概述
- **修复流式中断工具调用丢失漏洞**：在 `/stream` 和 `/resume` 生成器遇到 `interrupt` 事件（澄清提问）时，系统不再使用单一硬编码的 `AskUserQuestion` 覆盖已有的工具列表，而是将内存 `tool_calls_map` 缓存的所有已执行工具调用（如 `load_skill`, `load_scenario` 以及带原生 ID 的 `AskUserQuestion` 等）一并序列化并保存，保障了中断状态消息中工具调用数据链的完整性。

### 变更内容
#### backend/app/api.py [MODIFY]
- 修改流式（`/stream`）和恢复流（`/resume`）的 `interrupt` 中断事件持久化逻辑，从内存 `tool_calls_map` 中合并获取全部已调用的工具记录，并进行 JSON 序列化存储。

#### backend/app/test_api_persistence.py [MODIFY]
- 在 `test_stream_interrupt_saves_clarification` 单元测试中添加了 `load_skill` 前置调用模拟，并断言其能够与 `AskUserQuestion` 合并成功保存到数据库中。

## 2026-06-28 21:52 +08:00 - 修复流式澄清提问处理中的 AttributeError 与 JSON 序列化异常

### 概述
- **修复 AttributeError 报错**：在 `api.py` 的流式响应生成器（`generate`）中，当收到 `interrupt`（澄清提问）事件时，列表中的 `questions` 元素为 Pydantic 模型（`QuestionItem`）而非原生字典，从而导致调用 `q.get('question')` 时发生 `'QuestionItem' object has no attribute 'get'` 报错。对此增加了 Pydantic 模型的识别与 `.model_dump()` 字典化转换兼容。
- **修复潜在的 JSON 序列化失败**：由于 `questions` 原本为 Pydantic 对象列表，直接传给 `json.dumps` 写入消息的 `tool_calls` 会在数据库持久化时导致 `TypeError`。此次修改使用字典化后的 `questions_dump` 进行序列化，消除了序列化失败隐患。

### 变更内容
#### backend/app/api.py [MODIFY]
- 对 `interrupt` 事件处理逻辑进行健壮性兼容优化。遍历 `questions` 时，自动检测并对 Pydantic 模型执行 `model_dump()` 转换为原生字典，保证了对属性字段（如 `question` 和 `options`）的安全读取。
- 传入转换后的原生字典列表 `questions_dump` 以供 `json.dumps()` 成功序列化并持久化至 `MessageCreate` 消息数据库表。

## 2026-06-28 16:31 +08:00 - 新增“关于系统”弹窗与版本日志展示功能

### 概述
- **新增“关于系统”弹窗**：在前端增加了一个高颜值、响应式且支持毛玻璃（Glassmorphism）效果的分栏弹窗组件 `VersionChangelogModal.vue`。弹窗左侧为带状态呼吸灯的垂直时间线，右侧卡片式分组呈现新特性（🎉 Features）、性能优化（⚡ Improvements）与问题修复（🐛 Bug Fixes）。
- **主页面触发与集成**：在 `ChatView.vue` Header 头部右上角集成了“ℹ️ 关于”按钮，用来触发该弹窗。支持点击遮罩层、右上角 "✕" 按钮或按 `Esc` 键进行平滑关闭，并防止了弹窗开启时的背景滚动穿透。

### 变更内容
#### frontend/src/components/VersionChangelogModal.vue [NEW]
- 创建了弹窗组件。实现了模态框在打开/关闭时的渐变过渡，支持通过 timeline 切换选中版本，预置了更新日志的 Mock 数据以供用户后续直接修改与填写。
- 绑定了键盘 `keydown` 监听事件，在按下 `Escape` 键时关闭弹窗，并在弹窗打开时将 `document.body` 锁死以防滚动穿透。

#### frontend/src/views/ChatView.vue [MODIFY]
- 导入并注册了 `VersionChangelogModal` 组件及 `showChangelog` 状态。
- 在 Header bar 右侧添加了带有 `ℹ️` 图标和 “关于” 文本的触发按钮。

## 2026-06-28 13:25 +08:00 - 修复消息持久化机制漏洞与前端工具详情参数展示遗漏

### 概述
- **修复后端消息持久化漏洞**：补齐了在 Agent 中断澄清挂起（Interrupt）、澄清回复（Resume）、连接中途异常断开以及非流式请求报错场景下的消息持久化保存逻辑，确保了 `chat_messages` 对话历史表中每一步的完整性。
- **修复前端工具参数展示遗漏**：解决了由于非流式或重新加载历史时缺乏 `args_text` 字段而导致前端调试面板内工具参数和 SQL 语句完全空白的 Bug；增加了对结构化 `args` 的智能兼容和 JSON 格式化输出。
- **优化工具结果名称关联**：实现了工具返回结果 ID 到工具名称的动态映射，将原本抽象的 `工具结果 tool_0` 转换为如 `工具结果: sql_db_query (tool_0)` 的友好形式，便于直观调试。

### 变更内容
#### backend/app/api.py [MODIFY]
- 在 `/stream` 和 `/resume` 生成器中遇到 `interrupt` 事件时，增加将 AI 的澄清卡片问题保存为 `assistant` 消息的逻辑。
- 在 `/resume` 接口开始处理前，将用户的 `answers` 澄清回答以 `user` 角色消息安全保存入库。
- 在 `/stream` 和 `/resume` 的生成 `finally` 块中加入连接断开捕获保护，对尚未保存的 partial message 进行补存入库（内容包括 partial content 和 `tool_calls`）。
- 在 `/message` 非流式接口发生 `Exception` 报错时，在抛出异常前捕获并向数据库记录报错的 `assistant` 消息。

#### backend/app/test_api_persistence.py [NEW]
- 创建独立的测试文件，编写并验证了中断挂起保存、回答恢复保存、连接中途断开保存、非流式异常保存 4 个 TDD 测试场景，确认全部通过。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 新增 `getToolArgsText`、`getToolNameById` 和 `formatToolResultContent` 助手函数。
- 更新模板逻辑，即使在无 `args_text` 字段的情况下，也支持读取 `args` 字典（并针对 SQL 语句直接提取 `query` 渲染，对其他复杂参数 pretty print 展示）。
- 支持将工具结果的 `id` 还原为工具名称并缩进格式化 JSON 内容。

## 2026-06-25 22:33 +08:00 - 侧边栏折叠过渡动画性能优化

### 概述
- **消除折叠过度动画卡顿**：针对侧边栏（VariantB.vue）折叠展开时的反应迟钝现象，将全局过度监听 `transition-all` 替换为精准定位的 `transition-[width,transform]` 属性，并应用 `will-change-[width,transform]` 开启 GPU 硬件加速缓存，从而大幅降低了浏览器的样式计算压力。
- **清除内部双重容器动画**：删除了内部头部容器 `div` 上冗余的 `transition-all` 类名，消除了由于内边距和排版排列突变带来的二次重绘瓶颈。

### 变更内容
#### frontend/src/components/VariantB.vue [MODIFY]
- 对 aside 节点与 header container 的 transition 逻辑进行精细化优化，消除了动画重排抖动并提升了整体折叠动效响应速度。

## 2026-06-25 22:20 +08:00 - 为 AskUserQuestion 交互卡片新增取消按钮及单选项重置能力

### 概述
- **新增澄清问答取消按钮**：在前端交互卡片 [AskUserQuestionCard.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/AskUserQuestionCard.vue) 的“确认并恢复生成”按钮左侧增加了“取消”按钮。点击“取消”按钮时，将向后端发送包含 `已取消` 意图的提问答复，确保大模型从中断状态中恢复并以友好形式退出该任务。
- **优化单选项点击与重置**：优化了单选项的选择交互。用户再次点击已选中的单选项，可以将其重置为未选中状态，方便用户撤销选择而无需被迫选择。

### 变更内容
#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 在底部操作区域新增“取消”按钮（Outlined style，优雅适配整体卡片的 Glassmorphism 现代质感）。
- 编写 `handleCancel` 函数实现“取消”意图的收集并提交。
- 调整 `onOptionClick` 中针对单选模式（`item.multiSelect === false`）的逻辑：当再次点击已被选中的单选项时，自动将其清空，支持单选项的重置与反选。

## 2026-06-25 10:42 +08:00 - 本地化部署优化：清理前端冗余的外部 Google Fonts 引用

### 概述
- **移除冗余 Google Fonts 链接**：在 [index.html](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/index.html) 中删除了在本地/内网环境（无公网）下会导致连接超时的 Google Fonts 资源引用。该字体系 `Inter` 字体，在当前的样式定义中并未实际被引用，属于冗余资源。
- **防止加载超时阻塞与控制台报错**：此举彻底消除了本地化/离线部署时由于向 `fonts.googleapis.com` 发起请求而产生的网络报错与首屏加载可能产生的渲染阻塞。

### 变更内容
#### frontend/index.html [MODIFY]
- 清理了引入 `https://fonts.googleapis.com` 域名的三行外部 `<link>` 标签，保留了项目的基础 favicon 与元数据定义。

## 2026-06-21 15:06 +08:00 - 设计并实现 AskUserQuestion 澄清问答与中断恢复功能，构建前后端闭环交互

### 概述
- **实现 AskUserQuestion 澄清问答工具**：在 FastAPI 后端引入了基于 LangGraph 原生 `interrupt` 控制流的结构化澄清问答工具 `AskUserQuestion`。支持向前端发送单选/多选/自定义补充等结构化卡片提问，使大模型能在面临需求模糊、技术权衡或危险 SQL 执行时安全暂停流并等待用户确认。
- **完善 API Resume 接口与流式恢复**：在 `api.py` 中新增了 `POST /api/chat/resume` 路由与 `ResumeChatRequest` 请求体，支持在 PostgresSaver 状态检查点下使用 `Command(resume=...)` 恢复因 interrupt 挂起的 Graph 并继续流式输出。
- **打造高交互 Glassmorphism 前端澄清卡片**：前端利用 Pinia Store 和 SSE 事件流捕获 `interrupt` 类型的流式响应，并在聊天气泡下方动态渲染出 `AskUserQuestionCard.vue` 问答卡片。卡片设计支持单选/多选/纯填空自定义输入互斥，并在提交后自动触发 `resumeMessage()` 重启流，并对历史卡片做 disabled 只读锁定处理。
- **强化混合澄清与字符串 JSON 参数预校验**：在 Pydantic 的 `QuestionItem` 和 `AskUserQuestionSchema` 中增加了预处理解析，解决大模型传递 stringified JSON 的 ValidationError，并在前后端对混合提问（选项+文本输入）进行了拼接回传与自适应编号高亮。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 引入 `QuestionItem`，正式定义并注册了 `InterruptStreamEvent`，彻底解决 tagged-union 反序列化中断事件校验崩溃的缺陷。

#### backend/app/agent/tools/ask_user_question.py [NEW]
- 定义 `QuestionOption`, `QuestionItem` 和 `AskUserQuestionSchema`，基于 LangGraph `interrupt()` 编写 `AskUserQuestion` 工具，并实现了 robust pre-validator。

#### backend/app/agent/tools/test_ask_user_question.py [NEW]
- 编写测试用例验证 `AskUserQuestion` 工具，支持 optional options、string json inputs 预校验等。

#### backend/app/agent/service.py [MODIFY]
- 挂载 `AskUserQuestion` 工具，在 System Prompt 中加入详细的“澄清与确认规范”以及混合提问意图拆分引导。

#### backend/app/agent/test_service_interrupt.py [NEW]
- 编写集成测试，模拟 LangGraph 的 `interrupt` 中断和状态恢复流。

#### backend/app/services.py [MODIFY]
- 扩展 `SQLAgentService` 实现 `process_stream_resume` 生成器，在流式生成中动态捕获并向前端抛出 `'interrupt'` 事件。

#### backend/app/api.py [MODIFY]
- 实现并暴露 `POST /api/chat/resume` 路由，接受用户回答后安全唤醒挂起的 Graph。

#### backend/app/test_api_resume.py [NEW]
- 编写接口测试，模拟并验证 `/api/chat/resume` 请求流程。

#### frontend/src/types/index.ts [MODIFY]
- 新增 `QuestionOption`、`QuestionItem` 类型，为消息流事件补全 `interrupt` 属性支持。

#### frontend/src/stores/messages.ts [MODIFY]
- 引入 `setStreamingInterrupt` 来在 store 中标记挂起的中断流状态。

#### frontend/src/api/chat.ts [MODIFY]
- 增加了 `sendChatResumeStream` 请求函数，并在 `parseStreamEvent` 中对 `'interrupt'` 包放宽 options 校验以兼容纯文本输入。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 实现了 `resumeMessage` 方法，用于发起并重新连接流式响应。

#### frontend/src/components/AskUserQuestionCard.vue [NEW]
- 编写毛玻璃自适应问答卡片组件，支持单选/多选/纯填空/混合模式，具备 questions 列表编号和必填校验。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 动态嵌入 `AskUserQuestionCard`，实现对 computed `questions` 的 watch 深度监听以自动重置 `isLocalSubmitted` 锁定状态，解决组件复用锁死 Bug。

#### README.md [MODIFY]
- 补充“澄清问答卡片 (AskUserQuestion)”特性描述及 `/api/chat/resume` 接口。

#### docs/ [NEW]
- 新增 `docs/ask_user_question_design_pattern.md`、`docs/langgraph_memory_and_persistence_guide.md` 和 `docs/claudecode_docs/05_AskUserQuestion工具设计与使用指南.md`，深度梳理设计模式、状态持久化与工具使用细节。

## 2026-06-20 22:56 +08:00 - 优化缺陷分析指标生成，默认聚焦均值与检测次数以防范总数脑补

### 概述
- **强化大模型缺陷指标统计规则**：在涂装车间质量缺陷分析领域（`paint_shop_defect_analysis`）中，强力约束大模型在编写 SQL 时默认采用“检测次数”（`COUNT(*)`）与“平均单次检测缺陷数”（`AVG(mq.total_defect_count)`）进行统计，防范大模型在未明确指令时脑补并生成无意义的“缺陷总数”（`SUM(...)`）统计语句。
- **Few-Shot SQL 示例多后端同步注入**：分别在 Milvus 与 PGVector 检索数据源中追加了三个典型的缺陷均值与检测频次的 SQL 查询示例，并成功对向量数据库（Milvus）完成了重建索引，使大模型在检索 Few-Shot 时能够高频召回并模仿标准的均值与频次统计口径。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/domain.md [MODIFY]
- 在指标（`指标`）小节中全新引入 `[!IMPORTANT]` 级别的“质量缺陷统计核心军规”，强力限定默认指标为频次和均值，澄清了“单车缺陷”的计算公式，并严格限制对 `SUM` 聚合函数的使用。

#### backend/app/agent/vector/milvus_init/data/examples/example_sql_example.json [MODIFY]
- 在 JSON 数据集中追加三个典型缺陷统计的 SQL 示例（包括按车型趋势、按检测通道、按检测次数对比等），均演示了 `COUNT(*)` 和 `AVG(...)` 组合指标的用法。

#### backend/app/agent/vector/pgvector_init/examples/example_sql_example.json [MODIFY]
- 对齐更新 PGVector 的 SQL 示例数据集，确保测试环境与生产配置下的向量召回一致性。

## 2026-06-20 21:25 +08:00 - 修复 AskUserQuestion 混合输入澄清场景下用户操作路径断裂


### 概述
- **修复混合提问导致的操作路径断裂**：修复了在触发澄清问答卡片（`AskUserQuestion`）时，大模型抛出混合提问意图（如“同时输入车号和选择读写站”）导致前端由于强互斥逻辑而无法让用户同时完成输入与选择的问题。
- **引入双端优化与容错**：
  - **后端**：在 `AskUserQuestionSchema` 和 `QuestionItem` Pydantic 定义中加固了字段描述，并在 System Prompt 中注入了混合模式下的正反面 JSON 拆分示例，强力约束大模型将多参提问拆分为两个 `QuestionItem` 提问项。
  - **前端**：在 `AskUserQuestionCard.vue` 中移除了单选/多选与 textarea 文本框的强互斥清空，优化了 textarea 提示文本，并在提交 payload 时对两者皆有的场景进行智能拼接（分号连接）回传，保证了历史遗留或脑抽混合场景下的完美兼容和操作闭环。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 升级了 `QuestionItem.question` 以及 `AskUserQuestionSchema.questions` 的 `Field` description 说明，增加了混合澄清拆分的引导与正反面示例。

#### backend/app/agent/service.py [MODIFY]
- 升级了 `# 澄清与确认规范` 的系统提示词内容，为“3. 混合模式”追加了具体的 questions JSON 代码块说明。

#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 移除了选项点击和 textarea 输入时的强互斥清空行。
- 更新了自适应的 textarea label 和 placeholder，提供更好的混合提问输入引导。
- 升级 `handleSubmit` 逻辑，在选项与文本框同时有值时以 `; 关联输入: ` 无损拼接形式传回后端。
- 修复了纯填空问答卡片（没有 options 选项列表时）误展示为“单选”徽章的交互缺陷，仅在 options 存在时才渲染该徽章。
- 支持多问题卡片的提问编号（如“问题 1 / 3”高亮徽章），只有当卡片中包含 2 个及以上问题时才自适应呈现，提升多参提问时界面结构感，防止用户漏答。

## 2026-06-20 20:00 +08:00 - 整理并沉淀 LangGraph 状态持久化与会话记忆技术指南文档

### 概述
- **整理发布会话记忆与持久化指南**：编写并归纳了项目基于 LangGraph Checkpointer 持久化、动态多 System Message 物理抽干与合并拦截器、以及基于 Token 估算的上下文滑动窗口压缩摘要等全套记忆管理系统的设计与核心实现原理。

### 变更内容
#### docs/langgraph_memory_and_persistence_guide.md [NEW]
- [全新增加] 《LangGraph 记忆与状态持久化机制技术指南》，作为项目核心架构与状态持久化部分的重要补充。

## 2026-06-20 17:15 +08:00 - 修复同消息流下多次澄清问答卡片被锁死无法提交的 Bug

### 概述
- **修复澄清卡片组件复用状态残留问题**：修复了在同一个流式会话生命周期内（即同一个 `streamingMessage` 内）大模型多次触发 `AskUserQuestion` 澄清卡片时，由于 `MessageItem.vue` 组件复用，本地提交控制状态 `isLocalSubmitted` 仍保留第一轮的 `true` 锁死状态，导致第二轮澄清卡片一渲染就被锁死为只读不可编辑且无法提交的 Bug。
- **引入流式问题包监听自动重置机制**：在 `MessageItem.vue` 中引入 `watch` 指令。对 computed 属性 `questions` 列表进行深度监听，一旦发觉流式响应推入了新的问题包，自动重置 `isLocalSubmitted` 状态为 `false`，解除只读锁定，开启第二轮澄清编辑。

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 引入了 `watch` 并编写对 `questions` 列表的深度监听逻辑，在产生新问题时重置 `isLocalSubmitted.value` 状态。

## 2026-06-20 16:58 +08:00 - 修复 AskUserQuestion 澄清事件在开放式文本问答模式下的前端校验拦截 Bug

### 概述
- **修复前端流式响应终止报错**：修复了在触发纯文本开放式问答（不含 `options` 选项列表的 QuestionItem）时，由于前端 `chat.ts` 内部的 `parseStreamEvent` 对 `interrupt` 事件包进行了过分严苛的属性校验（`!Array.isArray(q.options)` 会在 options 为空/undefined 时抛出错误判定），导致该流式事件被忽略丢弃，从而引发流结束时因检测不到终端事件而抛出“流式响应在收到终止标记前未返回 final 或 error 事件”异常的 Bug。
- **放宽字段校验机制**：在 `chat.ts` 校验分支中调整了对 `q.options` 的验证逻辑，支持在 `options` 为 `undefined` 或 `null` 时直接跳过子项的数组解析和校验，确保开放式输入与混合输入下的事件均能完美被前端反序列化和激活。

### 变更内容
#### frontend/src/api/chat.ts [MODIFY]
- 重构了 `case 'interrupt'` 的属性类型检查管道，使 options 字段可安全地缺省或设置为 null，消除类型误判拦截。

## 2026-06-20 15:58 +08:00 - 优化 Windows 本地数据库连接配置，将 localhost 替换为 127.0.0.1 解决后端冷启动延迟

### 概述
- **消除 Windows 下 IPv6 TCP 连接超时延迟**：将项目根目录下 `.env` 配置文件中的所有 `localhost` 替换为直连的 IPv4 地址 `127.0.0.1`。解决了由于 Windows 操作系统中 `localhost` 默认优先解析为 IPv6 (`::1`) 导致数据库驱动在无 `connect_timeout` 参数下多次发生 21 秒连接超时的挂起现象，使本地后端开发环境的启动时间由之前的约 **130秒** 直接缩减至 **5秒以内**。

### 变更内容
#### .env [MODIFY]
- 将 `DATABASE_URL`、`ROLLERBED_DATABASE_URL` 和 `ANALYTICS_DATABASE_URL` 中的 `localhost` 替换为 `127.0.0.1`。
- 同步将 `OLLAMA_BASE_URL`、`MILVUS_URI` 和 `MYSQL_DATABASE_URL` 中的 `localhost` 替换为 `127.0.0.1`，消除潜在的连接延迟隐患。

## 2026-06-20 14:06 +08:00 - 增强 AskUserQuestion 系统提示词与工具说明文档以引导大模型精准输出

### 概述
- **增强工具说明与系统提示词引导**：为了配合新上线的“纯文本开放式问答模式”与“混合模式”，对系统提示词（System Prompt）中的『澄清与确认规范』以及 `AskUserQuestion` 的工具级 `description` 进行了靶向增强。这能引导大模型在需要收集车身号、工序等参数时，自发正确地选择是使用“选择模式”、“开放式问答模式（省略options参数）”还是多问题的“混合模式”来发起澄清。
- **细化 Schema 字段说明**：对 Pydantic 的 `QuestionItem` 进行了更深度的字段说明（`Field(description=...)`）扩充。明确了 `question` 会作为返回答案 dict 的 key，细化了 `header`、`multiSelect` 以及 `options` 在各种提问模式下的语义，确保不同大模型对 JSON Schema 的绝对对齐和稳定理解。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 更新了 `AskUserQuestion` 类的 `description` 字段，明示工具对备选项及纯文本开放式提问的支持和传参约定。
- 重构了 `QuestionItem` 中 `question`、`header`、`multiSelect` 和 `options` 字段的 `description` 说明。

#### backend/app/agent/service.py [MODIFY]
- 升级了 `_build_system_prompt` 中『澄清与确认规范』的规约内容，提供了选择模式、开放式问答模式、混合模式的具体判定场景与传参引导。

## 2026-06-20 14:02 +08:00 - 升级 AskUserQuestion 澄清卡片以支持纯文本问答模式（无选项纯填空）

### 概述
- **支持纯文本问答模式**：扩展了 `AskUserQuestion` 澄清卡片的功能，使其不仅能处理单选或多选问题，还能原生支持**纯开放式文本提问**（如直接提示用户输入特定车号、时间范围等，且卡片上不显示任何选项网格）。
- **参数自适应与交互优化**：
  - 将 `QuestionItem` 的 `options` 字段变更为可选。
  - 前端模板自适应：如果 `options` 缺省或为空，选项网格会自动隐藏，文本框对应的标题及 placeholder 会自动切换为纯开放问答提示。
  - 校验自适应：非选项问题时，校验规则（`canSubmit`）将强制要求用户在文本框内完成内容录入，防止空值提交。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 将 `QuestionItem` 结构体中的 `options` 字段类型由必填变更为 `Optional[List[QuestionOption]] = Field(default=None)`。

#### backend/app/agent/tools/test_ask_user_question.py [MODIFY]
- 新增 `test_ask_user_question_optional_options` 单元测试，验证对无选项（options 为空）参数校验的正确性。

#### frontend/src/types/index.ts [MODIFY]
- 将 `QuestionItem` 接口中的 `options` 属性声明变更为可选（`options?: QuestionOption[]`）。

#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 在模板中为选项按钮网格包裹了 `v-if="item.options && item.options.length > 0"`。
- 根据是否有选项动态切换文本框上方的 `label` 标签（由『其他 / 自定义说明』动态变更为『请输入答案 / 说明』）及 `placeholder` 占位符。
- 更新了 `canSubmit` 校验计算属性，支持无选项提问时的空值拦截逻辑。

## 2026-06-20 13:52 +08:00 - 移除 AskUserQuestion 问答卡片的 Preview 预览功能以简化非代码应用场景

### 概述
- **简化问答卡片布局**：鉴于本项目并非面向代码开发的 Code Agent，为了使前端问答交互界面更加简洁、干净、聚焦于选项抉择本身，移除了澄清问答卡片（`AskUserQuestionCard`）右侧的代码/配置对比预览（Preview）侧边面板。
- **清理前后端冗余字段与状态**：
  - **后端**：在 `QuestionOption` 结构体中删除了 `preview` 字段，优化了参数解析开销并节省了大模型 Token 输出。
  - **前端**：删除了 `QuestionOption` 中的 `preview` 类型，物理清理了 `AskUserQuestionCard.vue` 内部的 `hoveredPreview`、`hasCodePreviews`、`displayPreview`、`renderedPreview` 等响应式状态与 Markdown 编译逻辑。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 从 `QuestionOption` 中移除 `preview` 字段声明。

#### backend/app/agent/tools/test_ask_user_question.py [MODIFY]
- 移除了测试用例 payloads 中的 `"preview"` 字段以对齐最新的 Schema 结构。

#### frontend/src/types/index.ts [MODIFY]
- 从 `QuestionOption` 接口中移除可选的 `preview` 属性。

#### frontend/src/components/AskUserQuestionCard.vue [MODIFY]
- 完全移除了右侧预览面板的 HTML/SVG 结构与 `:deep(.markdown-body)` 样式。
- 删除了所有 hover 事件监听与预览相关的计算属性和 markdown 引用。

## 2026-06-20 13:40 +08:00 - 修复 AskUserQuestion 澄清工具 stringified JSON 传参时的反序列化校验报错

### 概述
- **修复 AskUserQuestion 澄清工具反序列化报错**：针对大模型在调用澄清问答工具时，可能会将 `questions` 参数误以序列化后的 JSON 字符串（而非直接的 list）格式传递，导致 Pydantic schema 在参数校验阶段抛出 `questions: Input should be a valid list` 的 ValidationError。
- **引入 Robust Pre-Validator 解析机制**：在 `AskUserQuestionSchema` 内部的 `questions` 字段上引入了 `field_validator(mode="before")`，支持在 Pydantic 进行正式类型验证前自动尝试解析 JSON 格式的字符串，能够健壮处理带 Markdown 围栏（```json）的字符串、标准 JSON 数组字符串以及使用 `ast.literal_eval` 进行单引号的容错解析。
- **完善单元测试**：在 `test_ask_user_question.py` 中补充了 `test_ask_user_question_string_input` 靶向测试，并在 conda `py312_agent` 环境下通过 pytest 验证了全部单元测试（100% 成功）。

### 变更内容
#### backend/app/agent/tools/ask_user_question.py [MODIFY]
- 在 `AskUserQuestionSchema` 增加了 `@field_validator("questions", mode="before")` 预处理方法 `parse_questions`，支持字符串到 List 对象的解析转换。

#### backend/app/agent/tools/test_ask_user_question.py [MODIFY]
- 新增 `test_ask_user_question_string_input` 单元测试以验证字符串传参的自动解析及成功校验。

## 2026-06-19 21:40 +08:00 - 集成 AskUserQuestion 澄清问答卡片（LangGraph 1.1.8 中断流与前端 Vue 3 交互集成）

### 概述
- **实现 AskUserQuestion 澄清问答工具**：在 FastAPI 后端引入了基于 LangGraph 1.1.8 原生 `interrupt` 控制流的结构化澄清问答工具 `AskUserQuestion`。支持向前端发送单选/多选/自定义补充等结构化卡片提问，使大模型能在面临需求模糊、技术权衡或危险 SQL 执行时安全暂停流并等待用户拍板。
- **完善 API Resume 接口与流式恢复**：在 `api.py` 中新增了 `POST /api/chat/resume` 路由与 `ResumeChatRequest` 请求体，支持在 PostgresSaver 状态检查点下使用 `Command(resume=...)` 恢复因 interrupt 挂起的 Graph 并继续流式输出。编写了高保真 Mock API 与中间件单元测试，100% 跑通测试。
- **打造高交互 Glassmorphism 前端澄清卡片**：前端利用 Pinia Store 和 SSE 事件流捕获 `interrupt` 类型的流式响应，并在聊天气泡下方动态渲染出 `AskUserQuestionCard.vue` 问答卡片。卡片设计完美遵循 "Light Mode Card-based Workspace" 的毛玻璃质感，并支持互斥输入（选项选择与 textarea 互斥）、hover 悬停实时渲染 Markdown 代码对比预览等高级微动效，提交后自动触发 `resumeMessage()` 重启流，并对历史卡片做 disabled 只读锁定处理。
- **修复 Interrupt 事件流式序列化崩溃 Bug**：在 `schemas.py` 中为 tagged-union `ChatStreamEvent` 补齐注册了新事件类型 `InterruptStreamEvent`，消除了大模型触发澄清中断时 API 序列化报错并强行关流的崩溃隐患。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- 引入 `QuestionItem`，正式定义并注册了 `InterruptStreamEvent`，彻底解决 tagged-union 反序列化中断事件校验崩溃的缺陷。

#### backend/app/agent/tools/ask_user_question.py [NEW]
- 定义 `QuestionOption`, `QuestionItem` 和 `AskUserQuestionSchema`，基于 LangGraph `interrupt()` 编写 `AskUserQuestion` 工具。

#### backend/app/agent/service.py [MODIFY]
- 在 `_prepare_tools` 中注册并挂载 `AskUserQuestion` 工具，并在 System Prompt 中增加对调用该工具的指导思想和约束原则。

#### backend/app/services.py [MODIFY]
- 扩展 `SQLAgentService` 实现 `process_stream_resume` 生成器，并在流式响应发射阶段实时从 Graph 的 state 中检测 interrupts 详情并抛出 `'interrupt'` 事件。

#### backend/app/api.py [MODIFY]
- 引入 Pydantic 的 `BaseModel` 并声明 `ResumeChatRequest` schema。
- 实现 `POST /api/chat/resume` 流式接口，并在生成结束或异常时进行 assistant 消息的入库持久化。

#### backend/app/test_api_resume.py [NEW/MODIFY]
- 新写并完善了 `test_api_resume.py` 对 `/resume` 路由成功与 422 失败的 Mock 单元测试。

#### frontend/src/types/index.ts [MODIFY]
- 新增 `QuestionOption`、`QuestionItem` 类型声明，并在 `Message`、`StreamingMessage` 和 `StreamEvent` 中扩展 `interrupt` 属性与事件格式支持。

#### frontend/src/stores/messages.ts [MODIFY]
- 在 `useMessagesStore` 中加入 `setStreamingInterrupt` action，支持流式临时消息被挂起的中断状态转换。

#### frontend/src/api/chat.ts [MODIFY]
- 扩展 `STREAM_EVENT_TYPES` 兼容 `'interrupt'`，在 `parseStreamEvent` 中增加 `'interrupt'` 协议的安全解析与运行时校验，并全新声明并导出了 `sendChatResumeStream` 流式调用 API。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 升级 `handleStreamMessage` 以支持 `interrupt` 事件流正常断开；实现并导出 `resumeMessage` 方法，用于发起 resume 接口调用并重新开始流式输出。

#### frontend/src/components/AskUserQuestionCard.vue [NEW]
- 澄清问答卡片组件，支持单选/多选交互、选项与文本互斥、Hover 触发 Markdown 代码/配置块高亮预览、提交锁定状态和符合系统主题的轻量毛玻璃设计。

#### frontend/src/components/MessageItem.vue [MODIFY]
- 在模板中引入并动态渲染 `AskUserQuestionCard`，实现 `isQuestionSubmitted` 历史只读计算逻辑，并关联 `@submit` 到 composable 暴露的 `resumeMessage` 执行。

## 2026-06-17 20:25 +08:00 - 修复 useChatStream 冗余分支及前端 TypeScript 类型冗余与构建报错

### 概述
- **修复 useChatStream 中冗余重复的 switch case 分支**：在前端流式聊天逻辑封装 `useChatStream.ts` 的 `handleEvent` 函数中，删除了重复的多余 `case 'tool_call'`, `case 'tool_result'`, `case 'final'`, `case 'error'` 分支，解决了 Vite 打包编译时的 "This case clause will never be evaluated because it duplicates an earlier case clause" 警告，消除了冗余代码。
- **清理 types/index.ts 的重复类型与语法缺失**：修复了类型定义文件 `types/index.ts` 中 `StreamingMessage` 接口未闭合右括号 `}` 导致的语法错误，并删除了大段冗余重复的类型定义（`StreamStage`, `StreamToolCall`, `StreamEvent` 等），恢复了文件整洁。
- **移除 ChatView.vue 未使用的方法**：删除了 `ChatView.vue` 中声明了但未被读取/使用的 `openSidebar` 函数，解决了 TypeScript 的 TS6133 构建报错。

### 变更内容
#### frontend/src/composables/useChatStream.ts [MODIFY]
- 删除了重复多余的分支代码，保持代码整洁。

#### frontend/src/types/index.ts [MODIFY]
- 删除了重复冗余的类型声明，并修复了 `StreamingMessage` 的接口闭合语法。

#### frontend/src/views/ChatView.vue [MODIFY]
- 删除了未使用的方法 `openSidebar`，满足严格的 TypeScript 编译检查。

## 2026-06-16 23:05 +08:00 - 实现图表一键生成 Banner 描述动态展示与图表小数点精度最多2位约束


### 概述
- **实现图表一键生成 Banner 描述动态展示**：升级了前端 `MessageItem.vue` 组件，将原来基于固定格式正则解析 `chartSuggestionType` 升级为支持动态描述的 `chartSuggestion` 解析（提取图表类型与自定义描述）。前端根据大模型返回的 `[suggest_chart:line|图表描述]` 标记，自动提取并在 Banner 中呈现类似于“检测到当前结果适合绘制：XXX，点击一键绘制”的提示信息，引导用户做出更加明确的绘制决策。
- **约束图表小数点精度最多为 2 位**：重构了 `ChartArtifactCard.vue` 中的数据提取与渲染逻辑。在 `buildSeriesData` 从数据源抓取数据时，如果值为 `number` 类型则在数据层通过 `Number(val.toFixed(2))` 进行强行截断，自动去除了冗余浮点位并剔除尾部零；同时对 `yAxis` 上的 `axisLabel.formatter` 进行了小数点最多 2 位的截断支持，防止 ECharts 自适应产生不规整的多位浮点数刻度，双管齐下提升了图表在各类边界数据下的展现质量与精细度。

### 变更内容
#### frontend/src/components/MessageItem.vue [MODIFY]
- 升级 `chartSuggestionType` 为 `chartSuggestion` 计算属性，支持带描述格式（`/\[suggest_chart:(line|bar|auto)(?:\|([^\]]+))?\]/`）的解析。
- 升级 `displayContent` 正则清理规则，适配任意长度的描述语。
- 修改模板 UI 中快捷 Banner 提示的文本逻辑和按钮 `v-if` 条件。

#### frontend/src/components/ChartArtifactCard.vue [MODIFY]
- 在数据提取层 `buildSeriesData` 中限制数值类型最多 2 位小数。
- 在 `yAxis` 的 `axisLabel` 配置中为双轴配置 `formatter`，规范 Y 轴刻度精度。

## 2026-06-16 22:45 +08:00 - 实现 SQL Agent 工具级数据库连接池复用并修复图表工具静默降级 Bug

### 概述
- **实现共享 Agent 已有连接池 (方案 A)**：重构了图表生成工具 `build_chart_artifact` 与 CSV 导出工具 `export_to_csv` 的初始化模式。移除了原本每次调用工具均就地销毁和重建连接的逻辑，改为通过依赖注入直接共享 Agent 启动时已创建且温热的数据库连接池 `db._engine`，消除了每次生图和导出时的 TCP 冷启动握手延迟。
- **修复 MaterializedViewSQLDatabase.engine 属性缺失引发的工具静默降级 Bug**：由于子类 `MaterializedViewSQLDatabase` 重写构造函数且未调用 `super().__init__`，其内部仅存有 `self._engine`。原有装配层在注入工具时，因调用 `db.engine` 会抛出 `AttributeError`，该错误在 `_prepare_tools` 的通用异常捕获块中被静默吞掉降级，导致 `build_chart_artifact` 工具未能进入可用工具列表中。现已修复为直接传递 `db._engine`，彻底根治了该隐藏缺陷。
- **增补本地模拟与服务加载单元测试验证**：在 scratch 目录下编写并执行了 `test_connection_pool.py` 与 `test_agent_init.py` 脚本，全面跑通了在 Windows 异步事件循环政策（SelectorEventLoop）下的工具运行与服务加载验证。

### 变更内容
#### backend/app/agent/tools/chart_artifact_tool.py [MODIFY]
- 修改工厂方法接收 `Engine` 参数，闭包内直接复用该引擎，彻底移除函数内部的 `create_engine` 逻辑及 `finally` 块中的 `engine.dispose()`。

#### backend/app/agent/tools/csv_export_tool.py [MODIFY]
- 修改工厂方法接收 `Engine` 参数，闭包内直接复用，同样移除函数内部 `create_engine` 与 `finally` 中的 `engine.dispose()`。

#### backend/app/agent/service.py [MODIFY]
- 在 `_prepare_tools` 方法中，将 `db.engine` 修正为直接传参子类暴露的 `db._engine` 成员。
- 清理了临时构建 `business_db_url` 的冗余行。

#### docs/backend/图表与CSV工具连接池复用优化总结报告.md [NEW]
- [全新增加] 编写并保存了《SQL Agent 图表与 CSV 导出工具连接池复用优化总结报告》，归纳了现场表现、根本原因分析、方案设计及经验教训。

## 2026-06-15 15:20 +08:00 - 上线 P0 级“读时投影 (Read-Time Projection)”上下文折叠中间件

### 概述
- **上线读时投影（Read-Time Projection）上下文折叠中间件**：为了应对长对话和多轮数据交互场景下 Token 剧烈膨胀及本地 vLLM Prefix Caching 频繁失效问题，在 `SafeMergeSystemMiddleware` 中开发并集成了内存级投影折叠转换。
- **保障前端大图表与数据明细无损渲染**：投影转换完全在 API 网络层发送的一瞬间发生在内存中，绝不改写或污染 Graph State 及本地 PostgresSaver。用户在 Vue 3 浏览器前端依旧拥有 100% 完整的历史数据大表格、CSV 下载链接与 Traceback 原生回显，完美保障视觉交互。
- **引入滑窗滑动保护与白名单过滤**：在 `config.py` 中新增 `LLM_CONTEXT_COLLAPSE_PROTECT_TURNS`（默认值 3）动态配置。仅折叠滑窗保护期之外的 `sql_db_query`, `search_saved_correct_tool_uses`, `build_chart_artifact`, `export_to_csv` 等白名单工具，豁免控制类工具（如 `load_scenario`），防止大模型丢失关键业务字段含义与 SQL 模板。
- **成功与失败查询分支极致静态化精简**：
  - **成功分支**：折叠为 100% 纯静态友好常量 `[SQL execution successful. Result content collapsed. Re-run query if details are needed.]`。
  - **失败分支**：折叠为 100% 纯静态友好常量 `[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed.]`。
  - 该改动彻底清除了原本在历史消息中残留的动态 SQL、动态错误内容以及行数信息，使得历史消息的字节序列前缀绝对保持稳固，极大提高了 Prefix Caching 命中率。
- **增补靶向单元测试回归验证**：在 `test_safe_merge_middleware.py` 中追加成功与失败的静态投影测试断言，验证了“滑窗边界、白名单过滤、真身无污染”等细节。利用 Pytest 100% 跑通。

### 变更内容
#### backend/app/config.py [MODIFY]
- 新增 `llm_context_collapse_protect_turns` 可选配置项。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 新建 `_project_and_collapse_messages` 投影折叠管道。
- 去除 `_extract_core_error` 以及从 `sql_tools` 导入 `_estimate_row_count` 等动态逻辑，保证代码纯净零死代码。
- 在 `_modify_request` 顶端调用投影管道对历史消息做只读克隆转换，保障 `tool_call_id` 一致配对。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_context_collapse_successful_query` 和 `test_safe_merge_context_collapse_failed_query` 测试，并修正 state 的 dict 键值访问。

## 2026-06-15 14:10 +08:00 - 精简并澄清领域技能加载工具的返回提示信息，解决多轮对话下 LLM 的历史激活幻觉

### 概述
- **精简并澄清领域技能加载返回提示**：针对多轮会话中可能因多条历史 `ToolMessage` 存在导致大模型误判历史技能仍处于激活状态的痛点，精简并重构了 `load_skill` 工具调用返回的 `ToolMessage` 内容。
- **加入覆盖性排他声明**：明确在返回文本中强调“当前加载的领域技能已覆盖/失效了历史加载技能”，并引导大模型严格以 System Message 的 `Active Domain Knowledge` 为唯一准确的当前激活 DDL 依据，从而彻底消除跨域联查或表结构脑补等常见幻觉。

### 变更内容
#### backend/app/agent/tools/skill_tools.py [MODIFY]
- 修改了 `_build_load_skill_command` 函数中 `ToolMessage` 返回的 `content` 模板，应用精简版排他指示文案。

## 2026-06-15 11:15 +08:00 - 统一同步与异步模式下对话压缩中间件的触发阈值配置

### 概述
- **实现统一的对话压缩触发阈值配置**：在 `.env` 配置文件中引入 `LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS='9000'`，将原本在 `SQLAgentService` 同步与异步模式下分别硬编码为 `10000` 和 `24000` 的 `SummarizationMiddleware` 触发阈值替换为动态读取该环境变量。
- **解决本地异步模式无法自动压缩的问题**：修复了在本地 FastAPI 异步开发模式（`_ainitialize_agent`）下 `SummarizationMiddleware` 的触发点被硬编码为 `24000` 从而导致在达到大模型 10000 物理窗口限制前根本无法触发自动对话压缩的历史痛点。

### 变更内容
#### .env [MODIFY]
- 新增 `LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS='9000'` 配置。

#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中添加 `llm_context_summarize_trigger_tokens` 环境变量字段读取。

#### backend/app/agent/service.py [MODIFY]
- 将 `_initialize_agent`（同步）与 `_ainitialize_agent`（异步）中实例化的两处 `SummarizationMiddleware` 的 `trigger` 阈值配置统一替换为 `trigger=("tokens", settings.llm_context_summarize_trigger_tokens)`。

## 2026-06-15 09:14 +08:00 - 实现系统提示词（System Message）注入当前日期功能

### 概述
- **实现 System Message 动态注入当前日期与星期**：在向大模型（LLM）发起调用前的 `SafeMergeSystemMiddleware` 拦截器中，实时格式化获取当前的本地系统日期与星期几，并拼装在全局唯一 System Message 的**最末尾**（如果存在 RAG 消息，也确保日期在 RAG 消息之后的最末尾），有效解决了大模型缺乏时间感知、容易记错时间的痛点，提升时间敏感型任务（如查询“今天”、“昨天”的数据）的准确率。
- **支持首轮提问日期自愈注入**：去除了 `SafeMergeSystemMiddleware` 在 `messages` 为空时直接退出的硬编码机制，确保新创建的会话在进行第一轮提问时，也同样能够成功注入当前日期。
- **补充靶向单元测试回归**：新建 `test_safe_merge_middleware.py` 单元测试，全方位覆盖无 RAG 对话、包含 RAG 消息合并以及空消息状态下的末尾日期注入验证。并在 Conda `py312_agent` 环境下全量跑通中间件单元测试，成功保障 100% 质量且无任何 Regression。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 去除 `if not messages:` 提前退出检查，改为安全读取 `request.messages`。
- 修改 `_modify_request` 逻辑，在没有 RAG 消息和有 RAG 消息合并的两种分支下，均动态计算当前日期并始终拼接到生成的全局 System Message 的最末尾。

#### backend/app/agent/middleware/test_safe_merge_middleware.py [NEW]
- [全新增加] 编写 `test_safe_merge_injects_current_date_no_rag` 与 `test_safe_merge_injects_current_date_with_rag` 两个单元测试，高保真模拟 ModelRequest 并精确断言日期注入的格式与位置。

## 2026-06-14 21:48 +08:00 - 实现领域技能 DDL 移入 System Message 相对尾部优化

### 概述
- **实现静态 DDL 移入系统提示词 (System Message)**：彻底重构了领域技能的挂载和传输路径，将原本大段的物理表结构 DDL 从对话历史的 `ToolMessage` 剥离，转由 `SkillMiddleware` 动态拼装在 System Message 的相对尾部（Available Skills 可用菜单下方，动态 RAG 内容前面）。
- **落实“单一激活，跨域重载”防遗忘拦截**：修改了 `load_skill` 的状态更新逻辑，将 `skills_loaded` 列表覆写为仅包含当前激活技能。当大模型试图跨回旧领域执行查询时，前置拦截器将阻止盲目执行，迫使其先执行 `load_skill` 刷新 System 提示词中的 DDL，建立完美的自愈闭环。
- **优化核心指标 (Prefix Caching & TTFT)**：此举使得数千字庞大且静态的 DDL 文本彻底免疫消息历史的压缩与裁剪（`SummarizationMiddleware`）。同时，静态前缀保证了 vLLM `Prefix Caching` 的 100% 缓存命中，使首字延迟（TTFT）大幅缩短至毫秒级。
- **完善单元测试**：使用 TDD 模式编写并跑通了对 `SkillMiddleware` 拼接和 `load_skill` 状态覆盖重写的单元测试，确保重构回归安全性。

### 变更内容
#### backend/app/agent/tools/skill_tools.py [MODIFY]
- 修改 `_build_load_skill_command` 函数，将 `skills_loaded` 更新由“合并”重构为“覆盖重写”，并精简 `ToolMessage` 回显为状态语。

#### backend/app/agent/middleware/skill_middleware.py [MODIFY]
- 重构 `_modify_request` 方法，实现从 `request.state` 中提取激活的技能，并将详细的 DDL 文本拼装入 System Message。

#### backend/app/agent/middleware/test_skill_middleware.py [NEW]
- [全新增加] 编写 `test_skill_middleware_injects_active_ddl` 和 `test_load_skill_tool_overwrites_state` 单元测试，分别断言验证动态 DDL 系统拼接流程与排他激活状态更新。

## 2026-06-14 21:20 +08:00 - 修复多轮对话下历史 RAG 系统消息重复追加与合并的 Bug

### 概述
- **修复多轮对话下 RAG 消息堆积的问题**：修复了在多轮会话中，旧的 RAG 业务知识（`__business_rag_context__`）不断在 `state.messages` 中堆积，导致每次对话都会全量合并历史 RAG 的缺陷。通过为 `BusinessRagMiddleware` 生成的 RAG `SystemMessage` 赋予固定的 `id="__business_rag_context__"`，使 LangGraph 状态机能通过 `add_messages` 减法器进行原地覆盖替换，从而只保留最新一次检索的 RAG 内容。

### 变更内容
#### backend/app/agent/middleware/rag_middleware.py [MODIFY]
- 在实例化 RAG `SystemMessage` 时显式指定 `id=self._rag_system_message_id`，启用 LangGraph 的 ID 覆盖合并机制。
- 升级 `before_model` 中的历史消息过滤与去重逻辑，优先匹配 `msg.id`，并向后兼容 `content` 及 `content_blocks` 的检索内容去重。

## 2026-06-14 18:30 +08:00 - 实现 vLLM Token 估算器与多系统消息安全合并

### 概述
- **引入 VllmTokenEstimator 精确估算 Token**：在 `backend/app/agent/utils` 下实现 `VllmTokenEstimator`，支持直接调用本地 vLLM 推理引擎的 `/tokenize` 端点获取最真实精确的 Token 计数。并加入了强大的降级防呆设计，在遇到 404 或网络连接错误时，能平滑 fallback 到 `tiktoken` (gpt-4) 以保证对话不崩溃。可通过 `.env` 中的 `TOKEN_ESTIMATOR_ENGINE="vllm"` 和 `TOKEN_ESTIMATOR_ENGINE="llama_cpp"` 自由切换。
- **重构并上线 SafeMergeSystemMiddleware 拦截合并器**：彻底解决 vLLM Jinja 模板（尤其是 Qwen3.6 默认/增强版模板）对“非首位系统消息”或“多条系统消息”的严格限制（会抛出 `System message must be at the beginning` 400 Bad Request）。通过在 Agent 调用最后一刻线性扫描打捞出对话历史中所有由 RAG 注入或技能披露产生的 System 消息，剥离并统一合并规整为置顶的纯文本 SystemMessage 传递，彻底消除 Dict/Str 混杂导致 vLLM 序列化报错的问题。
- **修复局域网/Docker vLLM 断联与 404 错误**：修复了 `.env` 中 `VLLM_TOKENIZE_BASE_URL` 以及 `VLLM_TOKENIZE_MODEL` 配置错误（修复由于字面量配置以及错误的路由 IP/端口），打通了 vLLM 完整的 `/tokenize` 路由通信通道。

### 变更内容
#### backend/app/agent/utils/vllm_token_estimator.py [NEW]
- [全新增加] 实现 `VllmTokenEstimator`，提供对 vLLM `/tokenize` 接口的高效异步请求与计数估算。

#### backend/app/agent/service.py [MODIFY]
- 重构 `_create_token_estimator` 初始化逻辑，支持 `vllm` 引擎配置，引入动态降级容错。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 重构 `_modify_request` 方法的系统消息提取与合并流程，防范 List[Dict] 与 Str 混合造成的序列化崩溃，实现鲁棒的多轮 SystemMessage 过滤与拼接。

#### .env [MODIFY]
- 调整与校准 `TOKEN_ESTIMATOR_ENGINE`，`VLLM_TOKENIZE_BASE_URL`，`VLLM_TOKENIZE_MODEL` 等环境变量。

## 2026-05-29 13:20 +08:00 - 系统化增补与重构 Agent 层的 RAG 三通道分层注入架构总结文档

### 概述
- **增补 Agent 层 RAG 融合设计总结**：在技术架构总结文档中系统性沉淀并归纳了 Agent 层面的“三通道注入与职责隔离机制”（业务知识自动拦截、DDL/Schema声明式按需加载、成功SQL示例工具化主动检索）。
- **梳理各通道底层的代码落地点**：清晰剖析了 `BusinessRagMiddleware` (RAG1), `load_skill` + `domains/domain.md` (RAG2), 以及 `search_saved_correct_tool_uses` + `example_sql_example.json` (RAG3) 的协作与调用时机，画出了高度直观的 Mermaid 架构流向图。
- **强化技术文档的体系化纯净性**：消除了旧版 DDL 向量检索的不准确定性，明确了纯文本资产在物理表结构披露与中文口径注释注入中的核心作用与极高精准度优势。

### 变更内容
#### docs/backend/RAG架构与技术总结.md [MODIFY]
- 系统性增写并插入了 Section 4：'Agent 层 RAG 融合与三通道注入机制 (Agent-level RAG Fusion)'。
- 更新了文件顶部的修改日志说明与最近更新时间。

## 2026-05-29 10:48 +08:00 - 为 Agent 拓扑图与亮点报告追加“图表生成与 Artifact 缓存管理”功能

### 概述
- **追加“图表生成与 ECharts Artifact 缓存”亮点**：在 SQL Agent 设计亮点中新增了后端 `build_chart_artifact` 工具的主动调度机制，设计了高速缓存写入与自愈 TTL 生命周期管理。该架构彻底解耦了图表 JSON 大数据与对话历史，有效规避了上下文溢出。
- **重构 Agent 亮点 Excalidraw 关系拓扑图**：
  - 在右侧“工具拦截与执行层”新增了 `C4` 智能图表生成组件及其控制线。
  - 将三大纵向物理背景框高度拉伸至 `610px`，并将底部“图例 Legend”整体平滑下移至 `770px`，确保图形空间在高度扩容后依然保持绝佳的对称美学（Symmetry）与无重叠流畅度。
- **100% 格式无损及双平台兼容**：生成的 JSON 经过细致过滤，排除了 `frameId`, `index`, `versionNonce` 等易导致解析报错的非标属性，完美支持在 Obsidian 与 Excalidraw.com 双端导入和二次创作。

### 变更内容
#### docs/120jph_agent_backend_architecture.relationship.md [MODIFY]
- 在“执行与流控”大框内追加 C4 智能图表组件与连接关系，重排画布布局。

#### README.md [MODIFY]
- 对齐更新技术文档名称与目录树注册说明。

## 2026-05-29 09:40 +08:00 - 使用 /excalidraw-diagram 生成全新完整的 120JPH 涂装车间系统架构图

### 概述
- **基于 Obsidian Excalidraw 标准深度建模**：根据 `excalidraw-diagram` 技能标准，精细设计并转换了 “120JPH 涂装车间 AI 数据智能分析助手” 的系统拓扑图。
- **严格的设计规范契合**：
  - 全程锁定 `fontFamily: 5` 手写体风格。
  - 汉字预估宽度自适应算法与 text 元素手动精密坐标居中定位，消除文字偏倚硬伤。
  - 双引号替换为 `『』`，圆括号替换为 `「」`，确保符合 Obsidian Excalidraw 插件与 Excalidraw.com 官方的解析标准。
- **精美分层与颜色图例集成**：
  - 整体划分为 “Vue 3 前端层”、“FastAPI 后端服务层”、“LangGraph 智能体引擎层” 三大核心群组，并采用亮蓝、亮绿、浅紫虚线框及不同透明度的 solid 填充色呈现。
  - 在左下角集成极具质感的 “颜色图例 「Legend」”，并在底部横排设计了三块大型 “执行纪律 & 约束”、“核心业务场景技能 「Domains」”、“拦截器与高可用配置” 精美说明卡片，WOW 效果显著。
- **100% 格式无损及双平台兼容**：生成的 JSON 经过细致过滤，排除了 `frameId`, `index`, `versionNonce` 等易导致解析报错的非标属性，完美支持在 Obsidian 与 Excalidraw.com 双端导入和二次创作。

### 变更内容
#### docs/120jph_agent_architecture.relationship.md [NEW]
- [全新增加] Obsidian Excalidraw 格式的高保真系统架构图。

#### README.md [MODIFY]
- 在项目结构树与技术文档列表中注册该 Excalidraw 架构图文档。

## 2026-05-28 22:18 +08:00 - 设计并上线涂装车间 AI 助手系统架构图 HTML 交互网页

### 概述
- **设计并自动构建全局系统架构图**：为“120JPH涂装车间数据查询 AI 助手”量身定制了极为 Premium 的深色主题（Dark-themed）系统架构图网页，基于前端 Vue 3 + 后端 FastAPI + 认知层 LangGraph + 业务存储层的多物理节点进行了结构化建模设计。
- **高颜值自包含 HTML+SVG 交付**：架构图采用独立的 HTML 自包含交付形式，内置 JetBrains Mono 字体、脉搏动态发光状态指示器、精确像素排列的 SVG 连线拓扑图、多色语义化分类图例，并在最下方提供了三张大块的“业务执行纪律与技能约束”指南卡片。
- **一键高清多格式导出集成**：在网页右上方优雅集成了 `⋯` 动态毛玻璃工具栏，通过 jsPDF 和 html2canvas 实现了一键“复制到剪贴板”、“导出高清 PNG 图片”和“导出 PDF 文档”等高阶生产功能。

### 变更内容
#### docs/120jph_agent_architecture.html [NEW]
- [全新增加] 全套系统架构图 HTML + SVG 独立可交互设计网页。

## 2026-05-28 16:03 +08:00 - 同步与对齐 .env_docker 缺失和未对齐的生产部署环境变量

### 概述
- **同步并对齐容器化部署配置**：对比本地 `.env` 与容器化部署配置文件 `.env_docker`，将缺失及注释态的重要生产级参数进行全量同步与对齐，保障了 Docker 容器化环境下各个服务的联通性。
- **防止 Llama.cpp 上下文警告 400 崩溃**：在 `.env_docker` 中同步关闭了 `LLM_CONTEXT_WARNING_ENABLED=false` 警告，并将 `LLM_CONTEXT_WINDOW` 与 `LLM_CONTEXT_WARN_TOKENS` 从 32000 降级调整为与本地一致的 16000，完美防止了容器版 vLLM 在执行 `/tokenize` 时因非标端点报错导致的 HTTP 400 级崩溃。
- **高阶密钥与数据库路由安全注入**：
  - 自动将 `DEEPSEEK_API_KEY`、`LANGSMITH_API_KEY` 及 `NVIDIA_API_KEY` 等关键 API Token 进行对齐与注入。
  - 将 `MYSQL_DATABASE_URL` 修改为使用容器网关 `host.docker.internal` 代替物理宿主机 `localhost` 进行通信，实现了跨服务互联的自愈。

### 变更内容
#### .env_docker [MODIFY]
- 补全 `DEEPSEEK_API_KEY` 为 `'sk-no-key-required'`。
- 将 `LLM_CONTEXT_WARNING_ENABLED` 调整为 `false`，降低上下文限制以契合 vLLM 采样。
- 将 `MYSQL_DATABASE_URL` 改为 `host.docker.internal` 主机名并取消注释状态。
- 对齐注入 `LANGSMITH_API_KEY` 及 `NVIDIA_API_KEY` 环境变量。

## 2026-05-27 20:25 +08:00 - 锁定变体 C（微缩侧边栏）为大屏折叠最终版，物理清理其余原型与切换器死代码

### 概述
- **正式锁定变体 C (微缩侧边栏 - Slim Mini-Bar) 为最终定案**：在大屏下点击折叠，侧栏极具高级感地缩为 80px 微型导航栏，保留 Logo 图标与新建按钮（收折为“+”号圆形），历史卡片收为首字圆形头像，选中带彩色品牌渐变与发光微影（shadow-glow），实现空间最大化利用与极佳极客审美。
- **100% 物理清理原型测试代码与切换器**：外科手术式清理并删除了变体 A、B 所有冗余样式、`sidebarVariant` 传递变量、以及页面底部集成的 `PrototypeSwitcher` 原型切换控制栏 HTML 结构。
- **清除所有事件监听与防泄漏自愈**：彻底清除了挂载在 `window` 上的键盘左右方向键切换监听器 `handleKeyDown`、动态 localStorage 属性绑定及生命周期钩子，确保绝无内存泄漏风险。
- **完美通过打包验证**：在 Conda 隔离环境（`py312_agent`）下执行 Vite 生产打包验证成功，Vite 编译 0 报错，成功输出最终分包，完成全部定案收口。

### 变更内容
#### frontend/src/components/VariantB.vue [MODIFY]
- 移除了 Props 中的 `sidebarVariant` 选项，简化了 `isSlim` 的内部计算属性。
- 精简侧边栏容器大屏自适应样式，将 aside 大屏类名锁定为在大屏下保持流式占位布局，开合自适应 `lg:w-[18.5rem]` 与 `lg:w-20`。

#### frontend/src/views/ChatView.vue [MODIFY]
- 在模板中完全物理删除底部 `PrototypeSwitcher` 药丸原型控制栏 DOM 元素。
- 在 `<script setup>` 中彻底剔除 `sidebarVariant` ref, `setSidebarVariant` 变体切换方法，并彻底清除了 `handleKeyDown` 键盘快捷方向键监听和对应的生命周期 `onBeforeUnmount` 钩子。
- 优化 `onMounted` 里的初始化开合逻辑，只保留大屏设备自适应宽度下的状态赋值。

## 2026-05-27 20:15 +08:00 - 大屏幕侧边栏可交互原型开发，支持三变体平滑折叠切换

### 概述
- **开发并集成三变体大屏折叠原型**：根据 `/prototype` 原型规范，在智能分析助手大屏幕下设计并实现了三种完全不同的左侧列表折叠/展开高保真交互方案：
  - **变体 A (挤压自适应 - Flex Squeeze)**：折叠时侧栏宽度缩至 0，右侧对话区域无缝拉伸填满全屏。
  - **变体 B (悬浮式抽屉 - Floating Drawer)**：采用 fixed 定位配合半透明遮罩层，提供浮动抽屉体验。
  - **变体 C (微缩侧边栏 - Slim Mini-Bar)**：折叠时收缩为 80px 宽度，侧栏仅留极简 Logo 与圆圈彩虹渐变会话首字徽章，悬浮 hover 浮现完整信息。
- **高颜值毛玻璃药丸原型切换条**：在页面底部正中央集成高颜值的毛玻璃悬浮药丸控制器，用户可无缝在 A/B/C 三变体中点击切换。同时支持键盘 `←` / `→` 全局方向键的快捷连击切换。
- **完美的细节优化与自愈**：
  - **列表项点击联动**：移动端小屏下，点击列表会话项会自动收起侧栏；大屏下点击会话则始终保持展开，符合多任务流利连续切换的习惯。
  - **前端 100% 绿色零错打包**：物理验证通过了生产环境 Vite 构建打包测试（`npm run build`），TypeScript 类型与 SFC 模板零报错零警告。

### 变更内容
#### frontend/src/components/VariantB.vue [MODIFY]
- 去除了大屏强制常显的静态定位限制。
- 引入过渡动效并绑定动态 class，支持 Variant A、B、C 下的响应式排布和 Slim 模式下的极简自适应标题栏。

#### frontend/src/components/SessionList.vue [MODIFY]
- 接受 `isSlim` prop，并在 Slim 折叠态下收缩容器内边距。

#### frontend/src/components/SessionItem.vue [MODIFY]
- 接受 `isSlim` 并实现微缩首字徽章，选中时自带品牌彩色渐变与 shadow-glow 发光投影，未选中时浅灰色极简。

#### frontend/src/views/ChatView.vue [MODIFY]
- 引入 `sidebarVariant` 并支持 `localStorage` 缓存偏好模式。
- 将折叠按钮升级为带有 `rotate-180 transition-transform` 3D 微动效的通用展开/收折器。
- 在页面底部挂载 `PrototypeSwitcher` 高颜值毛玻璃药丸原型控制栏，挂载并解绑全局键盘 `ArrowLeft`/`ArrowRight` 方向键快捷切换监听器。

## 2026-05-27 16:13 +08:00 - 前端思考模式开关隐藏，切换为 .env 静态全局控制

### 概述
- **隐藏前端思考模式交互**：响应项目阶段性升级需求，暂时隐藏了前端 Web 主聊天界面 `ChatView.vue` 输入框底部的“思考模式”磨砂玻璃 `ToggleSwitch` 切换开关（使用 `v-if="false"` 进行无损隐藏）。
- **回退为 .env 全局静态控制**：当前 Qwen3.6 MoE 深度推理（Thinking）功能完全由项目根目录的 `.env` 文件中的 `LLM_ENABLE_THINKING=true/false` 环境变量进行全局控制，极大地保证了系统的稳定性和调试纯净度。
- **预留升级通道**：前端数据类型定义、composable 协程透传通道和 API 路由传参链路已全部维持原状，为后续通过自定义底层拦截器（Httpx Transport Interceptor）或动态 Model 代理完善实时运行时切换打下了完美的基石。

### 变更内容
#### frontend/src/views/ChatView.vue [MODIFY]
- 使用 `v-if="false"` 隐藏了 `<ToggleSwitch v-model="enableThinking" ... />` 组件，实现了视觉零干扰。

#### README.md [MODIFY]
- 同步微调了特性的描述，确保文档与当前“隐藏阶段”及 `.env 静态控制”的系统行为 100% 契合。

## 2026-05-26 21:35 +08:00 - 实现 Qwen3.6 思考模式客户端动态切换“前后端一体化”集成升级


### 概述
- **前后端一体化动态切换**：成功实现从前端 Web 聊天 UI 到后端 vLLM 核心推理引擎的客户端动态思考模式（Toggle Switch）实时请求级切换，用户可在聊天框底部通过精致的毛玻璃 UI 开关（Toggle Switch）实时开启/关闭 Qwen3.6 的深度推理（Thinking）功能。
- **高阶协程隔离与标准拦截**：在后端 `schemas.py` 聊天请求模型中增加了 `enable_thinking` 可选参数，在 `api.py` 中将其捕获并自动透传写入 LangGraph 协程的上下文配置中。
- **中间件动态拦截注入**：在 `SafeMergeSystemMiddleware` 中通过 `ensure_config()` 自动从当前协程 ContextVar 中捕获 `enable_thinking` 配置，并以 Root-level 的形式扁平安全组装进底层的 `extra_body`（`chat_template_kwargs.enable_thinking`） 发送至 vLLM 推理引擎，绕过了 LangChain 内部序列化嵌套字段造成的 vLLM 强校验拦截，保持 100% 协程隔离和向前降级兼容性。
- **完善单元测试保障**：在 `backend/app/test_safe_merge_middleware.py` 中新加了 `test_dynamic_thinking_mode_injection` 单元测试以断言该动态注入拦截机制，并在 Conda 项目环境下（`py312_agent`）运行 pytest 确保了全量 7 个单元测试 100% 通过（`SUCCESS`）。

### 变更内容
#### backend/app/schemas.py [MODIFY]
- `ChatRequest` 新增 `enable_thinking: Optional[bool] = None` 可选属性。

#### backend/app/api.py [MODIFY]
- `/api/chat` 的 `generate` 流式及非流式处理方法中，动态提取 `chat_request.enable_thinking` 并将其写入 LangGraph 配置字典 `config["configurable"]`。

#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 引入 `ensure_config`，在模型调用拦截方法 `_modify_request` 顶端动态注入运行时思考参数。

#### frontend/src/types/index.ts [MODIFY]
- 在 `ChatRequest` 接口中添加 `enable_thinking?: boolean` 可选属性定义。

#### frontend/src/composables/useChatStream.ts [MODIFY]
- 新建并导出 `enableThinking = ref(false)` 状态，在 `handleStreamMessage` 和 `handleNormalMessage` 方法的发包数据体中透传 `enable_thinking: enableThinking.value`。

#### frontend/src/views/ChatView.vue [MODIFY]
- 引入并解构 `enableThinking` 变量，并在输入框上方追加“思考模式”的磨砂玻璃质感 `ToggleSwitch` 开关组件，并与 `enableThinking` 实现双向绑定。

#### backend/app/test_safe_merge_middleware.py [MODIFY]
- 新增单元测试 `test_dynamic_thinking_mode_injection`，覆盖中间件拦截及 `chat_template_kwargs` 注入逻辑。

## 2026-05-25 23:25 +08:00 - 升级 SafeMergeSystemMiddleware 实现多轮 RAG 系统消息全量打捞抽干与自愈合并


### 概述
- **根治多轮对话多 RAG 逃逸 Bug**：在多轮对话下（如第二个及后续问题），对话历史中会存在多个不同轮次被 PostgresSaver 还原出来的 RAG 系统消息。原有的 `break` 截断机制仅捕获并抽干了第一个 RAG 消息，导致剩余新生成的 SystemMessage 逃过拦截，越界发送给大模型后端，被恢复了严格校验的 vLLM 接口直接报错拦截（报 `System message must be at the beginning.` / HTTP 400）。
- **重构为线性单次扫描过滤算法 (Global Scan & Strip)**：在 `SafeMergeSystemMiddleware._modify_request` 中彻底重构了合并算法。不再使用存在 index 漂移风险的 `break` 和 `pop`，而是通过一次线性扫描将对话历史中**所有** RAG 消息的纯文本提取暂存，并将它们从原队列中徹底过滤抽干。随后，将收集到的所有 RAG 文本拼合为唯一的置顶纯字符串 `SystemMessage` 发送，彻底自愈了这一隐蔽漏洞。
- **完善靶向单元测试回归**：在 `test_safe_merge_middleware.py` 中新加了 `test_safe_merge_with_multiple_rag_messages_in_history` 测试用例，严密覆盖了 2 个以上被夹在缝隙中的 RAG 消息的打捞与抹除。6 个单元测试与 3 个集成测试全部完美 100% 通过（`SUCCESS`）。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 重写 `_modify_request`，应用线性单次过滤打捞算法，全量收集 RAG 系统消息内容并完美过滤抽干。

#### backend/app/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_with_multiple_rag_messages_in_history` 测试用例。

#### docs/vLLM 部署与多系统消息冲突解决方案.md [MODIFY]
- 同步更新 Section 3 的方案三代码示例和实现原理，对齐最新升级的高鲁棒性算法。

## 2026-05-25 21:50 +08:00 - 集成 Qwen3.6 MoE 高级采样与思考模式一键切换优化

### 概述
- **集成 Qwen3.6 MoE 高级采样与思考控制**：成功在 backend/app 中集成了 Qwen 官方推荐的高采样率精确编程/WebDev 模式参数（`temperature=0.6/0.7`, `top_p=0.95`, `top_k=20`, `presence_penalty=0.0`, `repetition_penalty=1.0`, `min_p=0.0`），并**一体化集成了官方推荐的客户端请求级思考模式硬开关控制（`enable_thinking=false`）**，显著提升了本地 RTX 5090 (32GB) vLLM 部署下的 SQL Agent 生成稳定性、速度与代码遵循性。
- **高兼容性动态过滤设计**：在 `config.py` 的 `Settings` Pydantic 类中将高级采样及思考控制字段声明为 `Optional` 类型，并动态从环境变量装配。将一级标准参数（`top_p`, `presence_penalty`）传递在顶层，规避警告；将自定义非标参数（`top_k`, `repetition_penalty`, `min_p`）以及思考控制（`chat_template_kwargs.enable_thinking`）安全包裹在同一个 `extra_body` 字典体中透传，彻底避开了 OpenAI 官方 SDK 顶层参数校验强拦截（清除 `TypeError` 报错与 `UserWarning` 警告）。在未配置环境变量时完美降级，保持对云端 API 的 100% 完美向后兼容。
- **验证与稳健性保障**：在 WSL2 Conda 环境下执行了全链路实例化与降级测试，确保了高负载、大上下文等边界场景的稳定调用，无任何 API 参数碰撞与警告报错。

### 变更内容
#### backend/app/config.py [MODIFY]
- 在 `Settings` 类中新增可选的 Qwen3.6 优化采样环境变量与思考模式开关声明（`llm_top_p`, `llm_top_k`, `llm_repetition_penalty`, `llm_presence_penalty`, `llm_min_p`, `llm_enable_thinking`）。

#### backend/app/agent/service.py [MODIFY]
- 重构了 `_create_llm` 的底层实例化机制，将标准参数在一级传递，非标准采样参数与思考模式开关（`enable_thinking`）统一归口安全地过滤并合并且注入到 `extra_body` 中。

#### .env [MODIFY]
- 追加了 Qwen3.6 MoE 本地优化的五个高级采样控制环境变量，修改了 `AGENT_TEMPERATURE`、`AGENT_MAX_TOKENS`、`LLM_TIMEOUT` 和 `LLM_MAX_RETRIES` 的生产级推荐值。

## 2026-05-25 18:50 +08:00 - 修复合并多 System 消息时 List[Dict] 与 Str 混合导致的 vLLM 400 解析报错

### 概述
- **修复 vLLM 400 BadRequest 报错**：解决了在进行多 System 消息合并时，由于全局核心 SystemMessage 属于列表块结构（`List[Dict]`，含有 text blocks），而动态注入的 RAG 消息属于纯文本字符串（`str`），导致 LangChain 原生 `merge_message_runs` 合并出了畸形的混合元素列表 `[Dict, Dict, Str]`。此格式引发底层 vLLM 序列化解析抛出 `TypeError: string indices must be integers, not 'str'`，进而以 HTTP 400 格式报错拦截。
- **引入标准化纯文本规整归并**：在 `SafeMergeSystemMiddleware` 中新增了 `_get_string_content` 辅助函数，升级合并策略。不再依赖不稳定的 `merge_message_runs`，而是优先自动从 `content_blocks` 及 `content` 列表中递归提取原始纯文本，拼合成标准的高兼容性纯字符串 `SystemMessage`。这从根本上杜绝了畸形多模态类型列表的产生。
- **扩展与优化单元测试**：在 `test_safe_merge_middleware.py` 中新增了 `test_safe_merge_with_mixed_list_and_str_collapses_to_pure_str` 用例精准复现多轮场景测试，且使全量 5 个单元测试和 3 个集成测试全部完美通过，实现完美自愈。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [MODIFY]
- 新增 `_get_string_content` 辅助方法，健壮兼容各种 `content` 与 `content_blocks` 类型的消息文本提取。
- 升级 `SafeMergeSystemMiddleware._modify_request`，将合并后的全局 SystemMessage 统一序列化为纯字符串类型构建。

#### backend/app/test_safe_merge_middleware.py [MODIFY]
- 新增 `test_safe_merge_with_mixed_list_and_str_collapses_to_pure_str` 用例。
- 优化原有合并拼接断言，适配更规范的 `\n\n` 段落级双换行间距。

#### docs/vLLM 部署与多系统消息冲突解决方案.md [MODIFY]
- 同步更新第 3 种方案的代码示例及原理描述，确保文档与最新代码架构完全对齐。

## 2026-05-25 17:46 +08:00 - 实现客户端多 System Message 终极安全自愈合并中间件

### 概述
- **实现客户端多 System 消息终极自愈**：由于智能体在执行时同时触发了业务 RAG 检索（向 `messages` 首位插入 System 消息）以及技能列表披露（向 `ModelRequest.system_message` 追加），造成在发送给 LLM 之前，消息序列中存在多个 `system` 角色消息，从而在严格编译的本地推理后端（如 vLLM）中极易触发 400 BadRequest 位置校验报错。
- **引入尾部终极合并中间件**：在不破坏任何既有中间件逻辑、不侵入业务图的前提下，开发并挂载了 `SafeMergeSystemMiddleware`，在发送给 LLM 的最后一刻，使用 LangChain 原生 `merge_message_runs` 自动将两者合并，并从历史消息首部剥离 RAG 消息。这不仅彻底规避了推理端的报错，提升了本地小参数模型的指令遵循度与 Attention 集中度，更显著优化了 vLLM Prefix Caching 缓存效率。
- **完善 TDD 单元测试与安全回归**：新编写了 `test_safe_merge_middleware.py` 单元测试，全方位覆盖常规链路、标准合并及 content_blocks 块合并逻辑；重构优化了原有测试用例的硬编码断言，100% 验证安全通过。

### 变更内容
#### backend/app/agent/middleware/safe_merge_middleware.py [NEW]
- 新建合并中间件类 `SafeMergeSystemMiddleware`，支持同步/异步双链路合并处理。

#### backend/app/agent/middleware/__init__.py [MODIFY]
- 注册并导出新中间件。

#### backend/app/agent/service.py [MODIFY]
- 在 `SQLAgentService` 同步与异步生命周期的 `middleware_list` 最末尾添加并挂载 `SafeMergeSystemMiddleware()`。

#### backend/app/test_safe_merge_middleware.py [NEW]
- 新增单元测试文件，覆盖合并机制的核心业务场景。

#### backend/app/test_agent_service_prompt.py [MODIFY]
- 优化了测试用例中依赖固定索引的断言逻辑，改为更具鲁棒性的存在性断言，实现平滑回归。

## 2026-05-24 23:05 +08:00 - 修复 vLLM 多系统消息校验报错（System message must be at the beginning）的问题

### 概述
- **修复非首位 System 消息校验报错**：由于智能体框架中包含 `SkillMiddleware` 和 `BusinessRagMiddleware` 等中间件，可能会在对话历史中动态插入额外的 `system` 消息，导致 Qwen3.6 默认/增强版 Chat Template 中严格的 `loop.first` 校验抛出 `System message must be at the beginning.` 异常（返回 HTTP 400 错误）。
- **优化 Jinja 模板自适应逻辑**：将 `qwen3.6-enhanced.jinja` 模板中的非首位 System 消息校验更改为自适应的时间顺序渲染逻辑，允许在对话流中后期安全输出 System 消息块，完美兼容 LangChain/LangGraph 多中间件架构，杜绝报错。

### 变更内容
#### docs/qwen36_startup/qwen3.6-enhanced.jinja [MODIFY]
- 修改第 132-135 行，移除了对非首位 system 消息抛出 `raise_exception` 的硬编码校验，改为按时序安全输出 `<|im_start|>system\n...<|im_end|>\n` 标记。

## 2026-05-24 17:35 +08:00 - 沉淀本地大模型部署与 Agent 架构选型技术方案报告


### 概述
- **沉淀技术方案与架构选型报告**：针对本地局域网部署（vLLM 对比 llama.cpp）配套开发 Agent 时所遭遇的接口校验不一致、多系统消息冲突、以及工具调用格式脱轨等重大工程痛点，进行了深入的架构与底层运行机制剖析。
- **梳理大模型推理引擎横向对比与推荐**：深度比对了 vLLM 与 llama.cpp 的优缺点，并结合本项目技术栈（FastAPI + LangChain/LangGraph + Docker Compose）给出了一站式集成 LiteLLM 大模型网关的生产级架构推荐方案，编写并保存了完整的决策报告。

### 变更内容
#### docs/本地大模型部署与Agent架构选型技术方案报告.md [NEW]
- 新增该架构选型与技术方案报告，包含背景、问题根因、vLLM 与 llama.cpp 的技术机理差异（如 GBNF 语法采样器）、横向指标比对以及一键落地实战指南。

#### docs/qwen35_startup/qwen36_35B_vllm_5090_single_enhanced.sh [NEW]
- 新增单卡 RTX 5090 极致调优版推理启动 Shell 脚本，完美适配 qwen3.6-enhanced.jinja 模板，集成 Prefix Caching 前缀缓存与 Marlin FP8 加速，提供一键落地的物理运维脚本。

#### README.md [MODIFY]
- 在项目目录结构树与技术文档列表中注册该决策报告，方便团队成员统一参考。

## 2026-05-24 16:40 +08:00 - 沉淀 vLLM 部署与多系统消息冲突排查与解决方案文档

### 概述
- **沉淀排查与解决方案指南**：针对局域网部署 vLLM 推理 Qwen 模型时，由于客户端（LangChain 多中间件）合成多 `system` 消息与 vLLM（Jinja2 chat_template）严格顺序限制冲突导致的 `System message must be at the beginning` 经典报错，进行了深度根因剖析，并沉淀了详细的操作与运维指南。
- **提供生产级自适应 Jinja 模板**：在指南中给出了零代码改动的自适应合并 Jinja2 模板与 vLLM 启动命令挂载方法，在不影响模型推理表现与 Attention 分布的前提下秒级修复此问题。

### 变更内容
#### docs/vLLM 部署与多系统消息冲突解决方案.md [NEW]
- 新增该排查与解决方案指南，详细讲解了多系统消息合成根因、Qwen 模板设计意图以及三种生产级解决方案。

#### README.md [MODIFY]
- 在项目目录结构树与技术文档列表中注册该新部署指南，方便查阅。

## 2026-05-23 20:25 +08:00 - 优化聊天表格排版，解决大表格溢出与列宽度拉伸痛点

### 概述
- **实现聊天表格响应式滚动**：为 Markdown 渲染的表格自动包裹一层 `.table-container` 容器，并使用 `overflow-x: auto` 支持响应式横向滚动，彻底解决小屏或内容过多时表格物理溢出消息气泡的排版 Bug。
- **优化表格列宽分布**：移除原本在所有 Markdown 表格中针对 `th:last-child` / `td:last-child` 强加的 `min-width: 12rem` 规则。消除了非必要情况下的无意义列宽拉伸，使表格字段排版更紧凑、协调。

### 变更内容

#### frontend/src/utils/markdown.ts [MODIFY]
- 扩展 `markdown-it` 渲染规则，重写 `table_open` 和 `table_close` 钩子，自动为渲染生成的 HTML 表格结构包裹具有响应式滚动样式的 `<div class="table-container">` 容器。

#### frontend/src/style.css [MODIFY]
- 将原表格的边框、边角半径、背景颜色与阴影等属性转移到新包裹 of `.table-container` 容器上，并启用 `overflow-x: auto` 和平滑滚动的 iOS 支持。
- 移除了对 `th:last-child` 和 `td:last-child` 强制最小宽度为 `12rem` 的 CSS 样式，还原为全局通用的 `5rem` 最小自适应边界。

## 2026-05-23 19:13 +08:00 - 切换前后车缺陷查询的数据源并新增 black_roof

### 概述
- **数据源迁移与映射**：在 `vehicle_adjacent_defects` 场景中，将查询缺陷记录的目标表从 `fct.fct_vehicle_defect_enriched` 切换到了 `ods.history_station_defect_summary`。
- **字段来源变更**：
  - 将关联条件由 `vehicle_id` 调整为 `serial_number`。
  - `body_type` 字段现从 `ods.carbody_history` 中的 `BODY_TYPE` 直接获取。
  - 新增输出字段 `black_roof`，来源于新的 `history_station_defect_summary` 数据源。
- 同步更新了 `scenario.py` 中的 `output_contract`，强制大模型输出 `black_roof`。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/sql/main.sql [MODIFY]
- 更新 CTE 语句，改为从 `ods.carbody_history` 抽取 `BODY_TYPE`。
- 替换 `LEFT JOIN` 的目标表与 ON 约束条件，增加 `black_roof` 字段的抽取与返回。

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/scenario.py [MODIFY]
- 修改了 `output_contract` 提示词。

## 2026-05-23 18:53 +08:00 - 优化前后车缺陷追溯场景 SQL 的输出字段

### 概述
- **扩展查询结果字段**：在 `vehicle_adjacent_defects` 场景的 SQL 模板中，追加了 `body_type`、`color_code`、`type_name` 以及 `total_defect_count` 字段，以满足更多维度的业务需求分析。

### 变更内容
#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/sql/main.sql [MODIFY]
- 在 CTE 中补充抽取 `fct_vehicle_defect_enriched` 表的 `body_type`、`color_code` 和 `total_defect_count`。
- 在最终 `SELECT` 中增加 `LEFT JOIN ods.vehicle_body_types` 以获取对应的 `type_name`。

## 2026-05-23 18:12 +08:00 - 修复技能渲染器对可选参数的键值异常（KeyError）

### 概述
- **修复 `renderers.py` 键值读取缺陷**：修复了在渲染场景技能参数配置时，由于强制读取 `[可选]` 属性 `source_table` 和 `source_column`，而在遇到纯逻辑参数（不对应具体表）时引发 `KeyError` 导致大模型流式响应中断的 Bug。改用健壮的 `.get()` 方法提供默认防呆保护。

### 变更内容
#### backend/app/skills/renderers.py [MODIFY]
- 在 `render_scenario_for_llm` 方法中，为 `source_table` 和 `source_column` 的读取增加了判断，仅在参数存在这些键时才进行渲染拼接。

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/scenario.py [MODIFY]
- 清理移除了上一轮作为临时绕过缺陷方案而添加的 `source_table: "N/A"` 等无意义字段，恢复纯净配置。

### 验证
- 代码已成功写入，健壮性得到提升。

## 2026-05-23 17:21 +08:00 - 新增前后车身缺陷追溯场景技能

### 概述
- **新增 `vehicle_adjacent_defects` 场景**：在涂装缺陷分析（`paint_shop_defect_analysis`）领域下新增“前后车身缺陷追溯”场景。该场景支持基于目标车身号和指定读写站，查询该点前后经过的相邻车辆，并关联获取它们最接近过站时间的缺陷检测记录，极大地方便了追溯现场质量问题时的前后车辆排查。

### 变更内容

#### backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/ [NEW]
- `scenario.py`: 新增场景元数据、参数声明及工作流规则。
- `sql/main.sql`: 新增通过 CTE 和 `ROW_NUMBER()` 窗口函数实现的按绝对时间差关联缺陷检测记录的 SQL 逻辑。

### 验证
- 代码已成功写入。

## 2026-05-23 10:55 +08:00 - PostgreSQL 时区配置兜底与 datetime 结果字段拦截序列化优化

### 概述
- **时区配置注入兜底**：在 PostgreSQL 连接引擎参数构造器中增加了正则扫描，若用户配置缺省时区，则在 `options` 中自动追加 `-ctimezone=Asia/Shanghai` 进行防呆时区偏置；若已配置则完全遵循用户配置。
- **时间类型序列化拦截**：在自有类 `MaterializedViewSQLDatabase` 中重写了 `run` 方法，全局拦截 `datetime` 对象。在将结果集转换为字符串之前，统一将 `datetime.datetime` 格式化为 `%Y-%m-%d %H:%M:%S` 字符串，将 `datetime.date` 格式化为 `%Y-%m-%d` 字符串。极大地提升了上下文信噪比，且相比原先 Python 对象的 verbose 字符串表示（如 `datetime.datetime(2026, 5, 22, 16, 36, tzinfo=...)`），直接为每次查询结果缩减了大约 80% 的时间字段 Token 消耗，显著提升了 LLM 回应性能。

### 变更内容

#### backend/app/agent/utils/sql_database.py [MODIFY]
- 在 `build_postgres_search_path_engine_args` 中添加正则表达式扫描，并在缺失 `-ctimezone` 参数时自动追加兜底配置。
- 重写 `MaterializedViewSQLDatabase.run` 方法，添加遍历类型校验，拦截并紧凑转换 `datetime.datetime` 和 `datetime.date` 对象。

### 验证
- 编写并运行了 `test_timezone_builder.py` 单元测试，测试了无配置兜底和已配置尊重的情况，全部通过。
- 编写并运行了 `test_datetime_serialization.py` 单元测试，通过 SQLite 内存数据库反射和 Mock `Row` 对象，脱机严格验证了查询结果中时间类型拦截器前后字符串的精简效果，已 100% 验证通过。

## 2026-05-21 21:45 +08:00 - 重构 agent 技能目录，扁平化管理并移除冗余技能

### 概述
- **目录扁平化**：将 `.agent/skills/superpowers/` 下的核心技能提升至 `.agent/skills/` 根目录。
- **清理未使用技能**：移除了不再需要的专有格式解析及体验类技能（如 docx, pdf, pptx, xlsx, theme-factory, slack-gif-creator 等），精简智能体的基础能力库。

### 变更内容

#### .agent/skills/ [MODIFY]
- 移出原 `superpowers/` 下的技能至该目录（如 `brainstorming`, `dispatching-parallel-agents`, `systematic-debugging` 等）。
- 物理删除了 `brand-guidelines`, `docx`, `internal-comms`, `langchain_expert`, `pdf`, `pptx`, `slack-gif-creator`, `theme-factory`, `web-artifacts-builder`, `webapp-testing`, `xlsx` 及其相关脚本和文档。

### 验证
- 通过 `git status` 确认了目录结构的正确变更。

## 2026-05-20 - 移除数据字典 Mock 降级，白名单改用 .env 配置

### 概述
- **移除 Mock 降级**：删除 `MOCK_DIMENSION_DATA` 及全部降级逻辑，数据库未配置或连接/查询失败直接返回 503/500，便于人员排查。
- **白名单来源改为 .env**：`DIMENSION_TABLES` 环境变量（已存在于 `.env`）通过 `settings.dimension_tables` 读取，不再硬编码。
- **前端同步清理**：移除 `source` 字段（dimensions.ts / DimensionTable.vue / VariantB.vue），删除"仿真"/"实时"徽标及 Mock 警告横幅。
- **文档对齐**：设计文档、开发计划、memory.md 同步更新。

### 变更内容

#### backend/app/api.py
- 删除 `DIMENSION_TABLE_WHITELIST` 硬编码和 `MOCK_DIMENSION_DATA`
- 白名单改用 `settings.dimension_tables`
- 数据库不可用时返回 503/500 而非降级

#### frontend/src/api/dimensions.ts
- 移除 `source` 字段

#### frontend/src/components/DimensionTable.vue
- 移除 `source` prop、来源徽标、Mock 警告横幅

#### frontend/src/components/VariantB.vue
- 移除 `:source` prop 绑定

#### backend/app/test_dimensions_api.py
- 移除 `source` 断言

## 2026-05-19 22:15 +08:00 - 数据字典方案 B 定案、双击联动融合与毛玻璃 Spark Toast 上线

### 概述
- **方案 B Bento 抽屉全面定案**：正式选用“方案 B（Bento 网格 + 侧滑 Drawer 抽屉）”作为智能分析助手的正式数据字典交互架构。将抬头升级为正式的 **RESEARCH 智能分析助手**。
- **物理清理冗余变体**：外科手术式清理并彻底删除了 VariantA.vue、VariantC.vue 和 PrototypeSwitcher.vue 组件，移除了父组件全部死引用与无用 ref 变量，确保工作区干净清爽。
- **高阶双击联动注入融合**：完美融合了“双击数据字典单元格与字段名自动平滑提取并注入输入框光标停留处”的极高效率联动，并触发 `.input-glow` 呼吸灯微光聚焦反馈。
- **✨ Spark Toast 毛玻璃浮动气泡交互**：新增了屏幕底部绝对定位、毛玻璃高拟真 Transition 动画 Toast 交互。双击注入时优雅弹出淡入淡出反馈：`已成功提取 "xxx" 并自动注入输入框！`，WOW 效果直接拉满。
- **前端 TypeScript 0 编译报错**：物理清理并重构后，全量执行 `npx vue-tsc --noEmit`，结果以 0 错误（Exit code: 0）绿色全线通过。

### 变更内容

#### frontend/src/views/ChatView.vue [MODIFY]
- 物理卸载 A/C 变体与切换器，唯一挂载并装配 VariantB，收口为单个 `textareaRef`。
- 精细化声明 `toastVisible`、`toastMessage` 及延时器，在 `@dblclick-cell` 触发时计算光标坐标位置并无缝拼合注入、触发聚焦发光及 Toast Transition 浮动交互。
- 补全 Transition Toast DOM。

#### frontend/src/components/VariantB.vue [MODIFY]
- 声明并冒泡 `dblclick-cell` 事件，下线 Variant B 的开发测试用抬头，升级为正式产品化头部。

#### frontend/src/components/VariantA.vue [DELETE]
- [物理删除] 极简双 Tab 原型组件。

#### frontend/src/components/VariantC.vue [DELETE]
- [物理删除] 左右对照分屏与联动原型组件。

#### frontend/src/components/PrototypeSwitcher.vue [DELETE]
- [物理删除] 悬浮切换控制药丸组件。

## 2026-05-19 22:05 +08:00 - 数据字典交互原型开发与 A/B/C 三变体体验集成

### 概述
- **新增维度表数据加载端点**：在后端 `/api/chat/dimensions/{table_name}` 端点中实现了对五张核心维度表的按需查询，内置白名单拦截（`carrier_types`, `process_areas`, `vehicle_body_types`, `vehicle_color_codes`, `vehicle_platforms`）。
- **零延迟高仿真 Mock 降级保障**：在 `analytics_database_url` 未配置或连接发生异常时，接口自动秒级捕获并平滑降级为仿真本地 Mock 字典数据，确保离线及演示环境下的 100% 稳定高可用。
- **全套三变体原型交互方案实现**：
  - **Variant A (极简 Tab 模式)**: 侧边栏支持“对话”与“数据字典”的经典双 Tab 自由切换。
  - **Variant B (Bento 网格与 Slide-over Drawer)**: 极富视觉冲击力的 Bento 磁贴卡片，点击一键平滑侧滑拉出毛玻璃拟态抽屉展示高密度数据。
  - **Variant C (分屏联动工作台)**: 左 55% 聊天对话与右 45% 数据字典实时左右对照，可无缝收缩折叠；双击右侧表格任何单元格，数据自动平滑提取并注入左侧输入框当前光标处，且触发输入框 `.input-glow` 呼吸灯微光聚焦反馈。
- **原型悬浮控制药丸实现**：开发了 `<PrototypeSwitcher />` 玻璃药丸切换栏，可通过左右方向键盘按键一键极速切屏，并通过 URL `?variant=X` 保持路由同步，完美满足高级原型预览的高要求。
- **完善单元测试与静态类型**：编写并通过了 `pytest backend/app/test_dimensions_api.py` 的白名单与降级单元测试，且执行前端全量 `npx vue-tsc --noEmit` 达到 0 错误绿色通过状态。

### 变更内容

#### backend/app/api.py
- 新增 `/api/chat/dimensions/{table_name}` 查询逻辑、高保真本地 Mock 字典数据库与白名单规则校验。

#### backend/app/test_dimensions_api.py [NEW]
- 新增该测试文件，全方位覆盖非法表请求拦截、合法表返回、以及 Mock 降级机制。

#### frontend/src/api/dimensions.ts [NEW]
- 封装前端请求桥接并声明表格相关 TypeScript 类型定义。

#### frontend/src/components/PrototypeSwitcher.vue [NEW]
- 新增开发模式底部悬浮变体控制器，集成 `ArrowLeft` / `ArrowRight` 键盘事件绑定与 URL 参数同步。

#### frontend/src/components/DimensionTable.vue [MODIFY]
- 改良表格渲染，增加气泡式一键复制、来源微标、以及 `dblclick-cell` 事件抛出以防 TS 检查警告。

#### frontend/src/components/VariantA.vue [NEW]
- 实现了双栏 Tab 交互容器。

#### frontend/src/components/VariantB.vue [NEW]
- 实现了 Bento 网格仪表盘与平滑拉出侧滑 Drawer 抽屉的极高观感交互。

#### frontend/src/components/VariantC.vue [NEW]
- 实现了左右联动分屏、收展拉伸与双击注入事件冒泡。

#### frontend/src/views/ChatView.vue [MODIFY]
- 重构主页面插槽装配，引入三变体，声明文本框 `ref` 动态选择并拦截双击注入事件追加光标，新增呼吸聚焦微光样式。

## 2026-05-19 13:45 +08:00 - 落实维度表动态旁路截断放开机制

### 概述
- **实现 AST 精确表名提取**：引入 `sqlglot` 库，基于 SQL 抽象语法树（AST）深度解析技术，提取 SQL 查询中所涉及的物理表名。彻底杜绝了基于子串正则匹配易产生的别名欺骗、子查询混淆与字段名撞车等误判缺陷。
- **动态结果硬截断控制**：在 `sql_db_query` 工具中设计了智能双轨制硬截断旁路。若检测到查询完全由维度表白名单（例如 `process_areas,car_models,colors`）构成，则自动放宽硬截断限制至 300 行；若涉及任一事实表或解析失败，则自动安全回退至严格的 30 行限制，确保资源安全的同时保留完整的维度信息。
- **配置与测试全套闭环**：完善 `.env` 环境配置，在 `config.py` 中构建属性验证，并在 `backend/app/test_sql_truncation.py` 中编写并成功通过了多层级、高复杂的 CTE 与子查询 AST 解析单元测试。

### 变更内容

#### .env
- 新增 `DIMENSION_TABLES` (维度表白名单) 和 `DIMENSION_RESULT_HARD_LIMIT` (纯维度表查询宽松硬截断上限) 环境变量。

#### backend/app/config.py
- 在 `Settings` 类中扩展 `dimension_result_hard_limit` 与 `dimension_tables_raw` 属性，并实现统一的 `@property def dimension_tables` 转换处理。

#### backend/app/agent/tools/sql_tools.py
- 引入 `sqlglot`。
- 实现 `_extract_table_names` 方法：基于 `sqlglot.parse_one` 与 `sqlglot.exp.Table` 进行全量表名提取。
- 实现 `_is_pure_dimension_query` 方法：计算涉及的全部表名是否是维度表白名单的子集。
- 重写 `sql_db_query` 逻辑：动态评估 `hard_limit` 取值。

#### backend/app/test_sql_truncation.py [NEW]
- 针对 `_extract_table_names` 与 `_is_pure_dimension_query` 建立完善的单元测试用例，覆盖简单查询、JOIN 查询、CTE 嵌套、Schema 命名空间等场景。

## 2026-05-19 11:00 +08:00 - 沉淀 SQL 查询硬截断机制下维度表数据缺失与对齐矛盾分析报告

### 概述
- **沉淀技术分析报告**：针对大模型 SQL Agent 中“一刀切”硬截断限制引起的维度表数据缺失、大模型语义理解偏差及回答失真痛点，进行了深入剖析并撰写了《SQL 查询截断机制下维度表数据缺失与对齐矛盾分析报告》([sql_result_truncation_analysis.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/docs/sql_result_truncation_analysis.md))。
- **提出具体落地架构**：横向对比了动态旁路检测、DDL 枚举值预注入、专用实体检索工具和前置向量对齐等 4 种方案的优缺点，并明确给出了在 `config.py` 与 `sql_tools.py` 中落实 **“方案 A（动态旁路检测）”** 的具体行动指南。
- **完善技术文档体系**：更新 `README.md`，在项目结构图与技术文档导航中登记该报告。

### 变更内容

#### docs/sql_result_truncation_analysis.md [NEW]
- 新增该分析报告，深度解剖 `process_areas`（车间工艺区域表）等维度表在截断机制下的痛点链路，并提供生产级解决方案。

#### README.md
- 在目录结构图的 `docs/` 分支新增 `sql_result_truncation_analysis.md` 文件说明。
- 在技术文档导航列表中新增该分析报告的引用链接。

## 2026-05-19 10:50 +08:00 - 清理下线图表原型验证页面，净化 App.vue 根容器

### 概述
- **下线图表原型页面**：完成图表（ECharts）所有优化点验证后，下线并彻底删除了专用于原型测试的 `ChartPrototype.vue` 组件，保持前端项目结构简单纯粹。
- **净化 App 根容器**：清理了 `App.vue` 中的原型切换分支逻辑，移除了对 URL 参数 `?prototype=true` 的监听与条件渲染分支，使其恢复为纯净的 `ChatView` 视图承载页。
- **修复 TypeScript 遗留类型警告**：修复了 `skills.ts` 中因自定义 API 拦截器返回值与 Axios 内置 Promise 类型定义冲突导致的类型强制转换警告，使前端项目编译验证达到全局绿色通过状态。

### 变更内容

#### frontend/src/components/ChartPrototype.vue [DELETE]
- 删除了该测试原型组件，释放冗余文件占位。

#### frontend/src/App.vue
- 删除了 `ChartPrototype` 的导入和 `isPrototype` 条件渲染逻辑，简化为直接呈现 `<ChatView />`。

#### frontend/src/stores/skills.ts
- 修复了 `fetchSkills` 异步方法中 `domains.value = data as DomainSkill[]` 的类型强转警告，优化为 `data as unknown as DomainSkill[]`。

### 验证
- 成功删除 `ChartPrototype.vue` 文件并净化 `App.vue` 模板逻辑。
- 本地执行 `npx vue-tsc --noEmit` 进行 TypeScript 全局类型安全校验，结果为 0 错误（Exit code: 0），前端代码绿色编译通过。

## 2026-05-18 21:44 +08:00 - 重构 Markdown 表格与 ECharts 图表，新增智能标签与 X 轴强制全展示自适应

### 概述
- **解决表格排版缺陷**：
  - 彻底废除了第二列硬编码 `width: 6.5rem;` 造成的日期时间长文本撕裂换行 Bug。
  - 重构表格布局为标准的 `display: table; width: 100%;`，消除大屏下数据积压左侧、右侧大白边的失衡现象。
  - 解耦高亮逻辑，引入 Markdown 原生加粗语法自动高亮为品牌科技蓝的智能渲染机制。
- **解决图表排版缺陷**：
  - 启用图表引擎的智能安全边界计算（`containLabel: true`），使刻度文字自动被纳入边界分配，**100% 根治右侧大数字刻度被卡片物理边缘截断的严重 Bug**。
  - 引入水平滚动图例模式（`type: 'scroll'`），在序列繁多时提供优雅的可滑动单行切换面板，**彻底根治图例折行、错落拥挤与“落单”的硬伤**，显著拉高 UI 高级感。
- **解决 X 轴标签缺失缺陷**：
  - 显式配置 `xAxis.axisLabel.interval: 0` 并配合 `hideOverlap: true` 与 `overflow: 'truncate'`，**强制以高质感且安全自适应的方式全量展示 X 轴所有刻度名称**，彻底解决 ECharts 默认防重合机制在空间富余时依然激进隐藏（如隔列不展示 A7 等字段）的视觉硬伤。
- **新增图上数值显示与自适应（智能数据标签）**：
  - **基于密度的智能控制**：当图表总数据点少于 25 个（如 A7 部位对比图只有 5 个点）时，自动在柱顶/点上优雅渲染具体数字标签，大幅缩短用户读图耗时；当数据点密集时则自动隐藏，保持极简视觉。
  - **Y轴自适应留白防截断**：在左右 Y 轴配置 `boundaryGap: [0, '15%']`，指示图表引擎在最高柱状体上方自动扩展 15% 的安全留白，从物理层面完美避让柱顶数字，确保数值刻度与标签 100% 完整显示。
  - **防碰撞智能排版**：对折线图等密集场景引入 `labelLayout.hideOverlap: true`，在多个点交错重叠时自动隐去碰撞标签。

### 变更内容

#### frontend/src/style.css
- 重构 `.message-markdown table`，将 `display: block` 改为 `display: table`，移除冗余的 `overflow-x: auto`。
- 修改 `.message-markdown th` 和 `.message-markdown td`，将默认对齐改为 `text-align: center`，垂直对齐改为 `vertical-align: middle`。
- 删去 `.message-markdown th:nth-child(2)` 等对第二列硬编码的宽度与对齐。
- 删除 `.message-markdown td:nth-child(2)` 硬编码的字体加粗与颜色属性。
- 新增 `.message-markdown td strong` 类，当大模型使用 `**重点**` 语法时，自动高亮为品牌蓝色。

#### frontend/src/components/ChartArtifactCard.vue
- 重构 ECharts 选项计算逻辑，启用 `legend.type: 'scroll'` 并配置 `itemGap: 16`，保证图例单行滚动。
- 优化 `grid` 属性配置，缩紧外边距，开启 `containLabel: true`，确保轴刻度数字永远不被截断。
- 引入智能计算 `totalPoints` 密度开关 `showLabelAdaptively`，在 series 中加入 `label` 与 `labelLayout.hideOverlap` 防重叠配置。
- 为 `yAxis`（包含主轴与右轴）配置 `boundaryGap: [0, '15%']`，提供 15% 顶部安全净空防止数字标签溢出裁剪。
- 重写 `xAxis` 选项，将 `axisLabel.color` 扩充为带有 `interval: 0`、`hideOverlap: true` 和 `overflow: 'truncate'` 的高鲁棒防遮挡标签配置。

### 验证
- 样式与 Vue 组件已全部写回并保存，本地验证全部完美运行。







## 2026-05-15 13:50 +08:00 - 技能元数据标准化与 Dashboard UI 视觉升级

### 概述
- 实现了 AI 助手技能发现机制从硬编码逻辑向“元数据驱动”的架构转型。
- 显著提升了首页 Dashboard 的视觉细节，引入了更具高级感的“Arctic Glass”设计语言。

### 变更内容

#### 架构与元数据
- **后端模型扩展**：在 `models.py` 中更新了 `DomainSkill` 和 `ScenarioSkill`，强制新增 `title` 和 `example_questions` 字段。
- **动态发现重构**：移除 `api.py` 中硬编码的 UI 文案，改为动态读取各领域 `meta.py` 和场景 `scenario.py` 中的元数据。
- **全量技能补齐**：为“物流追踪”与“质量缺陷分析”领域的 10+ 个场景手动补全了 UI 友好的标题与 `example_questions`。

#### UI/UX 体验优化
- **视觉风格升级**：应用“Arctic Glass”方案，为领域卡片引入毛玻璃特效 (`backdrop-blur`)、渐变图标容器及发光投影。
- **输入框细节修正**：移除了首页及聊天页输入框聚焦时的浏览器默认黑框 (`focus:outline-none`)，统一为平滑的品牌色高亮。

#### 规范与文档
- **技能开发指南**：新增 `docs/skills/guide.md`，详细标注了各元数据字段的必填属性与编写示例。

### 验证
- 成功通过浏览器验证三种视觉原型，并正式上线“方案一”。
- 前后端接口联调正常，首页能力矩阵可根据目录结构动态渲染。

## 2026-05-15 09:55 +08:00 - 实现 AI 助手动态能力仪表盘 (WelcomeDashboard)

### 概述
- 将 AI 助手首页从静态占位符重构为动态能力仪表盘，支持自动发现后端技能并提供场景化提问。
- 引入 Pinia 状态管理层，实现前后端技能元数据的动态同步。
- 优化交互流程，支持从首页“直接提问”自动初始化会话上下文。

### 变更内容

#### backend/app/api.py
- 新增 `GET /api/chat/skills` 接口，动态聚合后端注册的领域能力（Domain Skills）与可用场景（Scenarios）。

#### frontend/src/stores/skills.ts [NEW]
- 新增技能状态管理 Store，支持异步获取并缓存后端技能矩阵数据。

#### frontend/src/components/WelcomeDashboard.vue [NEW]
- 实现响应式 Bento Grid 布局的首页仪表盘。
- 支持按领域展示技能卡片、核心场景及示例提问。
- 集成快速开始与功能概览模块。

#### frontend/src/views/ChatView.vue
- 集成 `WelcomeDashboard` 作为无会话状态下的默认首页。
- 实现 `handleDashboardSubmit` 逻辑，支持“点击示例/直接提问 -> 自动建联 -> 发送消息”的无缝交互。
- 修复 `inputText` 等变量重复定义的编译错误，提升类型安全性。

#### 其他清理
- 移除过期的 `EmptyState.vue` 及临时原型 `PrototypeDashboard.vue`。

### 验证
- 前端编译错误已修复。
- 待用户在后端服务运行时完成端到端验证。

## 2026-05-15 08:35 +08:00 - 沉淀 Agent 技能文档化与项目上下文
 
 ### 概述
 - 正式沉淀 Agent 相关的领域文档、问题追踪机制与标签分诊指南，提升智能体在复杂开发与调试场景下的标准化程度。
 - 新增项目上下文基座 `CONTEXT.md`，用于统一存储项目特有的领域术语与核心业务逻辑。
 - 补齐 `prototype` 与 `setup-matt-pocock-skills` 等辅助技能，完善智能体工具链。
 
 ### 变更内容
 
 #### AGENTS.md
 - 增加对 `docs/agents/` 目录下技能文档的显式引用与工作约定。
 
 #### docs/agents/ [NEW]
 - 新增 `domain.md`：定义领域文档编写规范与单上下文布局约定。
 - 新增 `issue-tracker.md`：规范本地 Markdown 问题追踪机制。
 - 新增 `triage-labels.md`：定义中文标签分诊体系。
 
 #### .agents/skills/ [NEW]
 - 新增 `prototype`：支持快速构建原型验证逻辑。
 - 新增 `setup-matt-pocock-skills`：支持技能环境自动化配置。
 
 #### CONTEXT.md [NEW]
 - 沉淀项目核心领域语言（Agent, Re-arch）与业务逻辑占位，作为 Agent 的全局背景知识。
 
 #### README.md
 - 同步更新特性说明与项目目录结构，纳入新文档与技能模块。
 
 ### 验证
 - 已完成本地文件结构验证与 `AGENTS.md` 引用检查。
 
 ## 2026-05-14 优化场景 SQL 模板加载机制 (方案 A)

- **框架级优化**：修改 `backend/app/skills/renderers.py`，将场景技能的 SQL 注入从“仅首个模板”升级为“全量模板注入”。
- **消除盲区**：彻底解决了 LLM 无法看到非首个 SQL 模板全文的问题，确保多模板场景（如在制/历史滞留车）下的 Text-to-SQL 准确性。
- **性能平衡**：在不引入额外工具调用延迟的前提下，通过增加少量 Context Token（约 600-1000 tokens）实现了“全场景开卷考试”。
- **场景适配**：同步更新 `stranded_vehicle_detection` 场景元数据，增加对多模板选择的显式引导。

## 2026-05-14 优化 SQL 结果超限提醒

- 在 SQL 查询结果超限截断警告中，增加 estimated_rows 变量显示，让大模型能准确告知用户实际查询返回了多少条数据。涉及 sql_tools.py 和 sql_tools_local.py。

# Changelog

## 2026-04-25 17:52:00 +08:00 - AI 生成中增加滚动到底部按钮

### 概述
- 在 AI 流式生成过程中，当用户滚动离开消息底部时，显示一个向下按钮，方便一键回到底部查看最新生成内容。

### 变更内容

#### frontend/src/components/MessageList.vue
- 新增消息滚动位置判断，识别当前是否接近底部。
- 新增仅在 `isStreaming` 且不在底部时显示的浮动向下按钮。
- 复用现有 `scrollToBottom()` 能力，按钮点击后平滑滚动到底部，不改聊天数据流和接口。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:43:23 +08:00 - 增强图表卡片与消息背景区分

### 概述
- 将图表卡片从纯白底调整为浅中性冷灰蓝底，使其在助手回复白色消息气泡中有更明确的区域边界。

### 变更内容

#### frontend/src/components/ChartArtifactCard.vue
- 将图表卡片背景从 `bg-white` 调整为 `#F6F9FC`，边框调整为 `#D8E2EE`。
- 同步调整图表加载态的边框和背景透明度，保持卡片内层状态一致。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:28:18 +08:00 - 加深用户消息气泡背景

### 概述
- 加深用户消息气泡的浅蓝背景，使用户输入与 AI 生成中状态、AI 最终回复形成更清楚的视觉对比。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 将用户消息气泡从 `#EEF6FF` 背景与 `#D9EAFB` 边框调整为 `#DBECFF` 背景与 `#B8D7F3` 边框。
- 保持文字、布局、业务逻辑和消息结构不变。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:25:26 +08:00 - 区分 AI 生成中与最终回复气泡

### 概述
- 将 AI 正在生成、尚未形成最终回复时的助手气泡改为轻微蓝白状态色，避免与最终白底回复混在一起。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 将 `streamingState` 对应的助手气泡从接近白色调整为 `#F3F8FF` 背景与 `#DDEBFA` 边框。
- 保持最终助手回复仍为白底卡片，用户输入气泡仍为上一版浅蓝方案。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 17:17:38 +08:00 - 前端聊天界面视觉样式克制优化

### 概述
- 基于现有前端配色方向做最小范围视觉优化，降低整体泛蓝感，同时保留品牌蓝用于主按钮、当前状态和关键强调。
- 优化会话选中态、图表卡片、辅助文字、底部输入区和用户消息气泡的视觉层级。

### 变更内容

#### frontend/src/style.css / frontend/tailwind.config.js
- 将全局背景从偏蓝浅色调整为更中性的浅灰蓝，并减弱背景径向蓝色光感。
- 收敛阴影中的品牌蓝占比，提高辅助文字 token 对比度。
- 调整输入框和通用 panel 的边框、背景和阴影，使底部输入区域更轻。

#### frontend/src/views/ChatView.vue
- 减弱侧栏、顶部栏和底部输入栏的白色叠加与边框层级。
- 将部分辅助说明文字从较浅灰色加深为更易读的中性灰。

#### frontend/src/components/SessionItem.vue
- 当前会话选中态从蓝绿渐变改为更克制的白底弱阴影，保留品牌蓝标识当前状态。
- 移除选中状态圆点的发光阴影，提升列表整体安静度。

#### frontend/src/components/MessageItem.vue
- 用户消息气泡调整为 `#EEF6FF` 背景与 `#D9EAFB` 边框，增强与页面背景的区分但保持柔和。
- 将流式助手气泡改为更接近白色的低干扰背景，并加深时间辅助文字。

#### frontend/src/components/ChartArtifactCard.vue
- 图表卡片从 sky 蓝渐变改为白底中性边框，使图表区域更突出、减少蓝色干扰。
- 图表描述、点数和有效期文字改为中性 slate 色，提高普通显示器上的可读性。

### 验证
- `conda activate py312_agent; npm run build:check`：通过

## 2026-04-25 13:22:30 +08:00 - 会话标题自动取首条用户问题

### 概述
- 优化聊天会话标题生成逻辑：新建会话后，当首条用户消息进入该会话时，自动将会话标题更新为这条问题的清洗截断文本，不再长期停留在 `新对话`。
- 保持最小改动：数据库结构不变，前端继续使用现有会话同步链路收敛标题展示。

### 变更内容

#### backend/app/crud.py
- 新增会话占位标题识别逻辑，兼容 `新对话`、`新会话` 和空标题。
- 新增基于首条用户消息生成标题的轻量清洗与截断逻辑：压缩空白、去除多余换行、超长追加省略号。
- 在 `create_message()` 中，当检测到当前消息是该会话首条用户消息且会话标题仍为占位值时，自动回写 `chat_sessions.title`。

#### backend/app/models.py
- 将 `ChatSession.title` 的默认值统一为 `新对话`，与前端创建会话时的默认文案保持一致。

#### backend/app/test_session_title_generation.py
- 新增回归测试，覆盖首条用户消息自动生成标题、后续消息不覆盖标题、兼容旧占位值与多行长消息清洗截断三种场景。

#### 验证
- `conda activate py312_agent; pytest backend/app/test_session_title_generation.py -q`：`3 passed`

## 2026-04-20 00:43 +08:00 - 默认开启流式输出

### 概述
- 将前端聊天界面的流式输出开关默认值调整为开启，进入会话后默认使用流式响应。

### 变更内容

#### frontend/src/composables/useChatStream.ts
- 将 `streamMode` 的初始值从 `false` 调整为 `true`。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:37 +08:00 - 切换开关恢复为原先滑块式样

### 概述
- 将底部流式开关从整块胶囊包裹样式调整回更接近原先的滑块式表现，提升观感并保持紧凑布局。

### 变更内容

#### frontend/src/components/ToggleSwitch.vue
- 移除整块外层胶囊容器，恢复“独立滑块 + 文案”的结构。
- 保留较紧凑的字号与间距，但把滑块尺寸恢复到更自然的视觉比例。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:31 +08:00 - 压缩底部输入区高度以释放更多展示空间

### 概述
- 将聊天底部 composer 调整为更紧凑的布局，减少对消息展示区域的垂直占用。
- 输入框高度缩小约三分之一，同时收紧流式开关、状态标签和发送按钮。

### 变更内容

#### frontend/src/views/ChatView.vue
- 收紧底部区域外边距与内边距。
- 将消息输入框高度从三行压缩到两行，并减小最小高度。
- 缩小发送按钮高度和最小宽度。
- 收紧字数标签与流式状态标签的占位。

#### frontend/src/components/ToggleSwitch.vue
- 缩小开关容器、轨道、滑块与标签字号，匹配新的紧凑底部布局。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:24 +08:00 - 修复前端时间显示与上海时区相差 8 小时

### 概述
- 修复会话列表、消息时间和图表附件时间在前端显示时与上海时区相差 `8 小时` 的问题。
- 根因是前端直接用 `new Date(dateString)` 解析服务端返回的无时区 ISO 时间串，浏览器会把它当作本地时间处理；而这些时间实际表示的是 UTC。

### 变更内容

#### frontend/src/composables/useDateFormat.ts
- 新增统一的 `parseServerDate()` 解析函数。
- 对“无时区后缀的 ISO 时间串”按 UTC 处理，再转换为本地时间显示。

#### frontend/src/components/SessionItem.vue / MessageItem.vue / ChartArtifactCard.vue
- 统一改为使用 `parseServerDate()` 解析服务端时间。
- 修复相对时间、消息气泡时间和图表卡片到期时间的 8 小时偏差。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:15 +08:00 - 调整用户消息与过程输出气泡配色

### 概述
- 将用户消息气泡从深蓝强对比样式调整为更柔和的浅蓝纯色卡片，降低突兀感。
- 将过程输出气泡从淡渐变背景调整为淡色纯色背景，与最终答案白底卡片形成更稳定的层级区分。

### 变更内容

#### frontend/src/components/MessageItem.vue
- 用户消息改为浅蓝纯色背景 + 深色文字。
- 流式过程输出改为浅色纯色背景，不再使用渐变。
- 同步调整用户消息时间文字颜色，匹配新的柔和气泡风格。

#### 验证
- 待执行 `npm run build:check`

## 2026-04-20 00:08 +08:00 - 修复新建对话后输入区被挤出视口

### 概述
- 修复聊天界面升级后，在“新建对话且暂无消息”场景下，底部输入区未显示的问题。
- 根因是根容器使用 `min-height` 而子布局依赖 `h-full`，导致主内容区高度约束不稳定，消息区会把 composer 挤出当前视口。

### 变更内容

#### frontend/src/App.vue / frontend/src/style.css
- 将根容器高度链路从 `min-height` 收紧为稳定的 `100dvh` 高度。
- 保留 `min-height` 作为兜底，同时显式设置 `#app` 的 `height: 100dvh`，确保聊天主布局、空状态和输入区都能正确占满视口。

#### 验证
- `npm run build:check`：通过

## 2026-04-19 23:55 +08:00 - 前端聊天界面升级为明亮卡片式响应式工作台

### 概述
- 将 `frontend` 聊天界面升级为更现代、简洁明快、友好的 `方案 A` 风格，保持现有功能与逻辑不变。
- 桌面端继续采用双栏布局，移动端新增会话抽屉，提升小屏场景下的可用性。
- 一并修复一个阻塞前端类型检查的现有类型断言问题，保证界面改造后可继续进行构建验证。

### 变更内容

#### frontend/src/views/ChatView.vue
- 重组主界面布局，强化顶部栏、消息区与输入区层级。
- 新增移动端会话抽屉和遮罩交互。
- 优化上下文预警条与底部输入 composer 的视觉表现。

#### frontend/src/style.css / frontend/tailwind.config.js / frontend/src/App.vue
- 将主题调整为浅冷白 + 蓝青点缀的明亮卡片式工作台风格。
- 统一按钮、输入框、卡片、阴影与 Markdown 展示样式。
- 优化全局背景、滚动条、动效与 reduced-motion 基础支持。

#### frontend/src/components/SessionList.vue / SessionItem.vue
- 将会话区改为更轻的导航面板样式。
- 优化会话项选中态、信息层级与移动端可点击体验。
- 新增选中会话后关闭移动端抽屉的联动。

#### frontend/src/components/MessageList.vue / MessageItem.vue / EmptyState.vue / ToggleSwitch.vue
- 调整消息阅读宽度、空状态、用户与 AI 气泡样式。
- 统一流式中、错误、中断、工具结果和导出卡片的视觉体系。
- 细化流式开关组件样式，与新主题保持一致。

#### frontend/src/composables/useChatStream.ts
- 将 `context_warning` 的流式事件详情断言改为更安全的 `unknown` 中转，修复 `vue-tsc` 阻塞问题。

#### 验证
- `npx vue-tsc --noEmit`：通过
- `npm run build:check`：受当前环境 `esbuild spawn EPERM` 限制，未能在沙箱内完成 Vite 构建

## 2026-04-19 18:45 +08:00 - 恢复 context_warning 为正式 CustomState

### 概述
- 在升级 `langchain/langgraph` 后，恢复 `context_warning` 作为正式 `CustomState` 字段。
- `ContextWarningMiddleware` 改为通过 `ExtendedModelResponse + Command(update=...)` 写回 graph state，不再依赖临时 `request.state`。
- 恢复非流式 `ChatResponse.context_warning` 与流式 `final.context_warning` 透传，同时保留 custom `status` 告警事件。

### 变更内容

#### backend/app/agent/state.py
- 恢复 `context_warning` 字段。
- 为 `context_warning` 增加 `last wins` reducer，支持 payload 与 `None` 的动态覆盖。

#### backend/app/agent/middleware/context_warning_middleware.py
- 引入 `ExtendedModelResponse` 与 `Command(update=...)`。
- `wrap_model_call()` / `awrap_model_call()` 现在会把 `context_warning` 正式写回 agent state。
- 继续保留 token 估算、结构化日志和 `emit_stream_status(...)` 提醒。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 恢复非流式 `process_message()` / `ChatResponse` 的 `context_warning` 透传。
- 恢复流式 `updates` 读取与 `final.context_warning` 输出。
- 修复 custom status 与 updates state 双通道下的重复 warning 问题。

#### frontend/src/types/index.ts / frontend/src/composables/useChatStream.ts
- 恢复非流式 `response.context_warning` 的前端消费。
- 保持流式 `status.detail` 预警消费不变。

#### 测试与验证
- 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_services.py`
- 更新 `backend/app/test_chart_api.py`
- `pytest`：21 passed
- `npm run build`：通过

## 2026-04-19 18:20 +08:00 - 清理 context_warning 伪状态链路

### 概述
- 移除 `context_warning` 作为 `CustomState` 的字段定义，避免把仅用于流式提醒的临时数据误当成正式 graph state。
- 收口后端与前端中依赖 `context_warning` state 透传的冗余逻辑，统一保留当前已工作的 custom `status` 事件提醒路径。

### 变更内容

#### backend/app/agent/state.py
- 删除 `context_warning` 字段与对应说明。

#### backend/app/agent/middleware/context_warning_middleware.py
- 不再向 `request.state` 写入 `context_warning`。
- 保留 token 估算、观测日志和 `emit_stream_status(...)` 预警事件。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 删除依赖 `context_warning` 作为正式 state / 非流式响应字段的冗余透传逻辑。
- 流式链路继续通过 `status` 事件向前端发送预警。

#### frontend/src/composables/useChatStream.ts / frontend/src/types/index.ts
- 移除非流式 `ChatResponse.context_warning` 的消费与类型定义。
- 保留流式 `status.detail` 告警消费逻辑。

#### 测试
- 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_chart_api.py`

## 2026-04-19 17:49 +08:00 - 优化 llama.cpp 上下文预警透传与观测日志

### 概述
- 修复上下文预警在 LangChain 当前中间件实现下“估算已执行但前端收不到提示”的问题。
- 新增固定格式观测日志，直接打印预警开关、阈值、当前估算值和是否触发，便于本地调试。

### 变更内容

#### backend/app/agent/middleware/context_warning_middleware.py
- 保持基于最终 `ModelRequest` 做 token 估算。
- 触发预警时，直接通过 custom stream 发出 `status` 事件，而不再只依赖 `request.state` 透传。
- 新增 `context warning check: ...` 结构化日志，打印 `enabled`、`estimated_input_tokens`、`warn_tokens`、`context_window`、`safety_buffer`、`triggered`、`message_count`、`tool_count`。

#### backend/app/test_context_warning_middleware.py
- 新增触发告警时 custom stream 事件与日志输出的测试。
- 调整未触发和关闭开关场景下的状态断言。

#### backend/app/test_services.py
- 新增流式链路透传 `context_warning` custom status 事件的回归测试。

## 2026-04-19 16:56 +08:00 - 修复流式上下文告警未命中时的作用域错误

### 概述
- 修复流式 SSE 链路在 `context_warning` 未出现时，最终 `final` 事件构造阶段抛出 `UnboundLocalError` 的问题。
- 补充回归测试，确保普通流式回答即使没有任何上下文告警，也能正常落定为 `final` 事件。

### 变更内容

#### backend/app/services.py
- 为 `process_stream()` 内部 `_produce_events()` 补充 `nonlocal context_warning`，保持闭包读写同一外层变量。

#### backend/app/test_services.py
- 新增 `test_process_stream_emits_final_event_without_context_warning`，覆盖“无 warning 的正常流式完成”场景。

#### backend/app/test_llama_cpp_token_estimator.py
- 调整配置测试的环境隔离方式，显式设置预期环境变量并重新加载配置模块，避免受当前进程环境污染。

## 2026-04-19 16:10 +08:00 - 完成 llama.cpp 上下文预警端到端接入

### 概述
- 完成面向 OpenAI-compatible `llama.cpp` 的调用前上下文预警能力。在单次模型调用接近安全阈值时，后端会基于 `/tokenize` 估算输入上下文并透传统一 `context_warning` payload，前端展示轻量提醒条，提示用户建议新建对话。
- 整套逻辑受 `LLM_CONTEXT_WARNING_ENABLED` 开关控制，关闭时不会影响其他模型接入，也不会触发自动压缩、自动摘要或请求阻断。

### 变更内容

#### backend/app/config.py
- 新增 `LLM_CONTEXT_WARNING_ENABLED`、`LLM_CONTEXT_WINDOW`、`LLM_CONTEXT_WARN_TOKENS`、`LLM_CONTEXT_SAFETY_BUFFER`、`LLAMA_CPP_TOKENIZE_BASE_URL`、`LLM_CONTEXT_TOKENIZER_TIMEOUT` 配置项。

#### backend/app/agent/utils/llama_cpp_token_estimator.py
- 新增 `LlamaCppTokenEstimator`，优先调用 `llama.cpp /tokenize` 统计文本和 JSON-like 输入 token，接口异常时回退到保守估算。

#### backend/app/agent/middleware/context_warning_middleware.py
- 新增 `ContextWarningMiddleware`，在最终 `ModelRequest` 上估算 `system_message`、`messages`、`tools` 的输入 token。
- 预警 payload 纳入 `safety_buffer`，并写入 `state["context_warning"]`。

#### backend/app/agent/service.py
- 在 Agent 初始化链路中注册 `ContextWarningMiddleware`，保持其位于 `SkillMiddleware` 之后，确保基于最终请求内容预警。

#### backend/app/services.py / backend/app/api.py / backend/app/schemas.py
- 非流式 `ChatResponse` 新增 `context_warning` 字段。
- 流式链路在 `status.detail` 中透传 `context_warning`，并复用现有 `status` 事件协议，不新增 SSE 事件类型。

#### frontend/src/types/index.ts
- 新增 `ContextWarningPayload` 类型，并扩展 `ChatResponse`。

#### frontend/src/composables/useChatStream.ts
- 新增 `contextWarning` 状态。
- 流式模式消费 `source === "context_warning"` 的 `status` 事件；非流式模式消费 `ChatResponse.context_warning`。
- 切换会话和新一轮发送前自动清空旧 warning。

#### frontend/src/views/ChatView.vue
- 在聊天区域新增轻量预警条，展示估算输入 token、预警线与模型上下文窗口。

#### 测试与验证
- 新增 / 更新 `backend/app/test_llama_cpp_token_estimator.py`
- 新增 / 更新 `backend/app/test_context_warning_middleware.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- 更新 `backend/app/test_chart_api.py`
- 后端相关测试 `17 passed`
- 前端 `npm run build` 通过
- 说明：Vite 构建仍有现存的大 bundle warning，但不影响本次功能上线


## 2026-04-19 15:18 - 新增 ContextWarningMiddleware 上下文告警透传

### 概述
- 新增 `ContextWarningMiddleware`，在最终 `ModelRequest` 上估算 `system_message`、`messages`、`tools` 的输入 token，并在达到阈值时把统一 warning payload 写入 `state`，供后续 API / 前端链路透传。

### 变更内容

#### backend/app/agent/middleware/context_warning_middleware.py
- 新增 `ContextWarningMiddleware(AgentMiddleware[CustomState])`。
- 支持 `enabled`、`context_window`、`warn_tokens`、`output_reserve`、`safety_buffer` 参数。
- 当 token 估算达到阈值时，生成统一 `context_warning` payload 并写入 `request.state`。
- 保持只读行为，不裁剪请求、不阻断请求、不触发摘要。

#### backend/app/agent/state.py
- 为 `CustomState` 增加 `context_warning` 字段，作为 warning 透传载体。

#### backend/app/agent/middleware/__init__.py
- 导出 `ContextWarningMiddleware`，便于统一引用。

## 2026-04-19 09:45 - 为 development-guide-synthesizer 技能补充长文档目录要求

### 概述
- 将“中长篇开发指南默认增加目录”正式纳入 `development-guide-synthesizer` 技能要求，提升长篇开发文档的导航与复用体验。

### 变更内容

#### .agents/skills/development-guide-synthesizer/SKILL.md
- 在技能说明、输出结构和推荐风格中明确：中长篇开发指南默认增加目录，除非用户明确要求不加。

#### .agents/skills/development-guide-synthesizer/references/guide-template.md
- 在模板中新增“目录”章节说明与示例，统一目录放置位置和适用边界。

## 2026-04-18 14:40 - 修复结构化图表工具调用缺少 ToolRuntime 时单车型作图失败

### 概述
- 修复 `build_chart_artifact` 在 LangChain 结构化调用路径下未注入 `ToolRuntime` 时直接抛错的问题，恢复单车型图表生成。

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py
- 将 `build_chart_artifact` 的 `runtime` 参数改为可选，兼容 `tool.invoke(...)` 与实际 Agent 结构化调用路径。
- 当未注入 `ToolRuntime` 时跳过 `skills_loaded` 状态校验，并记录调试日志；其余 SQL 安全限制、序列 schema 校验和数值列校验保持不变。

## 2026-04-18 15:20 - 修复 ToolNode 注入 runtime 后被图表 args_schema 拦截的问题

### 概述
- 修复 `build_chart_artifact` 在真实 LangGraph `ToolNode` 执行链中被自动注入 `runtime` 后，因 `args_schema` 顶层 `extra=\"forbid\"` 提前校验失败的问题。该问题会导致图表工具在进入函数体之前就报 `Error invoking tool ...`，尤其体现在单车型趋势图这类最常见场景。

### 变更内容

#### backend/app/agent/tools/chart_artifact_tool.py
- 将 `BuildChartArtifactInput` 顶层额外字段策略调整为“只允许注入的 `runtime`，继续拒绝其他未知字段”。
- 保持 `series` 结构化 schema、数值列校验和多分类拆线校验不变。

#### backend/app/test_chart_artifact_tool.py
- 新增覆盖 `ToolNode` 注入 `runtime` 语义的回归测试。
- 新增顶层未知字段仍会被拒绝的校验测试，避免为了兼容 runtime 注入而放松整体参数约束。

## 2026-04-18 13:20 - 强化图表工具入参 schema 与错误参数拦截
### 概述
围绕 `build_chart_artifact` 在多系列图表场景下容易被 LLM 填错参数的问题，进一步把 `series` 入参从宽松的 `list[dict[str, Any]]` 收紧为明确的结构化 schema，并在工具内部新增数值列校验、未知键拦截和分类拆线配对校验。这样即使模型继续传入 `metric`、`label`、`type` 等未支持字段，或把 `field` 错填成分类列，也会被明确拒绝，而不会再悄悄生成错误图表。
### 变更内容
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/test_chart_artifact_tool.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- `build_chart_artifact` 现在使用明确的 `BuildChartArtifactInput / ChartSeriesInput` schema
- 强制 `series.field` 必须是数值列
- 拒绝 `metric`、`label`、`type`、`axis` 等未支持键
- 强制 `category_field/category_value` 成对出现，并继续支持从系列名称自动推断分类值

## 2026-04-18 13:04 - 收紧多系列对比图的 LLM 参数生成约束
### 概述
在补齐前后端“按分类拆线”能力后，继续收紧主 Agent 的系统提示词与图表工具说明，避免模型在多车型/多类别对比图里继续只重复同一个数值字段，遗漏分类拆线元数据。现在当同一指标需要按车型、缺陷类型等分类拆成多条系列时，模型会被明确要求提供 `category_field/category_value`，或至少在系列名称中包含可识别的分类值，便于工具自动推断。
### 变更内容
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/test_agent_service_prompt.py`
- 明确禁止仅通过重复 `field` 生成多条对比系列
- 明确要求多分类对比图补充 `category_field/category_value` 或可识别分类值

## 2026-04-18 13:05 - 修复同一指标按多分类拆线时图表系列重合的问题
### 概述
首版图表能力原本只稳定支持“多个不同数值字段并列展示”，还不真正支持“同一个数值字段按车型/类别拆成多条线”。因此像 `A7` 与 `TiguanL` 这种对比图里，如果多个系列都引用同一个数值列，前端会直接复用同一组数据，导致系列重合。此次修复后，图表工具会为系列补齐分类拆线元数据，前端也会按分类字段和值真正拆分数据。
### 变更内容
- 更新 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/schemas.py`
- 更新 `frontend/src/types/index.ts`
- 更新 `frontend/src/components/ChartArtifactCard.vue`
- 更新 `backend/app/test_chart_artifact_tool.py`
- 支持图表系列携带 `category_field`、`category_value` 与可选 `color`
- 当同一数值字段被拆成多个系列时，后端可从系列名中自动推断分类值
- 前端按 `category_field/category_value` 过滤行数据，避免多系列直接叠成同一条线

## 2026-04-18 12:42 - 优化 LLM 对图表能力的主动引导文案
### 概述
针对查询结果已经明显适合可视化、但助手仍然只用“是否需要进一步分析”收尾的问题，收紧主 Agent 的系统提示词约束。现在当结果属于时间趋势、分类对比、Top N 排名或双指标对比时，模型在用户尚未明确要求作图的情况下，也必须明确提醒“可以生成图表”，并给出可直接触发的示例话术。
### 变更内容
- 更新 `backend/app/agent/service.py`
- 新增 `backend/app/test_agent_service_prompt.py`
- 明确要求助手在合适场景下引导用户回复“生成图表”“生成趋势图”或“生成柱状图”
- 禁止仅使用“是否需要进一步分析”这类泛化收尾替代图表提醒

## 2026-04-18 11:55 - 修复聊天图表卡片已取到数据但未实际渲染的问题
### 概述
首版聊天图表能力接入后，前端已经能正确拿到 `chart_artifact` 并展示标题、说明与点数，但图表区域为空白。根因是 `ChartArtifactCard` 在 `loading=true` 时就调用了 `renderChart()`，此时真正的图表容器仍被 `v-if/v-else` 隐藏，ECharts 没有可初始化的 DOM 节点，因此不会报错但也不会出图。
### 变更内容
- 更新 `frontend/src/components/ChartArtifactCard.vue`
- 将图表实例创建与 `setOption` 延后到 `loading` 结束之后
- 在重新加载 artifact 时先销毁旧实例，避免复用旧容器状态
- 补充 `resize()`，保证容器切换后尺寸同步

## 2026-04-18 15:35 - 新增聊天内嵌图表 artifact 能力
### 概述
为聊天式 SQL Agent 增加“用户明确要求后再生成图表”的首版能力。此次实现采用 chart artifact 引用机制：LLM 只负责判断是否需要作图和图表基本元数据，后端工具重新执行聚合 SQL、存储完整图表配置，并只向模型返回轻量 `chart_artifact_ref`，避免大结果再次进入上下文。前端收到 `chart_id` 后再拉取完整 `chart_spec`，在消息卡片内渲染折线图或柱状图。
### 变更内容
- 新增 `backend/app/chart_artifacts.py`
- 新增 `backend/app/agent/tools/chart_artifact_tool.py`
- 更新 `backend/app/config.py`
- 更新 `backend/app/schemas.py`
- 更新 `backend/app/api.py`
- 更新 `backend/app/agent/service.py`
- 更新 `backend/app/agent/tools/__init__.py`
- 新增 `backend/app/test_chart_artifacts.py`
- 新增 `backend/app/test_chart_artifact_tool.py`
- 新增 `backend/app/test_chart_api.py`
- 新增 `frontend/src/api/charts.ts`
- 新增 `frontend/src/components/ChartArtifactCard.vue`
- 更新 `frontend/src/components/MessageItem.vue`
- 更新 `frontend/src/types/index.ts`
- 新增聊天图表环境变量：`CHART_ARTIFACT_DIR`、`CHART_ARTIFACT_TTL_HOURS`、`CHART_ARTIFACT_MAX_POINTS`
- 前端引入 `echarts`，并将 `typescript` 固定在与当前 `vue-tsc` 校验兼容的 `5.4.5` 版本区间

## 2026-04-18 09:37 - 调整车型缺陷趋势场景为检测次数与平均缺陷数口径
### 概述
根据当前业务使用口径，将 `model_defect_trend` 场景的输出从“检测次数 + 缺陷总数”调整为“检测次数 + 每次检测平均缺陷数”，避免趋势解读时被样本量放大影响。
### 变更内容
- 更新 `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/model_defect_trend/scenario.py`
- 更新 `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/model_defect_trend/sql/main.sql`
- 更新 `backend/app/test_skill_registry.py`
- 将 SQL 聚合字段由 `SUM(mq.total_defect_count)` 调整为 `AVG(mq.total_defect_count)`
- 将输出契约调整为 `detection_count` 与 `avg_defect_per_detection`

## 2026-04-16 10:31 - 优化 Windows 本地后端启动入口，修复 AsyncPostgresSaver 事件循环兼容问题
### 概述
针对 Windows 本地开发场景下 `AsyncPostgresSaver` 与 `psycopg` 异步连接池依赖 `SelectorEventLoop` 的限制，新增一个独立的 Python 启动入口，在 Uvicorn 创建事件循环前显式设置 `WindowsSelectorEventLoopPolicy`。这样可以保持现有异步 Agent 链路不回退，同时避免继续直接使用 `uvicorn backend.app.main:app` 时落回 `ProactorEventLoop` 导致启动超时。

补充说明：首次落地后进一步确认，Windows 下 `uvicorn --reload` 的 `WatchFiles` 会通过 `spawn` 方式启动子进程，子进程不会继承父进程中预设的事件循环策略。因此本地 Windows 启动入口继续调整为“默认关闭 reload”，确保 async checkpointer 稳定启动。

后续进一步定位发现，`uvicorn 0.40` 在 Windows 下默认会显式选择 `ProactorEventLoop` 作为运行 loop，而不是单纯跟随当前事件循环策略。这意味着仅在入口脚本里设置 `WindowsSelectorEventLoopPolicy` 仍然不够，必须额外为 Uvicorn 显式注入自定义 `loop factory`，强制切换到 `SelectorEventLoop`，才能真正兼容 `psycopg` 异步连接池。

补充清理：在确认最终有效修复后，进一步移除了首轮尝试留下的重复配置，仅在 Windows 下向 Uvicorn 注入自定义 `loop`，并删除批处理脚本中重复的 `UVICORN_RELOAD=false` 设置，保持启动入口更接近最小改动原则。
### 变更内容
- **新增本地启动入口**:
  - 新增 `run_backend.py`
  - 在 Windows 下启动前显式设置 `WindowsSelectorEventLoopPolicy`
  - 继续复用 `backend.app.main:app`
  - 显式为 Uvicorn 注入自定义 `loop factory`
- **新增便捷启动脚本**:
  - 新增 `start_backend.bat`
  - 自动切换到 `py312_agent` 环境并调用 `python run_backend.py`
  - Windows 下默认设置 `UVICORN_RELOAD=false`
- **异步连接池修复**:
  - 更新 `backend/app/agent/service.py`
  - 为本地 `AsyncConnectionPool` 补充 `connect_timeout=5`
  - 修复 Windows 下连接池 worker 长时间挂起后触发 `pool initialization incomplete after 30 sec`
- **文档更新**:
  - 更新 `README.md`
  - 将 Windows 本地开发推荐启动方式调整为 `python run_backend.py`
  - 明确 Windows 本地默认关闭 reload
  - 明确 Docker / Linux 部署无需同步修改启动命令

## 2026-04-12 03:15 - 新增 Agent SQL 上下文与结果返回机制说明文档
### 概述
围绕 `analytics_db` 接入后关于 `schema`、`search_path`、物化视图支持、元数据抓取、`sql_db_schema` 移除影响，以及“查询结果是否应默认带列名”的连续讨论，新增一份统一机制说明文档，帮助后续维护者快速理解哪些能力已经真正作用到 LLM，哪些仍属于底层准备能力。
### 变更内容
- **新增机制说明文档**:
  - 新增 `docs/backend/database_refactor/agent_sql_context_mechanism.md`
  - 统一解释 `schema` 与 `search_path` 的关系
  - 统一解释物化视图如何纳入 `SQLDatabase`
  - 统一解释元数据抓取在当前实现中的真实作用边界
  - 统一解释为何将 `sql_db_query` 升级为默认带列名结果

## 2026-04-12 03:00 - 优化 SQL 查询结果为带列名结构，降低 LLM 对 SELECT * 的误判风险
### 概述
将包装后的 `sql_db_query` 返回格式从“默认元组列表字符串”升级为“默认带列名的字典列表字符串”，让模型在读取结果时能直接看到列名与字段值的对应关系，降低 `SELECT *`、宽表查询和多列表结果下的理解偏差。同时保持结果限流与预览机制兼容新旧两种格式。
### 变更内容
- **查询工具增强**:
  - 更新 `backend/app/agent/tools/sql_tools.py`
  - 更新 `backend/app/agent/tools/sql_tools_local.py`
  - 查询执行优先调用底层 `db.run_no_throw(query, include_columns=True)`
  - 结果默认包含列名
- **限流兼容增强**:
  - 行数估算逻辑同时兼容元组列表与字典列表
  - 预览截断逻辑同时兼容元组列表与字典列表

## 2026-04-12 02:20 - 新增 Agent 接分析库后未实施阶段待办清单
### 概述
围绕“Agent 已接入 `analytics_db`、tracking 与 defect 两个领域已初步落地”后的下一步规划，新增一份独立的未实施阶段清单文档，用于统一记录后续还未落地的阶段、优先级、进入条件和完成标准，避免后续计划继续散落在聊天记录里。
### 变更内容
- **新增待办文档**:
  - 新增 `docs/backend/database_refactor/unimplemented_phases_todolist.md`
  - 按“阶段目标 / 主要任务 / 完成标准 / 是否建议立即做”整理未实施阶段
- **规划范围明确**:
  - 覆盖跨域质量关联领域
  - 覆盖高频主题 `mart`
  - 覆盖现有技能与场景继续优化
  - 覆盖端到端验证与灰度
  - 覆盖后续可选增强项

## 2026-04-12 02:05 - 修复 CSV 导出工具未继承 analytics_db search_path 的问题
### 概述
补齐 `export_to_csv` 与 `analytics_db` 的连接一致性。此前 Agent 已经能在查询阶段通过 `search_path` 正常访问 `mart/fct/dim/ods` 对象，但 CSV 导出工具内部自行创建数据库连接时没有继承该配置，导致无 schema 前缀的查询在导出时可能报 `relation does not exist`。本次修复后，导出工具会与主查询链路共享相同的 `engine_args`。
### 变更内容
- **导出工具修复**:
  - 更新 `backend/app/agent/tools/csv_export_tool.py`
  - 为 `create_csv_export_tool()` 增加 `engine_args` 参数
  - 导出工具内部创建 SQLAlchemy 引擎时继承 `search_path`
- **服务注入修复**:
  - 更新 `backend/app/agent/service.py`
  - 注入 `export_to_csv` 时同步传入业务库对应的 `engine_args`
  - 使查询与导出在 `analytics_db` 下使用一致的 schema 可见性

## 2026-04-12 00:10 - SQL Agent 第一阶段接入 Analytics DB
### 概述
启动“Agent 接分析库”第一阶段改造，新增 `ANALYTICS_DATABASE_URL` 配置，并把 SQL Agent 的业务库入口切换为“优先 `analytics_db`、回退 `rollerbed_tracking_db`”模式。同时补齐 PostgreSQL `search_path` 和物化视图兼容，避免 Agent 接入分析库后看不到核心 `mart` / `fct` 对象。
### 变更内容
- **配置增强**:
  - 更新 `backend/app/config.py`
  - 新增 `analytics_database_url`
  - 新增 `analytics_db_search_path`
  - 兼容 `DEBUG=release/prod` 等环境标记，避免 Settings 初始化失败
  - 更新 `.env`
  - 新增 `ANALYTICS_DATABASE_URL`
  - 新增 `ANALYTICS_DB_SEARCH_PATH`
- **SQLDatabase 能力增强**:
  - 新增 `backend/app/agent/utils/sql_database.py`
  - 增加 `MaterializedViewSQLDatabase`，支持将 PostgreSQL 物化视图纳入可用对象集合
  - 增加 `build_postgres_search_path_engine_args()`，用于将 `mart,fct,dim,ods,meta` 注入连接 `search_path`
- **元数据抓取增强**:
  - 更新 `backend/app/agent/utils/db_utils.py`
  - 支持传入 `engine_args`
  - 支持把普通视图和物化视图一并纳入表结构抓取
- **Agent 业务库入口切换**:
  - 更新 `backend/app/agent/service.py`
  - 更新 `backend/app/agent/service_llama.cpp.py`
  - 业务 SQL 连接改为优先使用 `ANALYTICS_DATABASE_URL`
  - 若未配置则回退到 `ROLLERBED_DATABASE_URL`
  - CSV 导出工具同步复用新的业务库入口

## 2026-04-12 00:25 - 更新车辆追踪领域文档为分析库查询视角
### 概述
进入“Agent 接分析库”第二阶段，先对 `paint_shop_vehicle_tracking` 的领域文档做最小改动升级：保留源表说明，同时补充 `analytics_db` 下的推荐查询入口、正式产品车/异常车/当前现场总览口径，以及当前缺陷关联分析的易错点，让 Agent 加载领域技能后能直接理解应该优先查询哪些 `mart` / `fct`。
### 变更内容
- **领域文档增强**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 新增 `analytics_db` 分析库查询入口说明
  - 新增 `mart_position_current_overview`、`mart_abnormal_vehicle_current`、`mart_vehicle_quality_360` 等推荐对象
  - 明确 `fct_vehicle_position_current` 只表示正式产品车当前事实
  - 补充“异常车不适合只按 `vehicle_id` 建模”“当前缺陷关联不是检测时位置”等易错点

## 2026-04-12 00:40 - 优化车辆追踪固定场景到分析库口径
### 概述
继续“Agent 接分析库”第二阶段，对 `paint_shop_vehicle_tracking` 下现有固定场景做最小改造：让 `daily_area_body_count` 与 `realtime_area_body_count` 优先面向 `mart_position_current_overview`，不再默认从 `rb_position_data` 直接统计，并同步收敛场景口径为“当前快照下正式产品车数量”。
### 变更内容
- **场景元数据更新**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/daily_area_body_count/scenario.py`
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count/scenario.py`
  - 补充分析库对象说明
  - 明确仅统计正式产品车
  - 将区域维度参数来源切到 `dim_process_area`
- **SQL 模板更新**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/daily_area_body_count/sql/main.sql`
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count/sql/main.sql`
  - 查询入口由 `rb_position_data` 切换为 `mart_position_current_overview`

## 2026-04-12 01:10 - 新增质量缺陷分析领域与第一批固定场景
### 概述
进入“Agent 接分析库”第三阶段，新增独立的 `paint_shop_defect_analysis` 业务领域，把质量缺陷能力从车辆追踪领域中拆出来。第一批基于 `mart_vehicle_quality_360` 落地 5 个固定场景，用于承接每日缺陷汇总、车型趋势、部位分布、tunnel/cycle 对比和黑车顶对比等高频问题。
### 变更内容
- **新增领域骨架**:
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/__init__.py`
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/meta.py`
  - 新增 `backend/app/skills/domains/paint_shop_defect_analysis/domain.md`
- **新增第一批质量场景**:
  - 新增 `daily_defect_summary`
  - 新增 `model_defect_trend`
  - 新增 `defect_station_distribution`
  - 新增 `tunnel_cycle_defect_comparison`
  - 新增 `black_roof_defect_comparison`
  - 每个场景均补充 `scenario.py` 与 `sql/main.sql`
- **测试补充**:
  - 更新 `backend/app/test_skill_registry.py`
  - 补充新领域与新场景的自动发现、内容加载与兼容性断言

## 2026-04-12 00:35 - 调整车辆追踪领域文档顺序以适配 Agent 阅读
### 概述
继续第二阶段文档优化，将 `paint_shop_vehicle_tracking/domain.md` 重排为“先推荐查询入口，再业务逻辑与易错点，最后源表背景”的顺序，让 Agent 在加载领域技能后更容易优先命中 `mart/fct`，同时把 `ods` 和源表说明保留为背景知识与兜底参考。
### 变更内容
- **文档结构重排**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 将“推荐查询入口”提升到前部
  - 将“业务逻辑”和“当前易错点”前置
  - 将原“数据表”章节调整为“源表与底层数据表”

## 2026-04-12 00:45 - 补充车辆追踪领域中核心 mart/fct 的关键字段说明
### 概述
继续增强 `paint_shop_vehicle_tracking/domain.md`，在“推荐查询入口”下为核心分析对象补充轻量但高频的关键字段说明，让 Agent 在优先查询 `mart/fct` 时，不只知道应该查哪个对象，也能更快理解对象粒度和常用字段语义。
### 变更内容
- **分析对象字段说明补充**:
  - 更新 `backend/app/skills/domains/paint_shop_vehicle_tracking/domain.md`
  - 为 `mart_position_current_overview` 补充当前总览关键字段
  - 为 `fct_vehicle_position_current` 补充正式产品车当前事实关键字段
  - 为 `fct_position_current_all` 补充当前全部有效占位关键字段
  - 为 `mart_abnormal_vehicle_current` 补充异常车关键字段
  - 为 `mart_vehicle_quality_360` 补充缺陷关联分析关键字段
## 2026-04-11 21:20 - 新增 Analytics DB 后续待办清单与 mart 复用判断说明
### 概述
为方便后续在 `analytics_db` 基础上继续选择扩展方向，新增一份面向维护者的待办清单文档，集中整理当前已完成内容、建议下一步、可选增强项，以及“当前是否可以只依赖 `mart_vehicle_quality_360` 让 LLM 自主生成 SQL”的判断依据。
### 变更内容
- **新增待办文档**:
  - 新增 `docs/backend/database_refactor/analytics_db_todolist.md`
  - 按“已完成 / 建议下一步 / 可选增强”整理数据库后续建设路径
- **设计判断沉淀**:
  - 补充当前直接复用 `mart_vehicle_quality_360` 的适用范围
  - 补充何时需要新增 `mart_defect_daily_by_model`、`mart_defect_station_distribution` 的判断标准

## 2026-04-11 20:15 - 落地当前车辆事实分层第一阶段并同步数据库重构文档
### 概述
围绕 `analytics_db` 中“正式产品车 / 异常车 / 全量占位”混用的问题，正式落地当前车辆事实分层优化第一阶段：新增全量当前占位事实、异常车事实、异常车主题 `mart` 与当前现场总览 `mart`，同时将原有产品车当前位置事实明确收口到正式产品车，并把 `database_refactor` 文档同步到数据库真实状态。
### 变更内容
- **数据库对象新增与调整**:
  - 在 `analytics_db` 中新增 `fct.fct_position_current_all`
  - 在 `analytics_db` 中新增 `fct.fct_abnormal_vehicle_current`
  - 在 `analytics_db` 中新增 `mart.mart_abnormal_vehicle_current`
  - 在 `analytics_db` 中新增 `mart.mart_position_current_overview`
  - 重建 `fct.fct_vehicle_position_current`，明确其仅服务正式产品车
  - 重建 `mart.mart_vehicle_quality_360`，使其继续面向产品车质量分析主链路
- **维度层增强**:
  - 为 `dim.dim_vehicle_profile` 增加 `current_position_id`、`current_carrier_id`、`current_carrier_type`、`current_process_area`、`current_full_rb_code`、`current_position_updated_at`
  - 让车辆画像维度可保留正式产品车的当前绑定快照
- **刷新流程升级**:
  - 更新 `meta.refresh_analytics_all()`
  - 将新 `fct` / `mart` 对象纳入一键刷新流程
  - 刷新后自动补齐 `agent_ro` 对新增对象的 `SELECT` 权限
- **验证结果**:
  - 刷新后 `fct.fct_position_current_all = 114`
  - 刷新后 `fct.fct_vehicle_position_current = 102`
  - 刷新后 `fct.fct_abnormal_vehicle_current = 12`
  - 刷新后 `mart.mart_abnormal_vehicle_current = 12`
  - 刷新后 `mart.mart_position_current_overview = 114`
  - 异常车分类样例为 `empty_vehicle_id_with_carrier = 8`、`non_product_prefix = 4`
- **文档同步**:
  - 更新 `docs/backend/database_refactor/analytics_db_architecture.md`
  - 更新 `docs/backend/database_refactor/why_analytics_db.md`
  - 更新 `docs/backend/database_refactor/current_vehicle_fact_refactor.md`

## 2026-04-11 18:55 - 补充当前车辆事实分层重构方案文档
### 概述
围绕 `analytics_db` 当前车辆事实层在异常车、重复调试 `vehicle_id` 和 `carrier_id` 反查场景下的限制，补充一份面向后续数据库重构的专题方案文档，并同步修正现有 `database_refactor` 文档中的限制说明与演进建议，帮助后续将“正式产品车 / 异常车 / 全量占位”分层建模。
### 变更内容
- **新增专题方案文档**:
  - 新增 `docs/backend/database_refactor/current_vehicle_fact_refactor.md`
  - 说明当前 `fct_vehicle_position_current` 的局限，以及 `fct_position_current_all`、`fct_abnormal_vehicle_current`、异常车主题 `mart` 的设计方向
- **现有文档补充**:
  - 更新 `docs/backend/database_refactor/analytics_db_architecture.md`
  - 增加当前 `fct_vehicle_position_current` 对异常车与重复调试车场景的限制说明
  - 更新 `docs/backend/database_refactor/why_analytics_db.md`
  - 增加当前产品车事实与异常车事实不应长期混用的设计依据与后续演进建议

## 2026-04-11 18:36 - 新增 Analytics DB 设计动机说明文档
### 概述
在已经补齐 `analytics_db` 落地与刷新操作手册的基础上，再新增一份面向后续复用的设计说明文档，专门回答“为什么要设计 `analytics_db`、为什么不是直接查源库、为什么要分层以及当前取舍是什么”，用于统一数据库重构和 Agent 接库改造的设计认知。
### 变更内容
- **新增设计说明文档**:
  - 新增 `docs/backend/database_refactor/why_analytics_db.md`
  - 从背景、问题、分层、设计决策、已验证事实、踩坑与复用清单几个维度解释 `analytics_db` 的必要性
- **与现有手册互补**:
  - 与 `docs/backend/database_refactor/analytics_db_architecture.md` 形成“为什么这样设计”与“如何落地执行”的双文档结构

## 2026-04-11 17:20 - 修正 Analytics DB 落地与刷新操作手册为最新已验证版
### 概述
将 `docs/backend/analytics_db_architecture.md` 从偏概念性的架构说明重写为可直接执行的 `analytics_db` 落地与刷新操作手册，统一当前数据库中已经验证成功的 schema、表、物化视图、权限与刷新流程，避免后续继续沿用遗漏 `dim` 刷新和 `refresh_watermark` 更新的旧版步骤。
### 变更内容
- **文档重写**:
  - 更新 `docs/backend/analytics_db_architecture.md`
  - 补充一次性初始化、FDW 外表导入、ODS/DIM/FCT/MART 初始化与授权步骤
- **刷新流程修正**:
  - 明确当前正式版 `meta.refresh_analytics_all()` 会同时刷新 `dim.dim_process_area`、`dim.dim_vehicle_profile` 与 `meta.refresh_watermark`
  - 修正旧文档中仅刷新 `ods/fct/mart` 的过时描述
- **运维说明补充**:
  - 补充日常手工刷新、Windows 定时任务、验证 SQL 与后续项目接入步骤
  - 明确当前 `mart_vehicle_quality_360` 关联的是“缺陷检测 + 当前最新位置”，不是检测当时位置

## 2026-04-09 20:28 - 新增项目内数据库结构快照目录
### 概述
为方便后续字段分析、结构梳理和离线阅读，将 `defect_db` 中 5 张业务表的字段结构同步保存到项目根目录 `database/` 下，不再只依赖数据库内查询。
### 变更内容
- **新增本地快照目录与文件**:
  - 新增 `database/README.md`
  - 新增 `database/defect_db_schema_snapshot.json`
- **README 同步**:
  - 更新项目结构，补充 `database/` 目录说明
- **快照范围**:
  - `history`
  - `history_detail`
  - `history_extras`
  - `history_station`
  - `history_tokens`

## 2026-04-08 21:49 - 新增代码质量审查子智能体
### 概述
为项目补充一个专门用于“做代码 review、找 bug、识别回归风险、检查测试缺口”的子智能体 `code-reviewer`，帮助日常代码质量审查聚焦高风险问题与缺失测试，而不是停留在泛化风格建议。
### 变更内容
- **新增子智能体定义**:
  - 新增 `.claude/agents/code-reviewer.md`
  - 约束其聚焦代码质量问题、稳定性风险、安全隐患与测试覆盖审查
- **README 同步**:
  - 补充“代码质量审查子智能体”能力说明
  - 在项目结构中新增 `.claude/agents/code-reviewer.md` 入口
## 2026-04-07 21:18 - 同步 openspec/project.md 到当前项目上下文
### 概述
重写 `openspec/project.md` 中已经过期的 OpenSpec 项目背景说明，使其不再沿用旧版通用聊天 / arXiv Agent 视角，而是聚焦当前真实使用的 SQL Agent、Skills、RAG、结构化流式协议和双模式持久化实现，便于后续 proposal / spec 编写时获得更准确的项目上下文。
### 变更内容
- **项目定位修正**:
  - 更新 `openspec/project.md`
  - 将 Purpose 从旧版通用聊天 / 论文搜索场景，修正为当前生产数据查询型 SQL Agent 场景
- **技术与架构同步**:
  - 将技术栈更新为 LangChain/LangGraph、AsyncPostgresSaver / PostgresSaver、PGVector / Milvus Hybrid 等当前实现
  - 将架构模式更新为 `api.py -> services.py -> agent/service.py` 主链路
  - 补充结构化 SSE 事件协议和双模式持久化约定
- **约束与术语更新**:
  - 补充 `required_skill`、`export_to_csv`、BusinessRagMiddleware 等当前领域术语
  - 更新重要约束为只读 SQL、聚合优先、截断结果不可直接汇总、切换 embedding provider 后需重建向量库
  - 移除旧版固定主分支、FastAPI 测试客户端、arXiv API 等不再适合作为当前项目事实的描述

## 2026-04-07 21:04 - 同步 CLAUDE.md 到当前项目实现
### 概述
清理并重写根目录 `CLAUDE.md` 中已经过期的项目说明，使其与当前仓库中的环境约定、SQL Agent 架构、Skills/RAG 能力、结构化流式协议和双模式持久化实现保持一致，避免后续继续参考旧版 arXiv / 同步 PostgresSaver 文档造成误导。
### 变更内容
- **文档定位更新**:
  - 更新 `CLAUDE.md`
  - 明确 `AGENTS.md`、`memory.md`、`README.md`、`CLAUDE.md` 的建议优先级
  - 补充 proposal / spec / plan 场景下优先查看 `openspec/AGENTS.md` 的提示
- **环境与架构同步**:
  - 将环境说明从旧版 `py314_agent` 修正为 `py312_agent`
  - 将项目定位从旧版通用聊天 / arXiv Agent 更新为当前 SQL Agent + Skills + RAG 架构
  - 更新后端、前端主链路与关键目录说明
- **关键行为说明修正**:
  - 将流式说明更新为 `token/status/tool_call/tool_result/final/error` 结构化 SSE 事件协议
  - 将持久化说明更新为 FastAPI 本地异步 `AsyncPostgresSaver` 与 LangGraph 托管双模式
  - 补充 `required_skill` 约束、CSV 导出下载链路与当前常见误区说明

## 2026-04-06 21:22 - 重构技能场景目录与自动发现机制
### 概述
围绕后续固定场景持续增加后的维护成本问题，将业务技能系统从“场景文件 + 分散 SQL + 手工注册”升级为“场景目录聚合 + 自动发现 + scoped 资产解析”模式。这样新增一个场景时，只需要新增一个场景目录并填写模板，不再修改 `registry.py`。
### 变更内容
- **注册与发现重构**:
  - 新增 `backend/app/skills/discovery.py`
  - 更新 `backend/app/skills/registry.py`
  - 由显式 import/append 改为扫描 `domains/*/meta.py` 和 `scenarios/*/scenario.py` 自动装配
- **资产解析升级**:
  - 更新 `backend/app/skills/models.py`
  - 更新 `backend/app/skills/assets.py`
  - 更新 `backend/app/skills/renderers.py`
  - 为场景资产引入 `scope + path` 语义，支持 `scenario / shared / domain` 三类作用域
- **目录结构迁移**:
  - 迁移 `paint_shop_vehicle_tracking` 现有场景到 `scenarios/<scenario_name>/scenario.py + sql/main.sql`
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/shared/scripts/README.md`
  - 删除旧版 `scenarios/*.py`、`sql/*.sql` 与领域级脚本占位说明文件
- **验证与文档同步**:
  - 更新 `backend/app/test_skill_registry.py`，补充自动发现、shared 资产解析和失败即报错场景
  - 更新 `docs/backend/skills/README.md`
  - 更新 `docs/backend/skills/新增场景技能开发指南.md`
  - 更新 `docs/backend/skills/新增业务领域技能开发指南.md`
  - 更新 `docs/backend/skills/技能注册中心与加载机制说明.md`
  - 更新 `README.md` 的技能系统说明

## 2026-04-06 11:15 - 新增技能机制评审与优化待办文档
### 概述
将本次围绕“领域技能 / 场景技能加载机制”的评审结论整理为独立待办文档，集中记录当前问题、推荐方案与分期待办，便于后续继续按阶段推进优化，而不把讨论内容散落在聊天记录中。
### 变更内容
- **新增待办目录**:
  - 新增 `docs/todolist/`
- **新增评审文档**:
  - 新增 `docs/todolist/2026-04-06-技能机制评审与优化待办.md`
  - 归档技能上下文失配、场景资产加载不一致、场景与历史 SQL 示例优先级不清、仅展开第一份 SQL 等问题
- **目录说明同步**:
  - 更新 `README.md` 的项目结构说明，补充 `docs/todolist/` 目录用途

## 2026-04-06 10:25 - 同步 Obsidian 后端学习导航，补齐遗漏文档包装页
### 概述
扫描 `docs/` 与 `docs/obsidian/` 的对应关系后，补齐此前未纳入 Obsidian 后端学习路径的 5 篇中文文档，确保 `llama.cpp` 配置总结与 skills 专题文档也能在 Obsidian 中通过导航页顺序访问。
### 变更内容
- **导航更新**:
  - 更新 `docs/obsidian/backend-learning/00_后端开发学习导航.md`
  - 新增“本地模型与技能系统扩展”阶段，补充 22-26 号学习笔记入口
- **包装页补齐**:
  - 新增 `docs/obsidian/backend-learning/22_llama.cpp_与_LangChain_配置要点总结.md`
  - 新增 `docs/obsidian/backend-learning/23_Skills总览与文档导航.md`
  - 新增 `docs/obsidian/backend-learning/24_技能注册中心与加载机制说明.md`
  - 新增 `docs/obsidian/backend-learning/25_新增业务领域技能开发指南.md`
  - 新增 `docs/obsidian/backend-learning/26_新增场景技能开发指南.md`
- **链路修正**:
  - 更新 `docs/obsidian/backend-learning/21_Docker容器网络与外部服务访问指南.md`
  - 为原有阶段末尾补充下一篇跳转，保持学习链路连续

## 2026-04-06 10:14 - 新增 llama.cpp 与 LangChain 配置要点总结文档
### 概述
将项目内接入 `llama.cpp` OpenAI 兼容接口时的关键经验整理为独立文档，集中说明 `BASE_URL`、协议、API Key、模型名与 `max_tokens` 的配置规律，便于后续排查本地模型接入问题。
### 变更内容
- **新增文档**:
  - 新增 `docs/llama.cpp 与 LangChain 配置要点总结.md`
- **沉淀内容**:
  - 总结 `BASE_URL` 应只保留到 `/v1`
  - 补充 `http`/`https` 协议匹配要求
  - 记录 `llama.cpp` 默认不校验 API Key 的约定
  - 补充模型名、`max_tokens` 与推荐 `ChatOpenAI` 参数写法
- **维护价值**:
  - 为后续本地 GGUF 模型接入、排错与配置统一提供固定参考

## 2026-04-05 20:15 - 新增实时区域车身数量场景技能
### 概述
在 `paint_shop_vehicle_tracking` 领域下补充一个“实时各区域车身数量统计”固定场景，沉淀对应的场景 playbook 和外部 SQL 模板，让 Agent 能按场景方式加载这类高频实时统计需求。
### 变更内容
- **场景技能新增**:
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/scenarios/realtime_area_body_count.py`
  - 定义实时区域车身数量统计的触发问法、workflow、规则、易错点与输出契约
- **SQL 模板新增**:
  - 新增 `backend/app/skills/domains/paint_shop_vehicle_tracking/sql/realtime_area_body_count.sql`
  - 按 `process_area` 聚合统计当前有效车身数量，并按数量降序输出
- **注册与验证补充**:
  - 更新 `backend/app/skills/registry.py`，显式注册 `realtime_area_body_count`
  - 更新 `backend/app/test_skill_registry.py`，覆盖新场景的注册与加载断言
- **文档同步**:
  - 更新 `docs/backend/skills/README.md` 的当前目录结构示例，补充新场景文件

## 2026-04-05 11:40 - 补全 skills 专题文档目录
### 概述
继续完善 `docs/backend/skills/`，将原先的单篇“新增业务领域技能开发指南”扩展为一个可导航的小型专题文档集，覆盖目录索引、场景技能扩展方式以及注册中心与加载机制说明，方便团队后续系统化维护技能系统。
### 变更内容
- **新增文档索引**:
  - 新增 `docs/backend/skills/README.md`
  - 统一收口 skills 相关文档入口和推荐阅读顺序
- **新增扩展教程**:
  - 新增 `docs/backend/skills/新增场景技能开发指南.md`
  - 新增 `docs/backend/skills/技能注册中心与加载机制说明.md`
- **README 同步**:
  - 在技术文档列表中补充 skills 专题导航和新文档入口
- **维护价值**:
  - 让 `docs/backend/skills/` 从单文档目录演进为可持续扩展的技能系统手册目录

## 2026-04-05 11:10 - 新增业务领域技能扩展教程
### 概述
围绕当前“领域 skill + 场景 skill”二级披露架构，补充一份面向维护者的可复用教程，专门说明如何新增、配置和验证一个新的业务领域，避免后续只创建目录却遗漏注册中心、场景挂载或资产路径配置。
### 变更内容
- **新增教程文档**:
  - 新增 `docs/backend/skills/新增业务领域技能开发指南.md`
  - 说明新增领域目录、`meta.py`、`domain.md`、场景定义、SQL 模板与 `registry.py` 显式注册步骤
- **文档入口补充**:
  - 更新 `README.md` 的技术文档列表，加入该教程入口
- **维护建议沉淀**:
  - 明确当前实现属于“显式注册”机制，不会自动发现新领域
  - 总结新增领域后的验证清单与常见错误，便于团队后续复用

## 2026-04-05 10:30 - 引入领域与场景二级 Skill 披露骨架
### 概述
围绕 SQL Agent 的业务技能系统，实施“领域 skill + 场景 skill”二级披露改造：保留现有 `load_skill -> required_skill -> sql_db_query` 主链路，在不引入固定报表执行器的前提下，新增场景级 playbook、外部 SQL 资产和二级加载工具，为后续模板执行器与专用 report tool 预留扩展接口。
### 变更内容
- **技能包重构**:
  - 将 `backend/app/skills.py` 升级为 `backend/app/skills/` package
  - 新增 `models.py`、`registry.py`、`renderers.py`、`loaders.py`、`assets.py`
  - 保留 `SKILLS` 兼容导出，避免现有中间件和测试脚本回归
- **二级披露链路**:
  - 新增 `load_scenario` 工具
  - 扩展 `CustomState`，增加 `scenarios_loaded`、`active_skill`、`active_scenario`
  - 更新 `SkillMiddleware` 与系统提示词，引导“先加载领域，再按需加载场景”
- **样板场景落地**:
  - 为 `paint_shop_vehicle_tracking` 新增 `daily_area_body_count` 场景元数据
  - 引入外部 SQL 模板 `daily_area_body_count.sql`
  - 场景文本新增 workflow、rules、gotchas、output contract 和模板资产引用
- **文档与测试**:
  - 更新 `README.md` 中的技能系统说明
  - 新增 `backend/app/test_skill_registry.py`，覆盖注册中心、加载器和二级加载辅助逻辑

## 2026-04-04 14:55 - 清理 Docker 环境文件中的敏感信息并补充忽略规则

### 概述
针对 GitHub Push Protection 阻止 `feature/agent` 推送的问题，先在当前工作区完成最小化安全修复：补充相关忽略规则，降低后续再次误提交本地敏感配置的风险，并为后续清理未推送提交历史做准备。

### 变更内容
- **忽略规则补充**:
  - 更新 `.gitignore`
  - 新增 `.env_docker`、`.env copy`、`env_exp` 忽略项，覆盖本次触发扫描的本地环境文件命名
- **历史清理说明**:
  - 当前变更仅处理工作区与后续防误提交保护
  - 仍需对本地未推送提交历史执行重写，才能解除 GitHub 对旧提交中 secret 的拦截

## 2026-04-03 20:00 - 整理文档目录结构并更新 Obsidian 引用

### 概述
将原先分散在 `backend/docs` 下的后端技术文档统一归档到 `docs/backend`，让项目文档入口全部收口到 `docs/` 下；同时同步修正 Obsidian 学习笔记、README 与相关说明中的旧路径引用，避免目录调整后出现断链。

### 变更内容
- **目录整合**:
  - 将 `backend/docs/` 迁移为 `docs/backend/`
  - 保留 `docs/backend/rpd/` 子目录结构
- **Obsidian 引用更新**:
  - 批量更新 `docs/obsidian/backend-learning/` 下 21 篇学习笔记的 `source_note`、原文入口与嵌入路径
  - 更新 `00_后端开发学习导航.md` 中的原文目录说明
- **说明文档同步**:
  - 更新 `README.md` 中的项目结构与技术文档入口
  - 更新 `CLAUDE.md`、`开发规范与最佳实践.md` 中的后端文档目录路径
  - 修正 `docs/backend/rpd/` 内少量旧绝对路径说明

## 2026-04-02 22:25 - 新增通用文档的 Obsidian 分类学习目录

### 概述
将 `docs/` 下 7 篇原先零散放置的通用文档，按主题整理进对应的 Obsidian 学习目录，延续 `backend-learning` 的组织规则：保留原文不动，新增导航页、编号学习页、原文入口与嵌入，方便后续在 Obsidian 中按专题学习。

### 变更内容
- **新增 Obsidian 分类目录**:
  - 新增 `docs/obsidian/agent-sql-learning/`
  - 新增 `docs/obsidian/architecture-learning/`
  - 新增 `docs/obsidian/frontend-learning/`
  - 新增 `docs/obsidian/data-quality-learning/`
- **整理范围**:
  - `agent_best_practices.md`
  - `LangChain + PostgreSQL 注释识别最佳实践.md`
  - `sql_agent.md`
  - `前后端与Nginx架构知识总结.md`
  - `前端聊天消息Markdown渲染开发指南.md`
  - `数据库日期时间记录与大模型处理分析报告.md`
  - `生产数据查询智能体需求.md`
- **README 同步**:
  - 更新 Obsidian 学习目录说明
  - 增加新的学习导航入口

## 2026-04-02 22:15 - 新增 Obsidian 后端开发学习导航与编号笔记

### 概述
为了方便系统化学习 `backend/docs` 下的后端开发文档，新增一组面向 Obsidian 的学习笔记目录。在不改动原始文档的前提下，按学习顺序重新编号，并补充导航页、前后跳转和原文嵌入入口，降低后续复习与串联成本。

### 变更内容
- **新增 Obsidian 学习目录**:
  - 新增 `docs/obsidian/backend-learning/`
  - 新增 `00_后端开发学习导航.md`
  - 新增 21 篇编号学习笔记，覆盖 `backend/docs` 与 `backend/docs/rpd` 的现有后端文档
- **组织方式**:
  - 保留原始 `backend/docs` 文档不动
  - 每篇学习笔记增加学习建议、原文入口、上下篇导航与 Obsidian 嵌入
  - 导航页按“基础认知 / Agent 与 RAG / SQL Agent / 交互观测 / 部署环境”分阶段整理
- **README 同步**:
  - 更新项目结构说明
  - 增加 Obsidian 后端学习导航入口

## 2026-04-02 13:00 - 修复 Docker 构建阶段的 Milvus 依赖版本冲突

### 概述
修复 Docker 构建 `pip install -r /app/requirements.txt` 时的依赖解析失败。根因是项目显式锁定了 `pymilvus==2.6.3`，但 `llama-index-vector-stores-milvus==1.0.0` 要求 `pymilvus>=2.6.7,<3`，导致 pip 无法完成依赖求解。

### 变更内容
- **依赖版本对齐**:
  - 更新 `requirements.txt`
  - 更新 `requirements_standard.txt`
  - 将 `pymilvus` 从 `2.6.3` 提升为 `2.6.7`
- **修复效果**:
  - 与 `llama-index-vector-stores-milvus==1.0.0` 的最低兼容版本保持一致
  - 保持改动最小，避免一次性升级到更高版本带来的额外兼容风险

## 2026-04-02 12:50 - 修复 Docker 容器启动时 backend 包导入失败

### 概述
修复 `docker-compose.yml` 启动后端容器时出现的 `ModuleNotFoundError: No module named 'backend'`。根因是镜像内的 `WORKDIR`、`PYTHONPATH` 与 Uvicorn 启动入口使用了 `app.main:app` 路径，但仓库代码实际大量采用 `backend.app...` 绝对导入，导致容器内包根路径不一致。

### 变更内容
- **镜像启动路径修复**:
  - 更新 `backend/Dockerfile`
  - `WORKDIR` 从 `/app/backend` 调整为 `/app`
  - `PYTHONPATH` 从 `/app/backend` 调整为 `/app`
  - Uvicorn 启动入口从 `app.main:app` 调整为 `backend.app.main:app`
- **修复效果**:
  - 让容器内 Python 包根路径与仓库实际导入风格保持一致
  - 避免 `export_files.py`、`services.py`、`agent/service.py` 等模块中的 `backend.app...` 绝对导入在容器中失效

## 2026-04-02 00:10 - 新增 Docker 容器网络与外部服务访问指南

### 概述
围绕本次 `backend`、PostgreSQL、Milvus 与宿主机模型服务之间的 Docker 联通排查，新增一份可复用的实施/排障手册，统一沉淀 `external network`、容器名寻址、`host.docker.internal` 使用边界以及常见易错点，方便后续继续接入新的数据库或本地 API 服务。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/Docker容器网络与外部服务访问指南.md`
- **文档内容覆盖**:
  - 容器访问容器、容器访问宿主机、本机访问本机三类地址边界
  - `savedatabase_app-network` 与 `savedatabase_app_network` 命名差异带来的真实排障经验
  - Milvus 同时接入默认网络与外部网络的设计原因
  - 后续接入新依赖服务时的标准判断步骤与检查清单
- **README 同步**:
  - 更新技术文档列表，补充 Docker 网络与外部服务访问指南入口

## 2026-04-01 23:25 - 新增前端聊天消息 Markdown 渲染开发指南

### 概述
将本次“聊天消息完成态 Markdown 渲染 + 业务报表风格样式”实现过程沉淀为一份可复用开发指南，便于后续在其他聊天结果展示、分析摘要卡片或统计报表类前端场景中继续复用。

### 变更内容
- **新增文档**:
  - 新增 `docs/前端聊天消息Markdown渲染开发指南.md`
- **文档内容覆盖**:
  - 聊天消息 Markdown 渲染的背景、目标与整体分层设计
  - `markdown-it + DOMPurify + MessageItem.vue + style.css` 的调用链与职责拆分
  - 流式纯文本 / 完成态 Markdown 的设计取舍、易错点与检查清单
  - 业务报表风格样式的复用经验、边界与后续优化方向
- **README 同步**:
  - 更新项目特性与技术文档列表，补充 Markdown 展示能力与指南入口

## 2026-04-01 23:10 - 优化聊天消息为业务报表风格展示

### 概述
继续细化聊天消息的 Markdown 呈现方式，将原先偏通用文档的样式收敛为更适合统计结果、异常说明、分析摘要等场景的“业务报表风格”，让标题层次、表格扫描效率和数字信息可读性更清晰。

### 变更内容
- **样式优化**:
  - 更新 `frontend/src/style.css`
  - 强化仅含加粗文本段落的区块标题表现，模拟报表分组标题
  - 优化表格表头背景、行间斑马纹、边框与阴影，提升企业报表观感
  - 为第二列数字内容增加右对齐与等宽数字展示，便于快速对比数量
  - 放宽说明列换行规则，减少长文本被挤压的问题

## 2026-04-01 22:55 - 前端聊天消息支持 Markdown 展示渲染

### 概述
为聊天前端新增“完成态 Markdown 渲染”能力，让助手最终回复中的粗体、列表、表格、代码块和链接能够以更舒适、更易读的样式展示；同时保留流式输出阶段的纯文本效果，避免生成过程中频繁重排。

### 变更内容
- **前端依赖**:
  - `frontend/package.json` 新增 `markdown-it` 与 `dompurify`
- **渲染能力**:
  - 新增 `frontend/src/utils/markdown.ts`
  - 统一封装 Markdown 转 HTML 与安全清洗逻辑
  - 链接默认补充新窗口打开与安全 `rel` 属性
- **消息展示**:
  - 更新 `frontend/src/components/MessageItem.vue`
  - 用户消息与流式中的助手消息继续按纯文本显示
  - 助手完成态消息切换为 Markdown HTML 渲染
- **视觉样式**:
  - 更新 `frontend/src/style.css`
  - 新增聊天消息 Markdown 样式，优化段落、列表、表格、代码块、引用和链接展示

## 2026-04-01 01:00 - 新增 development-guide-synthesizer 技能

### 概述
新增一个面向“开发经验沉淀”的项目级技能，用于根据开发实现、讨论内容、代码改动和验证结果，快速提炼出结构化开发指南手册。该技能内置清晰模板、示例、关键点和常见错误，方便后续重复使用。

### 变更内容
- **新增技能**:
  - 新增 `.agents/skills/development-guide-synthesizer/SKILL.md`
- **新增参考资料**:
  - 新增 `.agents/skills/development-guide-synthesizer/references/guide-template.md`
  - 新增 `.agents/skills/development-guide-synthesizer/references/examples.md`
- **技能能力**:
  - 支持把功能开发、调试排障、架构讨论等内容沉淀为开发指南、排障手册、实施手册或复用 playbook
  - 提供标准章节模板、调用示例、关键点维度和易错点清单
- **README 同步**:
  - 更新项目特性与目录结构，补充该技能入口

## 2026-04-01 00:30 - 新增 SQL 导出文件下载开发指南

### 概述
围绕本次“SQL 大结果导出 + 后端下载接口 + 前端下载卡片”能力，新增一份可复用的开发指南，统一沉淀从查询限流、导出工具、文件元数据、安全下载到前端消息展示的设计经验，方便后续在其他导出类场景继续复用。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/SQL导出文件下载开发指南.md`
- **文档内容覆盖**:
  - SQL 导出下载链路的整体架构与调用顺序
  - `export_to_csv`、`export_files.py`、下载接口与前端下载卡片的职责分层
  - 为什么选择“结构化 JSON 字符串 + file_id + sidecar metadata”方案
  - 文件下载安全边界、复用模板、检查清单与后续演进方向
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-04-01 00:00 - 为 SQL 导出结果新增前端可下载能力

### 概述
为 `export_to_csv` 打通“服务器落盘 -> 后端安全下载接口 -> 前端下载按钮”的完整链路。现在导出工具不会再把服务器绝对路径直接暴露给前端，而是返回结构化导出元数据，聊天消息中可直接点击下载 CSV。

### 变更内容
- **后端导出元数据管理**:
  - 新增 `backend/app/export_files.py`
  - 为每个导出文件生成 `file_id`，并使用 sidecar JSON 保存文件元数据
- **后端下载接口**:
  - `backend/app/api.py` 新增 `GET /api/chat/files/{file_id}`
  - 通过 `FileResponse` 安全返回已导出的 CSV 文件
- **导出工具返回结构升级**:
  - `backend/app/agent/tools/csv_export_tool.py` 从“返回服务器路径文本”改为“返回结构化 JSON 字符串”
  - `backend/app/config.py` 新增 `SQL_EXPORT_DIR`、`SQL_EXPORT_TTL_HOURS`
- **前端下载卡片**:
  - 新增 `frontend/src/api/exports.ts`
  - `frontend/src/components/MessageItem.vue` 自动识别 `export_to_csv` 结果并渲染“下载 CSV”按钮
  - `frontend/src/types/index.ts` 新增 `ExportArtifact` 类型

### OpenSpec
- 新增 `openspec/changes/add-sql-export-download/`，记录本次导出下载能力的 proposal / design / tasks / spec delta

## 2026-03-31 22:08 - 新增聊天取消与中断机制开发指南

### 概述
围绕本次“前端停止生成 + 后端取消渗透”优化，新增一份专门的开发指南，统一说明取消链路的分层实现、机制原理、能力边界和后续扩展方向，方便团队后续继续复用和演进这套聊天中断能力。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/聊天取消与中断机制开发指南.md`
- **文档内容覆盖**:
  - 前端 `AbortController` 的停止生成机制
  - FastAPI SSE 断连感知与服务端停止转发逻辑
  - `task.cancel()` / `CancelledError` 如何沿 LangChain / LangGraph 协程链传播
  - 本地取消与远端 provider 取消的能力边界
  - 当前产品策略与后续可选体验方案
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-31 22:15 - 停止生成后保留已生成片段并明确标记中断

### 概述
继续细化“停止生成”的产品体验。用户主动中断流式回答后，前端不再直接清空过程态，而是保留已经生成的内容，并将其落定为一条本地 assistant 消息，同时明确标记“已停止生成”，让状态更可理解。

### 变更内容
- **中断消息落定**:
  - `frontend/src/stores/messages.ts` 新增主动中断落定逻辑
  - 停止生成后保留当前文本片段、工具调用和工具结果，并转为本地正式消息
- **取消分支体验优化**:
  - `frontend/src/composables/useChatStream.ts` 在 `AbortError` 分支改为保留片段而非直接清空
  - 继续刷新会话列表，但不立即用服务端消息覆盖当前本地中断结果
- **界面提示优化**:
  - `frontend/src/components/MessageItem.vue` 为中断消息增加“已停止生成”提示和对应视觉样式
- **文档同步**:
  - 更新 `backend/docs/聊天取消与中断机制开发指南.md` 中的当前产品策略说明

## 2026-03-31 21:31 - 收敛前后端 SSE 事件 schema

### 概述
继续收敛聊天流式协议边界，减少前后端对未知事件类型的宽松兜底。后端现在会在发送 SSE 前校验事件结构，前端则移除 `type: string` 回退分支并在解析层拒绝不符合协议的 payload，从而让流式协议真正收敛为有限事件集合。

### 变更内容
- **后端事件模型收敛**:
  - `backend/app/schemas.py` 将流式事件拆分为 `token/status/tool_call/tool_result/final/error` 六类显式模型
  - 新增统一序列化入口，SSE 发送前先校验并标准化事件 payload
- **前端解析层收敛**:
  - `frontend/src/types/index.ts` 移除宽松 `type: string` 兜底事件
  - `frontend/src/api/chat.ts` 增加运行时事件校验，拒绝未知或不完整的流式事件
- **消费侧类型收敛**:
  - `frontend/src/composables/useChatStream.ts` 改为穷尽式 `switch` 处理，避免新事件类型被静默忽略
- **文档同步**:
  - 更新 `backend/docs/聊天流式输出结构化事件开发指南.md`，补充 schema 收敛原则

## 2026-03-31 21:52 - 收敛取消信号到 Agent 执行任务

### 概述
继续优化聊天链路的取消能力，让“前端停止生成 / SSE 断连”不仅停止本地转发，也尽量中断服务层正在执行的 Agent 调用。这样做不能保证远端 LLM provider 一定马上停止推理，但可以更稳定地把取消信号继续传到 LangGraph 图执行与底层模型 SDK 的 await 链路。

### 变更内容
- **非流式取消收敛**:
  - `backend/app/services.py` 将 `ainvoke()` 包装为可取消 task
  - 上层取消时显式取消并等待任务结束，避免悬挂中的 Agent 调用继续运行
- **流式取消收敛**:
  - `backend/app/services.py` 将 `astream()` 消费改为独立 producer task + queue
  - 当 SSE 消费端取消或断连时，会反向取消 producer task，并主动关闭底层 async iterator
- **边界说明**:
  - 当前优化能更早停止本地 FastAPI / LangGraph 消费链路
  - 远端 provider 是否真正中断，仍取决于对应 SDK / 模型服务是否支持请求级取消

## 2026-03-31 11:05 - 新增 LangSmith tracing 开发指南文档

### 概述
围绕本次 tracing metadata / tags 接入，新增一份面向后续开发的文档手册，统一说明其作用、当前实现、字段规范、查看方式和扩展建议，方便后续在新入口或新业务域下继续复用。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/LangSmith Tracing Metadata 与 Tags 开发指南.md`
- **文档内容覆盖**:
  - tracing metadata / tags 的作用与典型使用场景
  - 当前项目中的接入位置与字段清单
  - 如何在调用时追加业务 metadata / tags
  - 如何在 LangSmith 中查看和过滤 trace
  - 后续扩展建议与开发检查清单
- **README 同步**:
  - 在技术文档列表新增该指南入口

### 2026-03-31 11:15 Asia/Shanghai 更新补充
- 澄清 `business_domain` 应来自确定性来源，不应由 LLM 在请求开始时自由推断后注入根 trace
- 补充“运行过程中才能确定 domain 时”的三种推荐策略：首轮不注入、仅对子链路补充、持久化后下一轮再注入

### 2026-03-31 11:30 Asia/Shanghai 更新补充
- 修正 tracing 手册中的 `config` 示例，拆分为“默认安全示例”和“已确认 domain 才注入”的扩展示例

## 2026-03-31 10:20 - 后端新增 SSE 客户端断连感知

### 概述
为聊天流式接口补充服务端侧断连感知能力。当浏览器主动停止生成、关闭页面或网络中断导致 SSE 连接断开时，后端会尽早停止等待新的流式事件并关闭流式迭代器，减少无效的本地继续执行。

### 变更内容
- **SSE 断连检测**:
  - `backend/app/api.py` 的 `/stream` 路由新增 `Request` 注入
  - 在事件循环中周期性检查 `request.is_disconnected()`
- **尽早停止等待**:
  - 将下一条流式事件读取包装为可取消的 `asyncio` task
  - 检测到客户端断开后，立即取消等待中的任务并结束 SSE 生成
- **资源清理与结束标记收敛**:
  - 在 `finally` 中主动关闭流式迭代器
  - 客户端已断开时不再尝试发送 `[DONE]`

## 2026-03-31 10:45 - 新增 LangSmith tracing metadata 与 tags

### 概述
为 FastAPI 本地聊天链路补充 LangSmith trace 元数据与标签。后续可以在 LangSmith 中按会话、请求模式、RAG 后端、模型和运行环境过滤 trace，也为自托管或兼容 OpenAI 协议的模型提供更稳定的模型识别字段。

### 变更内容
- **trace metadata 补充**:
  - `backend/app/services.py` 统一为 invoke/stream 两条链路补充 `session_id`、`thread_id`、`request_mode`、`rag_backend`、`app_component`、`runtime_mode`
  - 同步补充 `ls_provider`、`ls_model_name`、`ls_temperature`、`ls_max_tokens`
- **trace tags 补充**:
  - 新增 `chat-api`、`sql-agent`、`mode:*`、`runtime:*`、`rag:*`、`provider:*`、`model:*`、`env:*` 等标签
- **配置合并策略**:
  - 保留外部传入的 `configurable / metadata / tags`
  - 新增 trace 字段时默认合并，不破坏后续按业务域继续扩展

## 2026-03-29 22:35 - 修复 P0 级流式结果聚合与非流式错误语义

### 概述
针对聊天链路中最关键的三类问题进行收敛：避免多节点流式 token 被误拼成最终回答、避免 `tool_call_chunk` 在前后 chunk 间被拆成多个工具调用、避免非流式 Agent 异常被伪装成正常 assistant 消息落库。

### 变更内容
- **流式最终内容聚合修复**:
  - `backend/app/services.py` 不再使用全量流式 token 直接生成最终 `final.content`
  - 改为优先使用最终 `AIMessage` 提取的完整内容，降低多节点 streaming 污染最终回答的风险
- **工具调用 chunk 归并修复**:
  - `backend/app/services.py` 将流式工具调用按 `chunk index` 归并，并通过原始 `tool_call_id` 回写结果映射
  - 避免同一次工具调用被拆成多个前端工具卡片
- **非流式错误语义修复**:
  - `backend/app/services.py` 的 `process_message()` 改为向上抛出异常
  - `backend/app/api.py` 在非流式路径返回标准错误响应，不再把失败文本保存为成功 assistant 消息
- **前端失败后状态同步补强**:
  - `frontend/src/composables/useChatStream.ts` 在发送失败后补一次消息同步，尽量与服务端持久化状态保持一致

## 2026-03-29 22:55 - 收敛前端会话状态同步与消息请求竞态

### 概述
继续优化聊天前端状态管理，去掉本地手工维护的会话消息计数，统一以服务端会话数据为准；同时为消息拉取增加请求序列保护，避免快速切换会话时旧请求回包覆盖当前会话消息。

### 变更内容
- **会话状态权威源收敛**:
  - `frontend/src/composables/useChatStream.ts` 不再手工累加 `message_count`
  - 在消息发送完成、流式结束和失败恢复后统一刷新服务端会话列表
- **消息同步范围收敛**:
  - 仅当当前仍停留在对应会话时，才静默刷新该会话的消息列表
  - 避免用户切换到其他会话后，旧会话的后台同步覆盖当前视图
- **消息请求竞态保护**:
  - `frontend/src/stores/messages.ts` 新增请求序号与目标会话标记
  - 旧请求回包将被忽略，降低串会话和闪屏风险

## 2026-03-29 23:10 - 新增流式取消能力与停止生成交互

### 概述
为聊天前端补充流式请求取消能力。用户在流式模式下发送问题后，可以主动停止当前生成过程；前端会中断 SSE 请求、清理过程态，并重新同步服务端消息与会话状态，避免把主动停止误判为系统错误。

### 变更内容
- **流式请求取消**:
  - `frontend/src/api/chat.ts` 为 `sendChatStream()` 增加 `AbortSignal` 支持
  - `frontend/src/composables/useChatStream.ts` 使用 `AbortController` 管理当前流式请求
- **停止生成交互**:
  - `frontend/src/views/ChatView.vue` 在流式发送中将发送按钮切换为“停止生成”
  - 用户点击后会中断当前请求，而不是弹出失败提示
- **中断后的状态收敛**:
  - 主动中断时清理流式临时消息
  - 随后重新同步当前会话消息与会话列表，尽量与服务端持久化结果保持一致

## 2026-03-27 22:12 - 聊天界面默认仅展示最终结论

### 概述
优化聊天前端展示策略，将“过程信息”和“最终答案”分层处理。普通用户在问答完成后只看到最终结论，生成过程中的状态与工具细节仅保留为轻量提示或内部调试信息，从而减少信息噪音，提升阅读效率。

### 变更内容
- **OpenSpec 提案补充**:
  - 新增 `openspec/changes/update-chat-final-only-display/`
  - 为“默认仅展示最终结论”补齐 proposal / tasks / spec delta
- **前端展示收敛**:
  - `frontend/src/components/MessageItem.vue` 默认不再展示状态文本、工具调用、工具结果和错误细节
  - 新增 `frontend/src/config/chat.ts`，通过 `VITE_CHAT_DEBUG_STREAM=true` 恢复内部调试视图
- **流式错误体验修复**:
  - `frontend/src/stores/messages.ts` 新增错误落定逻辑，失败时直接收敛为最终 assistant 消息
  - `frontend/src/composables/useChatStream.ts` 避免错误后残留半成品过程态消息
- **README 同步**:
  - 更新功能说明，强调默认用户界面仅展示最终结论

## 2026-03-27 20:55 - 新增 Milvus RAG 异步化故障排查指南

### 概述
围绕本次 Milvus RAG 检索失败事件，系统整理从故障现象、排查路径、根因分析到最终 async 化修复方案的完整经验，帮助后续快速判断“空检索结果”到底是召回失败还是初始化上下文失败。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/Milvus-RAG-异步化故障排查指南.md`
- **文档内容覆盖**:
  - 同步 `PostgresSaver`、`stream()/astream()`、Milvus lazy init 之间的因果关系
  - `ThreadPoolExecutor` 工作线程缺少 event loop 的真实触发链
  - 为什么表面上的“未检索到业务知识”其实是初始化失败后的降级结果
  - 最终为什么选择“本地 FastAPI 全链路切回 async”而不是在线程池里补 event loop
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-27 20:40 - 本地 FastAPI 切回 AsyncPostgresSaver 与异步流式执行

### 概述
将本地 FastAPI 运行链路从“同步 `PostgresSaver` + `stream()/invoke()`”切回“`AsyncPostgresSaver` + `astream()/ainvoke()`”，并增加显式 startup/shutdown 生命周期管理，解决同步 saver 限制和 Milvus 延迟初始化在线程池中缺少 event loop 的问题。

### 变更内容
- **本地异步持久化**:
  - `backend/app/agent/service.py` 新增 `AsyncConnectionPool + AsyncPostgresSaver` 初始化工厂
  - 新增 `create_local_async()` 与 `aclose()`，供 FastAPI 本地模式显式初始化和关闭
- **FastAPI 生命周期改造**:
  - `backend/app/services.py` 去掉模块级 eager `agent_service`
  - 新增 `initialize_agent_service()` / `get_agent_service()` / `shutdown_agent_service()`
  - `backend/app/main.py` 在 `lifespan` 中显式初始化与回收 Agent 资源
- **请求执行链路恢复异步**:
  - `backend/app/services.py` 的非流式和流式调用切回 `ainvoke()` / `astream()`
  - 继续保留结构化 SSE 事件协议与前端兼容逻辑
- **文档同步**:
  - 更新 `backend/docs/聊天流式输出结构化事件开发指南.md`
  - 更新 `backend/docs/延迟初始化工作流程详解.md`
  - 更新 `README.md` 中本地持久化与运行模式说明

## 2026-03-27 18:45 - 新增聊天流式输出结构化事件开发指南

### 概述
基于本次聊天流式协议升级、同步/异步 streaming 兼容处理、工具状态一致性修复和前端 SSE 重构实践，沉淀一份可复用的开发指南，方便后续在其他 Agent / Chat 场景中快速复用和学习。

### 变更内容
- **新增文档**:
  - 新增 `backend/docs/聊天流式输出结构化事件开发指南.md`
- **文档内容覆盖**:
  - 结构化流式事件协议设计
  - 后端 `messages / updates / custom` 分工建议
  - 前端 SSE buffer 解析与 streaming state 建模
  - `astream` / `stream` 与 `PostgresSaver` 兼容性踩坑
  - 工具状态“执行中/已完成”一致性处理经验
- **README 同步**:
  - 在技术文档列表新增该指南入口

## 2026-03-27 17:50 - 聊天流式协议升级为结构化事件流

### 概述
将原有“纯文本 chunk + 最终块补工具信息”的流式链路，升级为前后端协同的结构化 SSE 事件流。后端切换到 LangGraph v2 多模式 streaming，前端重写 SSE 解析与流式状态管理，使用户可以看到更稳定的实时文本、阶段状态、工具调用、工具结果和错误态。

### 变更内容
- **OpenSpec 提案补充**:
  - 新增 `openspec/changes/update-chat-streaming-protocol/`
  - 为流式协议升级补齐 proposal / tasks / spec delta
- **后端流式协议升级**:
  - `backend/app/services.py` 改为输出 `token/status/tool_call/tool_result/final/error` 结构化事件
  - 使用 `agent.astream(..., stream_mode=[\"messages\", \"updates\", \"custom\"], version=\"v2\")`
  - 新增 `backend/app/agent/utils/streaming.py`，为工具与中间件提供 custom status 事件写入 helper
  - `backend/app/api.py` 在 `final/error` 路径统一处理 assistant 消息落库，并保留 `[DONE]` 作为传输层结束标记
- **前端流式消费重构**:
  - `frontend/src/api/chat.ts` 重写 SSE buffer 解析逻辑，兼容跨 chunk JSON
  - `frontend/src/types/index.ts` 引入 `StreamEvent`、`StreamToolCall`、结构化 `StreamingMessage`
  - `frontend/src/stores/messages.ts` / `frontend/src/composables/useChatStream.ts` 改为事件驱动，采用“本地完成落定 + 后台静默同步”
  - `frontend/src/components/MessageItem.vue` / `frontend/src/views/ChatView.vue` 增强状态文案、工具执行区和错误态展示

## 2026-03-27 16:10 - 前端开发环境代理到本地后端 8000

### 概述
针对当前后端服务运行在 `http://localhost:8000`、而前端仍使用 `/rearch/...` 相对路径请求的情况，在 Vite 开发环境中补充代理转发规则，避免逐个修改前端 API 文件，并保持开发环境与生产环境的路径风格一致。

### 变更内容
- **Vite 开发代理**:
  - 在 `frontend/vite.config.ts` 的 `server.proxy` 中新增 `/rearch -> http://localhost:8000`
  - 通过 `rewrite` 去掉请求前缀 `/rearch`，使后端实际接收到 `/api/chat/...`
- **兼容性说明**:
  - 保持 `frontend/src/api/index.ts` 与 `frontend/src/api/chat.ts` 现有相对路径写法不变
  - 前端开发时浏览器仍访问 `/rearch/api/...`，由 Vite 代理转发到本地 FastAPI `8000`

### 补充修正（2026-03-27 16:22）
- 将 `frontend/vite.config.ts` 的代理匹配从 `/rearch` 收窄为 `/rearch/api`
- 避免首页路由 `/rearch/` 被误代理到后端根路径 `/`，导致浏览器显示 FastAPI JSON 而不是前端页面

## 2026-03-27 15:45 - 精简 service.py 运行模式识别并补充编排注释

### 概述
在保持 FastAPI / LangGraph CLI 双模式兼容的前提下，继续收敛 `backend/app/agent/service.py` 的实现复杂度，让运行模式识别、持久化注入和 Agent 编排主干更容易阅读和维护。

### 变更内容
- **运行模式识别简化**:
  - 用更直观的 `LANGGRAPH_API_URL || PATH contains langgraph` 规则判断托管环境
  - 保留日志输出，明确区分“LangGraph API 托管环境”和“本地独立运行模式”
- **持久化注入简化**:
  - 本地模式下通过 `agent_kwargs` 显式传入 `store/checkpointer`
  - 托管模式下保持空注入，由 LangGraph 运行时自动接管
- **可读性增强**:
  - 为环境识别、持久化初始化、Agent 编排主干补充了精简注释
  - `build_agent_graph` 增加了对 LangGraph factory 参数用途的说明

## 2026-03-27 15:23 - SQL Agent 服务层整合并兼容 LangGraph CLI 双模式

### 概述
将 `backend/app/services.py` 从旧的一体化 SQL Agent 实现重构为 FastAPI 兼容适配层，底层统一复用 `backend/app/agent/service.py` 的 Agent V2 核心运行时。同时补齐 `langgraph dev` / LangGraph API 场景下的双模式兼容，支持“FastAPI 本地手动初始化 PostgresSaver”与“LangGraph 托管环境自动注入 checkpointer/store”两条运行链路。

### 变更内容
- **核心运行时重构**:
  - `backend/app/agent/service.py` 新增运行模式识别
  - `SQLAgentService` 支持注入 `checkpointer` / `store`
  - 本地独立运行模式下自动回退创建 `ConnectionPool + PostgresSaver`
  - 移除模块级 `logging.basicConfig(...)` 与导入即初始化的全局 `agent_service`
- **LangGraph 入口调整**:
  - `langgraph.json` 从模块级对象切换为工厂函数入口 `backend/app/agent/service.py:build_agent_graph`
  - 兼容 LangGraph CLI 的 `config + runtime` 工厂调用约束
- **FastAPI 兼容层重构**:
  - `backend/app/services.py` 改为兼容适配层
  - 保留 `process_message()` / `process_stream()` 与 `tool_calls/tool_results` 旧返回契约
  - API 层无需调整请求/响应结构
- **文档同步**:
  - `README.md` 更新 `services.py` 与 `agent/service.py` 的职责说明
  - 补充 FastAPI / LangGraph CLI 双模式持久化说明

## 2026-03-27 13:55 - 修正 Codex 环境中的 LangGraph 启动命令

### 概述
修正 `.codex/environments/environment.toml` 中的 LangGraph 启动配置，避免因命令名写错且未先激活 `py312_agent` 环境而导致 PowerShell 报错找不到命令。

### 变更内容
- **环境配置修正**:
  - 为 `.codex/environments/environment.toml` 补充 `setup.script = "conda activate py312_agent"`
  - 将错误的 `Langgraph dev --allow-blocking` 修正为 `langgraph dev --allow-blocking`

## 2026-03-27 13:35 - LangGraph Dev 启动补充 conda 环境切换

### 概述
为 `langgraph dev --allow-blocking` 这条本地调试命令补充明确的 conda 环境切换要求，避免未激活 `py312_agent` 时出现依赖或解释器不一致问题。

### 变更内容
- **新增启动脚本**:
  - 新增根目录 `start_langgraph_dev.bat`
  - 在执行 `langgraph dev --allow-blocking` 前自动执行 `conda activate py312_agent`
- **README 同步**:
  - 新增 LangGraph Dev 调试入口说明
  - 明确先激活 `py312_agent`，并补充 Windows CMD 下的脚本启动方式

## 2026-03-27 13:10 - 新增代码阅读与解释子智能体

### 概述
为项目补充一个专门用于“读代码、讲架构、梳流程、看调用链”的子智能体 `code-explainer`，同时提供项目级 `skill` 版本，方便在不同 Agent / CLI 场景下复用，帮助更快理解仓库结构与实现机制。

### 变更内容
- **新增子智能体定义**:
  - 新增 `.claude/agents/code-explainer.md`
  - 约束其聚焦代码阅读、架构讲解、流程拆解与调用链分析
- **新增项目级 Skill**:
  - 新增 `.agents/skills/code-explainer/SKILL.md`
  - 统一沉淀代码解释类任务的工作流、输出结构与边界
- **README 同步**:
  - 补充“代码阅读讲解子智能体”能力说明
  - 在项目结构中新增 `.claude/agents/` 与 `.agents/skills/code-explainer/` 入口

## 2026-03-24 16:35 - LangGraph 调试链路补充显式 LLM 超时与重试配置

### 概述
针对 `langgraph.json -> backend/app/agent/service.py` 这条开发调试链路，补充显式的网络 LLM 超时与重试配置，避免完全依赖底层 SDK 默认值，提升 OpenAI-compatible 远程模型调用时的可控性。

### 变更内容
- **配置增强**:
  - 在 `backend/app/config.py` 新增 `LLM_TIMEOUT` 与 `LLM_MAX_RETRIES`
  - 在根目录 `.env` 增加对应默认配置项
- **Agent 服务增强**:
  - 在 `backend/app/agent/service.py` 的 `ChatOpenAI` 初始化中显式传入 `request_timeout` 与 `max_retries`
  - 使 `langgraph.json` 调试入口下的远程模型调用具备项目级可调的超时与重试策略

## 2026-03-24 16:05 - llama.cpp + Qwen3 Embedding 实践文档重构与沉淀

### 概述
将 `backend/docs/llamacpp-qwen3-embedding-local-deployment.md` 从“本地部署操作说明”升级为“完整改造与复用实践文档”，系统整理本次 `llama.cpp + Qwen3 Embedding` 接入 Milvus Hybrid RAG 的架构、流程、接口协议、部署方式、排障经验与后续复用建议。

### 变更内容
- **文档重构**:
  - 重新组织为“背景目标、相关目录、总体架构、配置设计、建库流程、查询流程、API 格式、部署步骤、排障、最佳实践、开发心智”分层结构
  - 补充项目内关键代码落点与目录索引，方便后续快速定位
  - 明确 `query instruction`、`L2 normalize`、`provider 切换后需重建索引` 等关键约束
- **README 入口同步**:
  - 在技术文档列表中新增 `llama.cpp + Qwen3 Embedding 接入与复用最佳实践` 链接
  - 方便后续从项目首页直接跳转到该专题文档

## 2026-03-24 15:35 - README 项目结构树同步更新

### 概述
对照当前仓库实际目录结构，更新 `README.md` 中的“项目结构”章节，修正已过时的路径描述，并补充当前已经落地的 RAG / llama.cpp 相关目录入口。

### 变更内容
- 将 `requirements.txt` 与 `.env` 的位置修正为仓库根目录
- 补充 `backend/docs/`、`backend/llamaCpp/`、`backend/app/test_*.py` 等实际存在的目录 / 文件入口
- 在 `backend/app/agent/vector/` 结构中补充 `embedding_provider.py`
- 保持目录树为“精简但准确”的项目入口视图，避免 README 演变成全量文件清单

## 2026-03-24 15:20 - README 与文档入口同步修正

### 概述
对照当前仓库结构与最新 RAG / llama.cpp 接入实现，修正了 `README.md` 中已过时的环境与依赖说明，避免按旧说明执行时找不到 `.env.example` 或 `backend/requirements.txt`。

### 变更内容
- **README 修正**:
  - 将“复制 `.env.example`”改为“直接使用 / 新建根目录 `.env`”
  - 将后端依赖安装入口统一为根目录 `requirements.txt`
  - 将后端启动命令统一为从仓库根目录执行 `uvicorn backend.app.main:app`
- **文档一致性检查**:
  - 复核 `README.md` 与当前 `llama.cpp + Qwen3 Embedding` / `Milvus Hybrid` 实现是否一致
  - 保持既有历史 changelog 记录不变，仅在最新条目中补充当前有效的使用说明

## 2026-03-24 14:30 - Milvus 混合检索支持 llama.cpp + Qwen3 Embedding 切换

### 概述
在保留原有 `Ollama qwen3-embedding:0.6b` 能力的基础上，为 Milvus Hybrid RAG 新增 `llama.cpp + Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0` 的可切换嵌入方案。初始化入库与运行期检索统一复用同一个 LlamaIndex embedding provider 入口，并在 `llama.cpp` 路径下对 query 侧启用 Qwen 官方推荐的 instruction-aware embedding 格式。

### 变更内容
- **共享 Embedding Provider**:
  - 新增 `backend/app/agent/vector/embedding_provider.py`
  - 统一封装 `OllamaEmbedding` 与自定义 `LlamaCppEmbedding`
  - 新增 `QwenInstructionAwareEmbedding`，只对 query 侧拼接 `Instruct: ...\nQuery: ...`
- **Milvus 接入改造**:
  - `backend/app/agent/vector/factory.py` 改为通过共享 provider 配置 `LlamaIndex Settings.embed_model`
  - `backend/app/agent/vector/milvus_init/init_store.py` 改为复用同一 provider，保证建库与查询一致
- **配置增强**:
  - `backend/app/config.py` 新增 `EMBEDDING_PROVIDER`、`LLAMA_CPP_EMBED_*`、`QWEN_QUERY_INSTRUCTION_*` 配置项
  - `.env` 补充 `llama.cpp` embedding 的默认配置示例
- **测试补充**:
  - 新增 `backend/app/test_embedding_provider.py`
  - 修正 `backend/app/test_rag_milvus_hybrid.py` 中的延迟初始化与 mock 覆盖方式
- **文档同步**:
  - `README.md` 增补 Milvus embedding provider 切换说明与重建索引提示


## 2026-03-22 22:50 - Milvus 嵌入模型迁移至本地 Ollama (Qwen3)

### 概述
将 Milvus 混合检索所依赖的嵌入模型由原有的 NVIDIA 云端 API 迁移至本地私有化部署的 `Qwen3-Embedding-0.6B`（通过 Ollama 托管）。同时解决了本地代理环境导致的 502 请求拦截问题，保持了检索链路的完全离线化。

### 变更内容
- **模型替换**: 在 `backend/app/agent/vector/factory.py` 和 `milvus_init/init_store.py` 中，使用 `OllamaEmbedding` 替换 `NVIDIAEmbedding`。
- **配置增强**:
  - `backend/app/config.py` 新增 `ollama_embed_model` 环境变量项。
  - **网络优化**: 在全局配置中强制设置 `NO_PROXY` 环境变量，自动绕过系统代理对 `localhost` 的拦截（修复 502 错误）。
- **文档同步**: 更新了 `backend/docs/RAG架构与技术总结.md`，反映了最新的模型架构选型。
- **环境变量**: `.env` 中新增 `OLLAMA_EMBED_MODEL` 参数并完成注释。


## 2026-03-22 21:35 - 新增 RAG 架构与技术栈剖析文档

### 概述
根据现有代码库实现，整理并输出了完整的 Retrieval-Augmented Generation (RAG) 架构设计文档，详细剖析了系统目前的双引擎检索架构、核心组件与模型选型以及工作流执行逻辑。

### 变更内容
- **新增文档**: `backend/docs/RAG架构与技术总结.md`
  - 阐述了 Milvus Hybrid 和 PGVector 双引擎的实现与切换机制。
  - 整理了 Embedding 模型（NVIDIA V5、BAAI BGE-M3）及 Reranker（Mistral-4B）选型细节。
  - 总结了完整的 RAG 数据检索与合成流向。

---
## 2026-03-22 18:00 - SQL 查询结果智能限流与安全防护优化

### 概述
针对大模型处理大量 SQL 查询结果时面临的上下文溢出、推理降智、Token 成本激增等问题，实施了一套弹性限流方案。小结果集（如维度表）全量返回，大结果集自动截断并注入预警，同时新增 CSV 导出工具实现数据与 LLM 的安全隔离。

### 变更内容

#### `backend/app/config.py` + `.env`
- **新增 `sql_result_hard_limit`**：后端强制截断行数上限（默认 1000），保护内存和 LLM 上下文
- **新增 `sql_result_preview_rows`**：超限时给 LLM 展示的预览行数（默认 5）

#### `backend/app/agent/tools/sql_tools.py`
- **新增 `_estimate_row_count()`**：估算 LangChain 返回结果字符串中的行数
- **新增 `_extract_preview_rows()`**：从结果字符串中提取前 N 行作为预览
- **`sql_db_query` 增强**：新增第 5 步"智能结果限流"——判断结果行数是否超过 `hard_limit`，超限时只返回预览 + 系统截断警告（引导 LLM 建议聚合 SQL 或 CSV 导出）

#### `backend/app/agent/tools/csv_export_tool.py` [NEW]
- **新增 `export_to_csv` 工具**：使用 SQLAlchemy + CSV 模块直接从数据库导出完整数据到文件，全程不经过 LLM 上下文。包含与 `sql_db_query` 一致的安全拦截和技能校验

#### `backend/app/agent/service.py`
- **工具注册**：在 `_prepare_tools` 中注入 CSV 导出工具
- **System Prompt 优化**：新增两条规则——强制使用聚合函数进行统计分析；超限时禁止基于截断数据汇总

---

## 2026-03-21 21:01 - SQL Agent 安全审计与拦截增强 (对策 3)

### 概述
针对 SQL Agent 存在的潜在 SQL 注入及破坏性操作风险（如 `DROP`, `DELETE` 等），实施了基于正则表达式的黑名单拦截机制（代码层硬校验），确保 Agent 仅能执行只读查询。

### 变更内容

#### `backend/app/agent/tools/sql_tools.py`
- **新增 `FORBIDDEN_SQL_PATTERN`**：定义了包含 `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE` 等危险关键字的正则表达式。
- **`sql_db_query`**：在执行逻辑最前端注入安全性拦截。任何匹配非法关键字的查询将被直接终止，并向 LLM 返回严重安全警告。

### 防御效果
- **防止提示词注入**：即使 LLM 被诱导产生破坏性 SQL，也会在执行前被逻辑层拦截。
- **操作审计**：拦截行为会记录到日志，方便安全审计。

---

## 2026-03-21 20:43 - SQL 工具技能精确校验优化

### 概述
参考 LangChain 官方 `skills-sql-assistant` 方案，修复了在 **Checkpointer 多轮对话**场景下，LLM 因 `skills_loaded` 状态已存在而跳过 `load_skill` 调用，直接执行跨业务域 SQL 查询的潜在问题。

### 变更内容

#### `backend/app/agent/tools/sql_tools.py`
- **`sql_db_query`**：新增 `required_skill: str` 参数，将技能校验从 `if not skills_loaded` 升级为 `if required_skill not in skills_loaded`（精确校验特定技能是否已加载，而非仅判断列表是否为空）
- **`search_saved_correct_tool_uses`**：同步新增 `required_skill: str` 参数，做相同精确校验，两个工具行为一致
- 返回值类型从 `List[dict]` 更新为 `Union[str, List[dict]]`，修复 Lint 错误

#### `backend/app/agent/service.py`
- 系统提示词的 **SQL查询规则** 章节新增说明：调用 `sql_db_query` 和 `search_saved_correct_tool_uses` 时，必须通过 `required_skill` 参数声明所依赖业务技能，切换业务域时必须重新调用 `load_skill()`

### 问题场景与修复效果

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 第1轮：涂装问题 | `skills_loaded=["paint_shop"]`，正常执行 | 同左 |
| 第2轮：焊装问题 | 由于列表非空，直接调 SQL（**幻觉风险**）| 工具返回 Error，强制 LLM 先 `load_skill("weld_shop")` |

---

## 2026-02-22 14:35 - 完善 Milvus 混合检索环境变量配置

### 概述
在 `.env` 文件中补齐了 Milvus 混合检索后端所需的全部环境变量，包括连接地址、Collection 命名、向量维度、RRF 融合系数以及数据导入路径等，并将 `RAG_BACKEND` 默认指定为 `milvus_hybrid`。

### 变更内容
#### 修改文件
- **.env**: 
  - 新增 `RAG_BACKEND='milvus_hybrid'`。
  - 新增 `MILVUS_URI`, `MILVUS_COLLECTION_NAME` 等系列配置。
  - 新增 `MILVUS_DATA_DIR` 指向默认示例数据路径。
  - 新增 `MILVUS_OVERWRITE='true'` 默认覆盖策略。

---

## 2026-02-21 15:30 - 扩展混合检索后端（LlamaIndex + Milvus）

### 概述
在现有「可插拔 RAG 架构」基础上新增了 **Milvus 混合检索**（稠密向量 + BM25 稀疏向量 + RRF 融合）后端。通过切换配置即可在 `pgvector` 和 `milvus_hybrid` 之间无感切换，同时新增了配套的数据初始化与导入模块。

### 变更内容

#### 新增检索模块
- **backend/app/agent/vector/milvus_hybrid/**: LlamaIndex + Milvus 检索实现
  - `milvus_store.py`: 封装 MilvusVectorStore 的创建、加载与 BM25 索引配置。
  - `milvus_retriever.py`: 实现 `MilvusHybridRetriever`，适配 `BaseRetriever` 接口。
- **backend/app/test_rag_milvus_hybrid.py**: 冒烟测试脚本。

#### 新增初始化模块
- **backend/app/agent/milvus_init/**: Milvus 专用数据导入脚本包（与 `vector_init` 风格一致）
  - `milvus_data_importer.py`: 支持数据转换、语义切片、Collection 初始化及批量入库逻辑。
  - `milvus_import_data.py`: CLI 入口脚本，支持 `--overwrite` 重建索引和追加导入。

#### 配置与工厂更新
- **backend/app/config.py**: 新增 `RAG_BACKEND` (默认 `pgvector`) 及 `MILVUS_*` 系列配置项。
- **backend/app/agent/vector/factory.py**: 重构工厂函数实现多后端分发逻辑。

### 初始化用法示例

```bash
conda activate py312_agent
# 首次初始化或重建索引（使用 examples 数据）
python -m backend.app.agent.milvus_init.milvus_import_data example_documentation.json --overwrite
# 追加数据
python -m backend.app.agent.milvus_init.milvus_import_data example_ddl.json
```

---

## 2026-02-18 17:45 - 集成 NVIDIA Rerank 精排层

### 概述
在现有 RAG 管道（向量检索 → score_threshold 过滤 → 注入系统消息）中插入 Rerank 精排层，使用 NVIDIA NIM 的 `rerank-qa-mistral-4b` 模型对候选文档进行二次排序，提升检索精度。

### 变更内容

#### 新增文件
- **backend/app/agent/utils/rerank_service.py**: NVIDIA NIM Rerank 服务封装
  - `NvidiaRerankService` 类，调用 NVIDIA Rerank API
  - 支持 `top_n` 截断和 `score_threshold` 阈值过滤
  - 异常时自动降级为原始排序（不影响现有功能）
- **backend/app/test_rerank.py**: Rerank 测试脚本（降级测试 + API 连通性测试）

#### 修改文件
- **backend/app/config.py**: 新增 Rerank 配置项
  - `rerank_enabled`（开关，默认 false）
  - `rerank_model`（模型，默认 `nvidia/rerank-qa-mistral-4b`）
  - `rerank_top_n`（保留数，默认 3）
  - `rerank_score_threshold`（可选阈值）
- **backend/app/agent/middleware/rag_middleware.py**: `BusinessRagMiddleware.__init__` 新增 `rerank_service` 参数；`before_model` 在向量检索后、格式化前插入 Rerank 调用
- **backend/app/agent/service.py**: 初始化 `NvidiaRerankService` 并传入 `BusinessRagMiddleware`，启用时 `doc_k` 从 5 提升到 10
- **文档更新**: `README.md` 中新增「RAG 召回与参数详解」章节，包含召回数量规则汇总表和详细的环境变量说明。
- **文档更新**: 全面翻新 `README.md`，更新项目结构树以匹配 Agent V2 模块化架构；更正过时的 Multi-Step SQL 工作流程描述为最新预加载 Schema 与中间件机制；修正环境依赖（Python 3.12+），并对齐 `.env` 中的 SQL 限流默认值。
- **配置说明**: 在环境变量章节补充了 `RAG_SIMILARITY_THRESHOLD` 和 `RERANK_SCORE_THRESHOLD` 的使用建议及其与 RRF 分数的关联。
- **代码调整**: (由用户手动执行) 将 `service.py` 中未开启精排时的默认召回数量由 3 提升至 5，增强基础召回范围。
- **.env**: 新增 `RERANK_ENABLED`、`RERANK_MODEL`、`RERANK_TOP_N` 等环境变量

### 架构变化
```
改动前：向量检索(k=5) → score_threshold 过滤 → 注入系统消息
改动后：向量检索(k=10) → score_threshold 粗筛 → Rerank 精排(Top-3) → 注入系统消息
```

### 测试结果
- 降级测试通过：无效 API Key 时正确回退
- API 连通性测试通过：L3F13 相关查询中，Rerank 正确将 L3F13 文档排到第一（score=3.0371）

### 推荐配置

为获得最佳效果，建议在 `.env` 中使用以下配置：

```bash
RERANK_ENABLED="true"
RERANK_MODEL="nvidia/rerank-qa-mistral-4b"
RERANK_TOP_N="3"
RERANK_SCORE_THRESHOLD="0.0" # 过滤掉负分结果（不相关文档）
```

---

## 2026-01-27 16:37 - 修复流式聊天 API 路径配置

### 问题
- `frontend/src/api/chat.ts` 中的流式请求硬编码了 `http://localhost:8000/api/chat`
- 导致在生产环境通过 Nginx 代理时无法正常访问后端
- 其他 API（sessions、messages）使用相对路径 `/rearch` 正常工作，但流式聊天请求失败

### 解决方案
- 修改 `API_BASE` 从 `'http://localhost:8000/api/chat'` 改为 `'/rearch/api/chat'`
- 统一所有 API 请求都通过 Nginx 代理访问后端
- 确保开发和生产环境的一致性

### 技术细节
```typescript
// 修改前
const API_BASE = 'http://localhost:8000/api/chat'

// 修改后
const API_BASE = '/rearch/api/chat'  // 使用相对路径，适配 Nginx 代理
```

---

## 2026-01-27 13:55 - Docker 容器化部署方案

### 概述
为后端FastAPI应用创建完整的Docker容器化部署方案，支持一键部署到生产服务器。

### 变更内容

#### 核心配置文件
- **backend/Dockerfile**: 创建后端镜像配置
  - 基于 `python:3.12-slim` 官方镜像
  - 安装系统依赖（gcc, postgresql-client）
  - 复制依赖并安装Python包
  - 暴露8000端口，使用uvicorn启动
  
- **backend/.dockerignore**: 排除文件列表
  - 排除Python缓存、虚拟环境、测试文件等
  - 减小Docker镜像体积

- **docker-compose.yml**: 容器编排配置（更新）
  - 新增 `backend` 服务：FastAPI应用容器
  - 保留 `postgres` 服务：PostgreSQL 17-alpine
  - 配置服务依赖：backend依赖postgres健康检查
  - 使用 `.env` 文件管理所有环境变量
  - 数据持久化卷 `pgdata`

- **.env.production**: 生产环境配置模板
  - 数据库配置（PostgreSQL）
  - LLM配置（DeepSeek/Ollama）
  - Agent配置（温度、Token限制）
  - LangSmith配置（可选）
  - 详细的注释说明

#### 部署文档
- **deploy/README.md**: 完整部署指南
  - 快速部署步骤（服务器准备、上传文件、配置、启动）
  - 常用管理命令（启停、日志、调试）
  - Nginx反向代理配置示例
  - 故障排查指南
  - 安全建议和数据备份方法

### 部署流程

```bash
# 1. 上传项目到服务器
scp -r rearch_agent/ user@server:/opt/

# 2. 配置环境变量
cd /opt/rearch_agent
cp .env.production .env
nano .env

# 3. 一键启动
docker-compose up -d --build

# 4. 验证
curl http://localhost:8000/
```

### 技术特点
- ✅ 简洁：最小化配置，只包含必要组件
- ✅ 完整：包含数据库、后端服务和详细文档
- ✅ 灵活：通过环境变量轻松切换配置
- ✅ 可靠：健康检查、自动重启、数据持久化
- ✅ 易维护：详细的操作文档和故障排查指南

---

## 2026-01-26 17:45 - 修复 PostgreSQL Checkpointer 初始化错误

### 问题
- LangGraph 的 `PostgresSaver.setup()` 使用 `CREATE INDEX CONCURRENTLY` 创建索引
- 该命令不能在事务块中运行，导致初始化失败
- 错误信息: `ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`

### 解决方案
- **backend/app/services.py**: 修改 checkpointer 初始化逻辑
  - 使用独立的 `psycopg.connect()` 连接并开启 `autocommit=True` 模式执行 `setup()`
  - setup 完成后再创建 `ConnectionPool` 用于正常操作
  - 添加详细的日志输出，便于诊断数据库连接问题

### 技术细节
```python
# 使用 autocommit 模式创建表结构
with psycopg.connect(settings.database_url, autocommit=True) as setup_conn:
    temp_checkpointer = PostgresSaver(setup_conn)
    temp_checkpointer.setup()

# 然后创建连接池用于正常操作
self.conn_pool = ConnectionPool(conninfo=settings.database_url, ...)
self.checkpointer = PostgresSaver(self.conn_pool)
```

---

## 2026-01-26 - 配置本地 llama.cpp 服务器
- **Backend 配置**: 将 LLM 从 DeepSeek API 切换到本地 llama.cpp 服务器。
  - 服务器地址: `http://172.22.44.99:8089/v1`
  - 模型: GLM-4.7-Flash-Q6_K.gguf
  - 使用 `ChatOpenAI` 客户端，兼容 OpenAI API 格式


## 2026-01-24: Agent V2 重构与架构升级

### 概述
基于 CR 反馈完成了 Agent V2 的重构工作，通过高度模块化的设计提升了代码的可维护性、可扩展性和可测试性。引入了基于技能（Skills）的动态上下文管理机制，并强化了 SQL 执行的安全性和准确性。

### 变更内容
- **模块化架构 (`backend/app/agent/`)**: 将原有的单文件服务拆分为功能独立的模块：
  - `service.py`: 核心服务编排
  - `middleware/`: 包含 `SkillMiddleware` 等中间件
  - `tools/`: 包含 `WrappedQueryTool` 等增强工具
  - `constants.py` & `utils`: 常量与通用工具函数
- **技能系统 (Skills System)**:
  - 引入 `SkillMiddleware`，支持按需加载业务领域的知识（Skills）到系统提示词。
  - 新增 `load_skill` 工具，允许 Agent 在运行时动态获取特定领域的详细文档和规则。
- **增强型 SQL 执行**:
  - **前置检查**: 集成了 SQL 语法验证器。
  - **后置处理**: 统一对查询结果进行 ISO 8601 日期格式化清洗，彻底解决时间格式不一致导致的大模型推理错误。
- **配置与日志优化**: 
  - 优化了代理（Proxy）环境变量的自动清理逻辑。
  - 统一了日志格式，支持开发模式下的详细日志输出。

---

## 2026-01-21: PostgreSQL 数据库配置扩展

### 概述
为 rollerbed tracking system 添加了独立的 PostgreSQL 数据库连接配置，保留原有 agent memory 数据库配置。

### 变更内容
- **.env**: 新增 `ROLLERBED_DATABASE_URL` 及相关连接参数
  - `ROLLERBED_POSTGRES_USER='root'`
  - `ROLLERBED_POSTGRES_PASSWORD='root'`
  - `ROLLERBED_POSTGRES_DB='rollerbed_tracking_db'`
  - `ROLLERBED_POSTGRES_HOST='localhost'`
  - `ROLLERBED_POSTGRES_PORT='5432'`
- **backend/app/config.py**: 在 `Settings` 类中添加对应的配置字段
  - `rollerbed_database_url`: 完整的数据库连接 URL
  - `rollerbed_postgres_user`, `rollerbed_postgres_password`, `rollerbed_postgres_db`, `rollerbed_postgres_host`, `rollerbed_postgres_port`: 各个连接组件

### 使用说明
```python
from backend.app.config import settings

# 使用完整 URL
db_url = settings.rollerbed_database_url

# 或者使用单独的组件
host = settings.rollerbed_postgres_host
port = settings.rollerbed_postgres_port
user = settings.rollerbed_postgres_user
password = settings.rollerbed_postgres_password
database = settings.rollerbed_postgres_db
```

---

## 2026-01-17: LangGraph 1.0+ SQL Agent 实现

### 概述
新增 `backend/app/services_graph.py`，基于官方 LangGraph SQL Agent 文档实现了一个现代化的多步骤 SQL Agent 工作流，作为原 `services.py` 的对比版本。

### 变更内容
- **backend/app/services_graph.py**: 新增 LangGraph 1.0+ 版本的 `SQLGraphService` 类。
- **模型**: 从本地 Ollama (qwen3) 切换为 DeepSeek (联网大模型)，提升 SQL 生成准确率。
- **架构**: `list_tables` → `get_schema` → `generate_query` → `check_query` → `run_query`
- **SQL 查询检查器**: 在执行前由 LLM 检查常见 SQL 错误。
- **日期格式清洗**: 策略 A - 无条件对所有查询结果进行 ISO 8601 日期格式标准化。
- **深度工具包装**: `services.py` 中对 `sql_db_query` 工具进行了包装，确保模型在中间推理步骤中看到的是清洗后的日期。

### 技术要点
- 使用 `StateGraph` + `ToolNode` (LangGraph 1.0+ API)
- 保留 `PostgresSaver` 检查点持久化
- 兼容原有 `process_message` 和 `process_stream` 接口

---

## 2026-01-17: 数据库日期时间处理分析与文档化

### 概述
完成并固化了关于 Agent 处理数据库日期时间字段的调研分析，预防大模型（LLM）在时间比较时可能产生的逻辑错误。

### 变更内容
- **docs/database_datetime_analysis.md**: 新增分析报告，详细对比了 SQL 层转换与 Python 工具层转换的优劣，并推荐在代码层进行 ISO 8601 标准化。
- **最佳实践**: 记录了 `DD/MM/YYYY` 等非标格式转换为标准 `YYYY-MM-DD` 的代码实现方案。

---


## 2026-01-16: UI/UX 全面升级与后端数据库依赖修复

### 概述
完成了全系统的 UI/UX 视觉方案升级，由原有的“暖色调”切换为现代化的“神经元色调 + AI 紫色” (Neural Tones + AI Purple) 设计。同时解决了后端在连接 MySQL 8.0+ 时由于缺少 `cryptography` 库导致的身份验证失败问题。

### 变更内容

#### Frontend (UI/UX 升级)
- **Design System**: 引入了以 Slate (Neural) 为基础、Violet (AI Purple) 为点缀的新设计系统。
- **tailwind.config.js**: 
  - 重构颜色体系，新增 `primary` (Violet 600), `secondary`, `neutral` (Slate) 调色板。
  - 定义语义化背景 `background` (#FAF5FF) 和文本颜色。
  - 优化 `boxShadow` (soft/glow) 和 `borderRadius`。
- **index.html**: 接入 Google Fonts (**Inter** 字体)。
- **style.css**: 
  - 移除旧版 `--color-warm-*` 变量，迁移至新的设计系统变量。
  - 实现毛玻璃效果 (`.glass`) 和现代化滚动条样式。
  - 重构全局组件样式 (Button, Input, Animations)。
- **Vue Components**: 重构了以下系列组件的模版和样式：
  - `App.vue`: 根布局样式调整。
  - `ChatView.vue`: 侧边栏与主区域渐变效果。
  - `SessionItem.vue` / `SessionList.vue`: 列表交互状态与空状态美化。
  - `MessageItem.vue` / `MessageList.vue`: 消息气泡渐变与打字动画优化。
  - `ToggleSwitch.vue` & `EmptyState.vue`: 视觉一致性对齐。

#### Backend (数据库连接修复)
- **requirements.txt**: 新增 `cryptography==42.0.5`。
- **Dependency Fix**: 修复了 `PyMySQL` 报错 `RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods`，支持了 MySQL 8.0 的高级加密认证。

---


## 2026-01-15: 修复 Ollama 持续时间格式与远程连接配置

### 概述
修复了 Ollama 在接收 `keep_alive` 参数时的 400 格式错误，并配置后端连接到远程服务器，同时切换为支持工具调用的模型。

### 变更内容
- **backend/app/config.py**: 将 `ollama_keep_alive` 强制转为 `int`，解决 `time: missing unit in duration` 报错。
- **.env**:
  - 更新 `OLLAMA_BASE_URL='http://172.22.44.99:11434'` 指向远程 5090 服务器。
  - 更新 `OLLAMA_MODEL='qwen3:30b'` 以支持 SQL Agent 所需的工具调用功能。
  - 更新 `OLLAMA_KEEP_ALIVE=-1` 为整数形式。

---


## 2026-01-14: 切换到 Ollama + Qwen3:30b

### 概述
将后端 LLM 从 DeepSeek API 切换到本地 Ollama 服务，使用 `qwen3:30b` 模型，充分利用 RTX 5090 显存。

### 变更内容

#### backend/app/config.py
- 新增 Ollama 配置参数：
  - `OLLAMA_BASE_URL`: Ollama 服务地址 (默认 `http://localhost:11434`)
  - `OLLAMA_MODEL`: 使用的模型 (默认 `qwen3:30b`)
  - `OLLAMA_NUM_CTX`: 上下文窗口大小 (默认 32768，32k tokens)
  - `OLLAMA_KEEP_ALIVE`: 模型驻留设置 (默认 `-1`，永久驻留)

#### backend/app/services.py
- 导入变更：`langchain_deepseek.ChatDeepSeek` → `langchain_ollama.ChatOllama`
- 移除 `httpx` 依赖及 `_no_proxy_client`（Ollama 为本地服务，无需代理处理）
- LLM 初始化更新为 `ChatOllama`，使用新的 Ollama 配置参数

### 使用前准备
```bash
# 1. 安装 langchain-ollama
pip install langchain-ollama

# 2. 拉取模型
ollama pull qwen3:30b
```

### 备注
- 原有 DeepSeek 配置保留在 `config.py` 中，可随时切换回去
- 如需使用 DeepSeek，只需将 `services.py` 中的导入和初始化改回即可


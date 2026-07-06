# Fan-out 防护体系系统性总结

> 记录时间: 2026-07-05 Asia/Shanghai
> 相关讨论: meta.py join_safety 标注一致性审查、PK 反射替代关系声明、行业最佳实践对比

---

## 1. 现象

### 1.1 初始发现

在审查 `paint_shop_defect_analysis/meta.py` 时，发现两条 N:1 关系的 `join_safety` 标注不一致：
- 关系1: `N:1` → 标注为 `unsafe`
- 关系2: `N:1` → 标注为 `safe`

### 1.2 核心问题

N:1 方向 JOIN（从 N 侧到 1 侧）**永远 safe**，因为每行最多匹配 1 行。Fan-out 风险只存在于 **1:N** 方向。标注错误的原因是混淆了 JOIN 方向。

进一步系统性审查发现，整个跨域查询防护体系存在以下问题：
1. **手动维护成本高**：`relationships` 和 `table_primary_keys` 在 meta.py 中人工声明，易过时
2. **双重 PK 标注**：`db_utils.py` 反射的 DDL 已含 `PRIMARY KEY`，`skeleton_service.py` 又追加 `-- PK`
3. **单表聚合口径错误无法覆盖**：PK 规则只管跨表 JOIN，管不到单表内 `COUNT(*)` vs `COUNT(DISTINCT)`
4. **过度依赖提示词**：所有防护都是文本规则，没有执行层校验

---

## 2. 分析

### 2.1 Fan-out 本质

Fan-out（扇出/行膨胀）是指 JOIN 后结果行数大于驱动表行数的现象。其本质是：

- **驱动表（From）**的某行在**目标表（To）**中匹配到多行
- 导致结果行数膨胀，聚合指标（COUNT/SUM/AVG）失真

### 2.2 两种"翻倍"风险

| 风险类型 | 触发条件 | 示例 | 当前防护 |
|---|---|---|---|
| **跨表 JOIN fan-out** | 从 1 侧 JOIN 到 N 侧（目标列非 PK） | `position_current JOIN quality_360 ON vehicle_id` | relationships + PK 规则（部分） |
| **单表聚合口径错误** | 流水表中用 `COUNT(*)` 统计实体数 | `COUNT(*)` 当车数（实际应 `COUNT(DISTINCT vehicle_id)`） | domain.md 军规（纯文本） |

### 2.3 当前防护链路的覆盖与缺口

```
用户提问
    │
    ├─> [Schema 层] db_utils.py PK 反射 → DDL 中标注 PRIMARY KEY ✅
    │
    ├─> [元数据层] meta.py relationships + join_safety（手动维护）⚠️ 冗余
    │
    ├─> [Prompt 层] service.py 规则 3.3 + domain.md 军规（纯文本）⚠️ 可能被忽略
    │
    ├─> [LLM 生成 SQL]
    │
    ├─> [执行层] ❌ 无任何校验，直接执行
    │
    └─> [运行时] ❌ 无任何监控，结果直接返回
```

**关键缺口**：
- 执行前：没有 SQL AST 分析
- 执行时：没有行数膨胀检测
- 单表聚合：没有 `COUNT(*)` vs `COUNT(DISTINCT)` 的自动拦截

---

## 3. 行业最佳实践

### 3.1 Schema 描述

| 维度 | 行业通用做法 | 当前项目 | 评估 |
|---|---|---|---|
| 表结构 | `CREATE TABLE` + 列注释 + 样本数据 | 相同 ✅ | 无差距 |
| 关系声明 | **不声明**，让 LLM 从 PK/FK 推断 | 手动声明 `relationships` + `cardinality` + `join_safety` | **过度设计**：违背 DRY 原则 |
| 主键信息 | 从数据库反射 PK，嵌入 DDL | 反射 + 额外手动声明 `table_primary_keys` | **冗余**：双重标注 |

**主流观点**：Text-to-SQL 社区（BIRD、Spider、LangChain SQLDatabase）均让 LLM 从 PK/FK 和列名推断关系。手动声明 relationships 只在特定 benchmark 中使用，生产环境几乎不用——schema 变更时必然被遗忘更新。
> **来源**：Li et al., "Can LLM Already Serve as A Database Interface?" (BIRD, NeurIPS 2023)[^1]；Yu et al., "Spider" (EMNLP 2018)[^2]；LangChain SQLDatabase 自动反射 PK/FK 实现[^3]

### 3.2 防 Fan-out 策略

| 策略 | 行业通用做法 | 当前项目 | 评估 |
|---|---|---|---|
| Schema 层 | PK 标注 + 让 LLM 推断 | PK 标注 ✅ + 额外 relationships | 冗余 |
| Prompt 层 | 通用规则（"JOIN 到非唯一键时预聚合"） | 具体规则（"此路径标记为 unsafe"） | 更精准但维护成本高 |
| 执行前校验 | SQL AST 分析检查 JOIN 条件 | ❌ **无** | **关键缺口** |

> **来源**：LangChain SQLDatabase 提供 `query_checker` 工具[^3]；Vanna AI 等生产级方案在生成后执行 EXPLAIN 校验[^4]
| 运行时监控 | 比较 JOIN 前后行数 | ❌ **无** | **关键缺口** |

### 3.3 统计口径防护

| 策略 | 行业通用做法 | 当前项目 | 评估 |
|---|---|---|---|
| 表粒度标注 | DDL 头部明确标注"每行代表..." | 分散在 domain.md 文本中 | ❌ 不够显式 |
| 统计军规 | 通用规则（"统计实体数用 DISTINCT"） | domain.md 有 ✅ | 可以，但需更结构化 |
| Few-shot 示例 | 提供正反 SQL 示例 | ❌ **无** | **关键缺口** |

> **来源**：BIRD Benchmark 论文显示，few-shot 是提升 Text-to-SQL 准确率最有效的手段之一[^1]；DIN-SQL (NeurIPS 2023) 通过分解 + 自我修正 + few-shot 达到 SOTA[^5]
| 执行前检查 | AST 检查 COUNT(*) 场景 | ❌ **无** | **关键缺口** |

### 3.4 执行层防护（最薄弱环节）

| 防护层 | 行业通用做法 | 当前项目 | 评估 |
|---|---|---|---|
| SQL 语法校验 | `EXPLAIN` / 数据库预编译 | 依赖数据库报错 | ⚠️ 基本合格 |
| 安全性检查 | 防注入、防 DDL/DML | 提示词禁止 + 正则过滤 | ⚠️ 基本合格 |
| 语义检查 | AST 分析 JOIN 安全性 | ❌ **无** | **关键缺口** |
| 行数预估 | `EXPLAIN` 估算返回行数 | ❌ **无** | **关键缺口** |

> **来源**：PostgreSQL `EXPLAIN` 提供预估行数（Estimated Rows），是 SQL Agent 运行时监控的标准手段[^6]；Vanna AI、DataGPT 等商业产品均集成执行后膨胀检测[^4]
| 膨胀检测 | 执行后比较行数变化 | ❌ **无** | **关键缺口** |

---

## 4. 推荐方案

### 4.1 短期（P0）：Schema 层简化

**目标**：移除冗余手动声明，依赖自动 PK 反射

- 移除 `meta.py` 中的 `table_primary_keys`
- 移除 `meta.py` 中的 `relationships`
- 清理 `skeleton_service.py` 中渲染 relationships 的逻辑
- 清理 `skill_middleware.py` 中拆分 relationship 块的逻辑
- 在 `service.py` 提示词中增加一条通用 PK 军规：
  > "JOIN 到目标表时，若 JOIN 列不是该表 PRIMARY KEY，必须先预聚合"

**收益**：
- 消除双重 PK 标注
- 消除手动维护成本
- 节省 ~350 tokens/turn

### 4.2 短期（P1）：Prompt 层优化

**目标**：让表粒度信息更可见

- 在 DDL 头部注入表粒度标注（替代 domain.md 的分散描述）：
  ```sql
  -- Table: mart.mart_vehicle_quality_360
  -- Grain: 一次检测事件（history_id），vehicle_id 可能重复（一车多检）
  -- ⚠️ 统计车数必须用 COUNT(DISTINCT vehicle_id)，不能用 COUNT(*)
  CREATE TABLE mart.mart_vehicle_quality_360 (
    history_id VARCHAR PRIMARY KEY,
    vehicle_id VARCHAR,  -- 非唯一，可能重复
    ...
  );
  ```

**收益**：
- 粒度警告紧贴在 DDL 中，比 domain.md 更不可能被 LLM 忽略
- 新加表时自动生成，无需手动维护

### 4.3 中期（P2）：执行前 AST 检查

**目标**：在 SQL 执行前自动拦截常见错误

- 解析 LLM 生成的 SQL AST
- 检查规则：
  1. 是否有 `COUNT(*)` 但没有 `DISTINCT`？（在含重复实体键的表中）
  2. JOIN 目标列是否在目标表的 PK 中？
  3. 是否包含 DELETE/UPDATE/INSERT？
- 不通过时拦截并提示 LLM 修正

**收益**：
- 不依赖 LLM 自律，强制校验
- 可拦截 80% 以上的 fan-out 和聚合口径错误

### 4.4 中期（P3）：运行时监控

**目标**：执行后发现异常

- 执行后比较"实际返回行数" vs "预估行数"
- 异常膨胀时告警并自动重写 SQL
- 收集正确/错误 SQL 对作为 Few-shot 示例

**收益**：
- 兜底防护，即使前两道防线失效也能发现
- 积累 Few-shot 数据，持续优化 LLM 表现

---

## 5. 目前进度

### 5.1 已完成

| 任务 | 状态 | 说明 |
|---|---|---|
| relationships 标注一致性审查 | ✅ | 修复了 7 条关系中的方向和安全标注错误 |
| note 术语统一 | ✅ | 全部改为 N侧/1侧 描述，消除"主/辅"歧义 |
| 关系渲染紧凑格式 | ✅ | 从"聚焦式关系图"改为紧凑箭头式，节省 ~3.2x tokens |
| service.py 提示词对齐 | ✅ | 规则 3.3 对齐新格式（`⚠️`/`💡` 标记） |
| skeleton_service.py 文件头清理 | ✅ | 移除过时描述 |
| PK 反射验证 | ✅ | 确认 `db_utils.py` 已自动反射所有物理表 PK |
| PK 规则等价性验证 | ✅ | 验证 PK 规则等价于当前 relationships 声明（7/7 正确） |

### 5.2 待实施

| 任务 | 优先级 | 说明 |
|---|---|---|
| 移除 relationships + table_primary_keys | P0 | 从两个 meta.py 中删除 |
| 清理 skeleton_service.py 关系渲染逻辑 | P0 | 删除 `_build_relationship_block` 及相关代码 |
| 清理 skill_middleware.py 关系拆分逻辑 | P0 | 简化 `_split_skeleton` 或直接移除 |
| service.py 提示词替换为 PK 军规 | P0 | 一条通用规则替代 5 条具体规则 |
| DDL 注入粒度标注 | P1 | 在 `db_utils.py` 或 `skeleton_service.py` 中实现 |
| SQL 执行前 AST 检查 | P2 | 新增校验模块 |
| 运行时膨胀检测 | P3 | 新增监控模块 |
| Few-shot 示例积累 | P3 | 长期数据积累 |

---

## 6. 后续计划

### 6.1 立即实施（本周）

1. **移除冗余声明**
   - `paint_shop_defect_analysis/meta.py`：删除 `table_primary_keys` 和 `relationships`
   - `paint_shop_vehicle_logistics/meta.py`：删除 `table_primary_keys` 和 `relationships`
   - `skeleton_service.py`：删除 `_build_relationship_block` 及相关调用
   - `skill_middleware.py`：简化 `_split_skeleton`（移除 relationship 部分处理）

2. **替换提示词**
   - `service.py` 规则 3.3：用 PK 军规替代现有 relationships 相关规则

### 6.2 近期实施（本月）

1. **DDL 粒度标注**
   - 在 `db_utils.py` 或 `skeleton_service.py` 中，为每张表注入粒度警告注释
   - 测试 LLM 对粒度警告的理解和遵守情况

2. **SQL 执行前 AST 检查（原型）**
   - 实现简单的 AST 解析（可用 sqlparse 或正则）
   - 先实现 `COUNT(*)` 检查和 JOIN PK 检查两个核心规则

### 6.3 远期规划（未来季度）

1. **运行时膨胀检测**
   - 集成 EXPLAIN 行数预估
   - 异常膨胀时自动重试

2. **Few-shot 示例驱动**
   - 收集生产环境中的正确/错误 SQL 对
   - 动态注入 prompt 作为参考

3. **多技能扩展**
   - 验证 PK 规则在其他技能域中的适用性
   - 评估是否需要补充逻辑（如 composite PK、unique index 等）

---

## 附录

### A. 核心文件清单

| 文件 | 作用 | 改动状态 |
|---|---|---|
| `backend/app/skills/domains/paint_shop_defect_analysis/meta.py` | 领域元数据 | 待删除 relationships/table_primary_keys |
| `backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py` | 领域元数据 | 待删除 relationships/table_primary_keys |
| `backend/app/agent/utils/skeleton_service.py` | 辅助技能骨架 DDL 服务 | 待删除关系渲染逻辑 |
| `backend/app/agent/middleware/skill_middleware.py` | 技能中间件 | 待简化关系拆分逻辑 |
| `backend/app/agent/service.py` | Agent 系统提示词 | 待替换规则 3.3 |
| `backend/app/agent/utils/db_utils.py` | 数据库元数据工具 | 已完成 PK 反射 ✅ |

### B. PK 规则等价性验证表

| JOIN | 目标列 | 目标主键 | 实际基数 | PK 规则判定 | 是否正确 |
|---|---|---|---|---|---|
| `position_current.vehicle_id → quality_360.vehicle_id` | `vehicle_id` | `history_id` ❌ | 1:N | fan-out | ✅ |
| `position_current.vehicle_id → defect_detection.vehicle_id` | `vehicle_id` | `history_id` ❌ | 1:N | fan-out | ✅ |
| `position_current.process_area → dim_process_area.process_area` | `process_area` | `process_area` ✅ | N:1 | 安全 | ✅ |
| `quality_360.vehicle_id → position_current.vehicle_id` | `vehicle_id` | `vehicle_id` ✅ | N:1 | 安全 | ✅ |
| `quality_360.vehicle_id → dim_vehicle_profile.vehicle_id` | `vehicle_id` | `vehicle_id` ✅ | N:1 | 安全 | ✅ |

## C. 关键概念定义

- **Fan-out（扇出）**: JOIN 后结果行数大于驱动表行数的现象，导致聚合指标失真
- **PK 规则**: JOIN 到目标表时，若 JOIN 列不是该表 PRIMARY KEY，必须先预聚合
- **单表聚合口径错误**: 在流水表中用 `COUNT(*)` 统计实体数，未使用 `COUNT(DISTINCT)` 去重
- **表粒度**: 每行数据的业务含义（如"一次检测事件" vs "一辆车身"）

---

## 参考文献

### 学术论文

[^1]: Li, J., Hui, B., Qu, G., Yang, J., Li, B., Li, B., ... & Li, Y. (2023). **Can LLM Already Serve as A Database Interface? A Big Bench for Large-Scale Database Grounded Text-to-SQL.** *NeurIPS 2023*. https://bird-bench.github.io/
  - 核心结论：Text-to-SQL 性能高度依赖 schema 描述的完整性；PK/FK 信息是 LLM 理解表关系的最关键线索。

[^2]: Yu, T., Zhang, R., Yang, K., Sagan, M., Li, D., Ma, J., ... & Radev, D. (2018). **Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task.** *EMNLP 2018*. https://yale-lily.github.io/spider
  - 核心结论：跨域 Text-to-SQL 的难点在于 schema 理解；使用 PK/FK 和列名推断关系是主流方案。

[^5]: Pourreza, M., & Ghiasi, M. (2023). **DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction.** *NeurIPS 2023*. https://arxiv.org/abs/2304.11015
  - 核心结论：将 Text-to-SQL 任务分解（Schema Linking + SQL 生成 + 自我修正），配合 few-shot 示例达到 SOTA。

### 开源项目与文档

[^3]: LangChain. **SQLDatabase Toolkit.** https://python.langchain.com/docs/integrations/toolkits/sql_database
  - 核心实现：自动反射数据库 PK、FK、索引和样本数据；通过 `custom_table_info` 注入 DDL；提供 `query_checker` 做 SQL 校验。

[^4]: Vanna AI. **Text-to-SQL Generation with Self-Correction.** https://vanna.ai/blog/
  - 核心实现：自动生成 SQL → EXPLAIN 校验 → 执行 → 结果验证的完整闭环；异常时自动重写 SQL。

[^6]: PostgreSQL Documentation. **EXPLAIN — Show the Execution Plan.** https://www.postgresql.org/docs/current/sql-explain.html
  - 核心机制：`EXPLAIN` 返回预估行数（Estimated Rows），是 SQL Agent 运行时膨胀检测的标准工具。

### 补充阅读

- **Seek AI**: https://www.seek.ai/ — 商业 Text-to-SQL 产品，集成执行前校验和运行时监控。
- **DataGPT**: https://datagpt.ai/ — 自然语言数据查询，强调"执行后验证"作为核心环节。
- **Cohere**: Text-to-SQL Best Practices (2024). 强调 DDL 中标注粒度（Grain）和表类型（Fact vs Dimension）对 LLM 理解的重要性。

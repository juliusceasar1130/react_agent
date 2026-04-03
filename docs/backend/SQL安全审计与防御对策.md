# SQL 安全风险审计与防御对策

本文针对 SQL Agent 服务中存在的潜在 SQL 注入及破坏性操作风险进行深度分析，并提出多层次的防护对策。

## 🚨 风险点识别 (Risk Analysis)

### 1. 深度依赖 LLM 提示词 (Prompt Injection)
在 `service.py` 的 `_build_system_prompt` 中，防线仅仅依赖于提示词约束：`- 严禁执行 DML 语句(INSERT, UPDATE, DELETE, DROP 等）`。
- **风险**：LLM 存在幻觉，且容易遭受**提示词注入（Prompt Injection）攻击**。攻击者可以通过特定话术诱导 LLM 忽略系统提示词，从而执行破坏性 SQL（如 `DROP TABLE`）。

### 2. 缺乏代码层面的硬拦截 (Hard Enforcement)
在 `sql_tools.py` 的 `sql_db_query` 工具中，目前的逻辑是：
- 依靠 `original_checker_tool` 进行检查。这通常也是调用 LLM 检查语法是否通畅，而不是检查安全性。
- 如果 LLM 认为 `DROP TABLE users` 语法正确，它会直接透传并由 `original_query_tool.invoke` 执行。

### 3. 基于关键字的检查不足
目前的 `SQL_ERROR_KEYWORDS` 检查仅用于识别 SQL **执行后的报错**，而不用于**执行前的语义拦截**。这意味着它无法感知语句的破坏性，只能在执行失败后报错。

### 4. 数据库账号权限过高 (Over-Privileged Connection)
如果 `rollerbed_database_url` 使用的是具备增删改查（DML）或结构修改（DDL）权限的账号（如 `root` 或 `owner`），则应用层一旦失守，数据库将直接暴露在风险之下。

---

## 🛡️ 实施对策 (Countermeasures)

### 1. 数据库级别：实施最小权限原则 (Principle of Least Privilege)
这是最根本、最可靠的底线。
- **方案**：为 SQL Agent 专门创建一个**只读数据库用户（Read-Only User）**。
- **动作**：仅授予在该用户必要的表/视图上执行 `SELECT` 的权限。
- **效果**：即使应用层防护被绕过，数据库内核也会因 `Permission denied` 拒绝所有 `UPDATE`、`DELETE` 或 `DROP` 操作。

### 2. 代码级别：引入 AST（抽象语法树）解析拦截
在 SQL 发送给数据库之前，使用解析库（如 `sqlparse`）强制校验其操作类型。
- **方案**：引入 `sqlparse` (通过 `pip install sqlparse`)。
- **逻辑**：解析 SQL 语句，提取语句类型。
- **白名单规则**：仅允许 `SELECT` 和 `EXPLAIN`。任何涉及 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER` 等的语句直接在本地拦截并报错。

### 3. 代码级别：正则匹配快速拦截 (Regex Filter)
作为 AST 拦截的补充或轻量替代方案，对生成的 SQL 字符串进行严格的正则匹配。
- **匹配范式**：禁止任何以 `DROP`、`DELETE`、`TRUNCATE`、`UPDATE` 等开头的语句。
- **监控告警**：拦截时记录审计日志，并在后台上报潜在的攻击行为。

### 4. 架构隔离：使用视图（Views）而非基础表
- **方案**：为 Agent 创建专门的只读视图。
- **效果**：屏蔽敏感字段，同时即使发生意外，攻击者也无法通过视图直接破坏物理表结构。

### 5. 加强 Prompt 工程 (Improved Prompting)
- 在 System Prompt 中加入更明确的「拒绝策略」和「安全守则」。
- 加入 Few-shot 示例，向 LLM 展示如何安全地编写查询以及如何拒绝危险请求。

---

## 📎 实施建议
建议优先实施 **只读数据库账号**（物理层防线）与 **代码层面的 SQL 语句类型硬检查**（逻辑层防线）。两者结合可提供极高的安全水位。

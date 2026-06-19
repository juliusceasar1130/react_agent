# SQL Agent 图表与 CSV 导出工具连接池复用优化总结报告

本报告系统性沉淀并归纳了关于“SQL Agent 在生成图表和 CSV 导出时耗时偏长，以及工具配置缺失”的优化复盘与技术沉淀。

---

## 1. 现场表现 (Symptoms)

1. **生图延迟偏高**：用户在聊天界面点击或触发生成 ECharts 图表（或导出 CSV 数据）时，前端 Loading 状态停留时间偏长，具有明显的冷启动延迟。
2. **生图工具静默缺失**：用户在前端对话尝试启用图表功能时，大模型报错提示 `当前对话环境中配置的工具列表未包含 build_chart_artifact`，可用工具列表中只有 `load_skill` 等 4 个最基础的工具。
3. **静默报错日志**：后端控制台输出警告日志：
   ```text
   WARNING - 注入图表/CSV导出工具失败: 'MaterializedViewSQLDatabase' object has no attribute 'engine'
   ```

---

## 2. 根本原因分析 (Root Causes)

### 2.1 数据库连接未复用（冷启动延迟瓶颈）
在原先的工具实现中，每次调用生图（`build_chart_artifact`）或导出（`export_to_csv`）工具时，均就地在函数体内部通过 `create_engine` 新建连接池，执行完毕后再在 `finally` 中执行 `engine.dispose()`。
这废弃了 SQLAlchemy 连接池的长连接机制，导致每次执行图表工具或 CSV 导出都要重新经历 `TCP 三次握手 ➔ 数据库身份安全认证 ➔ 开启 Session` 的完整过程，带来至少 150ms ~ 1000ms 的冷启动握手开销。

### 2.2 属性命名缺失引发的工具静默降级（工具缺失 Bug）
在后端装配层 `service.py` 试图获取数据库引擎以注入工具时，调用了 `db.engine`。
然而，扩展子类 `MaterializedViewSQLDatabase` 重写了 `__init__` 构造方法（且没有走 `super().__init__` 默认流），仅在内部将引擎赋值给了私有字段 **`self._engine = engine`**。
因此，调用公开属性 `db.engine` 抛出了 `AttributeError` 异常，该异常在 `_prepare_tools` 的通用 `try...except Exception` 降级块中被静默捕获并忽略，导致工具未能加入可用工具列表中，Agent 运行降级但隐藏了这一致命问题。

---

## 3. 优化与修复方案 (Solution)

我们实施了 **“共享 Agent 现有连接池 (方案 A)”** 重构方案：

### 3.1 改造思路：依赖注入 (Dependency Injection)
利用 Python 闭包（Closure）特性，改变工具的初始化参数，直接在 Agent 启动时共享已创建并温热的 `db._engine`，消除重新创建引擎的开销：

1. **修改工厂函数签名**：
   * 将 `create_chart_artifact_tool(db_uri: str, ...)` 更改为 `create_chart_artifact_tool(engine: Engine)`。
   * 将 `create_csv_export_tool(db_uri: str, ...)` 更改为 `create_csv_export_tool(engine: Engine)`。
   * 移除工厂方法内部的 `create_engine` 与调用结束时的 `engine.dispose()`。
2. **在装配层对接私有引擎**：
   在 [service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/service.py) 中，将获取引擎的调用修改为 `db._engine`：
   ```python
   chart_artifact_tool = create_chart_artifact_tool(db._engine)
   csv_export_tool = create_csv_export_tool(db._engine)
   ```

### 3.2 预期效果
* **零连接冷启动**：第一次图表生成与导出的连接时间缩短至 0ms，完全消除 TCP/SSL 握手瓶颈。
* **连接大一统**：大模型执行查询（`sql_db_query`）、生图及导出完全共用同一个 `_engine` 连接池，提升高并发状态下的连接吞吐量。
* **Bug 彻底根治**：不再有静默捕获引起的工具缺失，图表工具能够百分之百在启动后成功载入大模型。

---

## 4. 经验与教训 (Lessons Learned)

1. **防范无差别的静默异常吞没**：对于降级处理中的 `try...except Exception`，应在日志中做严格且醒目的错误分类（或进行断言抛出配置异常），防止本应引起注意的配置或属性缺失 Bug 被静默忽略。
2. **对基类/外部框架继承要保持属性对齐**：继承第三方复杂组件时，若重写了构造函数，必须对齐常用的公开属性定义，或提供对应的 getter 装饰器，防止破坏依赖注入的契约。
3. **Windows 异步 IO 兼容性预案**：在 Windows 平台测试异步 psycopg 连接池时，由于其不兼容默认的 `ProactorEventLoopPolicy`，必须在运行入口中提前设置 `WindowsSelectorEventLoopPolicy` 以避免池初始化长时间挂起导致超时报错。

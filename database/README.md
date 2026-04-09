# Database Snapshots

更新时间：2026-04-09 Asia/Shanghai

本目录用于保存便于后续分析的数据库结构快照文件。

当前文件：

- `defect_db_schema_snapshot.json`：`defect_db` 中 5 张业务表的字段结构快照

来源说明：

- 数据源数据库：`defect_db`
- 数据源 schema：`public`
- 表范围：`history`、`history_detail`、`history_extras`、`history_station`、`history_tokens`

用途说明：

- 方便后续进行字段分析、建模、文档整理与 SQL 规则编写
- 作为项目内可追踪的本地结构快照，不依赖实时连接数据库

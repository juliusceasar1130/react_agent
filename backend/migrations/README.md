# 数据库迁移脚本

## 概述

本目录包含数据库迁移脚本，用于设置和配置向量存储所需的数据库结构。

## 迁移脚本列表

### `000_enable_pgvector.sql`

**用途**: 启用 pgvector 扩展

**说明**:
- 这是**唯一需要手动执行**的数据库迁移脚本
- 官方 LangChain PGVector 会自动创建所需的表结构
- 但 pgvector 扩展需要手动启用（需要超级用户权限）

**执行时机**: 
- 首次部署前
- 新数据库环境初始化时

**执行方式**:
```bash
psql -U your_user -d your_database -f 000_enable_pgvector.sql
```

或使用 Docker exec（如果使用 Docker）：
```bash
docker exec -it <容器名> psql -U your_user -d your_database -f /path/to/000_enable_pgvector.sql
```

## 官方 PGVector 自动创建的表

首次初始化 `PgVectorStoreWrapper` 时，官方 LangChain PGVector 会自动创建以下表：

### `langchain_pg_collection`
存储 collection 元数据
- `uuid` (UUID, PRIMARY KEY)
- `name` (VARCHAR, UNIQUE) - collection 名称
- `cmetadata` (JSONB) - collection 级别的元数据

### `langchain_pg_embedding`
存储向量和文档
- `uuid` (UUID, PRIMARY KEY)
- `collection_id` (UUID, FOREIGN KEY) - 关联到 collection
- `embedding` (vector) - 向量数据
- `document` (TEXT) - 文档内容
- `cmetadata` (JSONB) - 文档元数据
- `custom_id` (VARCHAR) - 自定义 ID

**注意**: 无需手动创建这些表，官方会自动处理。

## 已废弃的迁移脚本

### `001_create_vector_tables.sql` (已删除)

**状态**: ⚠️ 已废弃并删除

**原因**: 
- 该脚本创建的是自定义表结构 (`vector_documents`)
- 与官方 LangChain PGVector 的表结构不兼容
- 已迁移到使用官方自动创建机制

**处理**: 已删除，不再需要手动创建表。

## 迁移历史

- **2024-12-19**: 移除 `001_create_vector_tables.sql`，改用官方自动创建机制
- **2024-12-19**: 更新 `000_enable_pgvector.sql`，添加详细说明

## 相关文档

- `MIGRATION_GUIDE.md` - 迁移指南
- `MIGRATION_COMPLETED.md` - 迁移完成报告

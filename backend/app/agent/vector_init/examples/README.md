# 示例数据文件

本目录包含用于测试向量库数据导入功能的示例 JSON 文件。所有示例文件都遵循开发方案中定义的标准格式。

## 标准数据格式

所有 JSON 文件必须遵循以下格式：

```json
[
  {
    "document": "文档的完整文本内容，用于向量化检索",
    "type": "documentation" | "ddl" | "sql_example",
    "domain": "业务域（可选）"
  },
  {
    "document": "DDL语句",
    "type": "ddl",
    "table_name": "表名"
  }
]
```

**字段说明**：
- `document`: **必需**，文档的完整文本内容，用于向量化（默认字段名）
- `type`: **必需**，文档类型，必须是以下三种之一：
  - `"documentation"`: 文档类型
  - `"ddl"`: DDL类型（数据库表结构定义）
  - `"sql_example"`: SQL示例类型
- `domain`: 可选，业务域
- 其他字段根据类型自由定义（所有字段都会被作为元数据存储）

## 文件说明

### 1. `example_documentation.json` - 文档类型示例

**用途**: 展示 `documentation` 类型的数据格式

**数据格式**:
- `document`: 文档内容（必需）
- `type`: `"documentation"`（必需）
- `domain`: 业务域（如 "finance", "sales"）
- `metadata`: 嵌套的元数据对象（兼容旧格式）
  - `term`: 术语名称
  - `aliases`: 别名列表
  - `description`: 描述信息

**示例数据**:
- 包含 5 条业务术语文档
- 涵盖财务、销售等业务域
- 包含术语定义、别名等信息

**导入命令**:
```bash
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_documentation.json
```

### 2. `example_sql_example.json` - SQL示例类型

**用途**: 展示 `sql_example` 类型的数据格式

**数据格式**:
- `document`: 问题和SQL查询的完整文本（必需）
- `type`: `"sql_example"`（必需）
- `metadata`: 嵌套的元数据对象
  - `sql`: SQL查询语句
  - `complexity`: 复杂度（"low" | "medium" | "high"）
  - `domain`: 业务域
  - `description`: 问题描述
  - `keywords`: 关键词列表

**示例数据**:
- 包含 5 条SQL查询示例
- 涵盖环比增长率、客户留存率、商品排名等场景
- 包含不同复杂度的SQL查询

**导入命令**:
```bash
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_sql_example.json
```

### 3. `example_ddl.json` - DDL类型示例

**用途**: 展示 `ddl` 类型的数据格式

**数据格式**:
- `document`: DDL语句（CREATE TABLE等）（必需）
- `type`: `"ddl"`（必需）
- `metadata`: 嵌套的元数据对象
  - `table_name`: 表名
  - `domain`: 业务域
  - `schema`: 数据库模式（如 "public"）
  - `description`: 表描述
  - `indexes`: 索引列表（可选）
  - `constraints`: 约束列表（可选）

**示例数据**:
- 包含 5 个数据库表的DDL定义
- 涵盖订单、客户、商品、分类、订单明细等核心业务表
- 包含完整的表结构、索引、外键约束等信息

**导入命令**:
```bash
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_ddl.json
```

## 使用示例

### 示例 1: 导入文档类型数据（追加模式）

```bash
# 从项目根目录运行
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_documentation.json
```

### 示例 2: 指定集合名称和覆盖模式

```bash
# 使用 --collection-name 指定集合名称，--overwrite 清空集合后重新导入
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_sql_example.json \
    --collection-name business_knowledge \
    --overwrite
```

### 示例 3: 导入DDL数据

```bash
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_ddl.json
```

### 示例 4: 使用不同的内容字段名

如果 JSON 文件使用其他字段名称（如 `content` 而不是 `document`）：

```bash
python -m backend.app.agent.vector_init.import_data \
    data.json \
    --content-field content
```

## 数据格式要求

1. **JSON 格式**: 必须是有效的 JSON 数组
2. **数组元素**: 每个元素必须是一个对象
3. **document 字段**: 必需，字符串类型，包含文档的完整文本内容
4. **type 字段**: 推荐，用于区分文档类型（"documentation"、"ddl"、"sql_example"）
5. **元数据值**: 必须是可序列化的（字符串、数字、布尔值、列表、对象）

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `json_file` | 要导入的 JSON 文件路径（必需） | - |
| `--collection-name` | 向量集合名称 | `rag_store` |
| `--pg-connection-string` | PostgreSQL 连接字符串 | `DATABASE_URL` 环境变量 |
| `--nvidia-api-key` | NVIDIA API Key | `NVIDIA_API_KEY` 环境变量 |
| `--embedding-model` | Embedding 模型名称 | `baai/bge-m3` |
| `--content-field` | JSON 文件中内容字段的名 | `document` |
| `--metadata-fields` | 指定用作元数据的字段列表 | 除 document 字段外的所有字段 |
| `--batch-size` | 批量导入大小 | 100 |
| `--overwrite` | 覆盖模式：清空集合后重新导入 | False |
| `--encoding` | JSON 文件编码 | `utf-8` |

## 环境变量要求

- `DATABASE_URL`: PostgreSQL 数据库连接字符串（格式：`postgresql+psycopg://user:password@host:port/database`）
- `NVIDIA_API_KEY`: NVIDIA API Key 用于生成向量嵌入

## 三种类型说明

### 1. documentation 类型
用于存储业务术语、概念说明等文档内容。

**典型用途**:
- 业务术语定义
- 概念说明文档
- 知识库文档

**推荐字段**:
- `document`: 文档内容
- `type`: `"documentation"`
- `term`: 术语名称
- `domain`: 业务域
- `aliases`: 别名列表
- `description`: 详细描述

### 2. ddl 类型
用于存储数据库表结构定义（DDL语句）。

**典型用途**:
- CREATE TABLE 语句
- ALTER TABLE 语句
- 表结构说明

**推荐字段**:
- `document`: DDL语句
- `type`: `"ddl"`
- `table_name`: 表名
- `domain`: 业务域
- `schema`: 数据库模式
- `description`: 表描述
- `indexes`: 索引列表
- `constraints`: 约束列表

### 3. sql_example 类型
用于存储SQL查询示例和问题解答。

**典型用途**:
- SQL查询示例
- 问题解答（FAQ）
- 查询模板

**推荐字段**:
- `document`: 问题和查询的描述
- `type`: `"sql_example"`
- `sql`: SQL查询语句
- `complexity`: 复杂度级别
- `domain`: 业务域
- `description`: 问题描述
- `keywords`: 关键词列表

## 注意事项

- 确保在导入前已正确配置 `DATABASE_URL` 和 `NVIDIA_API_KEY` 环境变量
- 默认内容字段为 `document`，使用其他字段名需用 `--content-field` 参数指定
- 默认导入模式为**追加模式**（不会清空表中原有数据），使用 `--overwrite` 参数可切换为覆盖模式
- 使用 `--overwrite` 参数会清空表中所有现有数据，谨慎使用
- 建议先用小数据集测试，确认格式正确后再导入大量数据
- 可以根据实际需求修改示例文件中的数据

## 参考文档

详细的数据格式说明请参考：
- `.tree/features/agent/backend/progresql_vector开发指南/create_vector_collection_example.py`

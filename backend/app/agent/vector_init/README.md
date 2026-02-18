# 向量库数据导入模块

本模块提供从 JSON 文件导入数据到向量库的功能。

## 功能特性

- ✅ 从 JSON 文件加载数据
- ✅ 自动转换为 LangChain Document 格式
- ✅ 批量导入，支持进度显示
- ✅ 灵活的元数据配置
- ✅ 支持自定义内容字段和元数据字段
- ✅ 支持覆盖模式（清空现有数据后重新导入）

## 项目说明

本项目的向量库统一使用 `rag_store` 数据集合，用于存储以下三种数据结构：

| 数据类型 | 用途 | 说明 |
|----------|------|------|
| **documentation** | 业务文档类型 | 存储业务术语、概念说明、知识库文档等 |
| **ddl** | DDL 类型 | 存储数据库表结构定义（CREATE TABLE 等语句） |
| **sql_example** | SQL 示例类型 | 存储 SQL 查询示例、问题解答（FAQ）、查询模板 |

这三种类型的数据通过 `type` 元数据字段进行区分，存储在同一个 `rag_store` 集合中，便于统一检索和管理。

## 目录结构

```
vector_init/
├── __init__.py          # 模块初始化
├── json_loader.py        # JSON 文件加载
├── data_importer.py      # 数据导入核心逻辑
├── import_data.py        # 主入口脚本
├── README.md            # 使用说明
└── examples/            # 示例数据文件
    ├── README.md        # 示例文件说明
    ├── example_documentation.json   # 文档类型示例 (documentation)
    ├── example_sql_example.json     # SQL示例类型 (sql_example)
    └── example_ddl.json             # DDL类型示例 (ddl)
```

## 使用方法

### 1. 命令行使用

```bash
# 基本用法（默认内容字段为 document）
python -m backend.app.agent.vector_init.import_data data.json

# 指定集合名称
python -m backend.app.agent.vector_init.import_data data.json --collection-name my_collection

# 覆盖模式（清空现有数据后重新导入）
python -m backend.app.agent.vector_init.import_data data.json --overwrite

# 指定内容字段（如果使用 content 而不是 document）
python -m backend.app.agent.vector_init.import_data data.json --content-field content

# 指定元数据字段
python -m backend.app.agent.vector_init.import_data data.json \
    --metadata-fields type domain category

# 指定批量大小
python -m backend.app.agent.vector_init.import_data data.json --batch-size 50

# 完整示例
python -m backend.app.agent.vector_init.import_data data.json \
    --collection-name my_collection \
    --overwrite \
    --batch-size 50
```

### 2. 编程方式使用

```python
from backend.app.agent.vector_init import load_json_data, import_data_to_vector_store

# 加载 JSON 数据
data = load_json_data("data.json")

# 导入到向量库
imported_count = import_data_to_vector_store(
    data=data,
    table_name="rag_store",
    content_field="document",  # 默认为 document
    metadata_fields=["type", "domain"],
    batch_size=100,
)

# 覆盖导入（清空现有数据）
imported_count = import_data_to_vector_store(
    data=data,
    table_name="rag_store",
    clear_existing=True,
)
```

## JSON 数据格式

JSON 文件必须是一个对象数组，每个对象至少包含一个内容字段（默认为 `document`）。

### 基本格式

```json
[
    {
        "document": "这是第一条文档的内容...",
        "type": "article",
        "domain": "technology"
    },
    {
        "document": "这是第二条文档的内容...",
        "type": "tutorial",
        "domain": "programming"
    }
]
```

### 嵌套 metadata 格式（兼容示例文件）

```json
[
    {
        "document": "文档内容",
        "metadata": {
            "type": "documentation",
            "domain": "finance",
            "term": "术语名"
        }
    }
]
```

### 自定义内容字段

如果使用自定义内容字段（例如 `content`），JSON 格式如下：

```json
[
    {
        "content": "这是第一条文档的内容...",
        "type": "article",
        "domain": "technology"
    }
]
```

对应的导入命令：

```bash
python -m backend.app.agent.vector_init.import_data data.json --content-field content
```

## 参数说明

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `json_file` | JSON 文件路径（必需） | - |
| `--collection-name` | 向量集合名称 | `rag_store` |
| `--pg-connection-string` | PostgreSQL 连接字符串 | 使用 `DATABASE_URL` 环境变量 |
| `--nvidia-api-key` | NVIDIA API Key | 使用 `NVIDIA_API_KEY` 环境变量 |
| `--embedding-model` | Embedding 模型名称 | `baai/bge-m3` |
| `--content-field` | 内容字段名 | `document` |
| `--metadata-fields` | 元数据字段列表 | 使用除内容字段外的所有字段 |
| `--batch-size` | 批量导入大小 | `100` |
| `--overwrite` | 覆盖模式：清空集合后重新导入 | `False` |
| `--encoding` | JSON 文件编码 | `utf-8` |

### 编程接口参数

#### `load_json_data()`

- `json_file_path`: JSON 文件路径
- `encoding`: 文件编码（默认: `"utf-8"`）
- `required_fields`: 必需字段列表（可选）

#### `import_data_to_vector_store()`

- `data`: 要导入的数据列表
- `table_name`: 向量集合名称（默认: `"rag_store"`）
- `pg_connection_string`: PostgreSQL 连接字符串（可选）
- `nvidia_api_key`: NVIDIA API Key（可选）
- `embedding_model`: Embedding 模型名称（默认: `"baai/bge-m3"`）
- `content_field`: 内容字段名（默认: `"document"`）
- `metadata_fields`: 元数据字段列表（可选）
- `batch_size`: 批量导入大小（默认: `100`）
- `clear_existing`: 是否清空现有数据（默认: `False`）
- `progress_callback`: 进度回调函数（可选）

## 环境配置

确保已配置以下环境变量：

- `DATABASE_URL`: PostgreSQL 连接字符串（格式：`postgresql+psycopg://user:password@host:port/database`）
- `NVIDIA_API_KEY`: NVIDIA API 密钥（用于 Embedding）

或在 `.env` 文件中配置：

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/database
NVIDIA_API_KEY=your_api_key_here
```

## 注意事项

1. **数据格式**: JSON 文件必须是对象数组格式
2. **内容字段**: 默认查找 `document` 字段，如需使用其他字段请用 `--content-field` 指定
3. **元数据字段**: 支持嵌套的 `metadata` 对象，会自动扁平化处理
4. **批量导入**: 根据数据量调整 `batch_size`，避免内存溢出
5. **覆盖模式**: 使用 `--overwrite` 会清空表中所有现有数据，请谨慎使用

## 示例数据

本模块提供了多个示例数据文件，位于 `examples/` 目录下：

- **`example_documentation.json`**: 文档类型示例 (type: "documentation")
- **`example_sql_example.json`**: SQL示例类型 (type: "sql_example")
- **`example_ddl.json`**: DDL类型示例 (type: "ddl")

详细说明请参考 [examples/README.md](examples/README.md)。

## 使用示例

### 示例 1: 导入文章数据

```json
[
    {
        "document": "Python 是一种高级编程语言...",
        "title": "Python 简介",
        "category": "programming",
        "tags": ["python", "programming"]
    }
]
```

```bash
python -m backend.app.agent.vector_init.import_data articles.json \
    --metadata-fields title category tags
```

### 示例 2: 导入 SQL 示例数据（使用示例文件）

```bash
# 使用提供的示例文件
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_sql_example.json \
    --collection-name business_knowledge
```

### 示例 3: 导入 DDL 数据并覆盖

```bash
# 覆盖模式导入 DDL 数据
python -m backend.app.agent.vector_init.import_data \
    .tree/features/agent/backend/app/agent/vector_init/examples/example_ddl.json \
    --collection-name business_knowledge \
    --overwrite
```

## 故障排除

### 问题 1: 文件不存在

```
FileNotFoundError: JSON 文件不存在: data.json
```

**解决方案**: 检查文件路径是否正确

### 问题 2: JSON 格式错误

```
ValueError: JSON 格式无效: ...
```

**解决方案**: 检查 JSON 文件格式是否正确，可以使用 JSON 验证工具

### 问题 3: 缺少内容字段

```
WARNING: 数据项缺少内容字段 'document'，跳过
```

**解决方案**: 确保所有数据项都包含内容字段，或使用 `--content-field` 指定正确的字段名

### 问题 4: 数据库连接失败

```
ValueError: 未提供数据库连接字符串，请设置 DATABASE_URL 环境变量或传入 pg_connection_string 参数
```

**解决方案**: 检查 `DATABASE_URL` 环境变量是否正确配置

### 问题 5: NVIDIA API Key 未设置

```
ValueError: 未提供 NVIDIA_API_KEY，请设置环境变量或传入 nvidia_api_key 参数
```

**解决方案**: 检查 `NVIDIA_API_KEY` 环境变量是否正确配置

## 相关模块

- `backend.app.agent.utils.vector_store`: 向量库创建和配置
- `backend.app.agent.utils.pgvector_wrapper`: PgVector 包装器

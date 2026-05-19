# Data Dictionary Design Spec

## Goal

为用户提供前端数据字典页面，方便查看 `analytics_db` 中维度表的基础信息与术语定义，降低用户提问前的认知门槛，减少对 RAG 相似性检索的依赖。

## Scope

- `backend/app/api.py`
- `frontend/src/views/ChatView.vue`
- `frontend/src/api/dimensions.ts` [NEW]
- `frontend/src/components/DimensionTable.vue` [NEW]

## Architecture & Components

### 1. Backend: `GET /api/chat/dimensions/{table_name}`

**逻辑：**
- 接收 `table_name` 路径参数
- 使用 `analytics_database_url` 连接 PostgreSQL，执行 `SELECT * FROM {table_name}`
- 表格名白名单校验：仅允许 `carrier_types`, `process_areas`, `vehicle_body_types`, `vehicle_color_codes`, `vehicle_platforms`
- 返回上限受 `dimension_result_hard_limit`（默认 300 行）保护
- 返回格式：`{ "table_name": "...", "columns": [...], "rows": [...] }`
- 数据库连接使用 SQLAlchemy `create_engine` 按需创建（与 `chart_artifacts.py` / `csv_export_tool.py` 模式一致）

**白名单常量：**

```python
DIMENSION_TABLE_WHITELIST = frozenset({
    "carrier_types",
    "process_areas",
    "vehicle_body_types",
    "vehicle_color_codes",
    "vehicle_platforms",
})
```

**对应前端表名映射（用于中文显示）：**

```typescript
const TABLE_LABELS: Record<string, string> = {
  carrier_types: '载体类型',
  process_areas: '工艺区域',
  vehicle_body_types: '车型字典',
  vehicle_color_codes: '颜色字典',
  vehicle_platforms: '平台字典',
}
```

### 2. Frontend: Sidebar Tab Switch

在 `ChatView.vue` 侧边栏顶部（Workspace 标题行下方）增加两个 Tab：

```
[ 对话 ]  [ 数据字典 ]
```

- 默认选中"对话"
- 切换到"数据字典"时：侧边栏显示 5 张维度表的中文列表，主内容区显示占位提示"请选择一张表查看"
- 切换到"对话"时：恢复当前聊天布局
- 两个 Tab 状态互斥

### 3. Frontend: API Layer (`frontend/src/api/dimensions.ts`)

```typescript
export function getDimensionTableApi(tableName: string): Promise<DimensionTableData>
```

调用 `GET /rearch/api/chat/dimensions/${tableName}`。

### 4. Frontend: DimensionTable Component

- 接收 `DimensionTableData` prop
- 以 HTML table 渲染，表头显示列名，表体显示全部行数据
- 样式与现有前端设计系统一致（Tailwind CSS）
- 纯展示，无搜索/筛选/分页

## Data Flow

1. 用户点击侧边栏"数据字典" Tab → 侧边栏切换为表列表
2. 用户点击表名（如"工艺区域"） → 前端调用 `getDimensionTableApi('process_areas')`
3. 后端校验白名单 → 查询 analytics_db → 返回 `{table_name, columns, rows}`
4. 前端在主内容区以 DimensionTable 渲染全部行

## Error Handling

- **`ANALYTICS_DATABASE_URL` 未配置** → 后端返回 503 `{"detail": "Analytics database is not configured"}`
- **未在白名单内的表名** → 后端返回 400 `{"detail": "Table '{name}' is not in the dimension whitelist"}`
- **数据库连接失败** → 后端返回 500，前端 toast 提示"加载失败，请稍后重试"
- **表不存在（数据库返回错误）** → 后端返回 500，前端同上处理
- **空表（0 行）** → 正常返回空 rows，前端显示"该表暂无数据"

## API Contract

### Request

```
GET /api/chat/dimensions/{table_name}
```

### Response (200)

```json
{
  "table_name": "process_areas",
  "columns": ["process_area_name", "description", "sort_order"],
  "rows": [
    ["前处理", "预处理电泳前处理区域", 1],
    ["电泳", "电泳涂装区域", 2]
  ],
  "row_count": 2
}
```

### Response (400)

```json
{"detail": "Table 'unknown_table' is not in the dimension whitelist"}
```

## Testing & Verification

- 后端：验证白名单内 5 张表均返回 200 + 非空数据
- 后端：验证白名单外表名返回 400
- 前端：验证 Tab 切换正确，表列表显示正确
- 前端：验证点击表名正确加载并渲染数据表格

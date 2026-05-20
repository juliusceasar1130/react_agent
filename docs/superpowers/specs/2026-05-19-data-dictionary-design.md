# Data Dictionary Design Spec

> 修改时间: 2026-05-20
> 修改内容: 移除 Mock 降级（连接失败直接报错便于排查），白名单改用 .env DIMENSION_TABLES 配置

## Goal

为用户提供前端数据字典页面，方便查看 `analytics_db` 中维度表的基础信息与术语定义，降低用户提问前的认知门槛，减少对 RAG 相似性检索的依赖。

## Scope

- `backend/app/api.py` — 新增 `GET /api/chat/dimensions/{table_name}` 端点
- `frontend/src/api/dimensions.ts` [NEW] — 前端 API 层
- `frontend/src/components/DimensionTable.vue` [NEW] — 数据表格渲染组件
- `frontend/src/components/VariantB.vue` [NEW] — Bento 网格仪表盘 + 侧滑毛玻璃 Drawer 容器
- `frontend/src/views/ChatView.vue` — 重构为 VariantB 插槽装配，新增双击联动注入与 Toast

## Final Architecture: Variant B (Bento Grid + Slide-over Drawer)

经过三轮原型评估（A 极简 Tab / B Bento 抽屉 / C 分屏联动），最终选用**方案 B**作为正式产品化交互架构。

### 1. Backend: `GET /api/chat/dimensions/{table_name}`

**逻辑：**
- 接收 `table_name` 路径参数
- **白名单校验**：白名单从 `.env` 的 `DIMENSION_TABLES` 配置读取（逗号分隔），由 `settings.dimension_tables` 提供
- **数据库查询**：使用 `ANALYTICS_DATABASE_URL` 连接 PostgreSQL，执行 `SELECT * FROM "{table_name}"`
- **连接失败直接报错**：数据库未配置返回 503，连接/查询失败返回 500，不做降级，便于人员排查
- **行数限制**：受 `DIMENSION_RESULT_HARD_LIMIT`（默认 300 行）保护
- 数据库连接使用 SQLAlchemy `create_engine` 按需创建（与 `chart_artifacts.py` / `csv_export_tool.py` 模式一致）

**白名单来源（`.env`）：**

```
DIMENSION_TABLES='carrier_types,process_areas,vehicle_body_types,vehicle_color_codes,vehicle_platforms'
```

`config.py` 中 `settings.dimension_tables` 自动解析为 `set[str]`，若未配置则为空集。

### 2. Frontend: Bento Grid Dashboard (VariantB.vue)

**交互流程：**

1. 侧边栏保持纯聊天历史管理功能（无 Tab 切换）
2. 主区域右上角悬浮"📚 数据字典看板"按钮，点击进入 Bento 网格仪表盘
3. Bento 网格展示 5 张维度表的卡片：载体类型、平台、工艺区域、车型、颜色
4. 点击任意卡片 → 右侧滑出毛玻璃 Drawer 抽屉展示完整数据表格
5. 抽屉内加载 DimensionTable 组件，支持复制、双击注入等交互
6. 点击"返回对话"按钮或遮罩层关闭，返回聊天主视图

**对父组件暴露的接口（Slots + Emits）：**
- Slots: `sidebar-header-action`, `sidebar-chat-list`, `main-chat-area`
- Emit: `closeSidebar`, `dblclick-cell`

### 3. Frontend: API Layer (`frontend/src/api/dimensions.ts`)

```typescript
export interface DimensionTableData {
  table_name: string
  columns: string[]
  rows: (string | number)[][]
  row_count: number
}

export function getDimensionTableApi(tableName: string): Promise<DimensionTableData>
```

调用 `GET /api/chat/dimensions/${tableName}`。

### 4. Frontend: DimensionTable Component

- Props: `title`, `tableName`, `columns`, `rows`
- 以 HTML table 渲染，表头显示列名，表体显示全部行数据
- **一键复制**：每列标题旁有复制按钮，每行单元格 hover 时露出复制按钮，另有"复制表名"按钮
- **双击注入**：双击任意列标题或单元格触发 `dblclick-cell` 事件，将内容传递给父组件注入输入框
- NULL 值显示为 `NULL` 文本
- 复制成功触发全局 Mini Toast 反馈

### 5. Frontend: ChatView Integration

- 引入 VariantB 作为唯一容器组件，通过插槽注入侧边栏内容和聊天主区域
- **双击联动注入**：监听 `@dblclick-cell` 事件，将值插入 `<textarea>` 当前光标位置
  - 注入后触发 1 秒 `.input-glow` 呼吸灯蓝色微光动效
  - 触发毛玻璃 Transition Toast："已成功提取 "xxx" 并自动注入输入框！"
- 删除 Variant A/C 和 PrototypeSwitcher（原型阶段产物，已物理清理）

## Data Flow

1. 用户点击右上角"数据字典看板" → 主区域切换为 Bento 网格仪表盘
2. 用户点击 Bento 卡片（如"工艺区域字典"） → 右侧滑出毛玻璃 Drawer
3. VariantB 调用 `getDimensionTableApi('process_areas')`
4. 后端从 `.env` 读取白名单 → 校验 → 查询 analytics_db → 返回 `{table_name, columns, rows, row_count}`
5. 抽屉内 DimensionTable 渲染全部行数据
6. 用户双击单元格 → 事件冒泡到 ChatView → 注入输入框 → 触发动效 + Toast

## API Contract

### Request

```
GET /api/chat/dimensions/{table_name}
```

### Response (200)

```json
{
  "table_name": "process_areas",
  "columns": ["area_code", "area_name", "temperature_range", "manager", "description"],
  "rows": [
    ["PRE", "前处理/电泳", "28℃-32℃", "张工", "涂装最底层防腐处理区域..."],
    ["PVC", "涂胶区域", "22℃-25℃", "李工", "底盘防石击涂胶..."]
  ],
  "row_count": 5
}
```

### Response (400)

```json
{"detail": "Table 'unknown_table' is not in the dimension whitelist"}
```

### Response (503)

```json
{"detail": "Analytics database is not configured (ANALYTICS_DATABASE_URL)"}
```

## Error Handling

- **`DIMENSION_TABLES` 未配置** → 后端返回 503
- **`ANALYTICS_DATABASE_URL` 未配置** → 后端返回 503
- **数据库连接/查询失败** → 后端返回 500，日志记录详细错误
- **未在白名单内的表名** → 后端返回 400
- **空表（0 行）** → 正常返回空 rows，前端显示"该表暂无数据"
- **前端加载失败** → Drawer 内显示错误信息 + 重试按钮

## Component Tree

```
ChatView.vue
└── VariantB.vue (Bento 容器 + Drawer)
    ├── [slot: sidebar-header-action] — 新建按钮
    ├── [slot: sidebar-chat-list] — SessionList.vue
    ├── [slot: main-chat-area] — MessageList / WelcomeDashboard + 输入区
    └── DimensionTable.vue (抽屉内，按需加载)
```

## Deleted Files (原型阶段产物)

- `frontend/src/components/VariantA.vue` — 极简双 Tab 原型
- `frontend/src/components/VariantC.vue` — 左右分屏联动原型
- `frontend/src/components/PrototypeSwitcher.vue` — 三变体悬浮切换药丸

## Testing & Verification

- 后端：白名单内 5 张表均返回 200 + 非空数据
- 后端：白名单外表名返回 400
- 后端：数据库不可用时返回 503/500
- 前端：Bento 网格渲染正确，卡片点击滑出 Drawer
- 前端：DimensionTable 复制、双击注入功能正常
- 前端：TypeScript 编译零错误（`npx vue-tsc --noEmit`）

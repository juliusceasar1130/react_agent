# 业务场景技能与快捷直通查询 (Scenario Quick Direct Query) 设计与实施总纲

> **文档修改时间**: 2026-07-27  
> **归档位置**: `docs/skills/README.md`  
> **面向对象**: 开发者、系统架构师、前端/后端维护人员

---

## 一、 项目背景与设计动机 (Motivation)

在原有架构中，用户在首页选择场景时，请求会发送给 LLM Agent，由 Agent 进行意图识别、Skill 路由与 SQL 生成，最后通过流式 SSE 返回结果。

这种模式对于复杂开放式问答非常适用，但在处理固定查询（如“当前在制滞留车辆有多少”、“黑车顶缺陷对比”）时存在：
1. **响应延迟高**：依赖 LLM 推理耗时 3~10 秒；
2. **结果不确定**：LLM 吐出的 SQL 和回答可能产生随机波动；
3. **缺少直观操控**：无法提供结构化下拉筛选框、日期选择器、模板切换与毫秒级直通响应。

**解决方案**：建立与 LLM Agent 独立并存的**直通安全查询引擎 (Direct SQL Execution Path)**。绕过 LLM Agent 校验，通过解耦的模块直通执行场景模版 SQL，并在前端以**标准三栏 (3-Column) + 弹窗大屏 (ScenarioModal)** 提供极佳交互体验。

---

## 二、 架构设计与分层解耦 (Architecture)

### 2.1 系统全局架构图

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                     前端 UI 架构 (Vue 3)                                │
│  ┌──────────────────┐    ┌─────────────────────────────────┐    ┌───────────────────┐  │
│  │  左侧栏 Sidebar   │    │      中间主区 Center Area       │    │  右侧栏 Sidebar   │  │
│  │ (Session History)│    │ (Hero Search + Agent Skills Grid)│    │ (Scenario Cards)  │  │
│  └──────────────────┘    └─────────────────────────────────┘    └─────────┬─────────┘  │
│                                                                           │            │
│                                                               触发点击一键直通           │
│                                                                           ▼            │
│                                                          ┌──────────────────────────┐  │
│                                                          │ ⚡ ScenarioModal 弹窗页面 │  │
│                                                          │  - 多模板 Tab 切换       │  │
│                                                          │  - ParameterForm 动态表单│  │
│                                                          │  - Date / Select 控件    │  │
│                                                          │  - ResultRenderer (Table)│  │
│                                                          └────────────┬─────────────┘  │
│                                                                       │                │
├───────────────────────────────────────────────────────────────────────┼────────────────┤
│                                       RESTful API                     │                │
│   GET  /api/scenarios (按 is_direct_path_enabled 过滤)                │                │
│   GET  /api/scenarios/{domain}/{scenario}/params                      │                │
│   POST /api/scenarios/{domain}/{scenario}/execute ◄───────────────────┘                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                    后端引擎 (Python / FastAPI)                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐                  │
│  │   resolver.py    │ ──►│   executor.py    │ ──►│   formatter.py   │                  │
│  │(控件推断/日期支持)│    │ (命名绑定/SQL净化)│    │(Table/Scalar/Chart)│                 │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘                  │
│           │                       │                       │                            │
│           └───────────────────────┼───────────────────────┘                            │
│                                   ▼                                                    │
│                   skills.registry / skills.assets / models                             │
│                   (领域/场景三段解耦的物理模版与元数据)                                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、 后端直通引擎实现细节 (Backend)

### 3.1 核心模块架构 `backend/app/skills/direct_path/`

1. **`resolver.py` (参数解析层)**:
   - **控件推断 (`infer_widget`)**: 自动推断 `text`, `number`, `select`, `multiselect`, `date`, `daterange` 控件类型。
   - **动态选项查询 (`resolve_source_options`)**: 安全查询 `source_table` / `source_column` 去重值（如车种/平台代码），带 60s 内存缓存。
   - **配置化数据库连接**: 统一从 `backend.app.config.settings` 提取 `analytics_database_url`。

2. **`executor.py` (SQL 安全构建与执行层)**:
   - **模板加载 (`read_asset_text`)**: 读取场景下的 `sql/*.sql` 模板。
   - **动态 SQL 净化 (`build_executed_sql`)**: 对未赋值或空字符串参数在 SQL 中逐行裁剪，对有值参数使用命名变量绑定（`:param_name`），防 SQL 注入与 `--` 注释穿透。
   - **限制量控制**: 默认对全量查询取 `fetchmany(300)` 保护性能。

3. **`formatter.py` (结果格式化层)**:
   - 支持 `output_type="table"` 格式化为 `{type: "table", columns: [...], rows: [...], row_count: N}`。
   - 支持 `output_type="scalar"` 格式化为 `{type: "scalar", value: N, label: "..."}`。
   - 支持 `output_type="chart"` 格式化为 `{type: "chart", columns: [...], categories: [...], series: [...], rows: [...], row_count: N}`（用于多指标趋势与分布渲染）。

### 3.2 API 端点列表

- `GET /api/scenarios` — 获取全量领域直通场景分类树 (自动通过 `is_direct_path_enabled` 过滤掉纯 LLM 场景)；
- `GET /api/scenarios/{domain}/{scenario}/params` — 解析场景参数定义、默认值与 `sql_template_refs` 多模板信息；
- `POST /api/scenarios/{domain}/{scenario}/execute` — 接收参数输入，安全执行 SQL 查询并返回结构化结果。

---

## 四、 前端三栏与弹窗交互实现 (Frontend)

### 4.1 页面标准三栏布局 (Standard 3-Column Layout)

- **左侧栏 (Left Sidebar, `280px`)**: `SessionList.vue` 会话历史列表；
- **中间主区 (Center Main Area, `flex-1`)**: `WelcomeDashboard.vue` (Hero 搜索框 + AI Agent 问答能力矩阵卡片，全宽展示)；
- **右侧栏 (Right Sidebar, `320px~384px`)**: `ScenarioList.vue` (在首页 `!currentSession` 时展示，渲染为精致玻璃卡片入口)。

### 4.2 直通查询弹窗 (`ScenarioModal.vue`)

- **唤起逻辑**: 点击右侧栏场景卡片上的 **「⚡ 一键直通查询」** 按钮，触发唤起 `ScenarioModal.vue`；
- **大屏视觉 (`max-w-5xl` + 3D 毛玻璃遮罩)**:
  - 顶栏：场景标题 + 领域标签 + 关闭按钮 `✕`；
  - 模板 Tabs 切换条：若场景有多个 SQL 模板（如 `在制滞留车查询` 与 `历史滞留车查询`），提供优雅切换 Tabs；
  - 参数配置区 (`ParameterForm.vue`)：渲染推断出的 `TextWidget`, `NumberWidget`, `SelectWidget`, `MultiSelectWidget`, `DateWidget`；
  - 数据集展示区 (`ResultRenderer.vue` & `TableResult.vue`)：宽屏渲染 SQL 结果表，支持双击单元格值自动注入聊天框。

---

## 五、 今后二次开发与扩展指南 (Future Guidelines)

代码库中全量 12 个场景已统一升级为 **三段解耦结构 (Three-Block Architecture)**。

### 核心文档导航表

| 文档名称 | 对应适用场景 | 核心关注点 |
| :--- | :--- | :--- |
| 📖 **[scenario_architecture_spec.md](./scenario_architecture_spec.md)** | **场景技能二次开发 (SSoT 权威主规范)** | 三段解耦结构、`direct_path_enabled` 直通开关、SQL `:param` 命名绑定、防全表扫描避坑与二次开发 SOP |
| 📖 **[domain_skill_development_guide.md](./domain_skill_development_guide.md)** | **新增业务领域 (Domain) 开发指南** | `meta.py` 与 `DOMAIN_META` 编写、`domain.md` 全局业务上下文以及 `shared/` 共享资产规范 |
| 📖 **[registry_and_loading_mechanism.md](./registry_and_loading_mechanism.md)** | **注册中心与自动发现加载机制说明** | `discovery.py` 自动装配、`scope+path` 资产解析、智能体按需加载与快捷直通引擎双链路架构 |


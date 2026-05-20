# memory.md

## 项目长期约定

- 默认使用中文进行协作；必要时对关键术语补充英文。
- 代码修改优先遵循最小改动原则（minimal change）。
- 不确定项目约定时，先查阅现有文档与代码实现。
- 新增约定采用追加方式维护，不删除既有内容。

## 项目环境

- 本项目默认环境为：`conda activate py312_agent`。

## 文档维护约定

- `README.md` 用于记录项目主要特性与项目文件结构变更。
- `changelog.md` 用于记录新特性、重要优化以及其他重要修改说明。
- 每个优化或重要变更记录时，头部应注明优化时间和简要概括。
- 若项目根目录不存在 `changelog.md`，则应新建。

## 协作与修改记录偏好

- 修改完成后，应明确说明修改时间与主要修改内容。
- 如果文件本身不适合写入修改记录，则在回复中列出修改时间与主要变更。
- 普通代码文件通常不建议加入仅用于记录历史的注释。

## 代码工作方式偏好

- 倾向于小步修改、可验证完成。
- 倾向于保持现有风格，而不是主动统一风格。
- 倾向于只处理与当前任务直接相关的改动。
- 若发现无关问题，可提示，但不默认顺手修复。

## 常用术语

- minimal change: 最小改动原则
- surgical changes: 外科手术式修改，仅触达必要部分
- goal-driven execution: 以可验证目标驱动实施

## 待持续补充

- 项目特有术语
- 固定流程
- 目录职责
- 常见陷阱与历史决策

## 技术与文档约定

- 快速演进技术栈应优先参考官方文档与项目当前实现。
- 版本判断以项目依赖声明与锁文件为准。
- 文档 MCP 可作为官方文档与项目文档的优先入口。

## MCP Setup

- 已配置 LangChain docs MCP，用于查询 LangChain 官方文档。
- 已配置 Context7 MCP，用于查询通用第三方库文档。
- 已配置 chrome-devtools MCP，用于浏览器调试与前端问题排查。

## Documentation and Version Preference

- 文档查询优先使用 MCP，而不是依赖历史记忆。
- 版本判断以项目锁定依赖和现有代码实现为准。
- MCP 返回的内容主要用于补充文档与示例，不直接覆盖项目现状。

## 依赖管理

新增代码涉及第三方包的话，请更新requirements.txt

## 技能系统 (Skills) 开发约定

- **元数据驱动**：所有领域 (`meta.py`) 和场景 (`scenario.py`) 必须定义 `title` 和 `example_questions`。
- **目录发现**：场景技能通过 `backend/app/skills/domains/<domain>/scenarios/` 目录结构自动发现并加载，无需手动注册到中心化列表。
- **视觉标准**：前端仪表盘采用 **Arctic Glass** 风格。所有图标容器应适配 `bg-gradient-to-br` 与 `shadow-glow`。
- **详细指南**：参考 `docs/skills/guide.md`。

## 数据字典设计约定

- **方案 B 定案 (Variant B)**：正式选用 Bento 网格仪表盘 + 侧滑毛玻璃 Drawer 抽屉作为数据字典交互架构。A/C 变体及 PrototypeSwitcher 已物理清理。
- **白名单来源**：维度表白名单从 `.env` 的 `DIMENSION_TABLES` 配置读取（逗号分隔），由 `settings.dimension_tables` 提供。不在代码中硬编码。
- **连接失败直接报错**：数据库未配置或连接/查询失败直接返回 503/500，不做降级，便于人员排查。
- **双击联动注入 (Cell Double-Click Injection)**：双击维度表单元格或列名直接提取内容并注入到聊天输入框当前光标处，搭配 `.input-glow` 输入框呼吸聚焦蓝色微光动效及毛玻璃 Transition Toast。


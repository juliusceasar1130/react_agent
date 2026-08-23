# 主智能体系统提示词文件化解耦设计

- 日期: 2026-08-22
- 状态: 已评审（agy 评审通过，机制归 utils 为用户确认的修订）
- 范围: 后端 `backend/app/agent`，不涉及前端

## 1. 背景与目标

**现状**：

- 子智能体 `sql_domain_agent` 提示词已文件化：模板 `backend/app/agent/subagents/sql/base_system_prompt.md`，加载器 `SystemPromptLoader` 位于 `backend/app/agent/subagents/sql/prompts.py`（带缓存，`settings.debug` 下按 mtime 热重载），路径由 `settings.system_prompt_path`（env `SYSTEM_PROMPT_PATH`）配置，模板变量 `{dialect}` / `{top_k}` 经 `PromptTemplate` 渲染。
- 主智能体提示词硬编码在 `backend/app/agent/service.py` 第 528–545 行：`_build_agent_components()` 内联多行字符串 `main_system_prompt`（角色定位 + Task Delegation Protocol），无 loader、无配置项、无热重载，改动必须改代码走 CI。

**目标**：将主智能体提示词外置为 `.md` 模板文件，复用现有 loader 机制，新增正交配置项；同时按"机制 vs 内容"原则将通用 `SystemPromptLoader` 下沉为共享基础设施，保持子智能体提示词原位自治。

**非目标**：

- 不改造子智能体提示词的文件位置与渲染机制（`{dialect}`/`{top_k}` 仍走 `PromptTemplate`）。
- 不实现运行时零重启实时生效（见 §6 热重载语义）。
- 不为主提示词引入动态模板变量（当前无需求，避免 `PromptTemplate` 的花括号转义坑）。

## 2. 方案选型

经 agy 评审（Herdr 会话）与用户确认，采用 **Hybrid 分层 + 机制下沉 utils**：

| 层级 | 归属 | 理由 |
|------|------|------|
| 加载机制（`SystemPromptLoader`） | `backend/app/agent/utils/` | 被主/子两个 owner 共享的 cross-cutting 设施；`utils/` 已有同类先例（`llama_cpp_token_estimator.py` 等文件名=类名小写的支持类） |
| 主智能体提示词内容 | `backend/app/agent/prompts/`（纯资源目录） | 编排层资源；`prompts/` 空目录骨架已在 `docs/deepagent/refactoring_roadmap.md` Wave 1 预留 |
| 子智能体提示词内容 | `subagents/sql/` 原位不动 | 遵循 roadmap 确立的"子智能体自治包"约定，保持高内聚 |

放弃的选项：纯集中式 `agent/prompts/`（破坏子智能体封装边界）、仅抽文件不加配置（无法外部覆盖、与子智能体配置风格断层）。

## 3. 目标目录布局

```
backend/app/agent/
├── utils/
│   ├── system_prompt_loader.py   # 新建: SystemPromptLoader 类（自 subagents/sql/prompts.py:13-46 平移）
│   └── __init__.py              # 改: import + __all__ 增加 SystemPromptLoader
├── prompts/                      # 纯资源目录，无需 __init__.py
│   └── main_system_prompt.md     # 主智能体提示词模板（service.py:528-545 原样抽出）
└── subagents/sql/
    ├── prompts.py               # 改: 删除类定义，改 from ..utils import SystemPromptLoader
    └── base_system_prompt.md    # 原位不动
```

## 4. 文件级改动

### 4.1 `utils/system_prompt_loader.py`（新建）

自 `subagents/sql/prompts.py:13-46` 原样平移 `SystemPromptLoader` 类：文件存在性检查、mtime 监测、线程锁缓存、`settings.debug` 热重载。依赖仅 `logging`、`threading`、`pathlib`、`backend.app.config.settings`，无 SQL 耦合。

### 4.2 `utils/__init__.py`（修改）

```python
from .system_prompt_loader import SystemPromptLoader
# __all__ 增加 "SystemPromptLoader"
```

### 4.3 `prompts/main_system_prompt.md`（新建）

将 `service.py:528-545` 的 `main_system_prompt` 字符串原样迁入（角色定位 + 任务委派协议全文）。约束：

- 当前内容**不含任何 `{var}` 占位符**；
- 构建时**不走 `PromptTemplate`**（项目已知坑：JSON 示例花括号会被误解析为格式化占位符导致 `ValueError`；见 `docs/ask_user_question_design_pattern.md`）；
- 未来如需注入动态内容（如子智能体名称列表），用 `str.replace()` 精准替换，禁止全文 `format`。

### 4.4 `config.py`（修改）

在 `system_prompt_path`（现有第 55–59 行）旁新增正交配置项：

```python
# 主智能体系统提示词模板路径
main_system_prompt_path: str = os.getenv(
    "MAIN_SYSTEM_PROMPT_PATH",
    str(Path(__file__).resolve().parent / "agent" / "prompts" / "main_system_prompt.md"),
)
```

### 4.5 `subagents/sql/prompts.py`（修改）

- 删除 `SystemPromptLoader` 类定义；
- 改 `from backend.app.agent.utils import SystemPromptLoader`；
- 保留模块级单例 `_system_prompt_loader` 与 `_build_system_prompt()`（下游唯一引用 `service.py:31` 不变）；
- `load()` 返回纯模板字符串的行为不变，`_build_system_prompt` 继续走 `PromptTemplate` 渲染 `{dialect}`/`{top_k}`。

### 4.6 `service.py`（修改）

- 删除 528–545 行内联 `main_system_prompt` 字符串；
- 模块级新增（与 `subagents/sql/prompts.py` 同构）：

```python
from backend.app.agent.utils import SystemPromptLoader

_main_prompt_loader = SystemPromptLoader(settings.main_system_prompt_path)

def _build_main_system_prompt() -> str:
    """构建主智能体系统提示词（纯字符串，不经 PromptTemplate）。"""
    return _main_prompt_loader.load()
```

- `_build_agent_components()` 中 `main_system_prompt = _build_main_system_prompt()`。

无循环依赖：`system_prompt_loader.py` → `config`（低层）；`utils/__init__.py` 仅引入自身子模块。

## 5. 数据流与测试

**数据流**：`_build_agent_components()` → `_build_main_system_prompt()` → `SystemPromptLoader.load()`（缓存 + debug mtime 热重载）→ 纯字符串 → `create_deep_agent(system_prompt=...)`。

**现有测试兼容性**：`backend/tests/agent/test_agent_component_boundaries.py` 通过 `_build_agent_components()` 校验组件边界，默认路径正确即天然兼容，预期零改动。

**新增 `backend/tests/agent/test_prompt_loaders.py`**：

1. 默认 `main_system_prompt.md` 与 `base_system_prompt.md` 文件存在且可加载；
2. loader 缓存命中：同路径两次 `load()` 返回相同内容且不重读磁盘；
3. 文件缺失抛 `FileNotFoundError`；
4. `_build_main_system_prompt()` 结果包含委派协议锚点文本（如 "Task Delegation Protocol"、"sql_domain_agent"），防迁移截断。

**回归验证**：`pytest backend/tests` 全链路无回归；可选冒烟"查询底材车间在制车"正常路由（roadmap 冒烟金线）。

## 6. 热重载语义（文档表述基线）

mtime 热重载只在**重新调用 `_build_agent_components()`（即重新建图）**时触发。LangGraph 编译图常驻后，修改 `.md` 需重启进程才生效。changelog 与文档一律表述为"debug 模式重新建图时热加载"，**不**宣传"运行时零重启实时生效"。

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| re-export 遗漏破坏下游 import | 全库 grep 确认仅 `service.py:31` 引用 `subagents.sql.prompts._build_system_prompt`；改后跑边界测试 |
| 字符串迁移截断/改写 | 测试 4 锚点断言 + 全链路回归 |
| 热重载被误读为实时生效 | §6 固化表述，写进 changelog |
| `prompts/` 目录无 `__init__.py` 在部分打包/导入场景报错 | 本方案中 `prompts/` 仅作为按路径读取的资源目录，不作为 Python 包导入，无此风险 |

## 8. 实施顺序（建议 commit 边界）

1. `utils/system_prompt_loader.py` + `utils/__init__.py`（loader 下沉）
2. `subagents/sql/prompts.py` 改 import（re-export 兼容层）
3. `prompts/main_system_prompt.md` + `config.py` + `service.py`（主提示词外置）
4. 新增 `test_prompt_loaders.py` + 全链路回归

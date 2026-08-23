# 主智能体系统提示词文件化解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将主智能体系统提示词从 `service.py` 硬编码外置为 `.md` 模板文件并复用现有 loader 机制，同时把通用 `SystemPromptLoader` 下沉到 `agent/utils/` 作为共享基础设施。

**Architecture:** Hybrid 分层 + 机制下沉。加载器（机制）归 `utils/`，被主/子两个 owner 共享；主提示词内容归 `agent/prompts/`（纯资源目录）；子智能体提示词 `base_system_prompt.md` 原位不动。主提示词构建返回**纯字符串**，不走 `PromptTemplate`（规避 JSON 花括号误解析崩溃坑）。

**Tech Stack:** Python 3.12, LangChain `PromptTemplate`（仅子提示词用）, Pydantic Settings, pytest

## Global Constraints

- **最小改动原则**：仅触碰本计划列出的文件；不动 `subagents/sql/base_system_prompt.md` 的位置与渲染机制（`{dialect}`/`{top_k}` 仍走 `PromptTemplate`）。
- **主提示词禁用 `PromptTemplate`**：`main_system_prompt.md` 当前无任何 `{var}` 占位符；构建函数直接返回 `loader.load()` 纯字符串。未来需动态内容时用 `str.replace()` 精准替换，禁止全文 `format`。
- **热重载语义表述**：mtime 热重载只在重新调用 `_build_agent_components()`（重新建图）时触发；常驻编译图改 `.md` 需重启进程。changelog/文档一律表述为"debug 模式重新建图时热加载"，**不**写"运行时零重启实时生效"。
- **回归门禁命令**（从 `backend/` 目录运行）：`python -m pytest -m "not integration and not smoke"`，预期全绿。
- **提交门禁**：按项目约定（CLAUDE.md），**不得**自主 `git commit`；每个任务的 Step "Commit" 需在执行前获得用户允许，或由用户统一提交。下文 commit 步骤保留命令供用户执行。
- **测试运行环境**：`conda activate py312_agent`；pytest 配置在 `backend/pyproject.toml`（`testpaths=["tests"]`、`pythonpath=[".."]`），故所有 pytest 命令先 `cd backend`。

---

### Task 1: 将 SystemPromptLoader 下沉至 agent/utils/

**Files:**
- Create: `backend/app/agent/utils/system_prompt_loader.py`
- Modify: `backend/app/agent/utils/__init__.py`（增加 import 与 `__all__`）
- Modify: `backend/app/agent/subagents/sql/prompts.py`（删除类定义，改为 import，保留 re-export 与 `_build_system_prompt`）
- Test: `backend/tests/agent/utils/test_system_prompt_loader.py`

**Interfaces:**
- Consumes: `backend.app.config.settings`（`settings.debug`）
- Produces:
  - `SystemPromptLoader(template_path: str)` — 类；实例方法 `load(self, force_reload: bool = False) -> str`
  - `backend.app.agent.utils.SystemPromptLoader`（包级导出）
  - `backend.app.agent.subagents.sql.prompts.SystemPromptLoader`（兼容 re-export，与 utils 中为同一类）
  - `backend.app.agent.subagents.sql.prompts._build_system_prompt(db: MaterializedViewSQLDatabase) -> str`（保持不变，供 `service.py:31` 导入）

- [ ] **Step 1: 写失败测试**

Create `backend/tests/agent/utils/test_system_prompt_loader.py`:

```python
# backend/tests/agent/utils/test_system_prompt_loader.py
from backend.app.agent.utils import SystemPromptLoader
from backend.app.agent.utils.system_prompt_loader import SystemPromptLoader as _DirectLoader


def test_loader_class_exported_from_utils_package():
    """SystemPromptLoader 通过 utils 包导出，且与底层模块为同一类。"""
    assert SystemPromptLoader is _DirectLoader


def test_subagent_module_reexports_loader():
    """subagents.sql.prompts 兼容层仍导出 SystemPromptLoader（re-export 不破坏下游）。"""
    from backend.app.agent.subagents.sql.prompts import SystemPromptLoader as _SubLoader

    assert _SubLoader is SystemPromptLoader


def test_loader_reads_file_and_caches(tmp_path):
    """加载器读取文件内容并缓存；缺失文件抛 FileNotFoundError。"""
    f = tmp_path / "p.md"
    f.write_text("hello loader", encoding="utf-8")

    loader = SystemPromptLoader(str(f))
    first = loader.load()
    second = loader.load()
    assert first == "hello loader"
    assert second == first  # 命中缓存，返回同一字符串

    import pytest
    with pytest.raises(FileNotFoundError):
        SystemPromptLoader(str(tmp_path / "missing.md")).load()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/agent/utils/test_system_prompt_loader.py -v`
Expected: FAIL — `cannot import name 'SystemPromptLoader' from 'backend.app.agent.utils'`（`system_prompt_loader.py` 尚未创建）

- [ ] **Step 3: 创建 system_prompt_loader.py（原样平移类）**

Create `backend/app/agent/utils/system_prompt_loader.py`（内容取自 `subagents/sql/prompts.py:13-46`，去掉 SQL 相关依赖）:

```python
# backend/app/agent/utils/system_prompt_loader.py
import logging
import threading
from pathlib import Path

from backend.app.config import settings

logger = logging.getLogger(__name__)


class SystemPromptLoader:
    """系统提示词动态加载器，支持缓存和热重载。"""

    _lock = threading.Lock()

    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        self._cached_prompt: str = ""
        self._last_modified_time: float = 0.0

    def load(self, force_reload: bool = False) -> str:
        """加载提示词模板并返回（带缓存和热重载）。"""
        if not self.template_path.exists():
            raise FileNotFoundError(f"系统提示词模板文件不存在: {self.template_path}")

        mtime = self.template_path.stat().st_mtime
        should_reload = (
            not self._cached_prompt
            or force_reload
            or (settings.debug and mtime > self._last_modified_time)
        )

        if should_reload:
            with self._lock:
                if (
                    not self._cached_prompt
                    or force_reload
                    or (settings.debug and mtime > self._last_modified_time)
                ):
                    logger.info("加载系统提示词模板: %s", self.template_path)
                    self._cached_prompt = self.template_path.read_text(encoding="utf-8")
                    self._last_modified_time = mtime

        return self._cached_prompt
```

- [ ] **Step 4: 更新 utils/__init__.py 导出**

Modify `backend/app/agent/utils/__init__.py` — 在 import 块追加一行、在 `__all__` 追加一项：

```python
from .system_prompt_loader import SystemPromptLoader
```

`__all__` 增加：

```python
    "SystemPromptLoader",
```

- [ ] **Step 5: 改写 subagents/sql/prompts.py 为兼容层**

Replace the full content of `backend/app/agent/subagents/sql/prompts.py` with:

```python
# backend/app/agent/subagents/sql/prompts.py
import logging

from langchain_core.prompts import PromptTemplate

from backend.app.agent.utils import MaterializedViewSQLDatabase, SystemPromptLoader
from backend.app.config import settings

logger = logging.getLogger(__name__)

_system_prompt_loader = SystemPromptLoader(settings.system_prompt_path)


def _build_system_prompt(db: MaterializedViewSQLDatabase) -> str:
    """构建 Agent 系统提示词。"""
    template_str = _system_prompt_loader.load()
    template = PromptTemplate.from_template(template_str)
    return template.format(
        dialect=db.dialect,
        top_k=settings.sql_agent_top_k,
    )
```

（删除了不再使用的 `import threading` 与 `from pathlib import Path`；`SystemPromptLoader` 因本模块 import 而成为 re-export 名。）

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/agent/utils/test_system_prompt_loader.py -v`
Expected: PASS（3 tests）

- [ ] **Step 7: 运行边界测试确认无回归**

Run: `cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py -v`
Expected: PASS（该测试调 `_build_agent_components()`，`_build_system_prompt` 经新路径仍可构建）

- [ ] **Step 8: Commit（需用户允许）**

```bash
git add backend/app/agent/utils/system_prompt_loader.py backend/app/agent/utils/__init__.py backend/app/agent/subagents/sql/prompts.py backend/tests/agent/utils/test_system_prompt_loader.py
git commit -m "refactor(agent): 下沉 SystemPromptLoader 至 agent/utils 作为共享加载器"
```

---

### Task 2: 主智能体系统提示词外置为 .md + 配置项

**Files:**
- Create: `backend/app/agent/prompts/main_system_prompt.md`
- Modify: `backend/app/config.py:55-59`（新增 `main_system_prompt_path`）
- Modify: `backend/app/agent/service.py`（import、模块级 loader + `_build_main_system_prompt`、删除 528-545 内联串）
- Test: `backend/tests/agent/test_main_system_prompt.py`

**Interfaces:**
- Consumes: `backend.app.agent.utils.SystemPromptLoader`（Task 1 产出）; `backend.app.config.settings.main_system_prompt_path`
- Produces:
  - `backend.app.config.settings.main_system_prompt_path: str`
  - `backend.app.agent.service._build_main_system_prompt() -> str`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/agent/test_main_system_prompt.py`:

```python
# backend/tests/agent/test_main_system_prompt.py
from pathlib import Path

from backend.app.config import settings
from backend.app.agent.service import _build_main_system_prompt


def test_main_system_prompt_default_path_exists():
    """默认主提示词文件存在且非空。"""
    p = Path(settings.main_system_prompt_path)
    assert p.exists(), f"默认主提示词文件不存在: {p}"
    assert p.read_text(encoding="utf-8").strip()


def test_build_main_system_prompt_anchors():
    """主提示词构建结果包含委派协议锚点，防止迁移截断。"""
    result = _build_main_system_prompt()
    assert "sql_domain_agent" in result
    assert "Task Delegation Protocol" in result
    assert "search_db_value_lexicon" in result
    assert "AskUserQuestion" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/agent/test_main_system_prompt.py -v`
Expected: FAIL — `AttributeError: ... no attribute 'main_system_prompt_path'` 或 `cannot import name '_build_main_system_prompt'`（配置项与构建函数尚未创建）

- [ ] **Step 3: 创建主提示词模板文件**

Create `backend/app/agent/prompts/main_system_prompt.md`。内容为原 `service.py:528-545` 内联字符串的**运行时精确值**（相邻字符串字面量直接拼接、`\n` 为真实换行）:

```
你是一个企业级通用数据智能体编排助手。


当你收到用户关于数据库查询、数据统计分析、车间在制车数量、生成图表或导出 CSV 文件的请求时，请通过 task 工具委派给专门的 sql_domain_agent 数据库查询专家子智能体处理。


当你面临意图不明确、缺少关键前提条件或需要向用户进行参数/方案确认时，可以使用 AskUserQuestion 工具直接向用户发起结构化澄清与确认提问。

# 任务委派协议 (Task Delegation Protocol)
在通过 task 工具向 sql_domain_agent 委派任务时，必须严格遵守以下分工协议：

1. **主子职责分离**：
   - 描述中只传递用户的【业务目标】、【业务意图】、【业务过滤条件】（如车间名称、车型、时间范围）以及【期望产物格式】（如表格/图表）。
   - **严禁强行指定数据库物理表名、视图名或具体的 SQL 语法结构**（SQL 子智能体是专业的数据库分析专家，独占持有对应车间的领域技能与 Schema 自愈能力，不需要也不应当由你指定物理表/视图名）。

2. **自适应意图与探查授权**：
   - **确切需求**：若用户提供了明确确切的过滤参数（如 FIS 号、具体时间范围），精准转达业务参数。
   - **模糊/探索性需求**（如用户问题较宽泛、名称存疑或可能存在多种数据来源）：
     - 转达用户的核心业务意图；
     - **显式授权探查**：在 task 描述中补充提示："该需求属于探索性查询，请充分利用 search_db_value_lexicon 和物理词典工具探查数据库中数据的真实落地点与列值映射后再生成 SQL。"

对于日常问候、通用知识解答或普通文本问答，可以直接友好地回答用户。
```

> 注意：本文件**不含**任何 `{var}` 占位符，故构建函数不走 `PromptTemplate`。

- [ ] **Step 4: 新增 config 配置项**

Modify `backend/app/config.py` — 在 `system_prompt_path` 块（第 55-59 行）之后插入:

```python
    # 主智能体系统提示词模板路径
    main_system_prompt_path: str = os.getenv(
        "MAIN_SYSTEM_PROMPT_PATH",
        str(Path(__file__).resolve().parent / "agent" / "prompts" / "main_system_prompt.md"),
    )
```

- [ ] **Step 5: service.py 引入共享 loader 并替换内联串**

Modify `backend/app/agent/service.py`：

5a. 在既有 `from backend.app.agent.utils import (...)` 导入块（第 48-55 行）追加 `SystemPromptLoader`：

```python
from backend.app.agent.utils import (
    LlamaCppTokenEstimator,
    VllmTokenEstimator,
    MaterializedViewSQLDatabase,
    build_postgres_search_path_engine_args,
    ensure_windows_selector_loop,
    fetch_table_definitions_with_comments,
    SystemPromptLoader,
)
```

5b. 在模块级 `_MANAGED_AGENT_SERVICE = None`（第 68 行）之后新增:

```python
_main_prompt_loader = SystemPromptLoader(settings.main_system_prompt_path)


def _build_main_system_prompt() -> str:
    """构建主智能体系统提示词（纯字符串，不经 PromptTemplate 渲染）。"""
    return _main_prompt_loader.load()
```

5c. 将第 528-545 行的内联 `main_system_prompt = (...)` 多行字符串整块替换为:

```python
        main_system_prompt = _build_main_system_prompt()
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/agent/test_main_system_prompt.py -v`
Expected: PASS（2 tests）

- [ ] **Step 7: 运行边界测试确认组件装配无回归**

Run: `cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py -v`
Expected: PASS

- [ ] **Step 8: Commit（需用户允许）**

```bash
git add backend/app/agent/prompts/main_system_prompt.md backend/app/config.py backend/app/agent/service.py backend/tests/agent/test_main_system_prompt.py
git commit -m "feat(agent): 主智能体系统提示词外置为 .md 模板并支持 MAIN_SYSTEM_PROMPT_PATH 配置"
```

---

### Task 3: 全链路回归与 changelog 记录

**Files:**
- Modify: `changelog.md`（顶部追加条目）
- Test: 全量回归（无新测试文件）

**Interfaces:**
- Consumes: Task 1 + Task 2 全部产出
- Produces: 无（收尾）

- [ ] **Step 1: 新增/改动测试全量回归**

Run: `cd backend && python -m pytest tests/agent/test_main_system_prompt.py tests/agent/utils/test_system_prompt_loader.py tests/agent/test_agent_component_boundaries.py -v`
Expected: 全 PASS

- [ ] **Step 2: 全链路回归门禁**

Run: `cd backend && python -m pytest -m "not integration and not smoke"`
Expected: 全绿（与既有基线一致，无新增失败）

- [ ] **Step 3: 追加 changelog 条目**

Modify `changelog.md` — 在文件最顶部（第 1 行 `## 2026-08-21 ...` 之上）插入:

```markdown
## 2026-08-22 00:00 +08:00 - 主智能体系统提示词文件化解耦与加载器下沉 (`system_prompt_loader.py`, `service.py`, `config.py`) [BE]

### 变更内容

#### 1. SystemPromptLoader 下沉为共享基础设施 (`backend/app/agent/utils/system_prompt_loader.py`) [BE]
- 将原 `subagents/sql/prompts.py` 中的 `SystemPromptLoader` 平移至 `agent/utils/system_prompt_loader.py`，经 `utils/__init__.py` 包级导出。
- `subagents/sql/prompts.py` 改为从 `utils` 导入并保留 re-export，`_build_system_prompt` 行为不变，下游唯一引用（`service.py:31`）零改动。

#### 2. 主智能体提示词外置为 `.md` 模板 (`main_system_prompt.md`, `config.py`, `service.py`) [BE]
- 将 `service.py` 中硬编码的主智能体提示词（Task Delegation Protocol）原样外置至 `agent/prompts/main_system_prompt.md`。
- 新增 `main_system_prompt_path` 配置项（env `MAIN_SYSTEM_PROMPT_PATH`），与子智能体 `system_prompt_path` 正交。
- 主提示词构建走 `_build_main_system_prompt()` 纯字符串加载，**不经 `PromptTemplate`**，规避 JSON 花括号误解析风险。

#### 3. 热重载语义说明 [DOCS]
- mtime 热重载仅在重新建图（`_build_agent_components`）时触发；常驻编译图修改 `.md` 需重启进程生效，非"运行时零重启实时生效"。

---
```

> 条目时间以实际提交时刻为准；若与既有时间线冲突，执行时按当前本地时间微调。

- [ ] **Step 4: Commit（需用户允许）**

```bash
git add changelog.md
git commit -m "docs(changelog): 记录主智能体提示词外置与加载器下沉"
```

---

## Self-Review 备注

- **Spec 覆盖**：§3 布局 → Task 1/2 文件；§4.1 loader 下沉 → Task 1；§4.3 主提示词 `.md` + 不走 PromptTemplate → Task 2 Step 3/5；§4.4 config → Task 2 Step 4；§4.5 subagents 兼容层 → Task 1 Step 5；§4.6 service 精简 → Task 2 Step 5；§5 测试 4 项 → Task 1（loader 缓存/FileNotFound/同包导出）+ Task 2（默认路径存在/锚点）；§6 热重载表述 → Task 3 Step 3 changelog；§7 风险缓解 → 各任务 Step 7 边界测试 + Task 3 Step 2 全量门禁。
- **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码块与精确路径。
- **类型一致性**：`SystemPromptLoader`、`load(force_reload) -> str`、`_build_main_system_prompt() -> str`、`settings.main_system_prompt_path` 全篇一致；`main_prompt.py` 已按用户修订取消（主提示词构建直接落 `service.py` 模块级函数），无孤立引用。

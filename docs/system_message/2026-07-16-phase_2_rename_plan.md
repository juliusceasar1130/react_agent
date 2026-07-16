# Phase 2: Renaming & Code Rebranding Detailed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand SafeMergeSystemMiddleware to PromptCompilerMiddleware to reflect its role as the final system prompt assembly point, aligning the codebase with clean structural semantics.

**Architecture:** Rename safe_merge_middleware.py and test_safe_merge_middleware.py. Change the class name SafeMergeSystemMiddleware to PromptCompilerMiddleware, and update the exports in __init__.py and instantiation references in service.py.

**Tech Stack:** Python 3.12, pytest.

---

### Task 1: Rename implementation file and refactor class name

**Files:**
- Create: `backend/app/agent/middleware/prompt_compiler_middleware.py`
- Delete: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Copy and rename safe_merge_middleware.py to prompt_compiler_middleware.py**

Create a new file `backend/app/agent/middleware/prompt_compiler_middleware.py` containing the exact code from `safe_merge_middleware.py`, but rename the class from `SafeMergeSystemMiddleware` to `PromptCompilerMiddleware`.

The class definition and references should be updated as follows:

```python
# backend/app/agent/middleware/prompt_compiler_middleware.py
# Lines 86-91:
class PromptCompilerMiddleware(AgentMiddleware[CustomState]):
    """
    系统提示词与 RAG 背景知识终极编译合并中间件。
    """

    state_schema = CustomState
```

Also, update the logger prefix in `_modify_request`:
```python
        # Line 435:
        if rag_text:
            merged_content = f"{sys_text}\n\n{rag_text}{date_prompt}"
            new_system_message = SystemMessage(content=merged_content)
            logger.info("🛡️ PromptCompilerMiddleware: 状态化 RAG 消息合并完成。")
            return request.override(
                system_message=new_system_message,
                messages=filtered_messages
            )
```

- [ ] **Step 2: Delete safe_merge_middleware.py**

Delete the file `backend/app/agent/middleware/safe_merge_middleware.py` to prevent duplicate definitions in the same module.

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/middleware/prompt_compiler_middleware.py
git rm backend/app/agent/middleware/safe_merge_middleware.py
git commit -m "refactor: rename safe_merge_middleware to prompt_compiler_middleware"
```

---

### Task 2: Rename test file and adjust imports

**Files:**
- Create: `backend/app/agent/middleware/test_prompt_compiler_middleware.py`
- Delete: `backend/app/agent/middleware/test_safe_merge_middleware.py`

- [ ] **Step 1: Copy test_safe_merge_middleware.py to test_prompt_compiler_middleware.py and adjust imports**

Create a new test file `backend/app/agent/middleware/test_prompt_compiler_middleware.py` containing the exact tests from `test_safe_merge_middleware.py`, but change imports and instantiation from `SafeMergeSystemMiddleware` to `PromptCompilerMiddleware`.

```python
# backend/app/agent/middleware/test_prompt_compiler_middleware.py
# Lines 6-8:
from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
from backend.app.agent.state import CustomState

# And inside all test cases, instantiate it using:
# middleware = PromptCompilerMiddleware()
```

- [ ] **Step 2: Delete test_safe_merge_middleware.py**

Delete the old test file `backend/app/agent/middleware/test_safe_merge_middleware.py`.

- [ ] **Step 3: Run the new test suite to verify failures**

Since the package initialization exports (`__init__.py`) and service configurations (`service.py`) are not updated yet, running general tests will fail or raise import errors.
Run command:
`conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
Expected: PASS (if test imports directly from the file), or fail if we run general imports. Let's make sure it runs successfully since it imports directly.

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/middleware/test_prompt_compiler_middleware.py
git rm backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "refactor: rename test_safe_merge_middleware to test_prompt_compiler_middleware"
```

---

### Task 3: Update package exports and service instantiation

**Files:**
- Modify: `backend/app/agent/middleware/__init__.py`
- Modify: `backend/app/agent/service.py`

- [ ] **Step 1: Update package exports in middleware/__init__.py**

Modify `backend/app/agent/middleware/__init__.py` to import and export `PromptCompilerMiddleware` instead of `SafeMergeSystemMiddleware`:

```python
# backend/app/agent/middleware/__init__.py
# Replace lines 7 and 13:
from .prompt_compiler_middleware import PromptCompilerMiddleware

__all__ = [
    "SkillMiddleware",
    "BusinessRagMiddleware",
    "ContextWarningMiddleware",
    "PromptCompilerMiddleware",
]
```

- [ ] **Step 2: Update SQLAgentService initialization in service.py**

Modify `backend/app/agent/service.py` to import and instantiate the new compiler class:

```python
# backend/app/agent/service.py
# Line 38:
    PromptCompilerMiddleware,

# Line 633 & 770:
            middleware_list = [
                *call_limit_middlewares,
                summarization_middleware,
                SkillMiddleware(db),
                _create_context_warning_middleware(token_estimator),
                PromptCompilerMiddleware(),
            ]
```

- [ ] **Step 3: Run all backend tests to verify full integration**

Run command:
`conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
Expected: 20 passed.

Run general suite regression:
`conda activate py312_agent; python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/middleware/__init__.py backend/app/agent/service.py
git commit -m "refactor: update package exports and SQLAgentService middleware list to use PromptCompilerMiddleware"
```

---

## Self-Review

1. **Spec coverage:** The plan covers all renaming tasks, files, tests, package initialization, and service imports specified in `phase_2_rename_spec.md`.
2. **Placeholder scan:** Scanned. Complete code replacement blocks are shown. Exact python commands are present.
3. **Type consistency:** Checked. `PromptCompilerMiddleware` is used consistently across tests, exports, and class definitions.

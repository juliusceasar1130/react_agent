# Phase 2 详细设计规范 (Detailed Design Specification)
## 主题：类名及文件规范化重构 (Renaming & Code Rebranding)

本规范书定义了 **阶段 2：类名及文件规范化重构** 的具体修改细节，旨在将历史阶段的 `SafeMerge` 中间件重命名为 `PromptCompiler`（提示词编译器），消除过时职责所带来的代码歧义。

---

## 1. 物理文件重命名方案 (File Renaming)

需要重命名以下两个 Python 文件：

1.  **实现类文件**：
    - **旧路径**：`backend/app/agent/middleware/safe_merge_middleware.py`
    - **新路径**：[prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/prompt_compiler_middleware.py)
2.  **测试类文件**：
    - **旧路径**：`backend/app/agent/middleware/test_safe_merge_middleware.py`
    - **新路径**：[test_prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_prompt_compiler_middleware.py)

*(注：重命名时可先将文件拷贝至新文件，修改后再删除旧文件以保持版本控制平滑，避免 IDE 丢失历史)*

---

## 2. 代码重构细则 (Code Refactoring Details)

### 2.1 重构类名及内部日志 (在 `prompt_compiler_middleware.py` 中)
- 将类名 `SafeMergeSystemMiddleware` 统一变更为 `PromptCompilerMiddleware`。
- 将类文档注释进行相应更新，澄清其“静态+动态分区编译”的核心职责。
- 将日志输出前缀统一由 `🛡️ SafeMergeSystemMiddleware: ...` 改为 `🛡️ PromptCompilerMiddleware: ...`。

### 2.2 更新包初始化文件 ([__init__.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/__init__.py))
修改包入口以确保正常导出：
```python
# 旧导入与导出：
# from .safe_merge_middleware import SafeMergeSystemMiddleware
# 改为：
from .prompt_compiler_middleware import PromptCompilerMiddleware

__all__ = [
    "SkillMiddleware",
    "BusinessRagMiddleware",
    "ContextWarningMiddleware",
    "PromptCompilerMiddleware",  # 👈 更新此处
]
```

### 2.3 更新应用初始化服务 ([service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py))
*   **第 38 行左右**：将包导入 `SafeMergeSystemMiddleware` 变更为 `PromptCompilerMiddleware`。
*   **第 633 行与 770 行左右**：在中间件列表中，将 `SafeMergeSystemMiddleware()` 替换为 `PromptCompilerMiddleware()`：
```python
            middleware_list = [
                *call_limit_middlewares,
                summarization_middleware,
                SkillMiddleware(db),
                _create_context_warning_middleware(token_estimator),
                PromptCompilerMiddleware(),  # 👈 实例化重命名类
            ]
```

### 2.4 对齐单元测试类 ([test_prompt_compiler_middleware.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/middleware/test_prompt_compiler_middleware.py))
- 修改文件开头的模块导入：
  ```python
  from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
  ```
- 批量替换测试用例中所有的 `SafeMergeSystemMiddleware` 实例化调用为 `PromptCompilerMiddleware`。

---

## 3. 验收与验证 (Verification Plan)

1.  **运行单元测试**：
    运行新命名的测试用例，确保没有任何导入或重构错误：
    `conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
    **预期结果**：20 个用例全部 PASS。
2.  **验证 Agent 初始化编译**：
    运行 `python -m pytest` 对整个 agent 模块进行回归，验证 Graph 初始化与服务加载无报错。

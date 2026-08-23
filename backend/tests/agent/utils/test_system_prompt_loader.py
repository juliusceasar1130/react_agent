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

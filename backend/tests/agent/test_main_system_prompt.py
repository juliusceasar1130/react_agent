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

# backend/tests/agent/test_sampling_profile_loader.py
"""Sampling profile loader 单元测试。

覆盖 profile_loader 模块的公共函数与 fail-fast 校验，不涉及中间件或 LangGraph 运行时。
"""

import pytest

from backend.app.agent.config.profile_loader import (
    _load_profiles,
    apply_profile_to_model_settings,
    get_sampling_profile,
)

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_lru_cache():
    """每个用例前后清理 _load_profiles 的 lru_cache，防止跨用例污染。"""
    _load_profiles.cache_clear()
    yield
    _load_profiles.cache_clear()


@pytest.fixture(autouse=True)
def _default_effort_transport(monkeypatch):
    """统一默认 transport=top_level，避免开发机环境变量干扰存量用例。"""
    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "top_level")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _write_yaml(tmp_path, content: str) -> None:
    """在 tmp_path 下写 model_sampling_profiles.yaml 并清理缓存。"""
    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(content, encoding="utf-8")


# -----------------------------------------------------------------------------
# _load_profiles
# -----------------------------------------------------------------------------


def test_load_profiles_returns_both_modes(tmp_path, monkeypatch):
    """真实 YAML 加载后包含 thinking 和 fast 两个 profile。"""
    import backend.app.agent.config.profile_loader as pl

    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(
        """
thinking:
  top_level:
    temperature: 1.0
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level:
    temperature: 0.7
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()

    result = _load_profiles()
    assert "thinking" in result
    assert "fast" in result
    assert result["thinking"]["top_level"]["temperature"] == 1.0
    assert result["fast"]["top_level"]["temperature"] == 0.7


def test_load_profiles_missing_file_raises(tmp_path, monkeypatch):
    """文件缺失时抛 FileNotFoundError。"""
    import backend.app.agent.config.profile_loader as pl

    missing = tmp_path / "nonexistent.yaml"
    monkeypatch.setattr(pl, "_YAML_PATH", missing)
    _load_profiles.cache_clear()

    with pytest.raises(FileNotFoundError):
        _load_profiles()


def test_load_profiles_missing_profile_raises(tmp_path, monkeypatch):
    """缺少 thinking/fast 任一 profile 时抛 ValueError。"""
    import backend.app.agent.config.profile_loader as pl

    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(
        """
thinking:
  top_level: {}
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()

    with pytest.raises(ValueError, match="缺少 profile"):
        _load_profiles()


def test_load_profiles_unknown_section_raises(tmp_path, monkeypatch):
    """YAML 含未知段名时抛 ValueError。"""
    import backend.app.agent.config.profile_loader as pl

    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(
        """
thinking:
  top_level: {}
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: true
  unknown_section:
    key: value

fast:
  top_level: {}
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()

    with pytest.raises(ValueError, match="未知段"):
        _load_profiles()


# -----------------------------------------------------------------------------
# get_sampling_profile
# -----------------------------------------------------------------------------


def test_get_sampling_profile_true_returns_thinking(tmp_path, monkeypatch):
    """enable_thinking=True 返回 thinking profile。"""
    import backend.app.agent.config.profile_loader as pl

    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(
        """
thinking:
  top_level:
    temperature: 1.0
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level:
    temperature: 0.7
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()

    profile = get_sampling_profile(True)
    assert profile["top_level"]["temperature"] == 1.0


def test_get_sampling_profile_false_returns_fast(tmp_path, monkeypatch):
    """enable_thinking=False 返回 fast profile。"""
    import backend.app.agent.config.profile_loader as pl

    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(
        """
thinking:
  top_level:
    temperature: 1.0
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level:
    temperature: 0.7
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()

    profile = get_sampling_profile(False)
    assert profile["top_level"]["temperature"] == 0.7


def test_get_sampling_profile_returns_copy(tmp_path, monkeypatch):
    """修改返回 dict 不影响缓存（浅拷贝验证：最外层 key 不穿透）。"""
    import backend.app.agent.config.profile_loader as pl

    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(
        """
thinking:
  top_level:
    temperature: 1.0
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level: {}
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()

    profile = get_sampling_profile(True)
    # 浅拷贝：修改最外层 key 不应影响缓存
    profile["new_key"] = "should_not_exist"

    profile2 = get_sampling_profile(True)
    assert "new_key" not in profile2


# -----------------------------------------------------------------------------
# apply_profile_to_model_settings
# -----------------------------------------------------------------------------


def test_apply_profile_writes_top_level_params():
    """temperature/top_p/presence_penalty 写入 model_settings 顶层。"""
    model_settings: dict = {}
    profile = {
        "top_level": {
            "temperature": 1.0,
            "top_p": 0.95,
            "presence_penalty": 0.0,
        },
        "extra_body": {},
        "chat_template_kwargs": {},
    }
    apply_profile_to_model_settings(model_settings, profile)

    assert model_settings["temperature"] == 1.0
    assert model_settings["top_p"] == 0.95
    assert model_settings["presence_penalty"] == 0.0


def test_apply_profile_writes_extra_body_params():
    """top_k/repetition_penalty/min_p 写入 extra_body。"""
    model_settings: dict = {}
    profile = {
        "top_level": {},
        "extra_body": {
            "top_k": 20,
            "min_p": 0.0,
            "repetition_penalty": 1.0,
        },
        "chat_template_kwargs": {},
    }
    apply_profile_to_model_settings(model_settings, profile)

    assert model_settings["extra_body"]["top_k"] == 20
    assert "reasoning_effort" not in model_settings["extra_body"]


def test_apply_profile_writes_enable_thinking():
    """enable_thinking/reasoning_effort 写入 extra_body.chat_template_kwargs。"""
    model_settings: dict = {}
    profile = {
        "top_level": {},
        "extra_body": {},
        "chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "medium"},
    }
    apply_profile_to_model_settings(model_settings, profile)

    assert model_settings["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
    assert model_settings["extra_body"]["chat_template_kwargs"]["reasoning_effort"] == "medium"


def test_apply_profile_idempotent():
    """重复调用同一 profile 无副作用。"""
    model_settings: dict = {}
    profile = {
        "top_level": {"temperature": 1.0},
        "extra_body": {"top_k": 20},
        "chat_template_kwargs": {"enable_thinking": True},
    }
    apply_profile_to_model_settings(model_settings, profile)
    apply_profile_to_model_settings(model_settings, profile)

    assert model_settings["temperature"] == 1.0
    assert model_settings["extra_body"]["top_k"] == 20


def test_apply_profile_overrides_existing_values():
    """已有 model_settings 値被 profile 覆写。"""
    model_settings: dict = {"temperature": 0.5, "extra_body": {"top_k": 10}}
    profile = {
        "top_level": {"temperature": 1.0},
        "extra_body": {"top_k": 20},
        "chat_template_kwargs": {},
    }
    apply_profile_to_model_settings(model_settings, profile)

    assert model_settings["temperature"] == 1.0
    assert model_settings["extra_body"]["top_k"] == 20


# -----------------------------------------------------------------------------
# Phase 3: thinking_level 覆写
# -----------------------------------------------------------------------------

# YAML fixture 含 thinking_level_map（Phase 3 新增）
_YAML_WITH_MAP = """
thinking_level_map:
  low: low
  medium: medium
  high: xhigh

thinking:
  top_level:
    temperature: 1.0
  extra_body:
    top_k: 20
    reasoning_effort: medium
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level:
    temperature: 0.7
  extra_body:
    top_k: 20
  chat_template_kwargs:
    enable_thinking: false
"""


def _setup_yaml(tmp_path, monkeypatch, content: str = _YAML_WITH_MAP):
    """写入 YAML fixture 并 patch _YAML_PATH。"""
    import backend.app.agent.config.profile_loader as pl
    yaml_path = tmp_path / "model_sampling_profiles.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(pl, "_YAML_PATH", yaml_path)
    _load_profiles.cache_clear()


def test_load_profiles_contains_thinking_level_map(tmp_path, monkeypatch):
    """YAML 加载后含 thinking_level_map 且值正确。"""
    _setup_yaml(tmp_path, monkeypatch)
    result = _load_profiles()
    assert "thinking_level_map" in result
    assert result["thinking_level_map"]["low"] == "low"
    assert result["thinking_level_map"]["medium"] == "medium"
    assert result["thinking_level_map"]["high"] == "xhigh"


def test_load_profiles_unknown_section_still_raises_with_map(tmp_path, monkeypatch):
    """白名单跳过 thinking_level_map 后，真正的未知段仍会拋错。"""
    _setup_yaml(tmp_path, monkeypatch, _YAML_WITH_MAP + "  unknown_section:\n    key: value\n")
    with pytest.raises(ValueError, match="未知段"):
        _load_profiles()


def test_get_sampling_profile_with_thinking_level_high(tmp_path, monkeypatch):
    """thinking + high -> reasoning_effort=xhigh，其余参数不变。"""
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(True, thinking_level="high")
    assert profile["extra_body"]["reasoning_effort"] == "xhigh"
    assert profile["top_level"]["temperature"] == 1.0
    assert profile["extra_body"]["top_k"] == 20


def test_get_sampling_profile_with_thinking_level_low(tmp_path, monkeypatch):
    """thinking + low -> reasoning_effort=low。"""
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(True, thinking_level="low")
    assert profile["extra_body"]["reasoning_effort"] == "low"


def test_get_sampling_profile_thinking_level_none_defaults_medium(tmp_path, monkeypatch):
    """thinking + None -> reasoning_effort=medium（Phase 2 兼容）。"""
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(True, thinking_level=None)
    assert profile["extra_body"]["reasoning_effort"] == "medium"


def test_get_sampling_profile_fast_ignores_thinking_level(tmp_path, monkeypatch):
    """fast + high -> 不传 reasoning_effort（忽略传入值）。"""
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(False, thinking_level="high")
    assert "reasoning_effort" not in profile.get("extra_body", {})


def test_get_sampling_profile_map_missing_ignores_level(tmp_path, monkeypatch):
    """YAML 不含 map + thinking_level=high -> 不覆写，用 profile 默认 medium。"""
    _setup_yaml(tmp_path, monkeypatch, """
thinking:
  top_level:
    temperature: 1.0
  extra_body:
    reasoning_effort: medium
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level: {}
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""")
    profile = get_sampling_profile(True, thinking_level="high")
    assert profile["extra_body"]["reasoning_effort"] == "medium"


def test_get_sampling_profile_map_key_missing_skips(tmp_path, monkeypatch):
    """YAML 含 map 但缺键（只留 low/medium）+ thinking_level=high -> 不覆写。"""
    _setup_yaml(tmp_path, monkeypatch, """
thinking_level_map:
  low: low
  medium: medium

thinking:
  top_level: {}
  extra_body:
    reasoning_effort: medium
  chat_template_kwargs:
    enable_thinking: true

fast:
  top_level: {}
  extra_body: {}
  chat_template_kwargs:
    enable_thinking: false
""")
    profile = get_sampling_profile(True, thinking_level="high")
    assert profile["extra_body"]["reasoning_effort"] == "medium"


def test_get_sampling_profile_returns_deep_copy(tmp_path, monkeypatch):
    """嵌套段修改也不污染缓存（深拷贝验证）。"""
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(True, thinking_level="high")
    # 修改嵌套段
    profile["extra_body"]["reasoning_effort"] = "tampered"
    profile["extra_body"]["top_k"] = 999

    profile2 = get_sampling_profile(True, thinking_level="high")
    assert profile2["extra_body"]["reasoning_effort"] == "xhigh"
    assert profile2["extra_body"]["top_k"] == 20


# -----------------------------------------------------------------------------
# REASONING_EFFORT_TRANSPORT 传输位置开关
# -----------------------------------------------------------------------------

def test_get_sampling_profile_transport_ctk_default_medium(tmp_path, monkeypatch):
    """transport=chat_template_kwargs + thinking 默认 → medium 落在 ctk 段，extra_body 无残留。"""
    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "chat_template_kwargs")
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(True, thinking_level=None)
    assert profile["chat_template_kwargs"]["reasoning_effort"] == "medium"
    assert "reasoning_effort" not in profile["extra_body"]


def test_get_sampling_profile_transport_ctk_with_level(tmp_path, monkeypatch):
    """transport=chat_template_kwargs + thinking_level=high → xhigh 落在 ctk 段。"""
    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "chat_template_kwargs")
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(True, thinking_level="high")
    assert profile["chat_template_kwargs"]["reasoning_effort"] == "xhigh"
    assert "reasoning_effort" not in profile["extra_body"]


def test_get_sampling_profile_transport_ctk_fast_no_effort(tmp_path, monkeypatch):
    """transport=chat_template_kwargs + fast + level=high → 两段均不传 reasoning_effort。"""
    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "chat_template_kwargs")
    _setup_yaml(tmp_path, monkeypatch)
    profile = get_sampling_profile(False, thinking_level="high")
    assert "reasoning_effort" not in profile.get("extra_body", {})
    assert "reasoning_effort" not in profile.get("chat_template_kwargs", {})


def test_get_sampling_profile_invalid_transport_raises(tmp_path, monkeypatch):
    """REASONING_EFFORT_TRANSPORT 非法值 → fail-fast 抛 ValueError。"""
    monkeypatch.setenv("REASONING_EFFORT_TRANSPORT", "bogus")
    _setup_yaml(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="REASONING_EFFORT_TRANSPORT"):
        get_sampling_profile(True)

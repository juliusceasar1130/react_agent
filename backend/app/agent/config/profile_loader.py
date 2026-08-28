import yaml
from functools import lru_cache
from pathlib import Path
from typing import Any

_YAML_PATH = Path(__file__).resolve().parent / "model_sampling_profiles.yaml"

_VALID_SECTIONS = {"top_level", "extra_body", "chat_template_kwargs"}
_REQUIRED_PROFILES = {"thinking", "fast"}


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, dict[str, Any]]:
    """启动时一次性加载 YAML 配置并缓存。

    fail-fast: 文件缺失、profile 不全、含未知段时直接抛异常。
    """
    if not _YAML_PATH.exists():
        raise FileNotFoundError(f"采样参数配置文件不存在: {_YAML_PATH}")

    with open(_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError("采样参数配置文件为空")

    missing = _REQUIRED_PROFILES - set(data.keys())
    if missing:
        raise ValueError(f"采样参数配置缺少 profile: {missing}")

    for name, profile in data.items():
        if not isinstance(profile, dict):
            raise ValueError(f"profile '{name}' 必须是 dict")
        unknown = set(profile.keys()) - _VALID_SECTIONS
        if unknown:
            raise ValueError(
                f"profile '{name}' 含未知段: {unknown}，合法段: {_VALID_SECTIONS}"
            )

    return data


def get_sampling_profile(enable_thinking: bool) -> dict[str, Any]:
    """根据 enable_thinking 布尔值返回对应的采样参数组合。

    返回 dict(profile) 浅拷贝，防止调用方误改全局缓存。
    """
    profiles = _load_profiles()
    profile = profiles["thinking" if enable_thinking else "fast"]
    return dict(profile)


def apply_profile_to_model_settings(
    model_settings: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    """将采样参数组合按三段结构机械写入 model_settings（原地修改）。"""
    # top_level → model_settings[key]
    for k, v in profile.get("top_level", {}).items():
        model_settings[k] = v

    # extra_body → model_settings["extra_body"][key]
    if "extra_body" not in model_settings:
        model_settings["extra_body"] = {}
    for k, v in profile.get("extra_body", {}).items():
        model_settings["extra_body"][k] = v

    # chat_template_kwargs → model_settings["extra_body"]["chat_template_kwargs"][key]
    ctk = profile.get("chat_template_kwargs", {})
    if ctk:
        if "chat_template_kwargs" not in model_settings["extra_body"]:
            model_settings["extra_body"]["chat_template_kwargs"] = {}
        for k, v in ctk.items():
            model_settings["extra_body"]["chat_template_kwargs"][k] = v

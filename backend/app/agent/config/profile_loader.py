import copy
import logging
import os
import yaml
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_YAML_PATH = Path(__file__).resolve().parent / "model_sampling_profiles.yaml"

_VALID_SECTIONS = {"top_level", "extra_body", "chat_template_kwargs"}
_NON_PROFILE_KEYS = {"thinking_level_map"}
_REQUIRED_PROFILES = {"thinking", "fast"}

# reasoning_effort 传输位置：YAML 中统一声明在 extra_body 段，get_sampling_profile
# 按 REASONING_EFFORT_TRANSPORT 移到实际传输位置。
#   top_level             → 请求体顶层（ninfer 仅接受此位置；chat_template_kwargs 内非白名单键 400）
#   chat_template_kwargs  → 模板变量通道（vLLM ≤0.27.1 顶层不透传模板，仅 ctk 通道生效）
_VALID_EFFORT_TRANSPORTS = {"top_level", "chat_template_kwargs"}


def _get_effort_transport() -> str:
    """读取 REASONING_EFFORT_TRANSPORT（默认 top_level），非法值 fail-fast。"""
    transport = os.getenv("REASONING_EFFORT_TRANSPORT", "top_level").strip().lower()
    if transport not in _VALID_EFFORT_TRANSPORTS:
        raise ValueError(
            f"REASONING_EFFORT_TRANSPORT 非法值: {transport!r}，"
            f"合法值: {sorted(_VALID_EFFORT_TRANSPORTS)}"
        )
    return transport


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
        if name in _NON_PROFILE_KEYS:
            continue
        if not isinstance(profile, dict):
            raise ValueError(f"profile '{name}' 必须是 dict")
        unknown = set(profile.keys()) - _VALID_SECTIONS
        if unknown:
            raise ValueError(
                f"profile '{name}' 含未知段: {unknown}，合法段: {_VALID_SECTIONS}"
            )

    return data


def get_sampling_profile(
    enable_thinking: bool,
    thinking_level: str | None = None,
) -> dict[str, Any]:
    """根据 enable_thinking 返回对应 profile；thinking_level 存在时覆写 reasoning_effort。

    reasoning_effort 在 YAML 中统一声明于 extra_body 段，本函数按
    REASONING_EFFORT_TRANSPORT 将其移到实际传输位置（top_level=ninfer；
    chat_template_kwargs=vLLM ≤0.27.1）。

    返回 copy.deepcopy(profile) 深拷贝，防止调用方误改全局缓存（含嵌套段）。
    """
    profiles = _load_profiles()
    profile = profiles["thinking" if enable_thinking else "fast"]

    result = copy.deepcopy(profile)
    transport = _get_effort_transport()

    def _place_effort(effort: str) -> None:
        if transport == "chat_template_kwargs":
            result.setdefault("chat_template_kwargs", {})["reasoning_effort"] = effort
        else:
            result.setdefault("extra_body", {})["reasoning_effort"] = effort

    # extra_body 段声明的默认 effort 移到传输位置（top_level 时为原地 no-op）
    default_effort = result.get("extra_body", {}).pop("reasoning_effort", None)
    if default_effort is not None:
        _place_effort(default_effort)

    # thinking_level 仅对 thinking 档生效（fast 档不传 reasoning_effort，忽略传入值）
    if enable_thinking and thinking_level is not None:
        level_map = profiles.get("thinking_level_map")
        if level_map and thinking_level in level_map:
            _place_effort(level_map[thinking_level])
        # 若 map 缺失或缺键：跳过覆写（用 profile 默认值），不抛错

    return result


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


logger.info(
    "reasoning_effort 传输位置: %s（top_level=ninfer; chat_template_kwargs=vLLM ≤0.27.1）",
    _get_effort_transport(),
)

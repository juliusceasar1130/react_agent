"""
业务技能自动发现。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 新增基于目录约定的领域与场景自动发现
- 增加场景目录名、所属领域与资产路径的校验
- 为注册中心提供发现结果，替代手工 import/append
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from backend.app.skills.assets import DOMAINS_ROOT, resolve_asset_path
from backend.app.skills.models import ScenarioSkill


@dataclass(frozen=True)
class DiscoveredDomain:
    """自动发现到的领域定义。"""

    name: str
    meta: dict[str, Any]
    domain_dir: Path


def _should_skip_path(path: Path) -> bool:
    return path.name.startswith("_") or path.name == "__pycache__"


def _load_module_from_path(module_name: str, file_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法为模块创建导入规格: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_domains() -> dict[str, DiscoveredDomain]:
    """扫描并发现所有合法领域。"""
    discovered: dict[str, DiscoveredDomain] = {}

    for domain_dir in sorted(DOMAINS_ROOT.iterdir(), key=lambda item: item.name):
        if not domain_dir.is_dir() or _should_skip_path(domain_dir):
            continue

        meta_path = domain_dir / "meta.py"
        domain_doc_path = domain_dir / "domain.md"
        if not meta_path.exists():
            continue
        if not domain_doc_path.exists():
            raise ValueError(f"领域目录缺少 domain.md: {domain_dir}")

        module = _load_module_from_path(
            f"backend.app.skills.domains.{domain_dir.name}.meta",
            meta_path,
        )
        meta = getattr(module, "DOMAIN_META", None)
        if not isinstance(meta, dict):
            raise ValueError(f"领域元数据必须定义 DOMAIN_META: {meta_path}")

        domain_name = meta.get("name")
        if not isinstance(domain_name, str) or not domain_name:
            raise ValueError(f"领域元数据缺少合法 name: {meta_path}")
        if domain_name != domain_dir.name:
            raise ValueError(
                f"领域目录名与 DOMAIN_META['name'] 不一致: {domain_dir.name} != {domain_name}"
            )
        if domain_name in discovered:
            raise ValueError(f"发现重复领域名: {domain_name}")

        discovered[domain_name] = DiscoveredDomain(
            name=domain_name,
            meta=meta,
            domain_dir=domain_dir.resolve(),
        )

    return discovered


def discover_scenarios(domain: DiscoveredDomain) -> list[ScenarioSkill]:
    """扫描指定领域下的所有场景。"""
    scenarios_root = domain.domain_dir / "scenarios"
    if not scenarios_root.exists():
        return []

    discovered: list[ScenarioSkill] = []
    seen_names: set[str] = set()

    for scenario_dir in sorted(scenarios_root.iterdir(), key=lambda item: item.name):
        if not scenario_dir.is_dir() or _should_skip_path(scenario_dir):
            continue

        scenario_file = scenario_dir / "scenario.py"
        if not scenario_file.exists():
            raise ValueError(f"场景目录缺少 scenario.py: {scenario_dir}")

        module = _load_module_from_path(
            f"backend.app.skills.domains.{domain.name}.scenarios.{scenario_dir.name}.scenario",
            scenario_file,
        )
        scenario = getattr(module, "SCENARIO", None)
        if not isinstance(scenario, dict):
            raise ValueError(f"场景元数据必须定义 SCENARIO: {scenario_file}")

        scenario_name = scenario.get("name")
        if not isinstance(scenario_name, str) or not scenario_name:
            raise ValueError(f"场景元数据缺少合法 name: {scenario_file}")
        if scenario_name != scenario_dir.name:
            raise ValueError(
                "场景目录名与 SCENARIO['name'] 不一致: "
                f"{scenario_dir.name} != {scenario_name}"
            )
        if scenario.get("skill_name") != domain.name:
            raise ValueError(
                "场景 skill_name 与所属领域不一致: "
                f"{scenario.get('skill_name')} != {domain.name}"
            )
        if scenario_name in seen_names:
            raise ValueError(f"发现重复场景名: {domain.name}.{scenario_name}")

        scenario_payload = dict(scenario)
        scenario_payload.setdefault("parameters", {})
        scenario_payload.setdefault("sql_template_refs", [])
        scenario_payload.setdefault("script_refs", [])
        scenario_payload["scenario_root"] = str(scenario_dir.resolve())
        scenario_payload["domain_root"] = str(domain.domain_dir.resolve())

        typed_scenario = cast(ScenarioSkill, scenario_payload)
        for asset_ref in [
            *typed_scenario["sql_template_refs"],
            *typed_scenario["script_refs"],
        ]:
            resolve_asset_path(asset_ref, scenario=typed_scenario)

        discovered.append(typed_scenario)
        seen_names.add(scenario_name)

    return discovered

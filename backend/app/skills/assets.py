"""
业务技能资产读取工具。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 新增领域/场景外部资产路径解析
- 支持读取 SQL 模板、领域说明等文本资产
- 支持基于 `scope + path` 的场景/共享资产定位
"""

from pathlib import Path

from backend.app.skills.models import AssetRef, ScenarioSkill


SKILLS_ROOT = Path(__file__).resolve().parent
DOMAINS_ROOT = SKILLS_ROOT / "domains"


def read_text_file(file_path: Path) -> str:
    """读取文本文件。"""
    return file_path.read_text(encoding="utf-8").strip()


def _safe_resolve(base_dir: Path, relative_path: str) -> Path:
    target_path = (base_dir / relative_path).resolve()
    base_dir = base_dir.resolve()
    try:
        target_path.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"资产路径越界: base={base_dir}, path={relative_path}") from exc

    if not target_path.exists():
        raise FileNotFoundError(f"资产不存在: {target_path}")
    return target_path


def resolve_asset_path(asset_ref: AssetRef, *, scenario: ScenarioSkill) -> Path:
    """根据资产作用域解析绝对路径。"""
    scope = asset_ref["scope"]
    domain_root = Path(scenario["domain_root"])
    scenario_root = Path(scenario["scenario_root"])

    if scope == "scenario":
        base_dir = scenario_root
    elif scope == "shared":
        base_dir = domain_root / "shared"
    elif scope == "domain":
        base_dir = domain_root
    else:
        raise ValueError(f"不支持的资产 scope: {scope}")

    return _safe_resolve(base_dir, asset_ref["path"])


def read_asset_text(asset_ref: AssetRef, *, scenario: ScenarioSkill) -> str:
    """读取场景资产内容。"""
    return read_text_file(resolve_asset_path(asset_ref, scenario=scenario))

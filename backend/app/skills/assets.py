"""
业务技能资产读取工具。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增领域/场景外部资产路径解析
- 支持读取 SQL 模板、领域说明等文本资产
"""

from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parent
DOMAINS_ROOT = SKILLS_ROOT / "domains"


def resolve_asset_path(relative_path: str) -> Path:
    """将相对领域目录的资产路径解析为绝对路径。"""
    return (DOMAINS_ROOT / relative_path).resolve()


def read_asset_text(relative_path: str) -> str:
    """读取文本资产内容。"""
    asset_path = resolve_asset_path(relative_path)
    return asset_path.read_text(encoding="utf-8").strip()

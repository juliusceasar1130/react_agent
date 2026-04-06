"""
技能注册中心与加载器测试。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 覆盖领域/场景注册与文本加载
- 覆盖 `load_skill` / `load_scenario` 的辅助构造函数
- 补充 `realtime_area_body_count` 场景的注册与加载断言
"""

from types import SimpleNamespace

from backend.app.agent.tools.skill_tools import (
    _build_load_scenario_command,
    _build_load_skill_command,
)
from backend.app.skills import (
    SKILLS,
    get_scenario_by_name,
    get_skill_by_name,
    list_scenarios_by_skill,
    load_domain_content,
    load_scenario_content,
)


def _make_runtime(state: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(tool_call_id="test-call", state=state or {})


def test_skill_registry_returns_paint_shop_domain() -> None:
    domain = get_skill_by_name("paint_shop_vehicle_tracking")
    assert domain is not None
    assert domain["name"] == "paint_shop_vehicle_tracking"
    assert any("daily_area_body_count" in item for item in domain["scenario_summaries"])
    assert any(
        "realtime_area_body_count" in item for item in domain["scenario_summaries"]
    )


def test_scenario_registry_returns_daily_area_body_count() -> None:
    scenarios = list_scenarios_by_skill("paint_shop_vehicle_tracking")
    assert len(scenarios) == 2
    scenario = get_scenario_by_name(
        "paint_shop_vehicle_tracking",
        "daily_area_body_count",
    )
    assert scenario is not None
    assert scenario["title"] == "每日各区域车身数量统计"


def test_scenario_registry_returns_realtime_area_body_count() -> None:
    scenario = get_scenario_by_name(
        "paint_shop_vehicle_tracking",
        "realtime_area_body_count",
    )
    assert scenario is not None
    assert scenario["title"] == "实时各区域车身数量统计"


def test_domain_content_includes_scenario_summary() -> None:
    content = load_domain_content("paint_shop_vehicle_tracking")
    assert content is not None
    assert "## 可用场景摘要" in content
    assert "daily_area_body_count" in content
    assert "realtime_area_body_count" in content


def test_scenario_content_includes_sql_template() -> None:
    content = load_scenario_content(
        "paint_shop_vehicle_tracking",
        "daily_area_body_count",
    )
    assert content is not None
    assert "## SQL 模板示例" in content
    assert "COUNT(*) AS vehicle_count" in content


def test_realtime_scenario_content_includes_sql_template() -> None:
    content = load_scenario_content(
        "paint_shop_vehicle_tracking",
        "realtime_area_body_count",
    )
    assert content is not None
    assert "实时各区域车身数量统计" in content
    assert "COUNT(*) AS vehicle_count" in content


def test_legacy_skills_export_is_compatible() -> None:
    assert SKILLS
    assert SKILLS[0]["name"] == "paint_shop_vehicle_tracking"
    assert "content" in SKILLS[0]


def test_load_skill_command_updates_state() -> None:
    command = _build_load_skill_command(
        "paint_shop_vehicle_tracking",
        _make_runtime(),
    )
    assert command.update["skills_loaded"] == ["paint_shop_vehicle_tracking"]
    assert command.update["active_skill"] == "paint_shop_vehicle_tracking"


def test_load_scenario_requires_loaded_skill() -> None:
    command = _build_load_scenario_command(
        "paint_shop_vehicle_tracking",
        "daily_area_body_count",
        _make_runtime(),
    )
    message = command.update["messages"][0].content
    assert "请先使用 load_skill('paint_shop_vehicle_tracking')" in message


def test_load_scenario_command_updates_state() -> None:
    command = _build_load_scenario_command(
        "paint_shop_vehicle_tracking",
        "daily_area_body_count",
        _make_runtime({"skills_loaded": ["paint_shop_vehicle_tracking"]}),
    )
    assert command.update["scenarios_loaded"] == [
        "paint_shop_vehicle_tracking.daily_area_body_count"
    ]
    assert command.update["active_scenario"] == "daily_area_body_count"

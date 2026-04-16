"""
技能注册中心与加载器测试。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 覆盖领域/场景注册与文本加载
- 覆盖 `load_skill` / `load_scenario` 的辅助构造函数
- 补充 `realtime_area_body_count` 场景的注册与加载断言
- 覆盖自动发现与 scoped 资产解析
"""

from pathlib import Path
import shutil
from types import SimpleNamespace
from uuid import uuid4

from backend.app.agent.tools.skill_tools import (
    _build_load_scenario_command,
    _build_load_skill_command,
)
from backend.app.skills.assets import resolve_asset_path
from backend.app.skills.discovery import discover_domains, discover_scenarios
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


def _make_workspace_temp_dir() -> Path:
    temp_root = Path.cwd() / f".tmp_skill_registry_{uuid4().hex}"
    temp_root.mkdir(parents=True, exist_ok=False)
    return temp_root


def test_skill_registry_returns_paint_shop_domain() -> None:
    domain = get_skill_by_name("paint_shop_vehicle_tracking")
    assert domain is not None
    assert domain["name"] == "paint_shop_vehicle_tracking"
    assert any("daily_area_body_count" in item for item in domain["scenario_summaries"])
    assert any(
        "realtime_area_body_count" in item for item in domain["scenario_summaries"]
    )


def test_skill_registry_returns_paint_shop_defect_domain() -> None:
    domain = get_skill_by_name("paint_shop_defect_analysis")
    assert domain is not None
    assert domain["name"] == "paint_shop_defect_analysis"
    assert any("daily_defect_summary" in item for item in domain["scenario_summaries"])
    assert any("model_defect_trend" in item for item in domain["scenario_summaries"])


def test_scenario_registry_returns_daily_area_body_count() -> None:
    scenarios = list_scenarios_by_skill("paint_shop_vehicle_tracking")
    assert len(scenarios) == 2
    scenario = get_scenario_by_name(
        "paint_shop_vehicle_tracking",
        "daily_area_body_count",
    )
    assert scenario is not None
    assert scenario["title"] == "每日各区域车身数量统计"
    assert scenario["sql_template_refs"][0]["scope"] == "scenario"
    assert scenario["sql_template_refs"][0]["path"] == "sql/main.sql"


def test_scenario_registry_returns_realtime_area_body_count() -> None:
    scenario = get_scenario_by_name(
        "paint_shop_vehicle_tracking",
        "realtime_area_body_count",
    )
    assert scenario is not None
    assert scenario["title"] == "实时各区域车身数量统计"


def test_scenario_registry_returns_daily_defect_summary() -> None:
    scenarios = list_scenarios_by_skill("paint_shop_defect_analysis")
    assert len(scenarios) == 5
    scenario = get_scenario_by_name(
        "paint_shop_defect_analysis",
        "daily_defect_summary",
    )
    assert scenario is not None
    assert scenario["title"] == "每日缺陷汇总"


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


def test_defect_domain_content_includes_scenario_summary() -> None:
    content = load_domain_content("paint_shop_defect_analysis")
    assert content is not None
    assert "## 可用场景摘要" in content
    assert "daily_defect_summary" in content
    assert "black_roof_defect_comparison" in content


def test_defect_scenario_content_includes_sql_template() -> None:
    content = load_scenario_content(
        "paint_shop_defect_analysis",
        "daily_defect_summary",
    )
    assert content is not None
    assert "SUM(mq.total_defect_count)" in content


def test_shared_asset_scope_can_be_resolved() -> None:
    scenario = get_scenario_by_name(
        "paint_shop_vehicle_tracking",
        "daily_area_body_count",
    )
    assert scenario is not None

    shared_asset = {
        "type": "doc",
        "name": "shared_scripts_readme",
        "scope": "shared",
        "path": "scripts/README.md",
        "description": "共享脚本目录说明",
    }
    resolved_path = resolve_asset_path(shared_asset, scenario=scenario)
    assert resolved_path.name == "README.md"
    assert "shared" in str(resolved_path)


def test_discovery_rejects_scenario_name_mismatch() -> None:
    root = _make_workspace_temp_dir()
    try:
        domain_dir = root / "demo_domain"
        scenario_dir = domain_dir / "scenarios" / "wrong_dir_name"
        scenario_dir.mkdir(parents=True)
        (domain_dir / "domain.md").write_text("# demo", encoding="utf-8")
        (domain_dir / "meta.py").write_text(
            "DOMAIN_META = {'name': 'demo_domain', 'description': 'demo', 'tags': ['demo']}\n",
            encoding="utf-8",
        )
        (scenario_dir / "scenario.py").write_text(
            "SCENARIO = {"
            "'skill_name': 'demo_domain', "
            "'name': 'expected_name', "
            "'title': 'demo', "
            "'description': 'demo', "
            "'triggers': [], "
            "'intent_keywords': [], "
            "'required_inputs': [], "
            "'optional_inputs': [], "
            "'workflow': [], "
            "'rules': [], "
            "'gotchas': [], "
            "'output_contract': 'demo', "
            "'sql_template_refs': [], "
            "'script_refs': [], "
            "'parameters': {}"
            "}\n",
            encoding="utf-8",
        )

        import backend.app.skills.discovery as discovery_module

        original_root = discovery_module.DOMAINS_ROOT
        discovery_module.DOMAINS_ROOT = root
        try:
            domains = discover_domains()
            try:
                discover_scenarios(domains["demo_domain"])
            except ValueError as exc:
                assert "场景目录名与 SCENARIO['name'] 不一致" in str(exc)
            else:
                raise AssertionError("预期发现阶段抛出场景目录名不一致错误")
        finally:
            discovery_module.DOMAINS_ROOT = original_root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_discovery_rejects_invalid_asset_path() -> None:
    root = _make_workspace_temp_dir()
    try:
        domain_dir = root / "demo_domain"
        scenario_dir = domain_dir / "scenarios" / "demo_scenario"
        (scenario_dir / "sql").mkdir(parents=True)
        (domain_dir / "domain.md").write_text("# demo", encoding="utf-8")
        (domain_dir / "meta.py").write_text(
            "DOMAIN_META = {'name': 'demo_domain', 'description': 'demo', 'tags': ['demo']}\n",
            encoding="utf-8",
        )
        (scenario_dir / "scenario.py").write_text(
            "SCENARIO = {"
            "'skill_name': 'demo_domain', "
            "'name': 'demo_scenario', "
            "'title': 'demo', "
            "'description': 'demo', "
            "'triggers': [], "
            "'intent_keywords': [], "
            "'required_inputs': [], "
            "'optional_inputs': [], "
            "'workflow': [], "
            "'rules': [], "
            "'gotchas': [], "
            "'output_contract': 'demo', "
            "'sql_template_refs': ["
            "{'type': 'sql', 'name': 'main', 'scope': 'scenario', 'path': 'sql/missing.sql', 'description': 'missing'}"
            "], "
            "'script_refs': [], "
            "'parameters': {}"
            "}\n",
            encoding="utf-8",
        )

        import backend.app.skills.discovery as discovery_module

        original_root = discovery_module.DOMAINS_ROOT
        discovery_module.DOMAINS_ROOT = root
        try:
            domains = discover_domains()
            try:
                discover_scenarios(domains["demo_domain"])
            except FileNotFoundError as exc:
                assert "资产不存在" in str(exc)
            else:
                raise AssertionError("预期发现阶段抛出无效资产路径错误")
        finally:
            discovery_module.DOMAINS_ROOT = original_root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_legacy_skills_export_is_compatible() -> None:
    assert SKILLS
    assert any(skill["name"] == "paint_shop_vehicle_tracking" for skill in SKILLS)
    assert any(skill["name"] == "paint_shop_defect_analysis" for skill in SKILLS)
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

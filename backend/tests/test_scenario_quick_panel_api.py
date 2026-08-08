import pytest
from backend.app.schemas import (
    ScenarioItem,
    ScenarioSummary,
    ParameterOptionSchema,
    ParameterDefSchema,
    TemplateInfoSchema,
    ScenarioParamsResponse,
    ScenarioExecuteRequest,
    ScenarioExecuteResponse,
)

def test_scenario_schemas_validation():
    summary = ScenarioSummary(
        domain="paint_shop_vehicle_logistics",
        domain_title="物流追踪",
        scenarios=[
            ScenarioItem(
                name="stranded_vehicle_detection",
                title="滞留车检测",
                description="车间滞留车辆信息查询与检测。"
            )
        ]
    )
    assert summary.domain == "paint_shop_vehicle_logistics"
    assert len(summary.scenarios) == 1

    params_resp = ScenarioParamsResponse(
        name="stranded_vehicle_detection",
        title="滞留车检测",
        output_type="table",
        templates=[TemplateInfoSchema(name="in_process", label="在制滞留")],
        default_template="in_process",
        parameters={
            "platform_filter": ParameterDefSchema(
                type="string",
                widget="select",
                description="按平台筛选",
                required=False,
                default="",
                options=[ParameterOptionSchema(value="", label="不限")]
            )
        }
    )
    assert params_resp.default_template == "in_process"
    assert params_resp.parameters["platform_filter"].widget == "select"

    exec_req = ScenarioExecuteRequest(
        params={"platform_filter": "ADP"},
        template_name="in_process"
    )
    assert exec_req.template_name == "in_process"

    exec_resp = ScenarioExecuteResponse(
        type="table",
        columns=["vehicle_id"],
        rows=[["V001"]],
        row_count=1
    )
    assert exec_resp.type == "table"
    assert exec_resp.row_count == 1


def test_api_list_scenarios():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "domain" in data[0]
        assert "scenarios" in data[0]


def test_api_get_scenario_params():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/scenarios/paint_shop_vehicle_logistics/stranded_vehicle_detection/params")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "stranded_vehicle_detection"
    assert data["default_template"] == "in_process"
    assert "parameters" in data
    assert "platform_filter" in data["parameters"]


def test_api_execute_scenario_invalid_name():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/scenarios/invalid_domain/invalid_scenario/execute",
        json={"params": {}}
    )
    assert response.status_code == 404


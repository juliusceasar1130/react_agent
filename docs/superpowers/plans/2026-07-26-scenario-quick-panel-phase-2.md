# 快捷场景面板 (Phase 2: Backend API & Schemas) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建快捷场景面板后端 Pydantic v2 Schema 响应模型与 3 个 RESTful API 端点（场景树列表、参数与模板解析、直通查询安全执行），并通过 FastAPI TestClient 单元/集成测试进行 100% 规则验证。

**Architecture:** 在 `schemas.py` 中使用 Pydantic v2 (`ConfigDict(from_attributes=True)`) 集中定义类型规则。在 `api.py` 中引入 `scenarios_router` (prefix `/api/scenarios`)，纯编排调用 Phase 1 构建的 `direct_path` 引擎（`resolve_params`, `execute_scenario`, `format_result`），在 `main.py` 中挂载路由。

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, TestClient.

---

## File Structure

- **Modify**: [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/schemas.py) (Add `ScenarioItem`, `ScenarioSummary`, `ParameterOptionSchema`, `ParameterDefSchema`, `TemplateInfoSchema`, `ScenarioParamsResponse`, `ScenarioExecuteRequest`, `ScenarioExecuteResponse`)
- **Modify**: [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/api.py) (Add `scenarios_router` with 3 endpoints: `GET /api/scenarios`, `GET /api/scenarios/{domain}/{scenario}/params`, `POST /api/scenarios/{domain}/{scenario}/execute`)
- **Modify**: [main.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/main.py) (Mount `scenarios_router` on FastAPI `app`)
- **Create**: [test_scenario_quick_panel_api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/test_scenario_quick_panel_api.py) (FastAPI TestClient integration tests)

---

### Task 1: Define Pydantic v2 Schemas in `schemas.py`

**Files:**
- Modify: `backend/app/schemas.py:260-263`
- Test: `backend/tests/test_scenario_quick_panel_api.py`

- [ ] **Step 1: Write failing test for Pydantic v2 schemas**

```python
# backend/tests/test_scenario_quick_panel_api.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/tests/test_scenario_quick_panel_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'ScenarioSummary' from 'backend.app.schemas'`

- [ ] **Step 3: Update `backend/app/schemas.py`**

Append to end of `backend/app/schemas.py`:

```python
# ==================== 快捷场景面板 (Scenario Quick Panel) Schemas ====================

class ScenarioItem(BaseModel):
    name: str
    title: str
    description: str


class ScenarioSummary(BaseModel):
    domain: str
    domain_title: str
    scenarios: List[ScenarioItem]

    model_config = ConfigDict(from_attributes=True)


class ParameterOptionSchema(BaseModel):
    value: str
    label: str


class ParameterDefSchema(BaseModel):
    type: str
    widget: str
    description: str
    required: bool = False
    default: Optional[Union[str, int, float]] = None
    options: List[ParameterOptionSchema] = []


class TemplateInfoSchema(BaseModel):
    name: str
    label: str


class ScenarioParamsResponse(BaseModel):
    name: str
    title: str
    output_type: str = "table"
    templates: Optional[List[TemplateInfoSchema]] = None
    default_template: Optional[str] = None
    parameters: Dict[str, ParameterDefSchema]

    model_config = ConfigDict(from_attributes=True)


class ScenarioExecuteRequest(BaseModel):
    params: Dict[str, Any] = {}
    template_name: Optional[str] = None


class ScenarioExecuteResponse(BaseModel):
    type: str  # "table" or "scalar"
    columns: Optional[List[str]] = None
    rows: Optional[List[List[Any]]] = None
    row_count: Optional[int] = None
    value: Optional[Union[str, int, float]] = None
    label: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/tests/test_scenario_quick_panel_api.py::test_scenario_schemas_validation -v`
Expected: PASS

---

### Task 2: Add RESTful API Endpoints (`scenarios_router`) in `api.py` and Mount in `main.py`

**Files:**
- Modify: `backend/app/api.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_scenario_quick_panel_api.py`

- [ ] **Step 1: Write failing integration tests for API endpoints**

```python
# Add to backend/tests/test_scenario_quick_panel_api.py
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_api_list_scenarios():
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "domain" in data[0]
        assert "scenarios" in data[0]

def test_api_get_scenario_params():
    response = client.get("/api/scenarios/paint_shop_vehicle_logistics/stranded_vehicle_detection/params")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "stranded_vehicle_detection"
    assert data["default_template"] == "in_process"
    assert "parameters" in data
    assert "platform_filter" in data["parameters"]

def test_api_execute_scenario_invalid_name():
    response = client.post(
        "/api/scenarios/invalid_domain/invalid_scenario/execute",
        json={"params": {}}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/tests/test_scenario_quick_panel_api.py::test_api_list_scenarios -v`
Expected: FAIL with status code 404 (route not mounted yet).

- [ ] **Step 3: Update `backend/app/api.py` and `backend/app/main.py`**

In `backend/app/api.py`, add `scenarios_router`:

```python
# ==================== 快捷场景面板 (Scenario Quick Panel) API ====================
from backend.app.skills.direct_path import resolve_params, execute_scenario, format_result
from backend.app.schemas import ScenarioSummary, ScenarioParamsResponse, ScenarioExecuteRequest, ScenarioExecuteResponse

scenarios_router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

@scenarios_router.get("", response_model=List[ScenarioSummary])
def list_scenarios_tree():
    """获取全量业务领域及其下属快捷场景列表。"""
    summary_list = []
    domain_skills = get_domain_skills()
    for domain_name, domain_info in domain_skills.items():
        scenarios_items = []
        for s in list_scenarios_by_skill(domain_name):
            scenarios_items.append({
                "name": s["name"],
                "title": s.get("title", s["name"]),
                "description": s.get("description", ""),
            })
        if scenarios_items:
            summary_list.append({
                "domain": domain_name,
                "domain_title": domain_info.get("title") or domain_name.replace("_", " ").title(),
                "scenarios": scenarios_items,
            })
    return summary_list


@scenarios_router.get("/{domain}/{scenario}/params", response_model=ScenarioParamsResponse)
def get_scenario_params_endpoint(domain: str, scenario: str, template_name: Optional[str] = None):
    """解析获取指定场景的参数定义与模板元数据。"""
    try:
        data = resolve_params(domain, scenario, template_name=template_name)
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to resolve scenario params for %s/%s: %s", domain, scenario, e)
        raise HTTPException(status_code=500, detail=f"Failed to resolve scenario params: {e}")


@scenarios_router.post("/{domain}/{scenario}/execute", response_model=ScenarioExecuteResponse)
def execute_scenario_endpoint(domain: str, scenario: str, request: ScenarioExecuteRequest):
    """直通安全执行指定场景的 SQL 查询并返回格式化结果。"""
    try:
        params_info = resolve_params(domain, scenario, template_name=request.template_name)
        output_type = params_info.get("output_type", "table")
        
        rows, columns = execute_scenario(
            domain_name=domain,
            scenario_name=scenario,
            params=request.params,
            template_name=request.template_name,
        )
        formatted_data = format_result(rows=rows, columns=columns, output_type=output_type)
        return formatted_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to execute scenario %s/%s: %s", domain, scenario, e)
        raise HTTPException(status_code=500, detail=f"Failed to execute scenario query: {e}")
```

In `backend/app/main.py`:

```python
from .api import router, scenarios_router, init_analytics_engine

# 注册 API 路由
app.include_router(router)
app.include_router(scenarios_router)
```

- [ ] **Step 4: Run integration test to verify it passes**

Run: `D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/tests/test_scenario_quick_panel_api.py -v`
Expected: PASS

---

## Self-Review Checklist

1. **Spec coverage:** Covers Pydantic v2 schemas in `schemas.py`, 3 API endpoints in `api.py` & `main.py`, and TestClient tests in `test_scenario_quick_panel_api.py`.
2. **Placeholder scan:** No TBDs, no TODOs, all code blocks provided.
3. **Type consistency:** Endpoint route paths and schema field names match the spec.

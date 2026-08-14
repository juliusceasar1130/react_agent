import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException

from backend.app.skills.registry import get_domain_skills, list_scenarios_by_skill
from backend.app.skills.direct_path import resolve_params, execute_scenario, format_result
from backend.app.schemas import (
    ScenarioSummary,
    ScenarioParamsResponse,
    ScenarioExecuteRequest,
    ScenarioExecuteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def is_direct_path_enabled(scenario: dict) -> bool:
    """判定场景是否开启快捷直通查询能力 (支持显式标志与模板特征判定)"""
    if "direct_path_enabled" in scenario:
        return bool(scenario["direct_path_enabled"])
    return bool(scenario.get("sql_template_refs")) and bool(scenario.get("default_template"))


@router.get("", response_model=List[ScenarioSummary])
def list_scenarios_tree():
    """获取全量业务领域及其下属快捷场景列表 (自动过滤仅 LLM 场景)。"""
    summary_list = []
    domain_skills = get_domain_skills()
    for domain_name, domain_info in domain_skills.items():
        scenarios_items = []
        for s in list_scenarios_by_skill(domain_name):
            if is_direct_path_enabled(s):
                scenarios_items.append({
                    "name": s["name"],
                    "title": s.get("title", s["name"]),
                    "description": s.get("description", ""),
                    "direct_path_enabled": True,
                })
        if scenarios_items:
            summary_list.append({
                "domain": domain_name,
                "domain_title": domain_info.get("title") or domain_name.replace("_", " ").title(),
                "scenarios": scenarios_items,
            })
    return summary_list


@router.get("/{domain}/{scenario}/params", response_model=ScenarioParamsResponse)
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


@router.post("/{domain}/{scenario}/execute", response_model=ScenarioExecuteResponse)
def execute_scenario_endpoint(domain: str, scenario: str, request: ScenarioExecuteRequest):
    """直通安全执行指定场景的 SQL 查询并返回格式化结果。"""
    try:
        params_info = resolve_params(domain, scenario, template_name=request.template_name)
        output_type = params_info.get("output_type", "table")
        
        req_page = request.page or 1
        req_page_size = request.page_size or 50

        rows, columns, total_count = execute_scenario(
            domain_name=domain,
            scenario_name=scenario,
            params=request.params,
            template_name=request.template_name,
            page=req_page,
            page_size=req_page_size,
        )
        formatted_data = format_result(
            rows=rows,
            columns=columns,
            output_type=output_type,
            total_count=total_count,
            page=req_page,
            page_size=req_page_size,
        )
        return formatted_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to execute scenario %s/%s: %s", domain, scenario, e)
        raise HTTPException(status_code=500, detail=f"Failed to execute scenario query: {e}")

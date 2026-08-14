import logging
from fastapi import APIRouter, HTTPException
from backend.app.skills.registry import get_domain_skills, list_scenarios_by_skill, reload_skills

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/skills")
def get_skills_endpoint():
    """获取所有已注册的领域和场景技能
    
    修改时间: 2026-05-15
    修改内容: 
    - 移除硬编码，改由各领域 meta.py 和场景 scenario.py 统一管理展示文案
    - 优先读取 title 和 example_questions 字段
    """
    skills_list = []
    domain_skills = get_domain_skills()
    for domain_name, domain_info in domain_skills.items():
        skills_list.append({
            "name": domain_name,
            "title": domain_info.get("title") or domain_name.replace("_", " ").title(),
            "description": domain_info["description"],
            "scenarios": [
                {
                    "name": s["name"],
                    "title": s.get("title", s["name"]),
                    "description": s.get("description", ""),
                    "questions": s.get("example_questions") or s.get("triggers", [])[:3]
                }
                for s in list_scenarios_by_skill(domain_name)
            ]
        })
    return skills_list


@router.post("/skills/reload")
def reload_skills_endpoint():
    """热重载全部技能"""
    success = reload_skills()
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reload skills. Check syntax in skill files.")
    return {"message": "Skills reloaded successfully"}

# Hot-Plugging Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement API-triggered hot-plugging for domain skills with robust thread safety and error handling.

**Architecture:** Transition static global dictionaries in `registry.py` to dynamic state accessed via getters. Introduce a `reload_skills()` function with try-catch error isolation to rebuild the state on demand, triggered by a new `POST /api/chat/skills/reload` endpoint.

**Tech Stack:** FastAPI, Docker Compose, Pytest.

---

### Task 1: Docker Infrastructure Update

**Files:**
- Modify: `docker-compose.yml:15-18`

- [ ] **Step 1: Modify docker-compose.yml to mount domains volume**
```yaml
    volumes:
      - ./backend/app/skills/domains:/app/backend/app/skills/domains
```

- [ ] **Step 2: Commit**
```bash
git add docker-compose.yml
git commit -m "chore: add volume mount for domain skills"
```

### Task 2: Refactor registry.py for Dynamic State

**Files:**
- Create: `backend/app/test_registry_reload.py`
- Modify: `backend/app/skills/registry.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/test_registry_reload.py
def test_reload_skills_success():
    from backend.app.skills.registry import reload_skills, get_all_skills
    old_skills = get_all_skills()
    assert reload_skills() is True
    new_skills = get_all_skills()
    assert len(new_skills) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/test_registry_reload.py`
Expected: FAIL with `ImportError` or `AttributeError` for `reload_skills`.

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/skills/registry.py` to replace static globals with a private `_RegistryState` and getters:

```python
import logging
from typing import Any
from backend.app.skills.discovery import discover_domains, discover_scenarios
from backend.app.skills.models import DomainSkill, ScenarioSkill, Skill
from backend.app.skills.assets import read_text_file
from backend.app.skills.renderers import render_domain_for_llm

logger = logging.getLogger(__name__)

class _RegistryState:
    def __init__(self):
        self.discovered_domains = {}
        self.scenarios_by_skill = {}
        self.domain_skills = {}
        self.skills = []

_state = _RegistryState()

def _build_scenario_summaries(scenarios: list[ScenarioSkill]) -> list[str]:
    return [f"- **{item['name']}**: {item['description']}" for item in scenarios]

def reload_skills() -> bool:
    """重新扫描并加载全部技能，使用 try-catch 隔离错误"""
    try:
        new_discovered = discover_domains()
        
        from collections import defaultdict
        new_scenarios_raw = defaultdict(list)
        for d_name, domain in new_discovered.items():
            for scenario in discover_scenarios(domain):
                new_scenarios_raw[d_name].append(scenario)
                
        new_scenarios_by_skill = {
            k: sorted(v, key=lambda i: i["name"]) 
            for k, v in new_scenarios_raw.items()
        }
        
        new_domain_skills = {
            d_name: {
                "name": d_name,
                "title": domain.meta.get("title", d_name),
                "description": domain.meta["description"],
                "domain_content": read_text_file(domain.domain_dir / "domain.md"),
                "scenario_summaries": _build_scenario_summaries(
                    new_scenarios_by_skill.get(d_name, [])
                ),
                "tags": list(domain.meta["tags"]),
                "domain_root": str(domain.domain_dir),
            }
            for d_name, domain in new_discovered.items()
        }
        
        new_skills = [
            {
                "name": domain["name"],
                "description": domain["description"],
                "content": render_domain_for_llm(
                    domain,
                    new_scenarios_by_skill.get(domain["name"], []),
                ),
            }
            for domain in new_domain_skills.values()
        ]
        
        # 原子更新
        _state.discovered_domains = new_discovered
        _state.scenarios_by_skill = new_scenarios_by_skill
        _state.domain_skills = new_domain_skills
        _state.skills = new_skills
        logger.info("Skills reloaded successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to reload skills: {e}", exc_info=True)
        return False

# 初始加载
reload_skills()

def get_all_skills() -> list[Skill]:
    return _state.skills

def get_domain_skills() -> dict[str, DomainSkill]:
    return _state.domain_skills

def get_skill_by_name(skill_name: str) -> DomainSkill | None:
    return _state.domain_skills.get(skill_name)

def list_scenarios_by_skill(skill_name: str) -> list[ScenarioSkill]:
    return list(_state.scenarios_by_skill.get(skill_name, []))

def get_scenario_by_name(skill_name: str, scenario_name: str) -> ScenarioSkill | None:
    for scenario in _state.scenarios_by_skill.get(skill_name, []):
        if scenario["name"] == scenario_name:
            return scenario
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/test_registry_reload.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/registry.py backend/app/test_registry_reload.py
git commit -m "feat: refactor registry to use private state and getters with reload_skills"
```

### Task 3: Refactor Consumers

**Files:**
- Modify: `backend/app/agent/middleware/skill_middleware.py`
- Modify: `backend/app/agent/tools/skill_tools.py`
- Modify: `backend/app/skills/loaders.py`
- Modify: `backend/app/skills/__init__.py`

- [ ] **Step 1: Write the failing test**

Run existing tests to see where static imports break:
Run: `pytest backend/app/test_skill_registry.py backend/app/test_agent.py`
Expected: FAIL due to missing `DOMAIN_SKILLS` or `SKILLS` attributes.

- [ ] **Step 2: Write minimal implementation**

In `backend/app/skills/__init__.py`:
Remove `SKILLS`, replace with `get_all_skills`.

In `backend/app/skills/loaders.py`:
Ensure it imports `get_scenario_by_name, get_skill_by_name, list_scenarios_by_skill`.

In `backend/app/agent/middleware/skill_middleware.py`:
Change `from backend.app.skills import SKILLS` to `from backend.app.skills.registry import get_all_skills`.
Remove `self.skills_prompt = _build_skills_prompt(SKILLS)` from `__init__`.
In `_modify_request`:
```python
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        from backend.app.skills.registry import get_all_skills
        skills_prompt = _build_skills_prompt(get_all_skills())
        skills_addendum = (
            f"\n\n## Available Skills\n\n{skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed domain knowledge. "
            "If the loaded domain skill shows a matching fixed scenario, use the "
            "load_scenario tool before composing SQL. For fixed statistics or "
            "fixed report-style questions, prefer loading a scenario instead of "
            "planning from scratch."
        )
        # ... rest remains the same
```

In `backend/app/agent/tools/skill_tools.py`:
Change imports:
```python
from backend.app.skills.registry import (
    get_all_skills,
    get_scenario_by_name,
    get_skill_by_name,
)
from backend.app.skills.loaders import (
    load_domain_content,
    load_scenario_content,
)
```
Change all list comprehensions over `SKILLS`:
`available = ", ".join(s["name"] for s in get_all_skills())`

Fix tests in `test_skill_registry.py` to use `get_domain_skills()` instead of `DOMAIN_SKILLS`.

- [ ] **Step 3: Run tests to verify**

Run: `pytest backend/app/`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/
git commit -m "refactor: update all consumers to use dynamic skill getters"
```

### Task 4: Expose Reload API

**Files:**
- Create: `backend/app/test_api_reload.py`
- Modify: `backend/app/api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/test_api_reload.py`:
```python
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_reload_skills_api():
    response = client.post("/api/chat/skills/reload")
    assert response.status_code == 200
    assert response.json()["message"] == "Skills reloaded successfully"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/test_api_reload.py`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api.py`:
Remove `from .skills.registry import DOMAIN_SKILLS` and `import backend.app.skills.registry`.
Add:
```python
from backend.app.skills.registry import get_domain_skills, list_scenarios_by_skill, reload_skills

@router.get("/skills")
def get_skills_endpoint():
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
    success = reload_skills()
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Failed to reload skills. Check syntax in skill files.")
    return {"message": "Skills reloaded successfully"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/test_api_reload.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api.py backend/app/test_api_reload.py
git commit -m "feat: add POST /api/chat/skills/reload endpoint"
```

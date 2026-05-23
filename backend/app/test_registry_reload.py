# backend/app/test_registry_reload.py
def test_reload_skills_success():
    from backend.app.skills.registry import reload_skills, get_all_skills
    old_skills = get_all_skills()
    assert reload_skills() is True
    new_skills = get_all_skills()
    assert len(new_skills) >= 1

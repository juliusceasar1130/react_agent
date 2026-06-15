from backend.app.config import settings

def test_context_collapse_config():
    # Verify default config parameter exists and is 3
    assert hasattr(settings, "llm_context_collapse_protect_turns")
    assert settings.llm_context_collapse_protect_turns == 3

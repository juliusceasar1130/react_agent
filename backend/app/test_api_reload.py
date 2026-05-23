from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_reload_skills_api():
    response = client.post("/api/chat/skills/reload")
    assert response.status_code == 200
    assert response.json()["message"] == "Skills reloaded successfully"

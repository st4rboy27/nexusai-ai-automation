import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test_nexusai.db"))
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with TestClient(app) as test_client:
        yield test_client

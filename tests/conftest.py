import pytest
from fastapi.testclient import TestClient

from judgpt.web.app import app


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()

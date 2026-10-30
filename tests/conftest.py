import pytest
from fastapi.testclient import TestClient

from source360.api import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)

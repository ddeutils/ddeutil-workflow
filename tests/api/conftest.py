from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.ddeutil.workflow.api.api import app


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient that uses the test database session.
    Override the get_db dependency to use the test session.
    """
    # def override_get_db():
    #     yield db
    #
    # app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

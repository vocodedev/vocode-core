import os
from typing import Generator
from unittest import mock

import pytest
from fakeredis import FakeAsyncRedis
from pytest import FixtureRequest, MonkeyPatch


@pytest.fixture(scope="session")
def default_env_vars() -> dict[str, str]:
    """
    Defines default environment variables for the test session.

    This fixture provides a dictionary of default environment variables that are
    commonly used across tests. It can be overridden in submodule scoped `conftest.py`
    files or directly in tests.

    :return: A dictionary of default environment variables.
    """
    return {
        "ENVIRONMENT": "test",
        "AZURE_OPENAI_API_BASE_EAST_US": "https://api.openai.com",
        "AZURE_OPENAI_API_KEY_EAST_US": "test",
    }


@pytest.fixture()
def mock_env(
    monkeypatch: MonkeyPatch, request: pytest.FixtureRequest, default_env_vars: dict[str, str]
) -> Generator[None, None, None]:
    """
    Temporarily sets environment variables for testing.

    This fixture allows tests to run with a modified set of environment variables,
    either using the default set provided by `default_env_vars` or overridden by
    test-specific parameters. It ensures that changes to environment variables do
    not leak between tests.

    :param monkeypatch: The pytest monkeypatch fixture for modifying environment variables.
    :param request: The pytest FixtureRequest object for accessing test-specific overrides.
    :param default_env_vars: A dictionary of default environment variables.
    :yield: None. This is a setup-teardown fixture that cleans up after itself.
    """
    envvars = default_env_vars.copy()
    if hasattr(request, "param") and isinstance(request.param, dict):
        envvars.update(request.param)

    with mock.patch.dict(os.environ, envvars):
        yield


@pytest.fixture
def redis_client(request: FixtureRequest) -> FakeAsyncRedis:
    """
    Provides a fake Redis client for asynchronous operations.

    This fixture can be used in tests that require a Redis client but should not
    interact with a real Redis instance. It leverages fakeredis to simulate Redis
    operations in memory without any external dependencies.

    :param request: The pytest request object, used here for potential future extensions.
    :return: An instance of a fake Redis client.
    """
    redis_client = FakeAsyncRedis()
    return redis_client

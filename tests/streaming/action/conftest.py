import pytest


@pytest.fixture(scope="session")
def default_env_vars(default_env_vars: dict[str, str]) -> dict[str, str]:
    """
    Extends the `default_env_vars` fixture specifically for the submodule.

    This fixture takes the session-scoped `default_env_vars` fixture from the parent conftest.py
    and extends or overrides it with additional or modified environment variables specific to
    the submodule.

    :param default_env_vars: The inherited `default_env_vars` fixture from the parent conftest.
    :return: A modified dictionary of default environment variables for the submodule.
    """
    submodule_env_vars = default_env_vars.copy()

    submodule_env_vars.update(
        {
            "VONAGE_API_KEY": "test",
            "VONAGE_API_SECRET": "test",
            "VONAGE_APPLICATION_ID": "test",
            "VONAGE_PRIVATE_KEY": """-----BEGIN PRIVATE KEY-----
fake_key
-----END PRIVATE KEY-----""",
            "BASE_URL": "test",
            "CALL_SERVER_BASE_URL": "test2",
        }
    )

    return submodule_env_vars

import os
from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID

import sentry_sdk
from loguru import logger

from vocode.meta import ensure_punkt_installed

environment = {}
logger.disable("vocode")

ensure_punkt_installed()


class ContextWrapper:
    """Context Variable Wrapper."""

    _instances: list = []

    def __init__(self, value: ContextVar) -> None:
        self.__value: ContextVar = value
        self.__token: Token
        ContextWrapper._instances.append(self)

    def set(self, value: Any) -> Token:
        """Set a context variable."""
        self.__token = self.__value.set(value)
        if isinstance(value, str):
            sentry_sdk.set_tag(self.__value.name, value)
        if isinstance(value, UUID):
            sentry_sdk.set_tag(self.__value.name, str(value))

        return self.__token

    def reset(self, token: Token | None = None) -> None:
        """Reset a context variable."""
        if not hasattr(self, "__token"):
            return

        if not token:
            token = self.__token
        self.__value.reset(token)
        return

    def __module__(self) -> Any:  # type: ignore
        return self.__value.get()

    @property
    def value(self) -> Any:
        """Gets the value of a context variable."""
        return self.__value.get()

    @classmethod
    def serialize_instances(cls) -> dict:
        """Gathers all instances of ContextWrapper."""
        instances = {}
        for instance in cls._instances:
            value = instance.__value.get()
            if isinstance(value, UUID):
                value = str(value)

            if isinstance(value, str):
                instances[instance.__value.name] = value
        return instances


def setenv(**kwargs):
    for key, value in kwargs.items():
        environment[key] = value


def getenv(key, default=None):
    return environment.get(key) or os.getenv(key, default)


api_key = getenv("VOCODE_API_KEY")
base_url = getenv("VOCODE_BASE_URL", "api.vocode.dev")


conversation_id: ContextWrapper = ContextWrapper(
    ContextVar("conversation_id", default=None),
)
sentry_span_tags: ContextWrapper = ContextWrapper(ContextVar("sentry_span_tags", default=None))
sentry_transaction = ContextWrapper(ContextVar("sentry_transaction", default=None))
get_serialized_ctx_wrappers = ContextWrapper.serialize_instances

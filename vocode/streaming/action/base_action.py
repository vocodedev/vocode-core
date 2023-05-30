import logging
from typing import Generic, Optional, TypeVar
from vocode.streaming.models.actions import ActionOutput, ActionType


ActionOutputType = TypeVar("ActionOutputType", bound=ActionOutput)


class BaseAction(Generic[ActionOutputType]):
    def run(self, params: str) -> ActionOutputType:
        raise NotImplementedError

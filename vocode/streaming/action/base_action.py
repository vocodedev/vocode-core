import logging
from typing import Any, Dict, Generic, Optional, TypeVar
from vocode.streaming.models.actions import ActionInput, ActionOutput

ActionInputType = TypeVar("ActionInputType", bound=ActionInput)
ActionOutputType = TypeVar("ActionOutputType", bound=ActionOutput)


class BaseAction(Generic[ActionInputType, ActionOutputType]):
    def run(self, action_input: ActionInputType) -> ActionOutputType:
        raise NotImplementedError

    def get_openai_function(self):
        # TODO: ideally, this should be reflexive and be able to be populated purely from the static information in the class
        raise NotImplementedError

    def create_action_input(
        self, conversation_id: str, params: Dict[str, Any]
    ) -> ActionInputType:
        # TODO: ideally, this should be reflexive and be able to be populated purely from the static information in the class
        raise NotImplementedError

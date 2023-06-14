import logging
from typing import Any, Dict, Generic, Optional, Type, TypeVar
from vocode.streaming.action.utils import exclude_keys_recursive
from vocode.streaming.models.actions import ActionInput, ActionOutput, ActionType

ActionInputType = TypeVar("ActionInputType", bound=ActionInput)
ActionOutputType = TypeVar("ActionOutputType", bound=ActionOutput)


class BaseAction(Generic[ActionInputType, ActionOutputType]):
    description: str = ""
    action_type: str = ActionType.BASE.value

    def run(self, action_input: ActionInputType) -> ActionOutputType:
        raise NotImplementedError

    @property
    def action_input_type(self) -> Type[ActionInputType]:
        raise NotImplementedError

    @property
    def action_output_type(self) -> Type[ActionOutputType]:
        raise NotImplementedError

    def get_openai_function(self):
        parameters_schema = self.action_input_type.schema()["definitions"]["Parameters"]
        parameters_schema = exclude_keys_recursive(parameters_schema, {"title"})
        return {
            "name": self.action_type,
            "description": self.description,
            "parameters": parameters_schema,
        }

    def create_action_input(
        self, conversation_id: str, params: Dict[str, Any]
    ) -> ActionInputType:
        return self.action_input_type(
            action_type=self.action_type,
            conversation_id=conversation_id,
            params=self.action_input_type.Parameters(**params),
        )

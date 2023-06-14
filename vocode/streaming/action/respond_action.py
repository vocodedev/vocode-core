from typing import Any, Dict, TypeVar
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.action.utils import exclude_keys_recursive
from vocode.streaming.models.actions import ActionInput, ActionOutput

ActionInputType = TypeVar("ActionInputType", bound=ActionInput)
ActionOutputType = TypeVar("ActionOutputType", bound=ActionOutput)


class RespondAction(BaseAction[ActionInputType, ActionOutputType]):
    def _user_message_param_info(self):
        return {
            "type": "string",
            "description": """A message to reply to the user with BEFORE we make the function call. 
                    Essentially a live response informing them that the function is about to happen.
                    Eg Let me check the weather in San Francisco CA for you """,
        }

    def get_openai_function(self):
        base_action_openai_function = super().get_openai_function()
        base_action_openai_function["parameters"]["properties"][
            "user_message"
        ] = self._user_message_param_info()
        base_action_openai_function["parameters"]["required"].append("user_message")
        return base_action_openai_function

    def create_action_input(
        self, conversation_id: str, params: Dict[str, Any]
    ) -> ActionInputType:
        del params["user_message"]
        return self.action_input_type(
            action_type=self.action_type,
            conversation_id=conversation_id,
            params=self.action_input_type.Parameters(**params),
        )

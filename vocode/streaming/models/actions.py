import asyncio
from abc import ABC
from enum import Enum
from typing import Annotated, Any, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from vocode.streaming.models.adaptive_object import AdaptiveObject
from vocode.streaming.models.message import BaseMessage

TriggerType = Literal["action_trigger_function_call", "action_trigger_phrase_based"]


class ActionTriggerConfig(BaseModel):
    pass


class _ActionTrigger(BaseModel):
    type: TriggerType
    config: ActionTriggerConfig


class FunctionCallActionTriggerConfig(ActionTriggerConfig):
    pass


class FunctionCallActionTrigger(_ActionTrigger):
    type: Literal["action_trigger_function_call"] = "action_trigger_function_call"
    config: FunctionCallActionTriggerConfig = Field(default_factory=FunctionCallActionTriggerConfig)


PhraseConditionType = Literal["phrase_condition_type_contains"]


class PhraseTrigger(BaseModel):
    phrase: str
    conditions: List[PhraseConditionType]


class PhraseBasedActionTriggerConfig(ActionTriggerConfig):
    phrase_triggers: List[PhraseTrigger]


class PhraseBasedActionTrigger(_ActionTrigger):
    type: Literal["action_trigger_phrase_based"] = "action_trigger_phrase_based"
    config: PhraseBasedActionTriggerConfig


ActionTrigger = Annotated[
    Union[FunctionCallActionTrigger, PhraseBasedActionTrigger],
    Field(discriminator="type"),
]


ActionType = Literal[
    "action_nylas_send_email",
    "action_wait",
    "action_record_email",
    "action_end_conversation",
    "action_external",
    "action_transfer_call",
    "action_dtmf",
]


ParametersType = TypeVar("ParametersType", bound=BaseModel)

ACTION_STARTED_FORMAT_STRING = "!STARTING ACTION {action_name} WITH PARAMETERS {action_params}!"
ACTION_FINISHED_FORMAT_STRING = "!ACTION {action_name} FINISHED WITH OUTPUT {action_output}!"


class ActionConfig(AdaptiveObject, ABC):
    type: Any
    action_trigger: ActionTrigger = FunctionCallActionTrigger(type="action_trigger_function_call")

    def action_attempt_to_string(self, input: "ActionInput") -> str:
        return ACTION_STARTED_FORMAT_STRING.format(
            action_name=self.type,
            action_params=input.params.json(),
        )

    def action_result_to_string(self, input: "ActionInput", output: "ActionOutput") -> str:
        return ACTION_FINISHED_FORMAT_STRING.format(
            action_name=self.type,
            action_output=output.response.json(),
        )


class ActionInput(BaseModel, Generic[ParametersType]):
    action_config: ActionConfig
    conversation_id: str
    params: ParametersType
    user_message_tracker: Optional[asyncio.Event] = None

    class Config:
        arbitrary_types_allowed = True


class FunctionFragment(BaseModel):
    name: str
    arguments: str


class FunctionCall(BaseModel):
    name: str
    arguments: str


class EndOfTurn(BaseModel):
    pass


class VonagePhoneConversationActionInput(ActionInput[ParametersType]):
    vonage_uuid: str


class TwilioPhoneConversationActionInput(ActionInput[ParametersType]):
    twilio_sid: str


ResponseType = TypeVar("ResponseType", bound=BaseModel)


class ActionOutput(BaseModel, Generic[ResponseType]):
    action_type: str
    canned_response: Optional[BaseMessage] = None
    response: ResponseType


ExternalActionProcessingMode = Literal["muted"]

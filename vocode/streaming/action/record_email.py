import re
from typing import Optional, Type

from pydantic.v1 import BaseModel, Field

from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import ActionConfig, ActionInput, ActionOutput

EMAIL_REGEX = r"^(?!\.)(?!.*\.\.)[a-zA-Z0-9._%+-]+(?<!\.)@(?![.])[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


class RecordEmailVocodeActionConfig(ActionConfig, type="action_record_email"):  # type: ignore
    pass


class RecordEmailParameters(BaseModel):
    descriptor: str = Field("A human readable descriptor; eg 'The user's email.'")
    raw_value: str = Field(
        ...,
        description="The raw value parsed from the transcript.",
    )

    formatted_value: str = Field(
        ...,
        description="The estimated FORMATTED value of the email.",
    )


class RecordEmailResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class RecordEmail(
    BaseAction[
        RecordEmailVocodeActionConfig,
        RecordEmailParameters,
        RecordEmailResponse,
    ]
):
    description: str = """Attempts to record an email from the transcript.

    You must format the value to match the field type, eg

    kian at g mail dot com -> kian@gmail.com
    ajay at vocode dot dev -> ajay@vocode.dev

    This function will do extra validation.
    """
    parameters_type: Type[RecordEmailParameters] = RecordEmailParameters
    response_type: Type[RecordEmailResponse] = RecordEmailResponse

    def __init__(
        self,
        action_config: RecordEmailVocodeActionConfig,
    ):
        super().__init__(
            action_config,
            quiet=False,
            should_respond="never",
        )

    def _validate_email(self, email: str) -> bool:
        return bool(re.match(EMAIL_REGEX, email))

    async def run(
        self, action_input: ActionInput[RecordEmailParameters]
    ) -> ActionOutput[RecordEmailResponse]:
        value = action_input.params.formatted_value

        success = self._validate_email(value)

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=RecordEmailResponse(success=success),
        )

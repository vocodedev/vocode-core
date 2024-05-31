from typing import Literal, Type

from loguru import logger
from pydantic.v1 import BaseModel

from vocode.streaming.action.phone_call_action import (
    TwilioPhoneConversationAction,
    VonagePhoneConversationAction,
)
from vocode.streaming.models.actions import ActionConfig as VocodeActionConfig
from vocode.streaming.models.actions import ActionInput, ActionOutput
from vocode.streaming.utils.async_requester import AsyncRequestor
from vocode.streaming.utils.phone_numbers import sanitize_phone_number
from vocode.streaming.utils.state_manager import (
    TwilioPhoneConversationStateManager,
    VonagePhoneConversationStateManager,
)


class TransferCallParameters(BaseModel):
    pass


class TransferCallResponse(BaseModel):
    success: bool


class TransferCallVocodeActionConfig(VocodeActionConfig, type="action_transfer_call"):  # type: ignore
    phone_number: str

    def action_attempt_to_string(self, input: ActionInput) -> str:
        assert isinstance(input.params, TransferCallParameters)
        return f"Attempting to transfer call to {self.phone_number}"

    def action_result_to_string(self, input: ActionInput, output: ActionOutput) -> str:
        assert isinstance(output.response, TransferCallResponse)
        if output.response.success:
            action_description = "Successfully transferred call"
        else:
            action_description = "Did not transfer call because user interrupted"
        return action_description


FUNCTION_DESCRIPTION = "Transfers the call to a new number. This is never used while on hold."
QUIET = True
IS_INTERRUPTIBLE = True
SHOULD_RESPOND: Literal["always"] = "always"


class TwilioTransferCall(
    TwilioPhoneConversationAction[
        TransferCallVocodeActionConfig, TransferCallParameters, TransferCallResponse
    ]
):
    description: str = FUNCTION_DESCRIPTION
    parameters_type: Type[TransferCallParameters] = TransferCallParameters
    response_type: Type[TransferCallResponse] = TransferCallResponse
    conversation_state_manager: TwilioPhoneConversationStateManager

    def __init__(
        self,
        action_config: TransferCallVocodeActionConfig,
    ):
        super().__init__(
            action_config,
            quiet=QUIET,
            is_interruptible=False,
            should_respond=SHOULD_RESPOND,
        )

    async def transfer_call(self, twilio_call_sid: str, to_phone: str):
        twilio_client = self.conversation_state_manager.create_twilio_client()

        url = "https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Calls/{twilio_call_sid}.json".format(
            twilio_account_sid=twilio_client.get_telephony_config().account_sid,
            twilio_call_sid=twilio_call_sid,
        )

        twiml_data = "<Response><Dial>{to_phone}</Dial></Response>".format(to_phone=to_phone)

        payload = {"Twiml": twiml_data}

        async with AsyncRequestor().get_session() as session:
            async with session.post(url, data=payload, auth=twilio_client.auth) as response:
                if response.status != 200:
                    logger.error(f"Failed to transfer call: {response.status} {response.reason}")
                    raise Exception("failed to update call")
                else:
                    return await response.json()

    async def run(
        self, action_input: ActionInput[TransferCallParameters]
    ) -> ActionOutput[TransferCallResponse]:
        twilio_call_sid = self.get_twilio_sid(action_input)

        sanitized_phone_number = sanitize_phone_number(self.action_config.phone_number)

        if action_input.user_message_tracker is not None:
            await action_input.user_message_tracker.wait()

        logger.info("Finished waiting for user message tracker, now attempting to transfer call")

        if self.conversation_state_manager.transcript.was_last_message_interrupted():
            logger.info("Last bot message was interrupted, not transferring call")
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=TransferCallResponse(success=False),
            )

        await self.transfer_call(twilio_call_sid, sanitized_phone_number)

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=TransferCallResponse(success=True),
        )


class VonageTransferCall(
    VonagePhoneConversationAction[
        TransferCallVocodeActionConfig, TransferCallParameters, TransferCallResponse
    ]
):
    description: str = FUNCTION_DESCRIPTION
    parameters_type: Type[TransferCallParameters] = TransferCallParameters
    response_type: Type[TransferCallResponse] = TransferCallResponse
    conversation_state_manager: VonagePhoneConversationStateManager

    def __init__(self, action_config: TransferCallVocodeActionConfig):
        super().__init__(
            action_config,
            quiet=QUIET,
            is_interruptible=IS_INTERRUPTIBLE,
            should_respond=SHOULD_RESPOND,
        )

    async def run(
        self, action_input: ActionInput[TransferCallParameters]
    ) -> ActionOutput[TransferCallResponse]:
        if action_input.user_message_tracker is not None:
            await action_input.user_message_tracker.wait()
        self.conversation_state_manager.mute_agent()

        sanitized_phone_number = sanitize_phone_number(self.action_config.phone_number)

        if self.conversation_state_manager.get_direction() == "outbound":
            agent_phone_number = self.conversation_state_manager.get_from_phone()
        else:
            agent_phone_number = self.conversation_state_manager.get_to_phone()

        await self.conversation_state_manager.create_vonage_client().update_call(
            vonage_uuid=self.get_vonage_uuid(action_input),
            new_ncco=[
                {
                    "action": "connect",
                    "timeout": "45",
                    "from": agent_phone_number,
                    "endpoint": [
                        {
                            "type": "phone",
                            "number": sanitized_phone_number,
                        }
                    ],
                }
            ],
        )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=TransferCallResponse(success=True),
        )

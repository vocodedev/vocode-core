import logging
import os

from typing import Type
from pydantic import BaseModel, Field

from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)

from telephony_app.models.call_status import CallStatus
from telephony_app.models.call_type import CallType
from telephony_app.utils.call_information_handler import (
    execute_status_update_by_telephony_id,
)
from twilio.rest import Client as TwilioRestClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HangUpCallActionConfig(ActionConfig, type=ActionType.HANGUP_CALL):
    call_status: CallStatus
    call_type: CallType
    starting_phrase: str


class HangUpCallParameters(BaseModel):
    pass


class HangUpCallResponse(BaseModel):
    status: str = Field("success", description="status of the hangup")


class HangUpCall(
    TwilioPhoneCallAction[
        HangUpCallActionConfig, HangUpCallParameters, HangUpCallResponse
    ]
):
    description: str = "hangs up the call. use when the phone call should be ended"
    parameters_type: Type[HangUpCallParameters] = HangUpCallParameters
    response_type: Type[HangUpCallResponse] = HangUpCallResponse

    async def hangup_twilio_call(
        self, call_status: str, call_type: CallType, twilio_call_sid: str
    ):
        """
        Hangs up an active Twilio call.

        :param call_status: The call status we want the call to be updated to
        :param call_type: Type of the call (inbound or outbound)
        :param twilio_call_sid: The twilio SID of the call to hang up
        """
        twilio_rest_client = TwilioRestClient(
            os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
        )
        logger.info(f"The call sid that is being hung up is {twilio_call_sid}")

        call = twilio_rest_client.calls(twilio_call_sid).update(status="completed")
        await execute_status_update_by_telephony_id(
            telephony_id=twilio_call_sid, call_status=call_status, call_type=call_type
        )
        return call.status

    async def run(
        self, action_input: ActionInput[HangUpCallParameters]
    ) -> ActionOutput[HangUpCallResponse]:
        twilio_call_sid = self.get_twilio_sid(action_input)

        await self.hangup_twilio_call(
            call_status=self.action_config.call_status,
            call_type=self.action_config.call_type,
            twilio_call_sid=twilio_call_sid,
        )

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=HangUpCallResponse(status="success"),
        )

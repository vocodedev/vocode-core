import asyncio
import logging
import os
import threading
from typing import Type

from pydantic import BaseModel, Field
from twilio.rest import Client as TwilioRestClient
from vocode.streaming.action.phone_call_action import TwilioPhoneCallAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.models.telephony import TwilioConfig

from telephony_app.models.call_status import CallStatus
from telephony_app.models.call_type import CallType
from telephony_app.utils.call_information_handler import (
    execute_status_update_by_telephony_id,
)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HangUpCallActionConfig(ActionConfig, type=ActionType.HANGUP_CALL):
    call_status: CallStatus
    call_type: CallType
    starting_phrase: str
    twilio_config: TwilioConfig


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
        self,
        call_status: CallStatus,
        call_type: CallType,
        twilio_call_sid: str,
        twilio_config: TwilioConfig,
    ):
        """
        Hangs up an active Twilio call.

        :param call_status: The call status we want the call to be updated to
        :param call_type: Type of the call (inbound or outbound)
        :param twilio_call_sid: The twilio SID of the call to hang up
        :param twilio_config: The twilio config for the account we're calling with
        """
        twilio_rest_client = TwilioRestClient(
            twilio_config.account_sid, twilio_config.auth_token
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

        def background_task():
            async def delayed_hangup():
                await asyncio.sleep(3.5)
                await self.hangup_twilio_call(
                    call_status=self.action_config.call_status,
                    call_type=self.action_config.call_type,
                    twilio_call_sid=twilio_call_sid,
                    twilio_config=self.action_config.twilio_config,
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(delayed_hangup())
            loop.close()

        threading.Thread(target=background_task).start()

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=HangUpCallResponse(status="success"),
        )

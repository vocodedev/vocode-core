import asyncio
import logging
import os
import time

from typing import Optional

import urllib.parse
from aioify import aioify
from twilio.rest import Client
from xml.etree import ElementTree as ET

from vocode.streaming.models.telephony import BaseCallConfig, TwilioConfig
from vocode.streaming.telephony.call_information_handler_helpers.call_information_handler import \
    get_transfer_conference_sid, execute_status_update_by_telephony_id
from vocode.streaming.telephony.call_information_handler_helpers.call_status import CallStatus
from vocode.streaming.telephony.client.base_telephony_client import BaseTelephonyClient
from vocode.streaming.telephony.templater import Templater

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TwilioClient(BaseTelephonyClient):
    def __init__(self, base_url: str, twilio_config: TwilioConfig):
        super().__init__(base_url)
        self.twilio_config = twilio_config
        # TODO: this is blocking
        self.twilio_client = Client(twilio_config.account_sid, twilio_config.auth_token)
        try:
            # Test credentials
            self.twilio_client.api.accounts(twilio_config.account_sid).fetch()
        except Exception as e:
            raise RuntimeError(
                "Could not create Twilio client. Invalid credentials"
            ) from e
        self.templater = Templater()

    def get_telephony_config(self):
        return self.twilio_config

    async def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,
        digits: Optional[str] = None
    ) -> str:
        # TODO: Make this async. This is blocking.
        twiml = self.get_connection_twiml(conversation_id=conversation_id)
        twilio_call = self.twilio_client.calls.create(
            twiml=twiml.body.decode("utf-8"),
            to=to_phone,
            from_=from_phone,
            send_digits=digits,
            record=record,
            timeout=30,
            status_callback=f"https://{os.getenv('BASE_URL')}/handle_status_callback/{urllib.parse.quote_plus(conversation_id)}",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method="POST",
            # machine_detection="Enable",
            **self.get_telephony_config().extra_params,
        )
        return twilio_call.sid

    def get_connection_twiml(self, conversation_id: str):
        return self.templater.get_connection_twiml(
            base_url=self.base_url, call_id=conversation_id
        )

    async def fetch_transfer_conference_sid(self, twilio_sid, max_retries=5, retry_interval=3):
        for _ in range(max_retries):
            response = await get_transfer_conference_sid(twilio_sid)
            calls = response.get('data', {}).get('calls', [])

            if calls and 'transfer_conference_sid' in calls[0]:
                return calls[0]['transfer_conference_sid']

            # If the data is not yet available, wait for retry_interval seconds before trying again
            await asyncio.sleep(retry_interval)
        return None  # Return None if data is not found after all retries

    async def end_call(self, twilio_sid):
        logging.info("I am ending the call now within the twilio client code")
        current_call = self.twilio_client.calls(twilio_sid).fetch()
        transfer_conference_sid = await self.fetch_transfer_conference_sid(twilio_sid)

        # if the call is part of a conference, we should just let it keep going instead
        if current_call.parent_call_sid is not None or transfer_conference_sid:
            await execute_status_update_by_telephony_id(telephony_id=twilio_sid,
                                                        call_status=CallStatus.TRANSFERRED.value)
            return False

        await execute_status_update_by_telephony_id(telephony_id=twilio_sid,
                                                    call_status=CallStatus.ENDED_BEFORE_TRANSFER.value)
        response = self.twilio_client.calls(twilio_sid).update(status="completed")
        return response.status == "completed"

    def validate_outbound_call(
        self,
        to_phone: str,
        from_phone: str,
        mobile_only: bool = False, # originally to conform with California law; we leave as False for testing purposes
    ):
        if len(to_phone) < 8:
            raise ValueError("Invalid 'to' phone")

        if not mobile_only:
            return
        line_type_intelligence = (
            self.twilio_client.lookups.v2.phone_numbers(to_phone)
            .fetch(fields="line_type_intelligence")
            .line_type_intelligence
        )
        if not line_type_intelligence or (
            line_type_intelligence and line_type_intelligence["type"] != "mobile"
        ):
            raise ValueError("Can only call mobile phones")

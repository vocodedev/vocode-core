import asyncio
import os
from typing import Optional

from twilio.rest import Client

from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.client.base_telephony_client import BaseTelephonyClient
from vocode.streaming.telephony.templater import Templater


class TwilioClient(BaseTelephonyClient):
    def __init__(self, base_url: str, twilio_config: TwilioConfig):
        super().__init__(base_url)
        self.twilio_config = twilio_config

        self.templater = Templater()
        self._client_ready = asyncio.Event()

        self._twilio_client = None
        self._client_initialized = False

    async def initialize_client(self):
        if not self._client_initialized:
            self._twilio_client = Client(self.twilio_config.account_sid, self.twilio_config.auth_token)
            try:
                # Test credentials
                self._twilio_client.api.accounts(self.twilio_config.account_sid).fetch()
            except Exception as e:
                raise RuntimeError("Could not create Twilio client. Invalid credentials") from e
            self._client_initialized = True

    @property
    def twilio_client(self):
        if not self._client_initialized:
            raise RuntimeError("Twilio client is not initialized. Call 'initialize_client' asynchronously.")
        return self._twilio_client

    def get_telephony_config(self):
        return self.twilio_config

    async def create_call(self, conversation_id: str, to_phone: str, from_phone: str, record: bool = False,
                          digits: Optional[str] = None) -> str:
        loop = asyncio.get_running_loop()
        twiml = self.get_connection_twiml(conversation_id=conversation_id)
        # if provided, use the status callback from the environment variable.
        status_callback = f'https://{self.base_url}/call_status' if os.getenv("STATUS_CALLBACK") is None else os.getenv(
            "STATUS_CALLBACK")

        twilio_call = await loop.run_in_executor(
            None,
            lambda: self.twilio_client.calls.create(
                twiml=twiml.body.decode("utf-8"),
                to=to_phone,
                from_=from_phone,
                send_digits=digits,
                record=record,
                status_callback=status_callback,
                status_callback_event=['ringing', 'answered', 'completed'],
                status_callback_method='POST',
                **self.get_telephony_config().extra_params,
            )
        )
        return twilio_call.sid

    def get_connection_twiml(self, conversation_id: str):
        return self.templater.get_connection_twiml(
            base_url=self.base_url, call_id=conversation_id
        )

    async def end_call(self, twilio_sid):
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.twilio_client.calls(twilio_sid).update(status="completed")
        )
        return response.status == "completed"

    async def validate_outbound_call(self, to_phone: str, from_phone: str, mobile_only: bool = True):
        if len(to_phone) < 8:
            raise ValueError("Invalid 'to' phone")

        if not mobile_only:
            return

        loop = asyncio.get_running_loop()
        line_type_intelligence = await loop.run_in_executor(
            None,
            lambda: self.twilio_client.lookups.v2.phone_numbers(to_phone)
            .fetch(fields="line_type_intelligence")
            .line_type_intelligence
        )

        # if not line_type_intelligence or (line_type_intelligence and line_type_intelligence["type"] != "mobile"):
        #     raise ValueError("Can only call mobile phones")

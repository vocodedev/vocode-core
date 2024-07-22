# Standard library imports
import os
import sys

import twilio
from custom_action_factory import MyCustomActionFactory
from custom_agent import CustomAgentConfig
from custom_agent_factory import CustomAgentFactory

# Local application/library specific imports
from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from pyngrok import ngrok
from sms_send_appointment_noti import SMSSendAppointmentNotiVocodeActionConfig

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

app = FastAPI(docs_url=None)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

agent_config=CustomAgentConfig(
    initial_message=BaseMessage(text="Hello! Are you here to set up an appointment?"),
    prompt_preamble="""If the caller confirms that they want to set up an appointment, complete these steps without moving onto the next step until the previous step is complete:
    - Collect patient's name and date of birth
    - Collect insurance information including payer name and ID
    - Ask if they have a referral, and to which physician
    - Collect chief medical complaint/reason they are coming in
    - Collect other demographics like address
    - Collect contact information, specifically phone number including the country code
    - Offer up best available providers and times with the following options: July 22nd at 9:00 AM with Dr. Shen or August 1st at 12:30 PM with Dr. Jaron""",
    generate_responses=True,
    openai_api_key=os.environ["OPENAI_API_KEY"],
    actions=[
        SMSSendAppointmentNotiVocodeActionConfig(
            type = "action_SMS_send_appointment_noti"
        ),
    ]
)

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=agent_config,
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=CustomAgentFactory(agent_config, action_factory=MyCustomActionFactory()),
)

app.include_router(telephony_server.get_router())

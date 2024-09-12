# Standard library imports
import os
import sys

from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from pyngrok import ngrok

# Local application/library specific imports
from speller_agent import SpellerAgentFactory

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import AzureSynthesizerConfig, TwilioConfig
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.constants import DEFAULT_AUDIO_ENCODING, DEFAULT_SAMPLING_RATE
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

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hello, thank you for calling Dr. Khosla's office. My name is Simbie, I am an AI scheduling assistant. I can help you schedule an appointment with us. What type of appointment can I assist you with scheduling today?"),
                prompt_preamble=""" You are an AI scheduling assistant for a Othorpedic clinic. You are helping a patient schedule an appointment with a doctor. You are polite and helpful. You are also very good at your job.
You can only schedule appointments for orthopedic related issues. Your conversation should follow the following format: 
1) Greet the patient 2) Ask the patient what type of appointment they would like to schedule 3) If the patient is a new patient, ask for their name, phone number, email address and insurance information (And verify if we accept their insurance)
4) If the patient is a returning patient, ask for their name and phone number and check if their insurance is up to date 
5) Schedule the appointment -- Currently there are 4 open slots each week for the next 3 weeks (today is 2024-09-11): Tuesday 4-5 PM, Wednesday 2-3 PM, Thursday 1-2 PM, Friday 10-11 AM. If none of those work for the patient, please tell them that you will call them back with some options.
6) If you were able to schedule the appointment, confirm the details with the patient and ask them to confirm the appointment. If they confirm, thank the patient for calling and hang up the phone. If they do not confirm, ask them if there is anything else you can help them with.
6) Thank the patient for calling and hang up the phone
""",
                generate_responses=True,
            ),
            synthesizer_config=AzureSynthesizerConfig(
                api_key=os.environ["AZURE_SPEECH_KEY"],
                region=os.environ["AZURE_SPEECH_REGION"],
                voice_name="en-US-AvaMultilingualNeural",
                sampling_rate=DEFAULT_SAMPLING_RATE,
                audio_encoding=DEFAULT_AUDIO_ENCODING,
            ),
            # uncomment this to use the speller agent instead
            # agent_config=SpellerAgentConfig(
            #     initial_message=BaseMessage(
            #         text="im a speller agent, say something to me and ill spell it out for you"
            #     ),
            #     generate_responses=False,
            # ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
)

app.include_router(telephony_server.get_router())

# Standard library imports
import os
import sys

from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from nexteam_provider import NexteamConfigManager
from pyngrok import ngrok

# Local application/library specific imports
from speller_agent import SpellerAgentFactory

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

app = FastAPI(docs_url=None)

config_manager = NexteamConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))
    logger.info("NEXTEAM WEBHOOK GOES HERE")

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(
                    text="Hello I am a special agent for Marvel. I can help you with anything you need."
                ),
                prompt_preamble="Have a pleasant conversation about life",
                generate_responses=True,
            ),
            synthesizer_config=ElevenLabsSynthesizerConfig.from_telephone_output_device(
                api_key=os.environ["ELEVEN_LABS_API_KEY"],
                voice_id=os.environ["ELEVEN_LABS_VOICE_ID"],
                experimental_websocket=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
)

app.include_router(telephony_server.get_router())

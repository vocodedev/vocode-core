import logging
import os
from fastapi import FastAPI
from pyngrok import ngrok
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import InboundCallConfig, TelephonyServer

from speller_agent import SpellerAgentFactory
import sys

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager()

BASE_URL = os.environ["BASE_URL"]

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info("ngrok tunnel \"{}\" -> \"http://127.0.0.1:{}\"".format(BASE_URL, port))

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        InboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="Have a pleasant conversation about life",
                generate_responses=True,
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
    logger=logger,
)

app.include_router(telephony_server.get_router())

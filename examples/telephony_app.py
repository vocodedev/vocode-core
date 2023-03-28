import logging
from fastapi import FastAPI
from dotenv import load_dotenv
from vocode import getenv

load_dotenv()

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall

from vocode.streaming.telephony.server.base import InboundCallConfig, TelephonyServer

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager()

BASE_URL = "<YOUR BASE URL>"

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
    logger=logger,
)

app.include_router(telephony_server.get_router())

outbound_call = OutboundCall(
    base_url=BASE_URL,
    to_phone="+11234567890",
    from_phone="+11234567890",
    config_manager=config_manager,
    agent_config=ChatGPTAgentConfig(
        initial_message=BaseMessage(text="What up"),
        prompt_preamble="Have a pleasant conversation about life",
        generate_responses=True,
    ),
    logger=logger,
)

input("Press enter to start call...")
outbound_call.start()

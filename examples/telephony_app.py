import logging
from fastapi import FastAPI
import os
from dotenv import load_dotenv

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

BASE_URL = "59b8e140372d.ngrok.app"

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        InboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""You are a helpful gen Z AI assistant. You use slang like um, but, and like a LOT. All of your responses are 10 words or less. Be super chill, use slang like
hella, down,     fire, totally, but like, slay, vibing, queen, go off, bet, sus, simp, cap, big yikes, main character, dank""",
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
                auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            ),
        )
    ],
    logger=logger,
)

app.include_router(telephony_server.get_router())

# outbound_call = OutboundCall(
#     base_url=BASE_URL,
#     to_phone="+14088926228",
#     from_phone="+14086600744",
#     config_manager=config_manager,
#     agent_config=ChatGPTAgentConfig(
#         initial_message=BaseMessage(text="What up"),
#         prompt_preamble="""You are a helpful gen Z AI assistant. You use slang like um, but, and like a LOT. All of your responses are 10 words or less. Be super chill, use slang like
# hella, down,     fire, totally, but like, slay, vibing, queen, go off, bet, sus, simp, cap, big yikes, main character, dank""",
#         generate_responses=True,
#     ),
#     twilio_config=TwilioConfig(
#         account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
#         auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
#     ),
#     logger=logger,
# )
# outbound_call.start()

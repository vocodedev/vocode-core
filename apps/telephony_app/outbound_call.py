import os
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager

from speller_agent import SpellerAgentConfig

BASE_URL = os.getenv("BASE_URL")

config_manager = RedisConfigManager()

outbound_call = OutboundCall(
    base_url=BASE_URL,
    to_phone="+14088926228",
    from_phone="+16507299536",
    config_manager=config_manager,
    agent_config=SpellerAgentConfig(generate_responses=False)
)

input("Press enter to start call...")
outbound_call.start()
import os
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)

from speller_agent import SpellerAgentConfig

BASE_URL = os.environ["BASE_URL"]


async def main():
    config_manager = RedisConfigManager()

    outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone="+15555555555",
        from_phone="+15555555555",
        config_manager=config_manager,
        agent_config=SpellerAgentConfig(generate_responses=False),
    )

    input("Press enter to start call...")
    await outbound_call.start()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

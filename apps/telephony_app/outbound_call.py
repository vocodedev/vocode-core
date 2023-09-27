import os
from dotenv import load_dotenv

from vocode import getenv
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.noise_canceler.noise_reduce import NoiseReduceNoiseCanceler, \
    NoiseReduceNoiseCancelingConfig

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
        to_phone="+17784007249",
        from_phone="+17786535432",
        config_manager=config_manager,
        mobile_only=False,
        twilio_config=TwilioConfig(
            account_sid=getenv("TWILIO_ACCOUNT_SID"),
            auth_token=getenv("TWILIO_AUTH_TOKEN"),
            noise_canceling_config=NoiseReduceNoiseCancelingConfig(use_torch=False),
        ),
        agent_config=SpellerAgentConfig(generate_responses=False),
    )

    await outbound_call.start()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

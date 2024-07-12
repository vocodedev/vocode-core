import os

from dotenv import load_dotenv

from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.pipeline import StreamingConversationConfig
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.telephony import TwilioCallConfig, TwilioConfig

load_dotenv()

from speller_agent import SpellerAgentConfig

from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall

BASE_URL = os.environ["BASE_URL"]


async def main():
    config_manager = RedisConfigManager()

    outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone="+15555555555",
        from_phone="+15555555555",
        config_manager=config_manager,
        pipeline_config=StreamingConversationConfig(
            transcriber_config=TwilioCallConfig.default_transcriber_config(),
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="Have a pleasant conversation about life",
                generate_responses=True,
            ),
            synthesizer_config=AzureSynthesizerConfig.from_telephone_output_device(
                voice_name="en-US-AriaNeural"
            ),
        ),
        telephony_config=TwilioConfig(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        ),
    )

    input("Press enter to start call...")
    await outbound_call.start()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

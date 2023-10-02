import os

from dotenv import load_dotenv

from vocode import getenv
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig, PunctuationEndpointingConfig
from vocode.streaming.telephony.noise_canceler import WebRTCNoiseCancelingConfig

load_dotenv()

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)

from speller_agent import SpellerAgentConfig

BASE_URL = os.environ["BASE_URL"]


async def main():
    config_manager = RedisConfigManager()
    eleven_conf = ElevenLabsSynthesizerConfig(sampling_rate=8000, audio_encoding=AudioEncoding.MULAW)
    eleven_conf.api_key = 'b47ca434de2ead60d51c530415595caa'
    eleven_conf.optimize_streaming_latency = 4
    eleven_conf.voice_id = 'rU18Fk3uSDhmg5Xh41o4'
    eleven_conf.experimental_streaming = True
    eleven_conf.stability = .8
    eleven_conf.similarity_boost = .9
    eleven_conf.model_id = 'eleven_monolingual_v1'

    transcriber_config = DeepgramTranscriberConfig(sampling_rate=8000, audio_encoding=AudioEncoding.MULAW,
                                                   chunk_size=2048)
    transcriber_config.mute_during_speech = False
    transcriber_config.model = 'phonecall'
    endpoint_config = PunctuationEndpointingConfig()
    endpoint_config.time_cutoff_seconds = 0.4
    transcriber_config.endpointing_config = endpoint_config

    outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone="+17784007249",
        synthesizer_config=eleven_conf,
        from_phone="+17786535432",
        config_manager=config_manager,
        transcriber_config=transcriber_config,
        mobile_only=False,
        twilio_config=TwilioConfig(
            account_sid=getenv("TWILIO_ACCOUNT_SID"),
            auth_token=getenv("TWILIO_AUTH_TOKEN"),
            noise_canceling_config=WebRTCNoiseCancelingConfig(),
        ),
        agent_config=SpellerAgentConfig(generate_responses=False),
    )

    await outbound_call.start()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

import os
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgentConfig
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.vector_db.factory import VectorDBFactory
from vocode.streaming.vector_db.pinecone import PineconeConfig


BASE_URL = os.getenv('BASE_URL')

# create logger object
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    config_manager = RedisConfigManager()
    vector_db_config = PineconeConfig(
    index=os.getenv('PINECONE_INDEX_NAME')
    )

    agent_config = ChatGPTAgentConfig(
        max_tokens=100,
        temperature=0.7,
        initial_message=BaseMessage(text="Hello!, I am Jonathan Arcadia."),
        vector_db_config=vector_db_config,
        end_conversation_on_goodbye=True,
        prompt_preamble="""
                I want you to act as an IT Architect. 
            Who answers to user's ML doubts based on the book field guide to data science.
"""
    )

    synthesizer_config = AzureSynthesizerConfig(
        voice_name="en-US-SteffanNeural",
        language_code="en-US",
        sampling_rate=8000,
        audio_encoding=AudioEncoding.MULAW
    )

    transcriber_config = DeepgramTranscriberConfig(
        language="en-US",
        sampling_rate=8000,
        audio_encoding=AudioEncoding.MULAW,
        chunk_size=4000
    )

    outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone=os.environ["TWILIO_TO_NUMBER"],
        from_phone=os.environ["TWILIO_FROM_NUMBER"],
        config_manager=config_manager,
        agent_config=agent_config,
        synthesizer_config=synthesizer_config,
        transcriber_config=transcriber_config,
        logger=logger
    )

    try:
        await outbound_call.start()
    except Exception as e:
        print(e)
        await outbound_call.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

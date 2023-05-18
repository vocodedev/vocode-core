import asyncio
import json
import logging
import requests
import signal
from dotenv import load_dotenv


load_dotenv()

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.agent import (
    ChatGPTAgentConfig,
    ChatGPTAgentConfig,
)
from vocode.streaming.agent.web_socket_user_implemented_agent import (
    WebSocketUserImplementedAgent,
)
from vocode.streaming.models.web_socket_agent import (
    WebSocketUserImplementedAgentConfig,
    WebSocketAgentMessage,
    WebSocketAgentTextMessage,
    WebSocketAgentTextStopMessage,
    WebSocketAgentStopMessage,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
)
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def on_response(message: WebSocketAgentMessage) -> None:
    if isinstance(message, WebSocketAgentTextMessage):
        print("Received text message: %s" % message.text)
    elif isinstance(message, WebSocketAgentTextStopMessage):
        print("Received text stop message: %s" % message.text)
    elif isinstance(message, WebSocketAgentMessage):
        print("Received stop message: %s" % message)
    else:
        print("Received unknown message type: %s" % message)


async def main() -> None:
    conversation_create_url = "https://adam-api.of.one/devices/744f0678-4f85-4572-976e-3b1eb88e81c7/conversations"

    ofone_conversation = requests.post(
        conversation_create_url,
        timeout=10,
        )
    print("Created OfOne conversation %s" % ofone_conversation)
    ofone_conversation_json = json.loads(ofone_conversation.text)
    ofone_conversation_id = ofone_conversation_json["id"]["id"]
    logging.info("Created OfOne conversation %s" % ofone_conversation_id)

    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        streaming=True, use_default_devices=True
    )

    socket_url = "wss://adam-api.of.one/vocode/conversations/%s/agent" % ofone_conversation_id
    logging.info("Connecting to %s" % socket_url)
    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input, endpointing_config=PunctuationEndpointingConfig()
            )
        ),
        agent=WebSocketUserImplementedAgent(
            agent_config=WebSocketUserImplementedAgentConfig(
                initial_message=BaseMessage(text=ofone_conversation_json["greeting"]),
                respond=WebSocketUserImplementedAgentConfig.RouteConfig(
                    url=socket_url,
                ),
                on_response=on_response
            ),
            logger=logger,
        ),
        synthesizer=AzureSynthesizer(
            AzureSynthesizerConfig.from_output_device(speaker_output)
        ),
        mute_mic_during_agent_response=True,
        logger=logger,
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.terminate())
    while conversation.is_active():
        chunk = microphone_input.get_audio()
        if chunk:
            conversation.receive_audio(chunk)
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())

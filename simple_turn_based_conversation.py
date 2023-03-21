import logging
from dotenv import load_dotenv
import os
from vocode.helpers import create_microphone_input_and_speaker_output
import vocode
from vocode.turn_based.agent.chat_gpt_agent import ChatGPTAgent
from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.turn_based.transcriber.whisper_transcriber import WhisperTranscriber
from vocode.turn_based.turn_based_conversation import TurnBasedConversation

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv()

if __name__ == "__main__":
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        streaming=False, use_default_devices=False
    )

    conversation = TurnBasedConversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber=WhisperTranscriber(),
        agent=ChatGPTAgent(
            system_prompt="The AI is having a pleasant conversation about life",
            initial_message="Hello!",
        ),
        synthesizer=AzureSynthesizer(sampling_rate=speaker_output.sampling_rate),
        logger=logger,
    )
    print("Starting conversation. Press Ctrl+C to exit.")
    while True:
        try:
            input("Press enter to start recording...")
            conversation.start_speech()
            input("Press enter to end recording...")
            conversation.end_speech_and_respond()
        except KeyboardInterrupt:
            break

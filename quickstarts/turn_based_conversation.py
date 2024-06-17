from pydantic_settings import BaseSettings, SettingsConfigDict

from vocode.helpers import create_turn_based_microphone_input_and_speaker_output
from vocode.turn_based.agent.chat_gpt_agent import ChatGPTAgent
from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.turn_based.transcriber.whisper_transcriber import WhisperTranscriber
from vocode.turn_based.turn_based_conversation import TurnBasedConversation


class Settings(BaseSettings):
    """
    Settings for the turn-based conversation quickstart.
    These parameters can be configured with environment variables.
    """

    openai_api_key: str = "ENTER_YOUR_OPENAI_API_KEY_HERE"
    azure_speech_key: str = "ENTER_YOUR_AZURE_KEY_HERE"

    azure_speech_region: str = "eastus"

    # This means a .env file can be used to overload these settings
    # ex: "OPENAI_API_KEY=my_key" will set openai_api_key over the default above
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

if __name__ == "__main__":
    (
        microphone_input,
        speaker_output,
    ) = create_turn_based_microphone_input_and_speaker_output(
        use_default_devices=False,
    )

    conversation = TurnBasedConversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber=WhisperTranscriber(api_key=settings.openai_api_key),
        agent=ChatGPTAgent(
            system_prompt="The AI is having a pleasant conversation about life",
            initial_message="Hello!",
            api_key=settings.openai_api_key,
        ),
        synthesizer=AzureSynthesizer(
            api_key=settings.azure_speech_key,
            region=settings.azure_speech_region,
            voice_name="en-US-SteffanNeural",
        ),
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

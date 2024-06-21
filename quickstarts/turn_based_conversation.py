from pydantic_settings import BaseSettings, SettingsConfigDict

from vocode.helpers import create_turn_based_microphone_input_and_speaker_output
from vocode.turn_based.agent.chat_gpt_agent import ChatGPTAgent
# from vocode.turn_based.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.eleven_labs_websocket_synthesizer import ElevenLabsWSSynthesizer
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.turn_based.transcriber.whisper_transcriber import WhisperTranscriber
from vocode.turn_based.turn_based_conversation import TurnBasedConversation


class Settings(BaseSettings):
    """
    Settings for the turn-based conversation quickstart.
    These parameters can be configured with environment variables.
    """

    openai_api_key: str = "sk-proj-YeZ7h3bQATXqQfuVCidlT3BlbkFJfyMaB1XDzLrPhtunO0Wq"
    elevenlabs_api_key: str = "c351ed39bfa85844ca69178632bab531"
    elevenlabs_voice_id: str = "keegJi4htO6RUdRwPfLR"
    deepgram_api_key: str = "999a6bd1716edd8ced35b6264a90d929be733974"

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
        synthesizer=ElevenLabsWSSynthesizer(
            ElevenLabsSynthesizerConfig.from_output_device(
            speaker_output,
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            experimental_websocket=True,
            ),
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

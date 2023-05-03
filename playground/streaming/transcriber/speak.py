import signal
from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.input_device.microphone_input import MicrophoneInput
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber, Transcription
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    async def listen():
        async def on_response(response: Transcription):
            print(response)

        microphone_input = MicrophoneInput.from_default_device()
        transcriber = DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input, endpointing_config=PunctuationEndpointingConfig()
            )
        )
        transcriber.set_on_response(on_response)
        asyncio.create_task(transcriber.run())
        print("Transcriber started, press Ctrl+C to end")
        while True:
            chunk = microphone_input.get_audio()
            if chunk:
                transcriber.send_audio(chunk)
            await asyncio.sleep(0)

    asyncio.run(listen())

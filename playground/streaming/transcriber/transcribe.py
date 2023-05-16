import signal
from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.input_device.microphone_input import MicrophoneInput
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber, Transcription
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.utils.worker import ThreadAsyncWorker


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    async def print_output(transcriber: BaseTranscriber):
        while True:
            transcription: Transcription = await transcriber.output_queue.get()
            print(transcription)

    async def listen():
        microphone_input = MicrophoneInput.from_default_device()

        # replace with the transcriber you want to test
        transcriber = DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input, endpointing_config=PunctuationEndpointingConfig()
            )
        )
        transcriber.start()
        asyncio.create_task(print_output(transcriber))
        print("Start speaking...press Ctrl+C to end. ")
        while True:
            chunk = microphone_input.get_audio()
            if chunk:
                transcriber.send_audio(chunk)
            await asyncio.sleep(0)

    asyncio.run(listen())

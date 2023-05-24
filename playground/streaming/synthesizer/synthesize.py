import time
from typing import Optional
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    GoogleSynthesizerConfig,
    PlayHtSynthesizerConfig,
    RimeSynthesizerConfig,
)
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.output_device.speaker_output import SpeakerOutput
from vocode.streaming.synthesizer import *
from vocode.streaming.utils import get_chunk_size_per_second


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    seconds_per_chunk = 1

    async def speak(
        synthesizer: BaseSynthesizer,
        output_device: BaseOutputDevice,
        message: BaseMessage,
        bot_sentiment: Optional[BotSentiment] = None,
    ):
        message_sent = message.text
        cut_off = False
        chunk_size = seconds_per_chunk * get_chunk_size_per_second(
            synthesizer.get_synthesizer_config().audio_encoding,
            synthesizer.get_synthesizer_config().sampling_rate,
        )
        synthesis_result = await synthesizer.create_speech(
            message=message,
            chunk_size=chunk_size,
            bot_sentiment=bot_sentiment,
        )
        chunk_idx = 0
        async for chunk_result in synthesis_result.chunk_generator:
            try:
                start_time = time.time()
                speech_length_seconds = seconds_per_chunk * (
                    len(chunk_result.chunk) / chunk_size
                )
                output_device.consume_nonblocking(chunk_result.chunk)
                end_time = time.time()
                await asyncio.sleep(
                    max(
                        speech_length_seconds - (end_time - start_time),
                        0,
                    )
                )
                print(
                    "Sent chunk {} with size {}".format(
                        chunk_idx, len(chunk_result.chunk)
                    )
                )
                chunk_idx += 1
            except asyncio.CancelledError:
                seconds = chunk_idx * seconds_per_chunk
                print(
                    "Interrupted, stopping text to speech after {} chunks".format(
                        chunk_idx
                    )
                )
                message_sent = f"{synthesis_result.get_message_up_to(seconds)}-"
                cut_off = True
                break

        return message_sent, cut_off

    async def main():
        while True:
            message_sent, _ = await speak(
                synthesizer=synthesizer,
                output_device=speaker_output,
                message=BaseMessage(text=input("Enter speech to synthesize: ")),
            )
            print("Message sent: ", message_sent)

    speaker_output = SpeakerOutput.from_default_device()

    # replace with the synthesizer you want to test
    synthesizer = AzureSynthesizer(
        AzureSynthesizerConfig.from_output_device(speaker_output)
    )
    asyncio.run(main())

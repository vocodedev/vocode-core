import asyncio
import base64
import logging
import os
import random
import re
import tempfile

# get req for wav as wav
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Tuple
from xml.etree import ElementTree

import aiohttp
import azure.cognitiveservices.speech as speechsdk
import numpy as np
from opentelemetry.context.context import Context
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage, SSMLMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    AFFIRMATIVE_AUDIO_PATH,
    AFFIRMATIVE_PHRASES,
    FILLER_AUDIO_PATH,
    FILLER_PHRASES,
    BaseSynthesizer,
    FillerAudio,
    SynthesisResult,
    encode_as_wav,
    tracer,
)

NAMESPACES = {
    "mstts": "https://www.w3.org/2001/mstts",
    "": "https://www.w3.org/2001/10/synthesis",
}

ElementTree.register_namespace("", NAMESPACES[""])
ElementTree.register_namespace("mstts", NAMESPACES["mstts"])


class WordBoundaryEventPool:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(
            {
                "text": event.text,
                "text_offset": event.text_offset,
                "audio_offset": (event.audio_offset + 5000) / (10000 * 1000),
                "boudary_type": event.boundary_type,
            }
        )

    def get_events_sorted(self):
        return sorted(self.events, key=lambda event: event["audio_offset"])


class AzureSynthesizer(BaseSynthesizer[AzureSynthesizerConfig]):
    OFFSET_MS = 100

    def __init__(
        self,
        synthesizer_config: AzureSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        azure_speech_key: Optional[str] = None,
        azure_speech_region: Optional[str] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
        azure_endpoint_id: Optional[str] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)
        # Instantiates a client

        azure_speech_key = (
            azure_speech_key
            or getenv("AZURE_SPEECH_KEY")
            or synthesizer_config.azure_speech_key
        )
        azure_speech_region = (
            azure_speech_region
            or getenv("AZURE_SPEECH_REGION")
            or synthesizer_config.azure_speech_region
        )
        azure_endpoint_id = (
            azure_endpoint_id
            or getenv("AZURE_ENDPOINT_ID")
            or synthesizer_config.azure_endpoint_id
        )
        if not azure_speech_key:
            raise ValueError(
                "Please set AZURE_SPEECH_KEY environment variable or pass it as a parameter"
            )
        if not azure_speech_region:
            raise ValueError(
                "Please set AZURE_SPEECH_REGION environment variable or pass it as a parameter"
            )
        speech_config = speechsdk.SpeechConfig(
            subscription=azure_speech_key, region=azure_speech_region
        )

        speech_config.speech_synthesis_voice_name = "PlaygroundLiteNeural"
        if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            if self.synthesizer_config.sampling_rate == 44100:
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Raw44100Hz16BitMonoPcm
                )
            if self.synthesizer_config.sampling_rate == 48000:
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
                )
            if self.synthesizer_config.sampling_rate == 24000:
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm
                )
            elif self.synthesizer_config.sampling_rate == 16000:
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
                )
            elif self.synthesizer_config.sampling_rate == 8000:
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm
                )
        elif self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw
            )
        self.synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        if azure_endpoint_id and "neural" in self.synthesizer_config.voice_name.lower():
            speech_config.endpoint_id = azure_endpoint_id

        self.voice_name = self.synthesizer_config.voice_name
        self.pitch = self.synthesizer_config.pitch
        self.rate = self.synthesizer_config.rate
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=4)
        self.logger = logger or logging.getLogger(__name__)

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        async def generate_filler_audio(filler_phrase):
            cache_key = "-".join(
                (
                    str(filler_phrase.text),
                    str(self.synthesizer_config.type),
                    str(self.synthesizer_config.audio_encoding),
                    str(self.synthesizer_config.sampling_rate),
                    str(self.voice_name),
                    str(self.pitch),
                    str(self.rate),
                )
            )
            filler_audio_path = os.path.join(FILLER_AUDIO_PATH, f"{cache_key}.bytes")
            if not os.path.exists(filler_audio_path):
                self.logger.debug(f"Generating filler audio for {filler_phrase.text}")
                ssml = await self.create_ssml(filler_phrase.text, volume=50, rate=4)
                result = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool_executor, self.synthesizer.speak_ssml, ssml
                )
                offset = self.synthesizer_config.sampling_rate * self.OFFSET_MS // 1000
                audio_data = result.audio_data[offset:]
                with open(filler_audio_path, "wb") as f:
                    f.write(audio_data)
            else:
                with open(filler_audio_path, "rb") as f:
                    audio_data = f.read()
            return FillerAudio(
                filler_phrase,
                audio_data,
                self.synthesizer_config,
            )

        tasks = [generate_filler_audio(phrase) for phrase in FILLER_PHRASES]
        filler_phrase_audios = await asyncio.gather(*tasks)
        return filler_phrase_audios

    async def get_phrase_affirmative_audios(self) -> List[FillerAudio]:
        async def generate_affirmative_audio(affirmative_phrase):
            cache_key = "-".join(
                (
                    str(affirmative_phrase.text),
                    str(self.synthesizer_config.type),
                    str(self.synthesizer_config.audio_encoding),
                    str(self.synthesizer_config.sampling_rate),
                    str(self.voice_name),
                    str(self.pitch),
                    str(self.rate),
                )
            )
            affirmative_audio_path = os.path.join(
                AFFIRMATIVE_AUDIO_PATH, f"{cache_key}.bytes"
            )
            if not os.path.exists(affirmative_audio_path):
                self.logger.debug(
                    f"Generating affirmative audio for {affirmative_phrase.text}"
                )
                ssml = await self.create_ssml(
                    affirmative_phrase.text, volume=55, rate=2
                )
                result = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool_executor, self.synthesizer.speak_ssml, ssml
                )
                offset = self.synthesizer_config.sampling_rate * self.OFFSET_MS // 1000
                audio_data = result.audio_data[offset:]
                with open(affirmative_audio_path, "wb") as f:
                    f.write(audio_data)
            else:
                with open(affirmative_audio_path, "rb") as f:
                    audio_data = f.read()
            return FillerAudio(
                affirmative_phrase,
                audio_data,
                self.synthesizer_config,
            )

        tasks = [generate_affirmative_audio(phrase) for phrase in AFFIRMATIVE_PHRASES]
        affirmative_phrase_audios = await asyncio.gather(*tasks)
        self.logger.debug("Affirmative audios generated")
        return affirmative_phrase_audios

    def add_marks(self, message: str, index=0) -> str:
        search_result = re.search(r"([\.\,\:\;\-\—]+)", message)
        if search_result is None:
            return message
        start, end = search_result.span()
        with_mark = message[:start] + f'<mark name="{index}" />' + message[start:end]
        rest = message[end:]
        rest_stripped = re.sub(r"^(.+)([\.\,\:\;\-\—]+)$", r"\1", rest)
        if len(rest_stripped) == 0:
            return with_mark
        return with_mark + self.add_marks(rest_stripped, index + 1)

    def word_boundary_cb(self, evt, pool):
        pool.add(evt)

    async def create_ssml(
        self,
        message: str,
        bot_sentiment: Optional[BotSentiment] = None,
        volume: int = 1,
        rate: int = -1,
    ) -> str:
        # Detect DTMF patterns
        dtmf_pattern = re.compile(r"DTMF_(\w)")
        parts = dtmf_pattern.split(message)
        # parts will be a list where even indices are normal text and odd indices are DTMF tones

        ssml_content = ""

        for index, part in enumerate(parts):
            if index % 2 == 0:
                # Normal text part
                if part:
                    ssml_content += part
            else:
                # DTMF tone part
                tone = part.upper()
                dtmf_url = f"https://evolution.voxeo.com/library/audio/prompts/dtmf/Dtmf-{tone}.wav"
                ssml_content += (
                    f'<audio src="{dtmf_url}">'
                    f'<prosody volume="0">DTMF tone {tone}</prosody>'
                    "</audio>"
                )

        # proceed with the existing SSML creation using ssml_content
        # remove trailing comma from message, if it exists
        message_text = ssml_content.strip()
        if message_text and message_text[-1] == ",":
            message_text = message_text[:-1]
        if rate == -1:
            rate = self.rate
        # remove newline from message to prevent it from saying "slash n"
        message_text = message_text.replace("\n", " ")
        # remove escaped newline from message
        message_text = message_text.replace("\\n", " ")
        # remove backslashes from message
        message_text = message_text.replace("\\", "")

        is_neural = "neural" in self.voice_name.lower()
        voice_language_code = (
            self.synthesizer_config.language_code if is_neural else None
        )
        rate_value = 0.1  # This rate assignment seems to be constant in both conditions

        code = f'"{voice_language_code}"' if voice_language_code else "None"
        if is_neural:
            ssml_root = ElementTree.fromstring(
                f'<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis"{f" xml:lang={code}" if voice_language_code else ""}></speak>'
            )
        else:
            ssml_root = ElementTree.fromstring(
                f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'></speak>"
            )
        voice = ElementTree.SubElement(ssml_root, "voice")
        voice.set("name", self.voice_name if is_neural else "PhoenixLatestNeural")

        if not is_neural:
            speaker = ElementTree.SubElement(
                voice, "{%s}ttsembedding" % NAMESPACES.get("mstts")
            )
            speaker.set("speakerProfileId", self.voice_name)
            speaker.text = message_text.strip()
        voice_root = voice
        if is_neural and self.synthesizer_config.language_code not in ["en-US", "en"]:
            lang = ElementTree.SubElement(voice, "{%s}lang" % NAMESPACES.get(""))
            lang.set("xml:lang", self.synthesizer_config.language_code)
            voice_root = lang

        if bot_sentiment and bot_sentiment.emotion and is_neural:
            styled = ElementTree.SubElement(
                voice_root, "{%s}express-as" % NAMESPACES.get("mstts")
            )
            styled.set("style", bot_sentiment.emotion)
            styled.set(
                "styledegree", str(bot_sentiment.degree * 2)
            )  # Azure specific, it's a scale of 0-2
            voice_root = styled

        if is_neural:
            prosody = ElementTree.SubElement(voice_root, "prosody")
            prosody.set("pitch", f"{self.pitch}%")
            prosody.set("rate", f"{rate_value * self.rate}%")
            # fixes symbols like euro for some reason
            message_text_encoded = message_text.encode("utf-8").decode("utf-8")
            prosody.set("volume", f"-{volume}%")
            prosody.text = message_text_encoded.strip()
            ElementTree.SubElement(prosody, "break", time="100ms")  # fixes the clicking

        self.logger.debug(
            f"""Created SSML: {ElementTree.tostring(ssml_root, encoding='unicode').replace("ns0:", "").replace(":ns0", "").replace("ns0", "")}"""
        )

        out = (
            ElementTree.tostring(ssml_root, encoding="unicode")
            .replace("ns0:", "")
            .replace(":ns0", "")
            .replace("ns0", "")
        )
        return out

    def synthesize_ssml(self, ssml: str) -> speechsdk.AudioDataStream:
        result = self.synthesizer.start_speaking_ssml_async(ssml).get()
        return speechsdk.AudioDataStream(result)

    def ready_synthesizer(self):
        connection = speechsdk.Connection.from_speech_synthesizer(self.synthesizer)
        connection.open(True)

    # given the number of seconds the message was allowed to go until, where did we get in the message?
    def get_message_up_to(
        self,
        message: str,
        ssml: str,
        seconds: float,
        word_boundary_event_pool: WordBoundaryEventPool,
    ) -> str:
        events = word_boundary_event_pool.get_events_sorted()
        # for event in events:
        #     if event["audio_offset"] > seconds:
        #         ssml_fragment = ssml[: event["text_offset"]]
        #         # TODO: this is a little hacky, but it works for now
        #         return ssml_fragment.split(">")[-1]
        return message

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        # this is so it says numbers slowly
        def remove_dashes(match):
            return match.group().replace("-", "...").replace("+", "")

        def format_digits(match):
            digits = match.group()
            digits = re.sub(
                r"(\d)-(\d)", r"\1\2", digits
            )  # Remove dashes between two numbers

            if len(digits) <= 7:
                formatted = ""
                for digit in digits:
                    formatted += digit + "... "
                return formatted

            first_digit = ""
            if len(digits) % 2 != 0:
                first_digit = digits[0]
                digits = digits[1:]

            formatted = ""
            for i in range(0, len(digits) - 4, 3):
                formatted += (
                    digits[i] + ", " + digits[i + 1] + ", " + digits[i + 2] + "... "
                )
            formatted += digits[-4:-2] + "... " + digits[-2:]

            if first_digit:
                ret = first_digit + "... " + formatted
                return ret
            return formatted

        modified_message = re.sub(
            r"\b\d+-\d+\b",
            remove_dashes,
            message.text.replace(" (", "").replace(") ", ""),
        )

        modified_message = re.sub(r"\b(\d{5,})\b", format_digits, modified_message)

        # offset = int(self.OFFSET_MS * (self.synthesizer_config.sampling_rate / 1000))
        offset = 0
        # self.logger.debug(f"Synthesizing message: {message}")

        # Azure will return no audio for certain strings like "-", "[-", and "!"
        # which causes the `chunk_generator` below to hang. Return an empty
        # generator for these cases.
        if not re.search(r"\w", message.text):
            return SynthesisResult(
                self.empty_generator(),
                lambda _: message.text,
            )

            # Start of Selection

        async def chunk_generator(
            audio_data_stream: speechsdk.AudioDataStream, chunk_transform=lambda x: x
        ):
            while True:
                if audio_data_stream.can_read_data(chunk_size):
                    try:
                        audio_buffer = bytes(chunk_size)
                        bytes_read = audio_data_stream.read_data(audio_buffer)
                        data = audio_buffer[:bytes_read]
                        yield SynthesisResult.ChunkResult(
                            chunk_transform(data),
                            True,
                        )
                    except Exception as e:
                        self.logger.error(f"Error reading data: {e}")
                        await asyncio.sleep(0.1)
                else:
                    # Check if the stream is finished
                    if audio_data_stream.status == speechsdk.StreamStatus.AllData:
                        # self.logger.debug("Stream status is FINISHED")
                        break
                    # self.logger.debug("Waiting for more audio data")
                    await asyncio.sleep(0.1)

        word_boundary_event_pool = WordBoundaryEventPool()
        self.synthesizer.synthesis_word_boundary.connect(
            lambda event: self.word_boundary_cb(event, word_boundary_event_pool)
        )

        # Split the message into parts and handle DTMF tones separately
        dtmf_pattern = re.compile(r"DTMF_(\w)")
        parts = dtmf_pattern.split(modified_message)

        async def dtmf_audio_generator(tone: str):
            dtmf_url = f"https://evolution.voxeo.com/library/audio/prompts/dtmf/Dtmf-{tone}.wav"
            async with aiohttp.ClientSession() as session:
                async with session.get(dtmf_url) as response:
                    audio_data = await response.read()
                    yield SynthesisResult.ChunkResult(audio_data, True)

        async def combined_generator():
            for index, part in enumerate(parts):
                if index % 2 == 0:
                    # Normal text part
                    if part:
                        ssml = await self.create_ssml(part, bot_sentiment=bot_sentiment)
                        audio_data_stream = (
                            await asyncio.get_event_loop().run_in_executor(
                                self.thread_pool_executor, self.synthesize_ssml, ssml
                            )
                        )
                        async for chunk in chunk_generator(audio_data_stream):
                            yield chunk
                else:
                    # DTMF tone part
                    tone = part.upper()
                    async for chunk in dtmf_audio_generator(tone):
                        yield chunk

        return SynthesisResult(
            combined_generator(),
            lambda seconds: self.get_message_up_to(
                message.text, "", seconds, word_boundary_event_pool
            ),
        )

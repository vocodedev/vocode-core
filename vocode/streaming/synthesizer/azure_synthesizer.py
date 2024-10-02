import asyncio
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

import aiohttp
from azure.cognitiveservices.speech import (
    AudioDataStream,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesisResult,
    SpeechSynthesisVisemeEventArgs,
    SpeechSynthesisWordBoundaryEventArgs,
    SpeechSynthesizer,
    StreamStatus,
)
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage, SSMLMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    encode_as_wav,
)
from vocode.streaming.utils import (
    AZURE_PHONETIC_SYMBOLS,
)


NAMESPACES = {
    "mstts": "https://www.w3.org/2001/mstts",
    "": "https://www.w3.org/2001/10/synthesis",
}

ET.register_namespace("", NAMESPACES[""])
ET.register_namespace("mstts", NAMESPACES["mstts"])

SLEEP_TIME = 0.1  # how long we sleep between checking for new data in the stream
AZURE_TICK_PER_SECOND = 10000000


def viseme_events_to_str(events: list[SpeechSynthesisVisemeEventArgs]):
    out = ""
    for evt in events:
        out += f"{ticks2s(evt.audio_offset):.2f}: {AZURE_PHONETIC_SYMBOLS[evt.viseme_id]}\n"
    return out


def word_events_to_str(events: list[SpeechSynthesisWordBoundaryEventArgs]):
    out = ""
    for evt in events:
        out += f"{ticks2s(evt.audio_offset):.2f}: '{evt.text}'\n"
    return out


def ticks2s(ticks: int):
    return ticks / AZURE_TICK_PER_SECOND


def get_events_for(
    events: list[SpeechSynthesisVisemeEventArgs | SpeechSynthesisWordBoundaryEventArgs],
    from_s: float,
    to_s: float,
    result_id: str = None
):
    # NOTE we sometimes get 0 as audio_offset, so we need to filter those out
    out = [event for event in events if event.audio_offset and from_s <= ticks2s(event.audio_offset) < to_s]
    # NOTE, for debug, we can provide a result_id and ensure we get only events for that result_id
    # but this is not on by default
    if result_id:
        right = []
        wrong = []
        for event in out:
            if event.result_id == result_id:
                right.append(event)
            else:
                wrong.append(event)
        out = right
    return out


def get_lipsync_events(
    viseme_events: list[SpeechSynthesisVisemeEventArgs],
    from_s: float, 
    to_s: float, 
    result_id: str = None):
    out = [
        {
            "audio_offset": ticks2s(evt.audio_offset) - from_s,
            "viseme_id": evt.viseme_id,
        }
        for evt in get_events_for(viseme_events, from_s, to_s, result_id)
    ]
    return out


def get_message_up_to(
    ssml: str, 
    word_events: list[SpeechSynthesisWordBoundaryEventArgs], 
    to_s: float,
    result_id: str = None):
    events = get_events_for(word_events, to_s, 10000, result_id)
    if events:
        ssml_fragment = ssml[: events[0].text_offset]
        # TODO: this is a little hacky, but it works for now
        return ssml_fragment.split(">")[-1]
    else:
        return None


def speech_config_hash(config: SpeechConfig):
    # NOTE, if more variables of speech config are used, the hash need to update
    return config.region + config.subscription_key + config.speech_synthesis_output_format_string


class SynthesizerPool:
    def __init__(
        self,
        maximum_synthesizers: int = 20,
    ):
        self._synthesizer_stacks: dict[str, list[SpeechSynthesizer]] = {}
        self._maximum_synthesizers = maximum_synthesizers

    def get(self, speech_config: SpeechConfig) -> SpeechSynthesizer:
        key = speech_config_hash(speech_config)
        if key not in self._synthesizer_stacks:
            self._synthesizer_stacks[key] = []

        stack = self._synthesizer_stacks[key]
        if stack:
            return stack.pop()
        else:
            synth = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            return synth

    def put(self, synth: SpeechSynthesizer, speech_config: SpeechConfig, logger: Optional[logging.Logger] = None):
        key = speech_config_hash(speech_config)
        if key not in self._synthesizer_stacks:
            self._synthesizer_stacks[key] = []
        stack = self._synthesizer_stacks[key]

        if len(stack) < self._maximum_synthesizers:
            stack.append(synth)
            if logger:
                logger.debug(f"Putting back a synthesizer, now have {len(stack)} in stack")
        else:
            if logger:
                logger.warning(f"Disposing of a synthesizer as above max number of {self._maximum_synthesizers}.")
            synth.stop_speaking_async()


synthesizer_pool = SynthesizerPool()


class AzureSynthesizer(BaseSynthesizer[AzureSynthesizerConfig]):
    """Objects of this class keeps track of the specific configuration that's needed to synthesize speech using Azure
    within one specific vocode conversation. The actual work will be done by `SpeechSynthesizer` instances that are
    fetched from a global pool which ensures quick synthesis times."""

    def __init__(
        self,
        synthesizer_config: AzureSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        azure_speech_key: Optional[str] = None,
        azure_speech_region: Optional[str] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        azure_speech_key = azure_speech_key or os.getenv("AZURE_SPEECH_KEY")
        azure_speech_region = azure_speech_region or os.getenv("AZURE_SPEECH_REGION")
        if not azure_speech_key:
            raise ValueError("Please set AZURE_SPEECH_KEY environment variable or pass it as a parameter")
        if not azure_speech_region:
            raise ValueError("Please set AZURE_SPEECH_REGION environment variable or pass it as a parameter")
        speech_config = SpeechConfig(subscription=azure_speech_key, region=azure_speech_region)
        if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            if self.synthesizer_config.sampling_rate == 44100:
                speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Raw44100Hz16BitMonoPcm)
            if self.synthesizer_config.sampling_rate == 48000:
                speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm)
            if self.synthesizer_config.sampling_rate == 24000:
                speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm)
            elif self.synthesizer_config.sampling_rate == 16000:
                speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm)
            elif self.synthesizer_config.sampling_rate == 8000:
                speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
            else:
                raise ValueError(f"Invalid sample rate {self.synthesizer_config.sampling_rate} used")

        elif self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            speech_config.set_speech_synthesis_output_format(SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)

        # Note, Azure will synthesize as best it can even if language_code, sample rate, pitch, rate etc are not valid
        self.speech_config = speech_config
        self.language_code = self.synthesizer_config.language_code
        self.voice_name = self.synthesizer_config.voice_name
        self.pitch = self.synthesizer_config.pitch
        self.rate = self.synthesizer_config.rate
        self.as_wav = self.synthesizer_config.should_encode_as_wav
        self.logger = logger or logging.getLogger(__name__)
        self.pool = synthesizer_pool

    def create_ssml(self, message: str, bot_sentiment: Optional[BotSentiment] = None) -> str:
        ssml_root = ET.fromstring(
            f'<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xml:lang="{self.language_code or "en-US"}"></speak>'
        )

        voice = ET.SubElement(ssml_root, "voice")
        voice.set("name", self.voice_name)
        voice_root = voice
        if self.language_code:
            lang = ET.SubElement(voice, "lang")
            lang.set("xml:lang", self.language_code)
            voice_root = lang

        if bot_sentiment and bot_sentiment.emotion:
            styled = ET.SubElement(voice_root, "{%s}express-as" % NAMESPACES.get("mstts"))
            styled.set("style", bot_sentiment.emotion)
            styled.set("styledegree", str(bot_sentiment.degree * 2))  # Azure specific, it's a scale of 0-2
            voice_root = styled

        # NOTE: Below comment and code from Vocode, but not clear if it's needed anymore?
        # this ugly hack is necessary so we can limit the gap between sentences
        # for normal sentences, it seems like the gap is > 500ms, so we're able to reduce it to 500ms
        # for very tiny sentences, the API hangs - so we heuristically only update the silence gap
        # if there is more than one word in the sentence
        # if " " in message:
        #     silence = ElementTree.SubElement(
        #         voice_root, "{%s}silence" % NAMESPACES.get("mstts")
        #     )
        #     silence.set("value", "500ms")
        #     silence.set("type", "Tailing-exact")
        prosody = ET.SubElement(voice_root, "prosody")
        prosody.set("pitch", f"{self.pitch}%")
        prosody.set("rate", f"{self.rate}%")
        prosody.text = message.strip()
        return ET.tostring(ssml_root, encoding="unicode")

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        self.logger.debug(f"Synthesizing message: {message}")

        # Azure will return no audio for certain strings like "-", "[-", and "!"
        # which causes the `chunk_generator` below to hang. Return an empty
        # generator for these cases.
        if not re.search(r"\w", message.text):
            self.logger.warning(f"Skipping synthesis for message '{message.text}' as it contains no words")
            return SynthesisResult(
                self.empty_generator(),
                lambda _: message.text,
            )

        ssml = (
            message.ssml
            if isinstance(message, SSMLMessage)
            else self.create_ssml(message.text, bot_sentiment=bot_sentiment)
        )
        viseme_events: list[SpeechSynthesisVisemeEventArgs] = []
        word_events: list[SpeechSynthesisWordBoundaryEventArgs] = []

        synthesizer = self.pool.get(self.speech_config)
        synthesizer.viseme_received.connect(lambda x: viseme_events.append(x))
        synthesizer.synthesis_word_boundary.connect(lambda x: word_events.append(x))

        result: SpeechSynthesisResult = synthesizer.start_speaking_ssml_async(ssml).get()
        text = re.sub(r"<.+?>", "", ssml)[0:20]
        self.logger.debug(
            f"Started synthesis for message '{text}…', using synth {id(synthesizer)}, Azure result_id: {result.result_id}"
        )
        chunk_transform = (lambda chunk: encode_as_wav(chunk, self.synthesizer_config)) if self.as_wav else (lambda chunk: chunk)

        # NOTE chunk_generator is responsible for disconnecting events and putting back synth once it has finished running
        async def chunk_generator():
            try:
                stream = AudioDataStream(result)
                chunk_data = bytes(chunk_size)
                await asyncio.sleep(SLEEP_TIME)
                while True:
                    if stream.status == StreamStatus.PartialData and not stream.can_read_data(chunk_size):
                        await asyncio.sleep(SLEEP_TIME)
                        continue

                    filled_size = stream.read_data(chunk_data)
                    last_chunk = filled_size < chunk_size
                    yield SynthesisResult.ChunkResult(chunk_transform(chunk_data[:filled_size]), last_chunk)
                    if last_chunk:
                        break
            except Exception:
                self.logger.exception(f"Error when generating chunks for result_id={result.result_id}")
            finally:
                # Finally should be called if we get an exception or if the generator is closed early using aclose()
                if stream.status != StreamStatus.AllData:
                    self.logger.warning(
                        f"Closing stream for result_id={result.result_id} with status {stream.status} and details {stream.cancellation_details.error_details if stream.cancellation_details else None}"
                    )
                synthesizer.viseme_received.disconnect_all()
                synthesizer.synthesis_word_boundary.disconnect_all()
                self.logger.debug(
                    f"Ended synthesis for result_id: {result.result_id}, putting back synth {id(synthesizer)}"
                )
                self.pool.put(synthesizer, self.speech_config, self.logger)

        return SynthesisResult(
            chunk_generator(),
            lambda to_s: (get_message_up_to(ssml, word_events, to_s) or message.text), 
            lambda from_s, to_s: get_lipsync_events(viseme_events, from_s, to_s)
        )

import asyncio
import audioop
import json
import logging
from typing import Optional
from urllib.parse import urlencode

import websockets
from openai import AsyncOpenAI, OpenAI
from vocode import getenv
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.transcriber import (
    ClassifierEndpointingConfig,
    DeepgramTranscriberConfig,
    EndpointingConfig,
    EndpointingType,
    PunctuationEndpointingConfig,
    TimeEndpointingConfig,
)
from vocode.streaming.transcriber.base_transcriber import (
    BaseAsyncTranscriber,
    Transcription,
    meter,
)
from websockets.client import WebSocketClientProtocol

PUNCTUATION_TERMINATORS = [".", "!", "?"]
MAX_SILENCE_DURATION = 2.0
NUM_RESTARTS = 5


avg_latency_hist = meter.create_histogram(
    name="transcriber.deepgram.avg_latency",
    unit="seconds",
)
max_latency_hist = meter.create_histogram(
    name="transcriber.deepgram.max_latency",
    unit="seconds",
)
min_latency_hist = meter.create_histogram(
    name="transcriber.deepgram.min_latency",
    unit="seconds",
)
duration_hist = meter.create_histogram(
    name="transcriber.deepgram.duration",
    unit="seconds",
)


class DeepgramTranscriber(BaseAsyncTranscriber[DeepgramTranscriberConfig]):
    def __init__(
        self,
        transcriber_config: DeepgramTranscriberConfig,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(transcriber_config)
        self.api_key = api_key or getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise Exception(
                "Please set DEEPGRAM_API_KEY environment variable or pass it as a parameter"
            )
        self._ended = False
        self.is_ready = False
        self.logger = logger or logging.getLogger(__name__)
        self.audio_cursor = 0.0
        self.openai_client = OpenAI(api_key="EMPTY", base_url=getenv("AI_API_BASE"))

    async def _run_loop(self):
        restarts = 0
        while not self._ended and restarts < NUM_RESTARTS:
            await self.process()
            restarts += 1
            self.logger.debug(
                "Deepgram connection died, restarting, num_restarts: %s", restarts
            )

    def send_audio(self, chunk):
        if (
            self.transcriber_config.downsampling
            and self.transcriber_config.audio_encoding == AudioEncoding.LINEAR16
        ):
            chunk, _ = audioop.ratecv(
                chunk,
                2,
                1,
                self.transcriber_config.sampling_rate
                * self.transcriber_config.downsampling,
                self.transcriber_config.sampling_rate,
                None,
            )
        super().send_audio(chunk)

    def terminate(self):
        terminate_msg = json.dumps({"type": "CloseStream"})
        self.input_queue.put_nowait(terminate_msg)
        self._ended = True
        super().terminate()

    def get_deepgram_url(self):
        if self.transcriber_config.audio_encoding == AudioEncoding.LINEAR16:
            encoding = "linear16"
        elif self.transcriber_config.audio_encoding == AudioEncoding.MULAW:
            encoding = "mulaw"
        url_params = {
            "encoding": encoding,
            "sample_rate": self.transcriber_config.sampling_rate,
            "channels": 1,
            "vad_events": "true",
            "interim_results": "true",
            "filler_words": "false",
        }
        extra_params = {}
        if self.transcriber_config.language:
            extra_params["language"] = self.transcriber_config.language
        if self.transcriber_config.model:
            extra_params["model"] = self.transcriber_config.model
        if self.transcriber_config.tier:
            extra_params["tier"] = self.transcriber_config.tier
        if self.transcriber_config.version:
            extra_params["version"] = self.transcriber_config.version
        if self.transcriber_config.keywords:
            extra_params["keywords"] = self.transcriber_config.keywords
        if (
            self.transcriber_config.endpointing_config
            and self.transcriber_config.endpointing_config.type
            == EndpointingType.PUNCTUATION_BASED
        ):
            extra_params["punctuate"] = "true"
        url_params.update(extra_params)
        return f"wss://api.deepgram.com/v1/listen?{urlencode(url_params, doseq=True)}"

    # This function will return how long the time silence for endpointing should be
    def get_classify_endpointing_silence_duration(self, transcript: str):
        preamble = """You are an amazing live transcript classifier! Your task is to classify, with provided confidence, whether a provided message transcript is: 'complete', 'incomplete' or 'garbled'. The message should be considered 'complete' if it is a full thought or question. The message is 'incomplete' if there is still more the user might add. Finally, the message is 'garbled' if it appears to be a complete transcription attempt but, despite best efforts, the meaning is unclear.

Based on which class is demonstrated in the provided message transcript, return the confidence level of your classification on a scale of 1-100 with 100 being the most confident followed by a space followed by either 'complete', 'incomplete', or 'garbled'.

The exact format to return is:
<confidence level> <classification>"""
        user_message = f"{transcript}"
        messages = [
            {"role": "system", "content": preamble},
            {"role": "user", "content": user_message},
        ]
        parameters = {
            "model": "Qwen/Qwen1.5-72B-Chat-GPTQ-Int4",
            "messages": messages,
            "max_tokens": 5,
            "temperature": 0,
            "stop": ["User:", "\n", "<|im_end|>", "?"],
        }

        response = self.openai_client.chat.completions.create(**parameters)

        classification = (response.choices[0].message.content.split(" "))[-1]
        silence_duration_1_to_100 = "".join(
            filter(str.isdigit, response.choices[0].message.content)
        )
        duration_to_return = 0.1
        if "incomplete" in classification.lower():
            duration_to_return = (
                float(silence_duration_1_to_100) / INCOMPLETE_SCALING_FACTOR / 100.0
            )
        elif "complete" in classification.lower():
            duration_to_return = 1.0 - (float(silence_duration_1_to_100) / 100.0)
        return duration_to_return * MAX_SILENCE_DURATION

    def is_speech_final(
        self, current_buffer: str, deepgram_response: dict, time_silent: float
    ):
        transcript = deepgram_response["channel"]["alternatives"][0]["transcript"]

        # if it is not time based, then return true if speech is final and there is a transcript
        if not self.transcriber_config.endpointing_config:
            return transcript and deepgram_response["speech_final"]
        elif isinstance(
            self.transcriber_config.endpointing_config, TimeEndpointingConfig
        ):
            # if it is time based, then return true if there is no transcript
            # and there is some speech to send
            # and the time_silent is greater than the cutoff
            return (
                not transcript
                and current_buffer
                and (time_silent + deepgram_response["duration"])
                > self.transcriber_config.endpointing_config.time_cutoff_seconds
            )
        elif isinstance(
            self.transcriber_config.endpointing_config, PunctuationEndpointingConfig
        ):
            return (
                transcript
                and deepgram_response["speech_final"]
                and transcript.strip()[-1] in PUNCTUATION_TERMINATORS
            ) or (
                not transcript
                and current_buffer
                and (time_silent + deepgram_response["duration"])
                > self.transcriber_config.endpointing_config.time_cutoff_seconds
            )
            # For shorter transcripts, check if the combined silence duration exceeds a fixed threshold
            # return (
            #     time_silent + deepgram_response["duration"]
            #     > self.transcriber_config.endpointing_config.time_cutoff_seconds
            #     if time_silent and deepgram_response["duration"]
            #     else False
            # )

        raise Exception("Endpointing config not supported")

    def calculate_time_silent(self, data: dict):
        end = data["start"] + data["duration"]
        words = data["channel"]["alternatives"][0]["words"]
        if words:
            return end - words[-1]["end"]
        return data["duration"]

    async def process(self):
        self.audio_cursor = 0.0
        extra_headers = {"Authorization": f"Token {self.api_key}"}

        async with websockets.connect(
            self.get_deepgram_url(), extra_headers=extra_headers
        ) as ws:

            async def sender(ws: WebSocketClientProtocol):  # sends audio to websocket
                while not self._ended:
                    try:
                        data = await asyncio.wait_for(self.input_queue.get(), 5)
                    except asyncio.exceptions.TimeoutError:
                        break
                    num_channels = 1
                    sample_width = 2
                    self.audio_cursor += len(data) / (
                        self.transcriber_config.sampling_rate
                        * num_channels
                        * sample_width
                    )
                    await ws.send(data)
                self.logger.debug("Terminating Deepgram transcriber sender")

            async def receiver(ws: WebSocketClientProtocol):
                buffer = ""
                buffer_avg_confidence = 0
                num_buffer_utterances = 1
                time_silent = 0
                transcript_cursor = 0.0
                while not self._ended:
                    try:
                        msg = await ws.recv()
                    except Exception as e:
                        self.logger.debug(f"Got error {e} in Deepgram receiver")
                        break
                    data = json.loads(msg)
                    if data["type"] == "SpeechStarted":
                        # self.logger.debug("VAD triggered")
                        self.output_queue.put_nowait(
                            Transcription(
                                message="vad",
                                confidence=1.0,
                                is_final=False,
                            )
                        )
                        continue
                    if (
                        not "is_final" in data
                    ):  # means we've finished receiving transcriptions
                        break
                    cur_max_latency = self.audio_cursor - transcript_cursor
                    transcript_cursor = data["start"] + data["duration"]
                    cur_min_latency = self.audio_cursor - transcript_cursor

                    avg_latency_hist.record(
                        (cur_min_latency + cur_max_latency) / 2 * data["duration"]
                    )
                    duration_hist.record(data["duration"])

                    # Log max and min latencies
                    max_latency_hist.record(cur_max_latency)
                    min_latency_hist.record(max(cur_min_latency, 0))

                    is_final = data["is_final"]
                    time_silent = self.calculate_time_silent(data)
                    top_choice = data["channel"]["alternatives"][0]
                    confidence = top_choice["confidence"]
                    self.output_queue.put_nowait(
                        Transcription(
                            message=json.dumps(
                                top_choice
                            ),  # since we're doing interim results, we can just send the whole data dict
                            confidence=confidence,
                            is_final=is_final,
                            time_silent=time_silent,
                        )
                    )
                self.logger.debug("Terminating Deepgram transcriber receiver")

            await asyncio.gather(sender(ws), receiver(ws))

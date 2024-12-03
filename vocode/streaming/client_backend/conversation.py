import io
import typing
import wave
from typing import Callable

from fastapi import APIRouter, WebSocket
from langfuse.decorators import langfuse_context, observe
from langfuse.media import LangfuseMedia
from loguru import logger

from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.models.client_backend import InputAudioConfig, OutputAudioConfig
from vocode.streaming.models.events import Event, EventType
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.transcript import TranscriptEvent
from vocode.streaming.models.websocket import (
    AudioConfigStartMessage,
    AudioMessage,
    ReadyMessage,
    WebSocketMessage,
    WebSocketMessageType,
)
from vocode.streaming.output_device.websocket_output_device import WebsocketOutputDevice
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.utils import events_manager
from vocode.streaming.utils.base_router import BaseRouter

BASE_CONVERSATION_ENDPOINT = "/conversation"


class ConversationRouter(BaseRouter):
    def __init__(
        self,
        agent_thunk: Callable[[], BaseAgent],
        transcriber_thunk: Callable[
            [InputAudioConfig], BaseTranscriber
        ] = lambda input_audio_config: DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_audio_config(
                input_audio_config=input_audio_config,
                endpointing_config=PunctuationEndpointingConfig(),
            )
        ),
        synthesizer_thunk: Callable[
            [OutputAudioConfig], BaseSynthesizer
        ] = lambda output_audio_config: AzureSynthesizer(
            AzureSynthesizerConfig.from_output_audio_config(output_audio_config=output_audio_config)
        ),
        conversation_endpoint: str = BASE_CONVERSATION_ENDPOINT,
    ):
        super().__init__()
        self.transcriber_thunk = transcriber_thunk
        self.agent_thunk = agent_thunk
        self.synthesizer_thunk = synthesizer_thunk
        self.router = APIRouter()
        self.router.websocket(conversation_endpoint)(self.conversation)
        self.recording = b""

    @observe(as_type="span")
    def get_conversation(
        self,
        output_device: WebsocketOutputDevice,
        start_message: AudioConfigStartMessage,
    ) -> StreamingConversation:
        transcriber = self.transcriber_thunk(start_message.input_audio_config)
        synthesizer = self.synthesizer_thunk(start_message.output_audio_config)
        synthesizer.get_synthesizer_config().should_encode_as_wav = True
        langfuse_context.update_current_observation(input={"output_device": output_device,
                                                           "start_message": start_message},
                                                    output={"output_device": output_device,
                                                            "transcriber": transcriber,
                                                            "agent": self.agent_thunk(),
                                                            "synthesizer": synthesizer,
                                                            "conversation_id": start_message.conversation_id,
                                                            "events_manager": (TranscriptEventManager(output_device)
                                                                               if start_message.subscribe_transcript
                                                                               else None)})
        return StreamingConversation(
            output_device=output_device,
            transcriber=transcriber,
            agent=self.agent_thunk(),
            synthesizer=synthesizer,
            conversation_id=start_message.conversation_id,
            events_manager=(
                TranscriptEventManager(output_device)
                if start_message.subscribe_transcript
                else None
            ),
        )

    @observe(as_type="span")
    async def conversation(self, websocket: WebSocket):
        await websocket.accept()
        start_message: AudioConfigStartMessage = AudioConfigStartMessage.parse_obj(
            await websocket.receive_json()
        )
        logger.debug(f"Conversation started")
        output_device = WebsocketOutputDevice(
            websocket,
            start_message.output_audio_config.sampling_rate,
            start_message.output_audio_config.audio_encoding,
        )
        conversation = self.get_conversation(output_device, start_message)
        await conversation.start(lambda: websocket.send_text(ReadyMessage().json()))
        while conversation.is_active():
            message: WebSocketMessage = WebSocketMessage.parse_obj(await websocket.receive_json())
            if message.type == WebSocketMessageType.STOP:
                break
            audio_bytes = typing.cast(AudioMessage, message).get_bytes()
            conversation.receive_audio(audio_bytes)
            self.recording += audio_bytes
        output_device.mark_closed()
        await conversation.terminate()
        media = LangfuseMedia(content_type="audio/wav", content_bytes=pcm_to_wav(pcm_data=self.recording,
                                                                                 sample_rate=48000))
        langfuse_context.update_current_trace(metadata={"Recording of the User": media})


    def get_router(self) -> APIRouter:
        return self.router


class TranscriptEventManager(events_manager.EventsManager):
    def __init__(
        self,
        output_device: WebsocketOutputDevice,
    ):
        super().__init__(subscriptions=[EventType.TRANSCRIPT])
        self.output_device = output_device

    async def handle_event(self, event: Event):
        if event.type == EventType.TRANSCRIPT:
            transcript_event = typing.cast(TranscriptEvent, event)
            await self.output_device.send_transcript(transcript_event)
            # logger.debug(event.dict())

    def restart(self, output_device: WebsocketOutputDevice):
        self.output_device = output_device

def pcm_to_wav(pcm_data, sample_rate=22050, channels=1, sample_width=2):
    """
    Args:
        :param sample_width: Sample width in bytes (e.g., 2 for 16-bit audio).
        :param channels: Number of audio channels.
        :param sample_rate: The sample rate of the audio.
        :param pcm_data: The PCM byte data.

    Returns:
        .wav byte data
    """

    with io.BytesIO() as wav_io:
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        wav_data = wav_io.getvalue()
    return wav_data

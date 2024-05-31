from typing import Optional

from pytest_mock import MockerFixture

from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.models.agent import AgentConfig, ChatGPTAgentConfig
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import PlayHtSynthesizerConfig, SynthesizerConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig, TranscriberConfig
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.telephony.constants import DEFAULT_CHUNK_SIZE, DEFAULT_SAMPLING_RATE
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramEndpointingConfig
from vocode.streaming.utils.events_manager import EventsManager

DEFAULT_DEEPGRAM_TRANSCRIBER_CONFIG = DeepgramTranscriberConfig(
    chunk_size=DEFAULT_CHUNK_SIZE,
    sampling_rate=DEFAULT_SAMPLING_RATE,
    audio_encoding=AudioEncoding.MULAW,
    endpointing_config=DeepgramEndpointingConfig(),
    model="2-phonecall",
    tier="nova",
)

DEFAULT_SYNTHESIZER_CONFIG = PlayHtSynthesizerConfig(
    sampling_rate=DEFAULT_SAMPLING_RATE,
    audio_encoding=AudioEncoding.MULAW,
)

DEFAULT_CHAT_GPT_AGENT_CONFIG = ChatGPTAgentConfig(
    prompt_preamble="You are an agent of chaos", initial_message=BaseMessage(text="Hi there!")
)


class DummyOutputDevice(BaseOutputDevice):
    def consume_nonblocking(self, chunk: bytes):
        pass


def create_fake_transcriber(mocker: MockerFixture, transcriber_config: TranscriberConfig):
    transcriber = mocker.MagicMock()
    transcriber.get_transcriber_config = mocker.MagicMock(return_value=transcriber_config)
    return transcriber


def create_fake_agent(mocker: MockerFixture, agent_config: AgentConfig):
    agent = mocker.MagicMock()
    agent.get_agent_config = mocker.MagicMock(return_value=agent_config)
    return agent


def create_fake_synthesizer(mocker: MockerFixture, synthesizer_config: SynthesizerConfig):
    synthesizer = mocker.MagicMock()
    synthesizer.get_synthesizer_config = mocker.MagicMock(return_value=synthesizer_config)
    return synthesizer


def create_fake_streaming_conversation(
    mocker: MockerFixture,
    transcriber: Optional[BaseTranscriber[TranscriberConfig]] = None,
    agent: Optional[BaseAgent] = None,
    synthesizer: Optional[BaseSynthesizer] = None,
    speed_coefficient: float = 1.0,
    conversation_id: Optional[str] = None,
    events_manager: Optional[EventsManager] = None,
):
    transcriber = transcriber or create_fake_transcriber(
        mocker, DEFAULT_DEEPGRAM_TRANSCRIBER_CONFIG
    )
    agent = agent or create_fake_agent(mocker, DEFAULT_CHAT_GPT_AGENT_CONFIG)
    synthesizer = synthesizer or create_fake_synthesizer(mocker, DEFAULT_SYNTHESIZER_CONFIG)
    return StreamingConversation(
        output_device=DummyOutputDevice(
            sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=AudioEncoding.MULAW
        ),
        transcriber=transcriber,
        agent=agent,
        synthesizer=synthesizer,
        speed_coefficient=speed_coefficient,
        conversation_id=conversation_id,
        events_manager=events_manager,
    )

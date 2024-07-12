from abc import ABC
from typing import Any, Literal

from vocode.streaming.models.adaptive_object import AdaptiveObject
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.transcriber import TranscriberConfig


class PipelineConfig(AdaptiveObject, ABC):
    type: Any


class StreamingConversationConfig(PipelineConfig):
    type: Literal["pipeline_streaming_conversation"] = "pipeline_streaming_conversation"
    transcriber_config: TranscriberConfig
    agent_config: AgentConfig
    synthesizer_config: SynthesizerConfig
    speed_coefficient: float = 1.0

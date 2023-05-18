import logging
from typing import Optional
from vocode.turn_based.agent.base_agent import BaseAgent
from vocode.turn_based.input_device.base_input_device import (
    BaseInputDevice,
)
from vocode.turn_based.output_device.base_output_device import BaseOutputDevice
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber


class TurnBasedConversation:
    def __init__(
        self,
        input_device: BaseInputDevice,
        transcriber: BaseTranscriber,
        agent: BaseAgent,
        synthesizer: BaseSynthesizer,
        output_device: BaseOutputDevice,
        logger: Optional[logging.Logger] = None,
    ):
        self.input_device = input_device
        self.transcriber = transcriber
        self.agent = agent
        self.synthesizer = synthesizer
        self.output_device = output_device
        self.maybe_play_initial_message()
        self.logger = logger or logging.getLogger(__name__)

    def maybe_play_initial_message(self):
        if self.agent.initial_message:
            self.output_device.send_audio(
                self.synthesizer.synthesize(self.agent.initial_message)
            )

    def start_speech(self):
        self.input_device.start_listening()

    def end_speech_and_respond(self):
        human_input = self.transcriber.transcribe(self.input_device.end_listening())
        self.logger.info(f"Transcription: {human_input}")
        agent_response = self.agent.respond(human_input)
        self.logger.info(f"Agent response: {agent_response}")
        self.output_device.send_audio(self.synthesizer.synthesize(agent_response))

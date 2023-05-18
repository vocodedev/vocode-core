import logging
from vocode.turn_based.agent.base_agent import BaseAgent
from vocode.turn_based.input_device.base_input_device import (
    BaseInputDevice,
)
from vocode.turn_based.output_device.base_output_device import BaseOutputDevice
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber
from vocode.helpers import LatencyManager, LatencyType


class TurnBasedConversation:
    def __init__(
        self,
        input_device: BaseInputDevice,
        transcriber: BaseTranscriber,
        agent: BaseAgent,
        synthesizer: BaseSynthesizer,
        output_device: BaseOutputDevice,
        logger: logging.Logger = None,
        show_latency: bool = True,
    ):
        self.input_device = input_device
        self.transcriber = transcriber
        self.agent = agent
        self.synthesizer = synthesizer
        self.output_device = output_device
        self.maybe_play_initial_message()
        self.logger = logger or logging.getLogger(__name__)
        self.show_latency = show_latency
        self.latency_manager = LatencyManager()
    
    def get_latency_manager(self):
        return self.latency_manager

    def maybe_play_initial_message(self):
        if self.agent.initial_message:
            self.output_device.send_audio(
                self.synthesizer.synthesize(self.agent.initial_message)
            )

    def start_speech(self):
        self.input_device.start_listening()

    def end_speech_and_respond(self):
        human_audio = self.input_device.end_listening()
        human_input = self.latency_manager.measure_latency(LatencyType.TRANSCRIPTION, self.transcriber.transcribe, human_audio)
        self.logger.info(f"Transcription: {human_input}")
        agent_response = self.latency_manager.measure_latency(LatencyType.AGENT, self.agent.respond, human_input)
        self.logger.info(f"Agent response: {agent_response}")
        synthesised_audio = self.latency_manager.measure_latency(LatencyType.SYNTHESIS, self.synthesizer.synthesize, agent_response)
        self.output_device.send_audio(synthesised_audio)

        if self.show_latency:
            self.logger.info(f"Latency - Transcription: {self.latency_manager.get_latency(LatencyType.TRANSCRIPTION)} seconds, Agent: {self.latency_manager.get_latency(LatencyType.AGENT)} seconds, Synthesis: {self.latency_manager.get_latency(LatencyType.SYNTHESIS)} seconds")
        

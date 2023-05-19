from vocode.streaming.agent.base_agent import BaseAsyncAgent, OneShotAgentResponse, TextAgentResponseMessage
from vocode.streaming.models.agent import GPT4AllAgentConfig
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.turn_based.agent.gpt4all_agent import GPT4AllAgent as TurnBasedGPT4AllAgent


class GPT4AllAgent(BaseAsyncAgent[GPT4AllAgentConfig]):
    def __init__(self, agent_config: GPT4AllAgentConfig):
        super().__init__(agent_config=agent_config)
        self.turn_based_agent = TurnBasedGPT4AllAgent(
            model_path=agent_config.model_path,
            system_prompt=agent_config.prompt_preamble,
            initial_message=agent_config.initial_message.text
            if agent_config.initial_message
            else None,
        )

    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        await super().did_add_transcript_to_input_queue(transcription)
        text_response = await self.turn_based_agent.respond_async(transcription.message)
        agent_response = OneShotAgentResponse(
            message=TextAgentResponseMessage(text=text_response)
        )
        await self.add_agent_response_to_output_queue(agent_response)

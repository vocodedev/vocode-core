from vocode.streaming.agent.base_agent import BaseAsyncAgent, OneShotAgentResponse, TextAgentResponseMessage
from vocode.streaming.transcriber.base_transcriber import Transcription


class EchoAgent(BaseAsyncAgent):
    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        await super().did_add_transcript_to_input_queue(transcription)
        agent_response = OneShotAgentResponse(
            message=TextAgentResponseMessage(text=transcription.message)
        )
        self.add_agent_response_to_output_queue(agent_response)

    def update_last_bot_message_on_cut_off(self, message: str):
        pass

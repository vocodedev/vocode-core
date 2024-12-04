from vocode.streaming.models.message import LLMToken


class InputStreamingSynthesizer:
    async def handle_end_of_turn(self):
        pass

    def get_current_utterance_synthesis_result(self):
        raise NotImplementedError

    async def send_token_to_synthesizer(
        self,
        message: LLMToken,
        chunk_size: int,
    ):
        raise NotImplementedError

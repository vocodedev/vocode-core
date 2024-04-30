import asyncio
import json
import time

import openai

from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.default_prompts.interrupt_prompt import INTERRUPTION_PROMPT
from vocode.streaming.utils.worker import AsyncQueueWorker

class InterruptWorker(AsyncQueueWorker):
    """Processes transcriptions to determine if an interrupt is needed."""

    def __init__(self, input_queue: asyncio.Queue[Transcription], conversation):
        super().__init__(input_queue)
        self.conversation = conversation

    async def classify_transcription(self, transcription: Transcription) -> bool:
        last_bot_message = self.conversation.transcript.get_last_bot_text()
        transcript_message = transcription.message
        # TODO: must be parametrized.
        chat_parameters = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": INTERRUPTION_PROMPT},
                {"role": "user", "content": transcript_message},
                {"role": "assistant", "content": last_bot_message},
            ]
        }
        try:
            response = await openai.ChatCompletion.acreate(**chat_parameters)
            decision = json.loads(response['choices'][0]['message']['content'].strip().lower())
            self.conversation.logger.info(f"Decision: {decision}")
            return decision['interrupt'] == 'true'

        except Exception as e:
            # Log the exception or handle it as per your error handling policy
            self.conversation.logger.error(f"Error in GPT-3.5 API call: {str(e)}")
            return False

    async def simple_interrupt(self, transcription: Transcription) -> bool:
        return not self.conversation.is_human_speaking and self.conversation.is_interrupt(transcription)

    async def process(self, transcription: Transcription):
        current_turn = self.conversation.turn_index
        is_propagate = await self.handle_interrupt(transcription, current_turn)
        if is_propagate:
            await self.conversation.transcriptions_worker.propagate_transcription(transcription)

    async def handle_interrupt(self, transcription: Transcription, current_turn: int) -> bool:
        if self.conversation.use_interrupt_agent:
            self.conversation.logger.info(
                f"Testing if bot should be interrupted: {transcription.message}"
            )
            is_interrupt = await self.classify_transcription(transcription)
            if self.conversation.turn_index != current_turn:
                # The conversation has moved on since this transcription was processed.
                self.conversation.logger.info(
                    f"Conversation has moved on since transcription was processed. Current turn: {current_turn}, index: {self.conversation.turn_index} ")
                return False
            if is_interrupt and self.conversation.is_bot_speaking:
                if self.conversation.is_bot_speaking:
                    self.conversation.broadcast_interrupt()
                return True
            elif (is_interrupt and self.conversation.bot_last_stopped_speaking and
                  (time.time() - self.conversation.bot_last_stopped_speaking) < 0.2 and
                  not self.conversation.is_human_speaking):
                # we don't interrupt but only propagate the transcription if the bot has stopped speaking.
                return True
            return False
        else:
            return await self.simple_interrupt(transcription)

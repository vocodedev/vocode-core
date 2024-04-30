import asyncio
import json
import time

import openai

from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.worker import AsyncQueueWorker

# TODO:MOVE IT, just WIP TEMP
INTERRUPTION_PROMPT = """
**Objective:**

Your primary task is to detect instances where the customer intends to interrupt the rep to stop the ongoing conversation. You only get the words said by customer and you have to base your decision on them.

You must differentiate between two types of customer interjections:

1. **Non-interrupting acknowledgements**: These are phrases which signify the customer is following along but does not wish to interrupt the rep. Are close to words like this:

"Ok"
"Got it"
"Understood"
 "I see"
"Right"
"I follow"
"Yes"
"I agree"
"That makes sense"
"Sure"
"Sounds good"
"Indeed"
"Absolutely"
"Of course"
"Go on"
"Keep going"
"I'm with you"
"Continue"
"That's clear"
"Perfect"

2. **Interrupting requests**: These include phrases indicating the customer's desire to interrupt the conversation.
Are close to words like this:
"Please, stop"
"stop"
"hold"
"No, no"
"Wait"
"what"
"No"
"Hold on"
"That's not right"
"I disagree"
"Just a moment"
"Listen"
"That's incorrect"
"I need to say something"
"Excuse me"
"Stop for a second"
"Hang on"
"That's not what I meant"
"Let me speak"
"I have a concern"
"That doesn't sound right"
"I need to correct you"
"Can I just say something"
"I don't think so"
"You're misunderstanding"

**Input Specification:**

You get words said by the customer.


**Output Specification:**

You must return a JSON object indicating whether the rep should be interrupted based on the customer's interjections.

- Return `{"interrupt": "true"}` if the customer's interjection is an interrupting request.
- Return `{"interrupt": "false"}` if the customer's interjection is a non-interrupting acknowledgement.


RULES: 
IF the customer is saying some information about his situation, assume interruption is needed and set it to TRUE.


Example of output:
{"interrupt": "true"}
"""


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
        if transcription.message.strip() and transcription.is_final and self.conversation.is_bot_speaking:
            if await self.handle_interrupt(transcription):
                self.conversation.broadcast_interrupt()

    async def handle_interrupt(self, transcription: Transcription) -> bool:
        if self.conversation.use_interrupt_agent:
            self.conversation.logger.info(
                f"Testing if bot should be interrupted: {transcription.message}"
            )
            is_interrupt = await self.classify_transcription(transcription)

            if is_interrupt and self.conversation.is_bot_speaking:
                if self.conversation.is_bot_speaking:
                    self.conversation.broadcast_interrupt()
                return True
            elif (self.conversation.bot_last_stopped_speaking and
                  (time.time() - self.conversation.bot_last_stopped_speaking) < 0.2 and
                  not self.conversation.is_human_speaking):
                # we don't interrupt but only propagate the transcription if the bot has stopped speaking.
                return True
            return False
        else:
            return await self.simple_interrupt(transcription)

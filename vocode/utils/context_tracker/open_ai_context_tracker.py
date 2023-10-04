import logging
from typing import Optional

import openai

from vocode import getenv
from vocode.utils.context_tracker import BaseContextTracker, BaseContextTrackerConfig, \
    ContextTrackerType

PROMPT = """
There is an ongoing call, between a call center, how tries to sell some stuff and potential customer.
we get both parts of chat from caller and the one who answers, and we want to determine if the last message is a 
response to caller, or just random people talking around the client.
Answer TRUE if it's related to context, or FALSE if it's not, just one of this words.
the context of call is as follow:
call context = trying to sell a box of cup cakes
"""


class OpenAIContextTrackerConfig(BaseContextTrackerConfig, type=ContextTrackerType.OPEN_AI.value):
    api_key: str = None
    model: str = "gpt-3.5-turbo"
    PROMPT: str = None


class OpenAIContextTracker(BaseContextTracker[OpenAIContextTrackerConfig]):
    def __init__(self, config: OpenAIContextTrackerConfig, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)
        openai.api_key = config.api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        base_prompt = self.config.PROMPT or PROMPT
        self.messages = [{"role": "system", "content": base_prompt}]

    def is_part_of_context(self, user_message: str) -> bool:
        self.messages.append({"role": "user", "content": user_message})
        response = openai.ChatCompletion.create(
            model=self.config.model,
            messages=self.messages,
        )
        resp = response['choices'][0]['message']['content']
        self.messages.append({"role": "assistant", "content": resp})
        is_related_to_context = 'true' in resp.lower()
        self.logger.debug(
            f"context tracker got message: {user_message}, and is_related_to_context is: {is_related_to_context}")
        return is_related_to_context

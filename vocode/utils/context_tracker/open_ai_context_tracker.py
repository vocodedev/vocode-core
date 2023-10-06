import logging
from typing import Optional

import openai

from vocode import getenv
from vocode.utils.context_tracker import BaseContextTracker, BaseContextTrackerConfig
from vocode.utils.context_tracker.context_tracker import ContextTrackerType

PROMPT = """
There is an ongoing chat, between a call center, who is trying do telemarketing. You can see 
customer side of the chat, and you want to determine if the last message is related to context of the call.
we get both parts of chat from caller and the one who answers, and we want to determine if the last message is a 
response to caller, or just random people talking around the client.
Answer TRUE if it's related to context, or FALSE if it's not, just one of this words.
the context of call is as follow:
call context = 
act as a phone announcer, just generate on side of things. ask for their name, and tell dear NAME,
contacti base features are now available on amazon web services and you can seee out features on www.contacti.AI
"""


class OpenAIContextTrackerConfig(BaseContextTrackerConfig, type=ContextTrackerType.OPEN_AI.value):
    api_key: str = getenv("OPENAI_API_KEY")
    model: str = "gpt-3.5-turbo"
    prompt: str = PROMPT


class OpenAIContextTracker(BaseContextTracker[OpenAIContextTrackerConfig]):
    def __init__(self, config: OpenAIContextTrackerConfig, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)
        openai.api_key = getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        base_prompt = PROMPT
        self.messages = [{"role": "system", "content": base_prompt}]
        response = await openai.ChatCompletion.acreate(
            model=self.config.model,
            messages=self.messages,
            stream=True,
        )
        self.logger.debug(f"openai for start response: {response}")

    async def is_part_of_context(self, user_message: str) -> bool:
        self.logger.error(f"user message: {user_message}")
        self.messages.append({"role": "user", "content": user_message})
        self.logger.debug(f"model: {self.config.model}")
        self.logger.debug(f"prompt: {self.config.prompt}")
        self.logger.debug(f"messages: {self.messages}")
        self.logger.debug(f"api_key: {self.config.api_key}")
        response = await openai.ChatCompletion.acreate(
            model=self.config.model,
            messages=self.messages,
            stream=True,
        )
        self.logger.debug(f"openai response: {response}")
        resp = response['choices'][0]['message']['content']
        logging.debug("openai response: %s", resp)
        self.messages.append({"role": "assistant", "content": resp})
        is_related_to_context = 'true' in resp.lower()
        self.logger.debug(
            f"context tracker got message: {user_message}, and is_related_to_context is: {is_related_to_context}")
        return is_related_to_context

import logging
from typing import Optional

import openai

from vocode import getenv
from vocode.streaming.models.agent import AzureOpenAIConfig
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
    azure_config: AzureOpenAIConfig = None


class OpenAIContextTracker(BaseContextTracker[OpenAIContextTrackerConfig]):
    def __init__(self, config: OpenAIContextTrackerConfig, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)

        if self.config.azure_config:
            openai.api_type = self.config.azure_config.api_type
            openai.api_base = getenv("AZURE_OPENAI_API_BASE")
            openai.api_version = self.config.azure_config.api_version
            openai.api_key = getenv("AZURE_OPENAI_API_KEY")
        else:
            openai.api_type = "open_ai"
            openai.api_base = "https://api.openai.com/v1"
            openai.api_version = None
            openai.api_key = self.config.api_key or getenv("OPENAI_API_KEY")

        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        base_prompt = PROMPT
        self.messages = [{"role": "system", "content": base_prompt}]
        response = openai.ChatCompletion.create(
            model=self.config.model,
            messages=self.messages,
            stream=True,
        )
        self.logger.debug(f"openai for start response: {response}")

    def is_part_of_context(self, user_message: str) -> bool:
        self.messages.append({"role": "user", "content": user_message})
        parameters = dict(
            model=self.config.model,
            messages=self.messages,
            stream=True,
        )
        if self.config.azure_config is not None:
            parameters["engine"] = self.config.azure_config.engine
        else:
            parameters["model"] = self.config.model
        self.logger.debug(f"openai parameters: {parameters}")
        response = openai.ChatCompletion.create(**parameters)
        self.logger.debug(f"openai response: {response}")
        resp = response['choices'][0]['message']['content']
        logging.debug("openai response: %s", resp)
        self.messages.append({"role": "assistant", "content": resp})
        is_related_to_context = 'true' in resp.lower()
        self.logger.debug(
            f"context tracker got message: {user_message}, and is_related_to_context is: {is_related_to_context}")
        return is_related_to_context

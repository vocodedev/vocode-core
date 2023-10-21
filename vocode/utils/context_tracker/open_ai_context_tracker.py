import logging
from typing import Optional

import openai

from vocode import getenv
from vocode.streaming.models.agent import AzureOpenAIConfig
from vocode.utils.context_tracker import BaseContextTracker, BaseContextTrackerConfig
from vocode.utils.context_tracker.context_tracker import ContextTrackerType


class OpenAIContextTrackerConfig(BaseContextTrackerConfig, type=ContextTrackerType.OPEN_AI.value):
    api_key: str = getenv("OPENAI_API_KEY")
    model: str = "gpt-3.5-turbo"
    prompt: str = ""
    azure_config: AzureOpenAIConfig = None


class OpenAIContextTracker(BaseContextTracker[OpenAIContextTrackerConfig]):
    def __init__(self, config: OpenAIContextTrackerConfig, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)

        if self.config.prompt == "":
            raise ValueError("Prompt must be set in config")

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

        self.messages = [{"role": "system", "content": self.config.prompt}]

    def is_part_of_context(self, user_message: str) -> bool:
        parameters = self._generate_parameters(user_message)

        response = openai.ChatCompletion.create(**parameters)
        resp = response['choices'][0]['message']['content']
        self.messages.append({"role": "assistant", "content": resp})
        is_related_to_context = 'true' in resp.lower()
        self.logger.debug(
            f"context tracker got message: {user_message}, and is_related_to_context is: {is_related_to_context}")
        return is_related_to_context

    def _generate_parameters(self, user_message):
        self.messages.append({"role": "user", "content": user_message})
        parameters = dict(
            model=self.config.model,
            messages=self.messages,
        )
        if self.config.azure_config is not None:
            parameters["engine"] = self.config.azure_config.engine
        else:
            parameters["model"] = self.config.model
        return parameters

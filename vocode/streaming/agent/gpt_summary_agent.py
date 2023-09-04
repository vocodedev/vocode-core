import logging
import os
from typing import Optional

import openai

from vocode.streaming.models.agent import ChatGPTAgentConfig


class ChatGPTSummaryAgent:
    def __init__(
            self,
            agent_config: ChatGPTAgentConfig,
            logger: Optional[logging.Logger] = None
    ):
        self.agent_config = agent_config
        openai.api_type = agent_config.azure_params.api_type
        openai.api_base = os.getenv("AZURE_OPENAI_API_BASE")
        openai.api_version = agent_config.azure_params.api_version
        openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.logger = logger

    # create async function to call openai and use params from agent_config
    async def get_summary(self, message: str):
        # pass values from agent_config to openai params
        return await openai.Completion.acreate(
            engine=self.agent_config.azure_params.engine,
            prompt=message,
            temperature=self.agent_config.temperature,
            max_tokens=self.agent_config.max_tokens,
        )



import logging
from typing import List, Optional

from langchain import OpenAI
from vocode.streaming.agent.llm_agent import LLMAgent
from ..models.agent import InformationRetrievalAgentConfig, LLMAgentConfig


class InformationRetrievalAgent(LLMAgent):
    def __init__(
        self,
        agent_config: InformationRetrievalAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        # super().__init__(agent_config, logger)
        prompt_preamble = f"""
        The AI is a friendly phone bot built for information retrieval. It understands IVR navigation and chooses which numbers to press based on the intended goal and the options provided.
Once it reaches the human, it verifies the identity of the person it is trying to reach and states its purpose. If it needs to be transferred, then the AI asks to speak to the intended recipient of the phone call.

Here is the context for the call:
Intended goal: { agent_config.goal_description }
Intended recipient: { agent_config.recipient_descriptor }
Information to be collected: { agent_config.fields }
Information to provide to the person who answers the phone: this is a robot calling on behalf of { agent_config.caller_descriptor }

The AI begins the call by introducing itself and who it represents.
        """
        super().__init__(
            LLMAgentConfig(
                prompt_preamble=prompt_preamble,
            ),
            logger=logger,
        )
        self.llm = OpenAI(model_name="text-davinci-003", temperature=1)  # type: ignore

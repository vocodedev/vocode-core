import asyncio
import logging
from typing import List, Optional
import re
import typing
import openai


from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.action.nylas_send_email import NylasSendEmail
from vocode.streaming.agent.base_agent import (
    ActionResultAgentInput,
    AgentInput,
    AgentInputType,
    AgentResponseFillerAudio,
    AgentResponseMessage,
    BaseAgent,
    TranscriptionAgentInput,
)
from vocode.streaming.agent.prompts.action_prompt import ACTION_PROMPT_DEFAULT
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    stream_openai_response_async,
)
from vocode.streaming.models.actions import ActionInput
from vocode.streaming.models.agent import ActionAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils.worker import InterruptibleEvent


class ActionAgent(BaseAgent[ActionAgentConfig]):
    def __init__(
        self,
        agent_config: ActionAgentConfig,
        action_factory: ActionFactory = ActionFactory(),
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config, logger=logger)
        self.agent_config = agent_config
        self.action_factory = action_factory
        self.actions_queue: asyncio.Queue[
            InterruptibleEvent[ActionInput]
        ] = asyncio.Queue()

        openai.api_key = getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.action_descriptions = self.get_action_descriptions()

    def _create_prompt(self):
        assert self.transcript is not None
        return ACTION_PROMPT_DEFAULT.format(
            actions=self.get_action_descriptions(),
            transcript=self.transcript.to_string(),
        )

    async def process(self, item: InterruptibleEvent[AgentInput]):
        assert self.transcript is not None
        try:
            self.logger.debug("Responding to transcription")
            agent_input = item.payload
            if isinstance(agent_input, TranscriptionAgentInput):
                self.transcript.add_human_message(
                    text=agent_input.transcription.message,
                    conversation_id=agent_input.conversation_id,
                )
            elif isinstance(agent_input, ActionResultAgentInput):
                self.transcript.add_action_log(
                    action_output=agent_input.action_output,
                    conversation_id=agent_input.conversation_id,
                )
            else:
                raise ValueError("Invalid AgentInput type")

            messages = [{"role": "system", "content": self._create_prompt()}]
            openai_response = await openai.ChatCompletion.acreate(
                model=self.agent_config.model_name,
                messages=messages,
                max_tokens=self.agent_config.max_tokens,
                temperature=self.agent_config.temperature,
                stream=True,
            )
            verbose_response = ""
            async for message in stream_openai_response_async(
                openai_response,
                get_text=lambda choice: choice.get("delta", {}).get("content"),
                sentence_endings=["\n"],
            ):
                maybe_response = self.extract_response(message)
                if maybe_response:
                    self.produce_interruptible_event_nonblocking(
                        AgentResponseMessage(message=BaseMessage(text=maybe_response))
                    )
                verbose_response += f"{message}\n"
            for action_input in self.get_action_inputs(
                verbose_response, agent_input.conversation_id
            ):
                event = self.interruptible_event_factory.create(action_input)
                self.actions_queue.put_nowait(event)
        except asyncio.CancelledError:
            pass

    def get_action_descriptions(self):
        descriptions = []
        for action_type in self.agent_config.actions:
            action = self.action_factory.create_action(action_type)
            docstring = action.run.__doc__
            action_name = action_type.value
            descriptions.append(
                f"Action Name: {action_name}\nAction Description: {docstring}\n"
            )
        return "\n".join(descriptions)

    def extract_action(self, response: str):
        match = re.search(r"Action:\s*(.*)", response)
        return match.group(1).strip() if match else None

    def extract_parameters(self, response: str):
        match = re.search(r"Action parameters:\s*(.*)", response)
        return match.group(1).strip() if match else ""

    def extract_response(self, response: str):
        match = re.search(r"Response:\s*(.*)", response)
        return match.group(1).strip() if match else ""

    def get_action_inputs(
        self, response: str, conversation_id: str
    ) -> List[ActionInput]:
        extracted_action = self.extract_action(response)
        extracted_parameters = self.extract_parameters(response)

        action_inputs = []
        for action_type in self.agent_config.actions:
            if action_type.value == extracted_action:
                action_inputs.append(
                    ActionInput(
                        action_type=action_type,
                        params=extracted_parameters,
                        conversation_id=conversation_id,
                    )
                )
        return action_inputs

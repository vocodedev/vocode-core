import asyncio
import json
import logging
from typing import List, Optional
import re
import typing
import openai


from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.action.nylas_send_email import NylasSendEmail
from vocode.streaming.action.phone_call_action import (
    TwilioPhoneCallAction,
    VonagePhoneCallAction,
)
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
        self.functions = self.get_functions()

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
                self.transcript.add_action_finish_log(
                    action_output=agent_input.action_output,
                    conversation_id=agent_input.conversation_id,
                )
            else:
                raise ValueError("Invalid AgentInput type")

            messages = format_openai_chat_messages_from_transcript(
                self.transcript, self.agent_config.prompt_preamble
            )
            openai_response = await openai.ChatCompletion.acreate(
                model=self.agent_config.model_name,
                messages=messages,
                functions=self.functions,
                max_tokens=self.agent_config.max_tokens,
                temperature=self.agent_config.temperature,
            )
            if len(openai_response.choices) == 0:
                raise ValueError("OpenAI returned no choices")
            message = openai_response.choices[0].message
            if message.content:
                self.produce_interruptible_event_nonblocking(
                    AgentResponseMessage(message=BaseMessage(text=message.content))
                )
            elif message.function_call:
                action = self.action_factory.create_action(message.function_call.name)
                params = json.loads(message.function_call.arguments)
                if "user_message" in params:
                    user_message = params["user_message"]
                    self.produce_interruptible_event_nonblocking(
                        AgentResponseMessage(message=BaseMessage(text=user_message))
                    )
                action_input: ActionInput
                if isinstance(action, VonagePhoneCallAction):
                    assert (
                        agent_input.vonage_uuid is not None
                    ), "Cannot use VonagePhoneCallActionFactory unless the attached conversation is a VonageCall"
                    action_input = action.create_phone_call_action_input(
                        message.function_call.name, params, agent_input.vonage_uuid
                    )
                elif isinstance(action, TwilioPhoneCallAction):
                    assert (
                        agent_input.twilio_sid is not None
                    ), "Cannot use TwilioPhoneCallActionFactory unless the attached conversation is a TwilioCall"
                    action_input = action.create_phone_call_action_input(
                        message.function_call.name, params, agent_input.twilio_sid
                    )
                else:
                    action_input = action.create_action_input(
                        agent_input.conversation_id,
                        params,
                    )
                event = self.interruptible_event_factory.create(action_input)
                self.transcript.add_action_start_log(
                    action_input=action_input,
                    conversation_id=agent_input.conversation_id,
                )
                self.actions_queue.put_nowait(event)
        except asyncio.CancelledError:
            pass

    def get_functions(self):
        return [
            self.action_factory.create_action(action_type).get_openai_function()
            for action_type in self.agent_config.actions
        ]

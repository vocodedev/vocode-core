import asyncio
import typing
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.agent import *
from vocode.streaming.agent.base_agent import AgentResponseMessage, AgentResponseType
from vocode.streaming.models.agent import (
    AgentConfig,
    ChatAnthropicAgentConfig,
    ChatGPTAgentConfig,
    EchoAgentConfig,
    GPT4AllAgentConfig,
    LLMAgentConfig,
    RESTfulUserImplementedAgentConfig,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import create_conversation_id


async def run_agent(agent: BaseAgent):
    ended = False

    async def receiver():
        nonlocal ended
        while not ended:
            try:
                event = await agent.get_output_queue().get()
                response = event.payload
                if response.type == AgentResponseType.FILLER_AUDIO:
                    print("Would have sent filler audio")
                elif response.type == AgentResponseType.STOP:
                    print("Agent returned stop")
                    ended = True
                    break
                elif response.type == AgentResponseType.MESSAGE:
                    print(
                        "\nAI: ",
                        typing.cast(AgentResponseMessage, response).message.text,
                    )
            except asyncio.CancelledError:
                break

    async def sender():
        conversation_id = create_conversation_id()
        while not ended:
            try:
                message = await asyncio.get_event_loop().run_in_executor(
                    None, input, "Human: "
                )
                agent.consume_nonblocking(
                    agent.interruptible_event_factory.create(
                        (Transcription(message, 1.0, True), conversation_id)
                    )
                )
            except asyncio.CancelledError:
                break

    await asyncio.gather(receiver(), sender())


async def main():
    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life.",
            end_conversation_on_goodbye=True,
        )
    )
    agent.start()
    task = asyncio.create_task(run_agent(agent))
    try:
        await task
    except KeyboardInterrupt:
        task.cancel()
        agent.terminate()


if __name__ == "__main__":
    asyncio.run(main())

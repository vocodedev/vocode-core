from vocode.streaming.agent.anthropic_agent import ChatAnthropicAgent
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.agent.gpt4all_agent import GPT4AllAgent
from vocode.streaming.agent.llm_agent import LLMAgent
from vocode.streaming.agent.restful_user_implemented_agent import (
    RESTfulUserImplementedAgent,
)
from vocode.streaming.models.agent import (
    AgentConfig,
    ChatAnthropicAgentConfig,
    ChatGPTAgentConfig,
    EchoAgentConfig,
    GPT4AllAgentConfig,
    LLMAgentConfig,
    RESTfulUserImplementedAgentConfig,
)
from vocode.streaming.utils import create_conversation_id


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    async def run_agent(agent: BaseAgent, generate_responses: bool):
        conversation_id = create_conversation_id()
        while True:
            if generate_responses:
                responses = agent.generate_response(
                    input("Human: "), conversation_id=conversation_id
                )
                async for response in responses:
                    print("AI:", response)
            else:
                response, _ = await agent.respond(
                    input("Human: "), conversation_id=conversation_id
                )
                print("AI:", response)

    agent = ChatAnthropicAgent(
        ChatAnthropicAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life.",
        )
    )
    asyncio.run(run_agent(agent=agent, generate_responses=True))

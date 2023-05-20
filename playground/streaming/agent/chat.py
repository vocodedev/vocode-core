from vocode.streaming.agent import *
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
                stream = agent.generate_response(
                    input("Human: "), conversation_id=conversation_id
                )
                async for sentence in stream:
                    print("AI:", sentence)
            else:
                response, _ = await agent.respond(
                    input("Human: "), conversation_id=conversation_id
                )
                print("AI:", response)

    # replace with the agent you want to test
    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life.",
        )
    )
    asyncio.run(run_agent(agent=agent, generate_responses=True))

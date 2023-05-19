from vocode.streaming.agent.anthropic_agent import ChatAnthropicAgent
from vocode.streaming.agent.base_agent import AgentResponse, BaseAgent, GeneratorAgentResponse, OneShotAgentResponse, TextAgentResponseMessage, TextAndStopAgentResponseMessage
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
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import create_conversation_id


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    async def handle_agent_response(response: AgentResponse):
        if isinstance(response, OneShotAgentResponse):
            if isinstance(response.message, (TextAgentResponseMessage, TextAndStopAgentResponseMessage)):
                print("AI: ", response.message)
            else:
                print("Invalid response type: ", response.message)
        elif isinstance(response, GeneratorAgentResponse):
            ai_response_sentence = ""
            async for message in response.generator:
                if isinstance(message, (TextAgentResponseMessage, TextAndStopAgentResponseMessage)):
                    if ai_response_sentence == "":
                        ai_response_sentence += message.text
                    else:
                        ai_response_sentence += " " + message.text
                else:
                    print("Invalid response message type: ", message)

            print("AI: ", ai_response_sentence)

    async def run_agent(agent: BaseAgent):
        agent.set_on_agent_response(handle_agent_response)

        while True:
            command_line_input = input("Human: ")
            transcription = Transcription(
                message=command_line_input,
                confidence=1.0,
                is_final=True,
                is_interrupt=False,
                )
            await agent.add_transcript_to_input_queue(transcription=transcription)

    # replace with the agent you want to test
    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life.",
        )
    )
    asyncio.run(run_agent(agent=agent))

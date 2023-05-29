import asyncio
import typing
import argparse
from dotenv import load_dotenv
from vocode.streaming.models.transcript import Transcript

load_dotenv()

from vocode.streaming.agent import *
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponseMessage,
    AgentResponseType,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import create_conversation_id
from vocode.streaming.utils.events_manager import EventsManager


async def run_agent(agent: BaseAgent):
    ended = False
    events_manager = EventsManager()
    conversation_id = create_conversation_id()

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
                    agent_response = typing.cast(AgentResponseMessage, response)

                    agent.transcript.add_bot_message(
                        agent_response.message.text, events_manager, conversation_id
                    )
                    print(
                        "AI: "
                        + typing.cast(AgentResponseMessage, response).message.text
                    )
            except asyncio.CancelledError:
                break

    async def sender():
        while not ended:
            try:
                message = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("Human: ")
                )
                agent.transcript.add_human_message(
                    message, events_manager, conversation_id
                )
                agent.consume_nonblocking(
                    agent.interruptible_event_factory.create(
                        AgentInput(
                            transcription=Transcription(
                                message=message, confidence=1.0, is_final=True
                            ),
                            conversation_id=conversation_id,
                        )
                    )
                )
            except asyncio.CancelledError:
                break

    await asyncio.gather(receiver(), sender())


async def agent_main():
    transcript = Transcript()
    # Replace with your agent!
    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life.",
            end_conversation_on_goodbye=True,
            generate_responses=True,
        )
    )
    agent.attach_transcript(transcript)
    agent.start()

    try:
        await run_agent(agent)
    except KeyboardInterrupt:
        agent.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace", action="store_true", help="Log latencies and other statistics"
    )
    args = parser.parse_args()

    if args.trace:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from playground.streaming.tracing_utils import PrintDurationSpanExporter

        trace.set_tracer_provider(TracerProvider(resource=Resource.create({})))
        span_exporter = PrintDurationSpanExporter()
        trace.get_tracer_provider().add_span_processor(
            SimpleSpanProcessor(span_exporter)
        )

    asyncio.run(agent_main())

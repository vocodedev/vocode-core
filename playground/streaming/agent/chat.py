import asyncio
import typing
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.agent import *
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponseMessage,
    AgentResponseType,
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
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import create_conversation_id
import curses


def clear_current_line(win):
    y, x = win.getyx()  # Get current position
    height, width = win.getmaxyx()  # Get window size
    win.addstr(y, 0, " " * (width - 1))  # Write spaces over the entire line
    win.move(y, 0)  # Move the cursor back to the start of the line


def get_user_input(win, human_idx):
    curses.noecho()
    message = ""
    while True:
        ch = win.getch()
        if ch in [curses.KEY_ENTER, 10, 13]:  # Enter key pressed
            break
        elif ch in [curses.KEY_BACKSPACE, 127]:  # Backspace key pressed
            message = message[:-1]
            clear_current_line(win)
            win.addstr(human_idx, 0, "Human: " + message)
        else:
            message += chr(ch)
            win.addstr(chr(ch))
        win.refresh()
    return message


async def run_agent(agent: BaseAgent, stdscr):
    ended = False

    # Determine the size and position of each window
    height, width = stdscr.getmaxyx()
    half_width = width // 2

    # Create two windows for AI and human
    ai_win = stdscr.subwin(
        height, half_width - 1, 0, 0
    )  # Starts at (0,0) and occupies the left half
    human_win = stdscr.subwin(
        height, half_width, 0, half_width
    )  # Starts at (0, half_width) and occupies the right half

    human_idx = 0

    async def receiver():
        nonlocal ended
        while not ended:
            try:
                event = await agent.get_output_queue().get()
                response = event.payload
                if response.type == AgentResponseType.FILLER_AUDIO:
                    ai_win.addstr("Would have sent filler audio\n")
                    ai_win.refresh()
                elif response.type == AgentResponseType.STOP:
                    ai_win.addstr("Agent returned stop\n")
                    ai_win.refresh()
                    ended = True
                    break
                elif response.type == AgentResponseType.MESSAGE:
                    ai_win.addstr(
                        "AI: "
                        + typing.cast(AgentResponseMessage, response).message.text
                        + "\n",
                    )
                    ai_win.refresh()

                    human_win.addstr(human_idx, 0, "Human: ")
                    human_win.refresh()
            except asyncio.CancelledError:
                break

    async def sender():
        nonlocal human_idx
        conversation_id = create_conversation_id()
        human_win.addstr("Human: ")
        human_win.refresh()
        while not ended:
            try:
                curses.echo()
                message = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: get_user_input(human_win, human_idx)
                )
                curses.noecho()
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
                human_win.refresh()
            except asyncio.CancelledError:
                break
            human_idx += 1

    await asyncio.gather(receiver(), sender())


def start_curses(stdscr):
    stdscr.clear()
    stdscr.refresh()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(agent_main(stdscr))
    loop.close()


async def agent_main(stdscr):
    # Replace with your agent!
    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life.",
            end_conversation_on_goodbye=True,
        )
    )
    agent.start()

    try:
        await run_agent(agent, stdscr)
    except KeyboardInterrupt:
        agent.terminate()


if __name__ == "__main__":
    curses.wrapper(start_curses)

from typing import Any, Dict, List, Optional, Union
from openai.openai_object import OpenAIObject
from pydantic import BaseModel
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    FunctionCall,
)
import pytest
from vocode.streaming.agent.utils import (
    collate_response_async,
    format_openai_chat_messages_from_transcript,
    openai_get_tokens,
)
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import (
    ActionFinish,
    ActionStart,
    Message,
    Transcript,
)


async def _agen_from_list(l):
    for item in l:
        yield item


def create_chatgpt_openai_object(
    delta: Dict[str, str], finish_reason: Optional[Any] = None
):
    return OpenAIObject.construct_from(
        {"choices": [{"delta": delta, "finish_reason": finish_reason}]}
    )


class StreamOpenAIResponseTestCase(BaseModel):
    openai_objects: List[OpenAIObject]
    expected_sentences: List[Union[str, FunctionCall]]
    get_functions: bool


OPENAI_OBJECTS = [
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Hello"}, "finish_reason": None},
        {"delta": {"content": "!"}, "finish_reason": None},
        {"delta": {"content": " How"}, "finish_reason": None},
        {"delta": {"content": " are"}, "finish_reason": None},
        {"delta": {"content": " you"}, "finish_reason": None},
        {"delta": {"content": " doing"}, "finish_reason": None},
        {"delta": {"content": " today"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Hello"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " What"}, "finish_reason": None},
        {"delta": {"content": " do"}, "finish_reason": None},
        {"delta": {"content": " you"}, "finish_reason": None},
        {"delta": {"content": " want"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " talk"}, "finish_reason": None},
        {"delta": {"content": " about"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "This"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " a"}, "finish_reason": None},
        {"delta": {"content": " test"}, "finish_reason": None},
        {"delta": {"content": " sentence."}, "finish_reason": None},
        {"delta": {"content": " Want"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " hear"}, "finish_reason": None},
        {"delta": {"content": " a"}, "finish_reason": None},
        {"delta": {"content": " joke"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Sure"}, "finish_reason": None},
        {"delta": {"content": ","}, "finish_reason": None},
        {"delta": {"content": " here"}, "finish_reason": None},
        {"delta": {"content": " are"}, "finish_reason": None},
        {"delta": {"content": " three"}, "finish_reason": None},
        {"delta": {"content": " possible"}, "finish_reason": None},
        {"delta": {"content": " things"}, "finish_reason": None},
        {"delta": {"content": " we"}, "finish_reason": None},
        {"delta": {"content": " could"}, "finish_reason": None},
        {"delta": {"content": " talk"}, "finish_reason": None},
        {"delta": {"content": " about"}, "finish_reason": None},
        {"delta": {"content": ":\n"}, "finish_reason": None},
        {"delta": {"content": " \n"}, "finish_reason": None},
        {"delta": {"content": "1"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " Goals"}, "finish_reason": None},
        {"delta": {"content": " and"}, "finish_reason": None},
        {"delta": {"content": " aspirations"}, "finish_reason": None},
        {"delta": {"content": "\n"}, "finish_reason": None},
        {"delta": {"content": "2"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " Travel"}, "finish_reason": None},
        {"delta": {"content": " and"}, "finish_reason": None},
        {"delta": {"content": " exploration"}, "finish_reason": None},
        {"delta": {"content": "\n"}, "finish_reason": None},
        {"delta": {"content": "3"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " H"}, "finish_reason": None},
        {"delta": {"content": "obbies"}, "finish_reason": None},
        {"delta": {"content": " and"}, "finish_reason": None},
        {"delta": {"content": " interests"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "$"}, "finish_reason": None},
        {"delta": {"content": "1"}, "finish_reason": None},
        {"delta": {"content": " +"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "3"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": "20"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " equal"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "4"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": "20"}, "finish_reason": None},
        {"delta": {"content": ".\n\n"}, "finish_reason": None},
        {"delta": {"content": "And"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "1"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": "40"}, "finish_reason": None},
        {"delta": {"content": " plus"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "2"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": "80"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " equal"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "4"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": "20"}, "finish_reason": None},
        {"delta": {"content": " as"}, "finish_reason": None},
        {"delta": {"content": " well"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "$"}, "finish_reason": None},
        {"delta": {"content": "2"}, "finish_reason": None},
        {"delta": {"content": " +"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "3"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": "00"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " equal"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "5"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "6"}, "finish_reason": None},
        {"delta": {"content": " +"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "4"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " equal"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " $"}, "finish_reason": None},
        {"delta": {"content": "10"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Hello"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " What"}, "finish_reason": None},
        {"delta": {"content": " do"}, "finish_reason": None},
        {"delta": {"content": " you"}, "finish_reason": None},
        {"delta": {"content": " want"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " talk"}, "finish_reason": None},
        {"delta": {"content": " about"}, "finish_reason": None},
        {"delta": {"function_call": {"name": "wave"}}, "finish_reason": None},
        {
            "delta": {"function_call": {"name": "_hello", "arguments": "{\n"}},
            "finish_reason": None,
        },
        {
            "delta": {"function_call": {"arguments": '  "name": "user"\n}'}},
            "finish_reason": None,
        },
        {"delta": {}, "finish_reason": "function_call"},
    ],
    [
        {"delta": {"function_call": {"name": "wave"}}, "finish_reason": None},
        {
            "delta": {"function_call": {"name": "_hello", "arguments": "{\n"}},
            "finish_reason": None,
        },
        {
            "delta": {"function_call": {"arguments": '  "name": "user"\n}'}},
            "finish_reason": None,
        },
        {"delta": {}, "finish_reason": "function_call"},
    ],
]

EXPECTED_SENTENCES = [
    ["Hello!", "How are you doing today?"],
    ["Hello.", "What do you want to talk about?"],
    ["This is a test sentence.", "Want to hear a joke?"],
    [
        "Sure, here are three possible things we could talk about:",
        "1. Goals and aspirations",
        "2. Travel and exploration",
        "3. Hobbies and interests",
    ],
    [
        "$1 + $3.20 is equal to $4.20.",
        "And $1.40 plus $2.80 is equal to $4.20 as well.",
    ],
    [
        "$2 + $3.00 is equal to $5.",
        "$6 + $4 is equal to $10.",
    ],
    [
        "Hello.",
        "What do you want to talk about",
        FunctionCall(name="wave_hello", arguments='{\n  "name": "user"\n}'),
    ],
    [
        FunctionCall(name="wave_hello", arguments='{\n  "name": "user"\n}'),
    ],
]

FUNCTIONS_INPUT = [
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Hello"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " What"}, "finish_reason": None},
        {"delta": {"content": " do"}, "finish_reason": None},
        {"delta": {"content": " you"}, "finish_reason": None},
        {"delta": {"content": " want"}, "finish_reason": None},
        {"delta": {"content": " to"}, "finish_reason": None},
        {"delta": {"content": " talk"}, "finish_reason": None},
        {"delta": {"content": " about"}, "finish_reason": None},
        {"delta": {"function_call": {"name": "wave"}}, "finish_reason": None},
        {
            "delta": {"function_call": {"name": "_hello", "arguments": "{\n"}},
            "finish_reason": None,
        },
        {
            "delta": {"function_call": {"arguments": '  "name": "user"\n}'}},
            "finish_reason": None,
        },
        {"delta": {}, "finish_reason": "function_call"},
    ],
    [
        {"delta": {"function_call": {"name": "wave"}}, "finish_reason": None},
        {
            "delta": {"function_call": {"name": "_hello", "arguments": "{\n"}},
            "finish_reason": None,
        },
        {
            "delta": {"function_call": {"arguments": '  "name": "user"\n}'}},
            "finish_reason": None,
        },
        {"delta": {}, "finish_reason": "function_call"},
    ],
]

FUNCTIONS_OUTPUT = [
    [
        "Hello.",
        "What do you want to talk about",
        FunctionCall(name="wave_hello", arguments='{\n  "name": "user"\n}'),
    ],
    [
        FunctionCall(name="wave_hello", arguments='{\n  "name": "user"\n}'),
    ],
]


@pytest.mark.asyncio
async def test_collate_response_async():
    test_cases = [
        StreamOpenAIResponseTestCase(
            openai_objects=[
                create_chatgpt_openai_object(**obj) for obj in openai_objects
            ],
            expected_sentences=expected_sentences,
            get_functions=any(
                isinstance(item, FunctionCall) for item in expected_sentences
            ),
        )
        for openai_objects, expected_sentences in zip(
            OPENAI_OBJECTS, EXPECTED_SENTENCES
        )
    ]

    for test_case in test_cases:
        actual_sentences = []
        async for sentence in collate_response_async(
            openai_get_tokens(_agen_from_list(test_case.openai_objects)),
            get_functions=test_case.get_functions,
        ):
            actual_sentences.append(sentence)
        assert actual_sentences == test_case.expected_sentences


def test_format_openai_chat_messages_from_transcript():
    test_cases = [
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!"),
                        Message(sender=Sender.BOT, text="How are you doing today?"),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                    ]
                ),
                "prompt preamble",
            ),
            [
                {"role": "system", "content": "prompt preamble"},
                {"role": "assistant", "content": "Hello! How are you doing today?"},
                {"role": "user", "content": "I'm doing well, thanks!"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!"),
                        Message(sender=Sender.BOT, text="How are you doing today?"),
                        Message(sender=Sender.HUMAN, text="I'm doing well, thanks!"),
                    ]
                ),
                None,
            ),
            [
                {"role": "assistant", "content": "Hello! How are you doing today?"},
                {"role": "user", "content": "I'm doing well, thanks!"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!"),
                        Message(sender=Sender.BOT, text="How are you doing today?"),
                    ]
                ),
                "prompt preamble",
            ),
            [
                {"role": "system", "content": "prompt preamble"},
                {"role": "assistant", "content": "Hello! How are you doing today?"},
            ],
        ),
        (
            (
                Transcript(
                    event_logs=[
                        Message(sender=Sender.BOT, text="Hello!"),
                        Message(
                            sender=Sender.HUMAN, text="Hello, what's the weather like?"
                        ),
                        ActionStart(
                            action_type="weather",
                            action_input=ActionInput(
                                action_config=ActionConfig(),
                                conversation_id="asdf",
                                params={},
                            ),
                        ),
                        ActionFinish(
                            action_type="weather",
                            action_output=ActionOutput(
                                action_type="weather", response={}
                            ),
                        ),
                    ]
                ),
                None,
            ),
            [
                {"role": "assistant", "content": "Hello!"},
                {
                    "role": "user",
                    "content": "Hello, what's the weather like?",
                },
                {
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": "weather",
                        "arguments": "{}",
                    },
                },
                {
                    "role": "function",
                    "name": "weather",
                    "content": "{}",
                },
            ],
        ),
    ]

    for params, expected_output in test_cases:
        assert format_openai_chat_messages_from_transcript(*params) == expected_output

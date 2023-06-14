from typing import Any, Dict, List, Optional
from openai.openai_object import OpenAIObject
from pydantic import BaseModel
import pytest
from vocode.streaming.agent.utils import stream_openai_response_async

GET_TEXT = lambda choice: choice.get("delta", {}).get("content")


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
    expected_sentences: List[str]


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
]


@pytest.mark.asyncio
async def test_stream_openai_response_async():
    test_cases = [
        StreamOpenAIResponseTestCase(
            openai_objects=[
                create_chatgpt_openai_object(**obj) for obj in openai_objects
            ],
            expected_sentences=expected_sentences,
        )
        for openai_objects, expected_sentences in zip(
            OPENAI_OBJECTS, EXPECTED_SENTENCES
        )
    ]

    for test_case in test_cases:
        actual_sentences = []
        async for sentence in stream_openai_response_async(
            _agen_from_list(test_case.openai_objects), GET_TEXT
        ):
            actual_sentences.append(sentence)
        assert actual_sentences == test_case.expected_sentences

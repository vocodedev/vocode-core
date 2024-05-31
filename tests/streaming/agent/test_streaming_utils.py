from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import pytest
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic.v1 import BaseModel

from vocode.streaming.agent.openai_utils import openai_get_tokens
from vocode.streaming.agent.streaming_utils import collate_response_async
from vocode.streaming.models.actions import FunctionCall


async def _agen_from_chunk_list(
    l: List[ChatCompletionChunk],
) -> AsyncGenerator[ChatCompletionChunk, Any]:
    for item in l:
        yield item


def create_chatgpt_openai_object(
    delta: Optional[Dict[str, str]] = None,
    finish_reason: Optional[Any] = None,
    prompt_annotations=None,
) -> ChatCompletionChunk:
    inner_obj = {
        "id": "test_id",
        "created": 1423143,
        "model": "gpt-3.5-turbo-0613",
        "object": "chat.completion.chunk",
        "choices": [],
    }
    if prompt_annotations:
        inner_obj["prompt_annotations"] = prompt_annotations
        inner_obj["choices"] = []
    elif delta:
        inner_obj["choices"] = [{"index": 0, "delta": delta, "finish_reason": finish_reason}]
    return ChatCompletionChunk.parse_obj(inner_obj)


class StreamOpenAIResponseTestCase(BaseModel):
    openai_objects: List[ChatCompletionChunk]
    expected_sentences: List[Union[str, FunctionCall]]
    get_functions: bool

    class Config:
        arbitrary_types_allowed = True


OPENAI_OBJECTS = [
    [
        {
            "prompt_annotations": [
                {
                    "prompt_index": 0,
                    "content_filter_results": {},
                }
            ]
        },
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
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Yes"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " Hi"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " Ok"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " What"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " it"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Ok"}, "finish_reason": None},
        {"delta": {"content": " gotcha"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " What"}, "finish_reason": None},
        {"delta": {"content": " is"}, "finish_reason": None},
        {"delta": {"content": " up"}, "finish_reason": None},
        {"delta": {"content": " man"}, "finish_reason": None},
        {"delta": {"content": "."}, "finish_reason": None},
        {"delta": {"content": " Nothing"}, "finish_reason": None},
        {"delta": {"content": " much"}, "finish_reason": None},
        {"delta": {"content": " how"}, "finish_reason": None},
        {"delta": {"content": " are"}, "finish_reason": None},
        {"delta": {"content": " you"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
    [
        {"delta": {"role": "assistant"}, "finish_reason": None},
        {"delta": {"content": "Hello"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {"content": " Yes"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {"content": " Hello"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {"content": "Is"}, "finish_reason": None},
        {"delta": {"content": " this"}, "finish_reason": None},
        {"delta": {"content": " Bob"}, "finish_reason": None},
        {"delta": {"content": "?"}, "finish_reason": None},
        {"delta": {}, "finish_reason": "stop"},
    ],
]

EXPECTED_SENTENCES = [
    ["Hello! How are you doing today?"],
    ["Hello. What do you want to talk about?"],
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
    ["$2 + $3.00 is equal to $5.", "$6 + $4 is equal to $10."],
    [
        "Hello. What do you want to talk about",
        FunctionCall(name="wave_hello", arguments='{\n  "name": "user"\n}'),
    ],
    [FunctionCall(name="wave_hello", arguments='{\n  "name": "user"\n}')],
    ["Yes. Hi. Ok. What is it?"],
    ["Ok gotcha. What is up man.", "Nothing much how are you?"],
    ["Hello? Yes? Hello?", "Is this Bob?"],
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
async def test_collate_response_async(mocker):
    test_cases = [
        StreamOpenAIResponseTestCase(
            openai_objects=[create_chatgpt_openai_object(**obj) for obj in openai_objects],
            expected_sentences=expected_sentences,
            get_functions=any(isinstance(item, FunctionCall) for item in expected_sentences),
        )
        for openai_objects, expected_sentences in zip(OPENAI_OBJECTS, EXPECTED_SENTENCES)
    ]

    for test_case in test_cases:
        actual_sentences = []
        async for sentence in collate_response_async(
            conversation_id="test",
            gen=openai_get_tokens(_agen_from_chunk_list(test_case.openai_objects)),
            get_functions=test_case.get_functions,
        ):
            actual_sentences.append(sentence)
        assert actual_sentences == test_case.expected_sentences

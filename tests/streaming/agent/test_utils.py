import asyncio
import time
from typing import Any, Dict, List, Optional, Union
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

from openai.types.chat.chat_completion_chunk import Choice, ChatCompletionChunk, ChoiceDelta, ChoiceDeltaToolCall, ChoiceDeltaToolCallFunction


async def _agen_from_list(l: List[ChatCompletionChunk]):
    for item in l:
        # add the created time for the chunk here
        item.created = int(time.time())
        await asyncio.sleep(0.15)
        yield item


class StreamOpenAIResponseTestCase(BaseModel):
    input_stream: List[ChatCompletionChunk]
    expected_sentences: List[Union[str, FunctionCall]]
    get_functions: bool


TEST_STREAM =[
    [
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content="Hello"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content="!"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content=" How"),index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content=" are"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content=" you"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content=" doing"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content=" today"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(content="?"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_1', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="stop")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content="Hello"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" What"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" do"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" you"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" want"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" talk"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content=" about"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(content="?"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_2', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="stop")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content="This"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" is"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" a"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" test"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" sentence."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" Want"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" hear"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" a"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content=" joke"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(content="?"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_3', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="stop")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="Sure"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=","), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" here"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" are"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" three"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" possible"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" things"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" we"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" could"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" talk"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" about"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=":\n"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" \n"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="1"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" Goals"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" and"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" aspirations"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="\n"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="2"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" Travel"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" and"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" exploration"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="\n"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="3"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" H"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content="obbies"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" and"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(content=" interests"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_4', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="stop")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="$"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="1"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" +"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="3"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="20"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" is"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" equal"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="4"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="20"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=".\n\n"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="And"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="1"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="40"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" plus"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="2"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="80"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" is"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" equal"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="4"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="20"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" as"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content=" well"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_5', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="stop")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="$"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="2"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" +"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="3"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="00"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" is"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" equal"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="5"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="6"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" +"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="4"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" is"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" equal"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content=" $"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="10"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_6', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="stop")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(role="assistant"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content="Hello"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content="."), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" What"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" do"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" you"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" want"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" to"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" talk"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(content=" about"), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_8', choices=[Choice(delta=ChoiceDelta(tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction(name="wave"))]), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction(arguments="{\n", name="_hello"))]), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction(arguments='  "name": "user"\n}'))]), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_7', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="function_call")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
    ],
    [
        ChatCompletionChunk(id='test_stream_8', choices=[Choice(delta=ChoiceDelta(tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction(name="wave"))]), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_8', choices=[Choice(delta=ChoiceDelta(tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction(arguments="{\n", name="_hello"))]), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_8', choices=[Choice(delta=ChoiceDelta(tool_calls=[ChoiceDeltaToolCall(index=0, function=ChoiceDeltaToolCallFunction(arguments='  "name": "user"\n}'))]), index=0)], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
        ChatCompletionChunk(id='test_stream_8', choices=[Choice(delta=ChoiceDelta(), index=0, finish_reason="function_call")], created=0, model='gpt-35-turbo-16k', object='chat.completion.chunk'),
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


@pytest.mark.asyncio
async def test_collate_response_async():
    test_cases = [
        StreamOpenAIResponseTestCase(
            input_stream=[
                obj for obj in test_stream
            ],
            expected_sentences=expected_sentences,
            get_functions=any(
                isinstance(item, FunctionCall) for item in expected_sentences
            ),
        )
        for test_stream, expected_sentences in zip(
            TEST_STREAM, EXPECTED_SENTENCES
        )
    ]

    for test_case in test_cases:
        actual_sentences = []
        async for sentence in collate_response_async(
            openai_get_tokens(_agen_from_list(test_case.input_stream)),
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

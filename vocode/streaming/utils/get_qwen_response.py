from copy import deepcopy
import json
from logging import Logger
from typing import Any, Dict, List, Optional
from vocode import getenv
import aiohttp
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.models.transcript import (
    ActionFinish,
    ActionStart,
    EventLog,
    Message,
    Transcript,
)

QWEN_MODEL_NAME = "Qwen/Qwen1.5-72B-Chat-GPTQ-Int4"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer 'EMPTY'",
}


def format_qwen_chat_completion_from_transcript(
    transcript: Transcript, prompt_preamble: Optional[str] = None
):
    formatted_conversation = ""
    if prompt_preamble:
        formatted_conversation += f"<|im_start|>system\n{prompt_preamble}<|im_end|>\n"
    # merge consecutive bot messages
    new_event_logs: List[EventLog] = []
    idx = 0
    while idx < len(transcript.event_logs):
        bot_messages_buffer: List[Message] = []
        current_log = transcript.event_logs[idx]
        while isinstance(current_log, Message) and current_log.sender == Sender.BOT:
            bot_messages_buffer.append(current_log)
            idx += 1
            try:
                current_log = transcript.event_logs[idx]
            except IndexError:
                break
        if bot_messages_buffer:
            merged_bot_message = deepcopy(bot_messages_buffer[-1])
            merged_bot_message.text = " ".join(
                event_log.text
                for event_log in bot_messages_buffer
                if event_log.text.strip()
            )
            if merged_bot_message.text.strip():
                new_event_logs.append(merged_bot_message)
        else:
            if (
                isinstance(current_log, Message) and current_log.text.strip()
            ) or isinstance(current_log, (ActionStart, ActionFinish)):
                new_event_logs.append(current_log)
            idx += 1
    for event_log in new_event_logs:
        if isinstance(event_log, Message):
            role = "assistant" if event_log.sender == Sender.BOT else "user"
            if event_log.text.strip():
                formatted_conversation += (
                    f"<|im_start|>{role}\n{event_log.text}<|im_end|>\n"
                )
        elif isinstance(event_log, ActionStart):
            formatted_conversation += f"<|im_start|>user\nSYSTEM: Submitted: Function call: {event_log.action_type} with arguments {event_log.action_input.params.json()}\nDo not answer the user's associated query until a response is received from the system.<|im_end|>\n"
        elif isinstance(event_log, ActionFinish):
            formatted_conversation += f"<|im_start|>user\nSYSTEM: Completed: Function {event_log.action_type}.\nResponse was: {event_log.action_output.response.json()}\nNow you can use the response in the conversation.<|im_end|>\n"
    formatted_conversation += "<|im_start|>assistant\n"
    return formatted_conversation


async def get_qwen_response(
    prompt_buffer: str,
    logger: Logger,
    stream_output: bool = True,
    retries_remaining: int = 40,
):
    sentence_buffer = ""
    async with aiohttp.ClientSession() as session:
        base_url = "http://148.64.105.83:4000/v1"
        data = {
            "model": QWEN_MODEL_NAME,
            "prompt": prompt_buffer,
            "stream": True,
            "stop": ["?", "SYSTEM"],
            "max_tokens": 120,
            "temperature": 0.1,
            "top_p": 0.9,
            "include_stop_str_in_output": True,
        }

        async with session.post(
            f"{base_url}/completions", headers=HEADERS, json=data
        ) as response:
            if response.status == 200:
                last_message = ""
                async for chunk in response.content:
                    # Parse each line of the response content
                    if chunk.startswith(b"data: {"):
                        # Extract JSON from the current chunk
                        first_brace = chunk.find(b"{")
                        last_brace = chunk.rfind(b"}")
                        json_str = chunk[first_brace : last_brace + 1].decode("utf-8")
                        try:
                            completion_data = json.loads(json_str)
                            if (
                                "choices" in completion_data
                                and completion_data["choices"]
                            ):
                                for choice in completion_data["choices"]:
                                    if "text" in choice:
                                        completion_text = choice["text"]
                                        completion_text = completion_text.replace(
                                            "SYSTEM", ""
                                        )
                                        sentence_buffer += completion_text
                                        last_message += completion_text
                                        # Find the earliest occurrence of punctuation and yield up to that punctuation
                                        punctuation_indices = [
                                            sentence_buffer.find(p)
                                            for p in [". ", "!", "?"]
                                        ]
                                        # Filter out -1's which indicate no occurrence of the punctuation
                                        punctuation_indices = [
                                            p for p in punctuation_indices if p != -1
                                        ]
                                        if punctuation_indices:
                                            earliest_punctuation_index = min(
                                                punctuation_indices
                                            )
                                            # Check if there are more than two words before the punctuation
                                            if (
                                                len(
                                                    sentence_buffer[
                                                        :earliest_punctuation_index
                                                    ]
                                                    .strip()
                                                    .split(" ")
                                                )
                                                > 2
                                            ):
                                                if stream_output:
                                                    yield sentence_buffer[
                                                        : earliest_punctuation_index + 1
                                                    ], False
                                                sentence_buffer = sentence_buffer[
                                                    earliest_punctuation_index + 1 :
                                                ].lstrip()
                                        if (
                                            (
                                                "finish_reason" in choice
                                                and choice["finish_reason"] == "stop"
                                            )
                                            or "?" in completion_text
                                            or "?" in sentence_buffer
                                        ):
                                            if stream_output:
                                                yield sentence_buffer, True
                                            sentence_buffer = ""
                                            return
                        except json.JSONDecodeError:
                            logger.error("Failed to decode JSON response.")
                            continue
                    else:
                        continue

                # If there's any remaining text in the buffer, yield it
                if sentence_buffer and len(sentence_buffer.strip()) > 0:
                    if stream_output:
                        yield sentence_buffer, False

                # Final yield to indicate the end of the stream
                # yield "", False
                # log what we sent out
                # self.logger.info(f"Sent out: {last_message}")
            else:
                if retries_remaining > 0:
                    logger.info("Qwen failed, retrying")
                    async for chunk in get_qwen_response(
                        prompt_buffer=prompt_buffer,
                        logger=logger,
                        stream_output=stream_output,
                        retries_remaining=retries_remaining - 1,
                    ):
                        yield chunk
                    return
                logger.error(f"Error while streaming from OpenAI: {str(response)}")
                return

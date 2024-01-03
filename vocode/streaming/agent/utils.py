from copy import deepcopy
import re
from typing import (
    Dict,
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    List,
    Literal,
    Optional,
    TypeVar,
    Union,
)
import logging
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta

# from openai.openai_object import OpenAIObject
from vocode.streaming.models.actions import FunctionCall, FunctionFragment
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import (
    ActionFinish,
    ActionStart,
    EventLog,
    Message,
    Transcript,
)

SENTENCE_ENDINGS = [".", "!", "?", "\n"]


async def collate_response_async(
    gen: AsyncIterable[Union[str, FunctionFragment]],
    sentence_endings: List[str] = SENTENCE_ENDINGS,
    get_functions: Literal[True, False] = False,
    logger: Optional[logging.Logger] = None
) -> AsyncGenerator[Union[str, FunctionCall], None]:
    sentence_endings_pattern = "|".join(map(re.escape, sentence_endings))
    list_item_ending_pattern = r"\n"
    buffer = ""
    function_name_buffer = ""
    function_args_buffer = ""
    prev_ends_with_money = False
    possible_sentence_ending = False

    async for token in gen:
        if not token:
            continue
        if isinstance(token, str):
            if prev_ends_with_money and token.startswith(" "):
                yield buffer.strip()
                buffer = ""

            if possible_sentence_ending and token.startswith(" "):
                to_return = buffer.strip()
                if to_return:
                    yield to_return
                buffer = ""
                
            buffer += token
            possible_list_item = bool(re.match(r"^\d+[ .]", buffer))
            possible_sentence_ending = bool(re.match(sentence_endings_pattern, token))
            ends_with_money = bool(re.findall(r"\$\d+.$", buffer))
            if possible_list_item and re.findall(list_item_ending_pattern, token):
            # if re.findall(
            #     list_item_ending_pattern
            #     if possible_list_item
            #     else sentence_endings_pattern,
            #     token,
            # ):
                if not ends_with_money:
                    to_return = buffer.strip()
                    if to_return:
                        yield to_return
                    buffer = ""
            prev_ends_with_money = ends_with_money
        elif isinstance(token, FunctionFragment):
            logger.debug(f"function token: {token}")
            if token.name:
                function_name_buffer += token.name
            if token.arguments:
                function_args_buffer += token.arguments
    to_return = buffer.strip()
    if to_return:
        yield to_return
    if function_name_buffer and get_functions:
        yield FunctionCall(name=function_name_buffer, arguments=function_args_buffer)


async def openai_get_tokens(gen, logger: Optional[logging.Logger] = None) -> AsyncGenerator[Union[str, FunctionFragment], None]:
    async for event in gen:
        # choices = event.get("choices", [])
        choices: List[Choice] = event.choices
        if len(choices) == 0:
            continue
        choice: Choice= choices[0]
        if choice.finish_reason:
            break
        delta: ChoiceDelta= choice.delta
        # if "text" in delta and delta["text"] is not None:
        #     token = delta["text"]
        #     yield token
        if delta.content is not None:
            token = delta.content
            yield token
        # if "content" in delta and delta["content"] is not None:
        #     token = delta["content"]
        #     yield token
        # elif "function_call" in delta and delta["function_call"] is not None:
        elif delta.function_call is not None:
            logger.debug(f"Delta function call: {delta.function_call}")
            yield FunctionFragment(
                name=delta.function_call.name,
                arguments=delta.function_call.arguments,
            )


def find_last_punctuation(buffer: str) -> Optional[int]:
    indices = [buffer.rfind(ending) for ending in SENTENCE_ENDINGS]
    if not indices:
        return None
    return max(indices)


def get_sentence_from_buffer(buffer: str):
    last_punctuation = find_last_punctuation(buffer)
    if last_punctuation:
        return buffer[: last_punctuation + 1], buffer[last_punctuation + 1 :]
    else:
        return None, None


def format_openai_chat_messages_from_transcript(
    transcript: Transcript, 
    prompt_preamble: Optional[str] = None,
    prompt_epilogue: Optional[str] = None
) -> List[dict]:
    chat_messages: List[Dict[str, Optional[Any]]] = (
        [{"role": "system", "content": prompt_preamble}] if prompt_preamble else []
    )

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
                event_log.text for event_log in bot_messages_buffer
            )
            new_event_logs.append(merged_bot_message)
        else:
            new_event_logs.append(current_log)
            idx += 1

    for event_log in new_event_logs:
        if isinstance(event_log, Message):
            chat_messages.append(
                {
                    "role": "assistant" if event_log.sender == Sender.BOT else "user",
                    "content": event_log.text,
                }
            )
        elif isinstance(event_log, ActionStart):
            chat_messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": event_log.action_type,
                        "arguments": event_log.action_input.params.json(),
                    },
                }
            )
        elif isinstance(event_log, ActionFinish):
            chat_messages.append(
                {
                    "role": "function",
                    "name": event_log.action_type,
                    "content": event_log.action_output.response.json(),
                }
            )
    if prompt_epilogue:
        chat_messages.append(
            {
                "role": "system", 
                "content": prompt_epilogue,
            }
        )

    return chat_messages


def vector_db_result_to_openai_chat_message(vector_db_result):
    return {"role": "user", "content": vector_db_result}

def replace_map_symbols(message, symbol_map):
    """
    Replace symbols in the message based on the provided symbol_map.

    Parameters:
    - message (str): The input message containing symbols to be replaced.
    - symbol_map (dict): A dictionary mapping symbol keys to their corresponding values.

    Returns:
    - str: The message with symbols replaced based on the provided symbol_map.
    """
    pattern = re.compile("|".join(re.escape(key) for key in symbol_map.keys()))
    return pattern.sub(lambda match: symbol_map[match.group(0)], message)

def replace_username_with_spelling_pattern(text) -> str:
    """
    Replace the username part of email addresses in the given text with a formatted pattern for the synthesized audio.

    Args:
        text (str): The input text containing email addresses.

    Returns:
        str: The text with replaced username parts according to the specified pattern.

    Example:
        >>> paragraph = "Contact me at john@example.com or support@company.com."
        >>> result = replace_username_with_pattern(paragraph)
        >>> print(result)
        "Contact me at j - o - h - n @example.com or s - u - p - p - o - r - t @company.com."

    The function uses a regular expression to identify email addresses in the input text. If email addresses are found,
    it replaces the characters in the username part with a formatted pattern using the provided `format_char` function.

    The `format_char` function is applied to each character in the username part to determine its formatted representation.
    By default, it converts characters to lowercase, but you can customize this function based on specific formatting preferences.

    If no email addresses are found in the input text, the function returns the original text without any replacements.
    """
    
    def format_char(char):
        return char.lower()
    
    def replace_chars(match):
        username = match.group(1)
        formatted_username = ' - '.join(format_char(char) for char in username)
        return f'{formatted_username} @{match.group(2)}'
    
    email_pattern = r'\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'

    if re.search(email_pattern, text):
        formatted_text = re.sub(email_pattern, replace_chars, text)
        return formatted_text
    else:
        return text
    
def get_time_from_text(text: str) -> str:
    """
    Extracts time strings in the format "HH:MM AM/PM" from the given text.

    Parameters:
    - text (str): The input text from which to extract time strings.

    Returns:
    - List[str]: A list of time strings found in the input text.
    """
    pattern = re.compile(r'\b(?:1[0-2]|0?[1-9]):[0-5][0-9] (?:AM|PM)\b')
    return pattern.findall(text)

def format_time(time_string: str) -> str:
    """
    Formats a time string in the "HH:MM AM/PM" format to a more readable format.

    Parameters:
    - time_string (str): The time string to be formatted.

    Returns:
    - str: The formatted time string in the "HH MM AM/PM" format.
    """
    time, am_pm = time_string.split(" ")
    hours, minutes = time.split(":")
    minutes_part = "" if minutes == "00" else f" {minutes}"
    modified_time = f"{hours}{minutes_part} {am_pm}"
    return modified_time

def format_time_in_text(text: str) -> str:
    """
    Replaces time strings in the format "HH:MM AM/PM" with a more readable format "HH MM AM/PM" in the given text.
    If no time strings are found in the input text, the function returns the original text without any replacements.

    Parameters:
    - text (str): The input text in which to replace time strings.

    Returns:
    - str: The modified text with formatted time strings.
    """
    matches = get_time_from_text(text)
    if matches:
        for match in matches:
            reformatted_time = format_time(match)
            text = text.replace(match, reformatted_time)
    return text
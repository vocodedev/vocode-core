from typing import List


def split_text(string_to_split: str, max_text_length: int) -> List[str]:
    # Base case: if the string_to_split is less than or equal to max_text_length characters, return it as a single element array
    if len(string_to_split) <= max_text_length:
        return [string_to_split.strip()]

    # Recursive case: find the index of the last sentence ender in the first max_text_length characters of the string_to_split
    sentence_enders = [".", "!", "?"]
    index = -1
    for ender in sentence_enders:
        i = string_to_split[:max_text_length].rfind(ender)
        if i > index:
            index = i

    # If there is a sentence ender, split the string_to_split at that index plus one and strip any spaces from both parts
    if index != -1:
        first_part = string_to_split[: index + 1].strip()
        second_part = string_to_split[index + 1 :].strip()

    # If there is no sentence ender, find the index of the last comma in the first max_text_length characters of the string_to_split
    else:
        index = string_to_split[:max_text_length].rfind(",")
        # If there is a comma, split the string_to_split at that index plus one and strip any spaces from both parts
        if index != -1:
            first_part = string_to_split[: index + 1].strip()
            second_part = string_to_split[index + 1 :].strip()
        # If there is no comma, find the index of the last space in the first max_text_length characters of the string_to_split
        else:
            index = string_to_split[:max_text_length].rfind(" ")
            # If there is a space, split the string_to_split at that index and strip any spaces from both parts
            if index != -1:
                first_part = string_to_split[:index].strip()
                second_part = string_to_split[index:].strip()

            # If there is no space, split the string_to_split at max_text_length characters and strip any spaces from both parts
            else:
                first_part = string_to_split[:max_text_length].strip()
                second_part = string_to_split[max_text_length:].strip()

    # Append the first part to the result array
    result = [first_part]

    # Call the function recursively on the remaining part of the string_to_split and extend the result array with it, unless it is empty
    if second_part != "":
        result.extend(split_text(string_to_split=second_part, max_text_length=max_text_length))

    # Return the result array
    return result

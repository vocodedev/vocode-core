from typing import Dict

unset = object()


def of(d: Dict[str, object]) -> Dict[str, object]:
    """
    Remove unset values from a dict.

    :param d: A dict to strip.
    :return A dict with unset values removed.
    """
    return {k: v for k, v in d.items() if v != unset}

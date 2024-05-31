from typing import Any, Dict, Set


def exclude_keys_recursive(d: Dict[str, Any], excluded_keys: Set[str]):
    if isinstance(d, dict):
        return {
            k: exclude_keys_recursive(v, excluded_keys)
            for k, v in d.items()
            if k not in excluded_keys
        }
    elif isinstance(d, list):
        return [exclude_keys_recursive(v, excluded_keys) for v in d]
    else:
        return d

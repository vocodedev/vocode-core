import re
from typing import List, Optional

from vocode.streaming.models.actions import ActionConfig, PhraseBasedActionTrigger


def matches_phrase_trigger(
    message: str,
    action_configs: List[ActionConfig],
) -> Optional[str]:
    cleaned = re.sub(r"[^\w\s]", "", message.lower())
    for action_config in action_configs:
        if not isinstance(action_config.action_trigger, PhraseBasedActionTrigger):
            continue

        for phrase_trigger in action_config.action_trigger.config.phrase_triggers:
            lowered = phrase_trigger.phrase.lower()
            for condition in phrase_trigger.conditions:
                if condition == "phrase_condition_type_contains" and lowered in cleaned:
                    return action_config.type
    return None

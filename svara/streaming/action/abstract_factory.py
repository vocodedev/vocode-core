from abc import ABC, abstractmethod

from svara.streaming.action.base_action import BaseAction
from svara.streaming.models.actions import ActionConfig


class AbstractActionFactory(ABC):
    @abstractmethod
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        pass

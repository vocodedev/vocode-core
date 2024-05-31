from abc import ABC, abstractmethod

from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import ActionConfig


class AbstractActionFactory(ABC):
    @abstractmethod
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        pass

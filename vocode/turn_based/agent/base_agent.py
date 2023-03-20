from typing import Optional


class BaseAgent:
    def __init__(self, initial_message: Optional[str] = None):
        self.initial_message = initial_message

    def respond(self, human_input: str):
        raise NotImplementedError

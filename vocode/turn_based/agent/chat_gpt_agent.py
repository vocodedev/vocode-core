from typing import Any, List, Optional

import openai

from vocode import getenv
from vocode.turn_based.agent.base_agent import BaseAgent


class ChatGPTAgent(BaseAgent):
    def __init__(
        self,
        system_prompt: str,
        api_key: Optional[str] = None,
        initial_message: Optional[str] = None,
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 100,
    ):
        super().__init__(initial_message=initial_message)
        api_key = getenv("OPENAI_API_KEY", api_key)
        if not api_key:
            raise ValueError("OpenAI API key not provided")
        self.client = openai.OpenAI(api_key=api_key)
        self.prompt = system_prompt
        self.model_name = model_name
        self.messages: List[Any] = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "assistant",
                "content": initial_message,
            },
        ]

    def respond(self, human_input: str):
        self.messages.append(
            {
                "role": "user",
                "content": human_input,
            }
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
        )
        content = response.choices[0].message.content
        self.messages.append(
            {
                "role": "system",
                "content": content,
            }
        )
        return content

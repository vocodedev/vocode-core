from vocode import getenv
from vocode.turn_based.agent.base_agent import BaseAgent

import google.generativeai as genai
import os
from typing import Any, List, Optional
class GeminiAgent(BaseAgent):
    def __init__(
        self,
        system_prompt: str = "You are a cat. Your name is Neko.",
        api_key: Optional[str] = None,
        initial_message: Optional[str] = "Good morning! How are you?",
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.7,
        max_tokens: int = 100,
    ):
        super().__init__(initial_message=initial_message)
        api_key = getenv("GEMINI_API_KEY", api_key)
        if not api_key:
            raise ValueError("Gemini API key not provided")
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model_name=model_name)
        self.system_prompt = system_prompt
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
        
        response = self.client.generate_content(prompt=human_input, system_instruction=self.system_prompt)
        
        content = response.text
        self.messages.append(
            {
                "role": "assistant",
                "content": content,
            }
        )
        return content
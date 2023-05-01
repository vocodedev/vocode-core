import logging
import sys
import threading
from typing import Optional
from vocode.turn_based.agent.base_agent import BaseAgent


class GPT4AllAgent(BaseAgent):
    SENTENCE_ENDINGS = [".", "!", "?"]

    DEFAULT_PROMPT_TEMPLATE = "{history}\nHuman: {human_input}\nAI:"

    def __init__(
        self,
        model_path: str,
        system_prompt: str,
        initial_message: Optional[str] = None,
        logger: logging.Logger = None,
    ):
        from pygpt4all.models.gpt4all_j import GPT4All_J
        
        super().__init__(initial_message)
        self.prompt_template = f"{system_prompt}\n\n{self.DEFAULT_PROMPT_TEMPLATE}"
        self.logger = logger or logging.getLogger(__name__)
        self.memory = [f"AI: {initial_message}"] if initial_message else []
        self.llm = GPT4All_J(model_path, log_level=logging.NOTSET)

    def create_prompt(self, human_input):
        history = "\n".join(self.memory[-5:])
        return self.prompt_template.format(history=history, human_input=human_input)

    def get_memory_entry(self, human_input, response):
        return f"Human: {human_input}\nAI: {response}"

    def respond(
        self,
        human_input,
    ) -> str:
        self.logger.debug("LLM responding to human input")
        prompt = self.create_prompt(human_input)
        response_buffer = ""
        def new_text_callback(text):
            nonlocal response_buffer
            response_buffer += text
            if len(response_buffer) > len(prompt) and response_buffer.endswith("Human:"):
                response_buffer = response_buffer[:-len("Human:")]
                sys.exit()
        thread = threading.Thread(target=self.llm.generate, args=(prompt,), kwargs={"new_text_callback": new_text_callback})
        thread.start()
        thread.join(timeout=10)
        response = response_buffer[(len(prompt) + 1):]
        self.memory.append(self.get_memory_entry(human_input, response))
        self.logger.debug(f"LLM response: {response}")
        return response


if __name__ == "__main__":
    chat_responder = GPT4AllAgent(
        system_prompt="The AI is having a pleasant conversation about life.",
        model_path='~/Downloads/ggml-gpt4all-j-v1.3-groovy.bin',
    )
    while True:
        response = chat_responder.respond(input("Human: "))
        print(f"AI: {response}")

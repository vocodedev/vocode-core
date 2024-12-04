import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Optional

from loguru import logger

from vocode.turn_based.agent.base_agent import BaseAgent

raise DeprecationWarning("This Agent is deprecated and will be removed in the future.")


class StopThreadException(Exception):
    pass


class GPT4AllAgent(BaseAgent):
    SENTENCE_ENDINGS = [".", "!", "?"]

    DEFAULT_PROMPT_TEMPLATE = "{history}\nHuman: {human_input}\nAI:"

    def __init__(
        self,
        model_path: str,
        system_prompt: str,
        initial_message: Optional[str] = None,
    ):
        from pygpt4all.models.gpt4all_j import GPT4All_J

        super().__init__(initial_message)
        self.prompt_template = f"{system_prompt}\n\n{self.DEFAULT_PROMPT_TEMPLATE}"
        self.memory = [f"AI: {initial_message}"] if initial_message else []
        self.llm = GPT4All_J(model_path)
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

    def create_prompt(self, human_input):
        history = "\n".join(self.memory[-5:])
        return self.prompt_template.format(history=history, human_input=human_input)

    def get_memory_entry(self, human_input, response):
        return f"Human: {human_input}\nAI: {response}"

    def respond(
        self,
        human_input,
    ) -> str:
        logger.debug("LLM responding to human input")
        prompt = self.create_prompt(human_input)
        response_buffer = ""

        def new_text_callback(text):
            nonlocal response_buffer
            response_buffer += text
            if len(response_buffer) > len(prompt) and response_buffer.endswith("Human:"):
                response_buffer = response_buffer[: -len("Human:")]
                sys.exit()

        future = self.thread_pool_executor.submit(
            self.llm.generate,
            prompt,
            new_text_callback=new_text_callback,
        )
        wait([future], timeout=10)
        response = response_buffer[(len(prompt) + 1) :]
        self.memory.append(self.get_memory_entry(human_input, response))
        logger.debug(f"LLM response: {response}")
        return response

    async def respond_async(self, human_input) -> str:
        prompt = self.create_prompt(human_input)
        response_buffer = ""

        def new_text_callback(text):
            nonlocal response_buffer
            response_buffer += text
            if len(response_buffer) > len(prompt) and response_buffer.endswith("Human:"):
                response_buffer = response_buffer[: -len("Human:")]
                raise StopThreadException("Stopping the thread")

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                self.thread_pool_executor,
                lambda: self.llm.generate(prompt, new_text_callback=new_text_callback),
            )
        except StopThreadException:
            pass
        response = response_buffer[(len(prompt) + 1) :]
        self.memory.append(self.get_memory_entry(human_input, response))
        return response


if __name__ == "__main__":

    async def main():
        chat_responder = GPT4AllAgent(
            system_prompt="The AI is having a pleasant conversation about life.",
            model_path="/Users/ajayraj/Downloads/ggml-gpt4all-j-v1.3-groovy.bin",
        )
        while True:
            response = await chat_responder.respond_async(input("Human: "))
            print(f"AI: {response}")

    asyncio.run(main())

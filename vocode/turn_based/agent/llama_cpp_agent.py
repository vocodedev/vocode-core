import logging
from typing import Optional
from vocode.turn_based.agent.base_agent import BaseAgent
from pyllamacpp.model import Model


class LlamaCPPAgent(BaseAgent):
    SENTENCE_ENDINGS = [".", "!", "?"]

    DEFAULT_PROMPT_TEMPLATE = "{history}\nHuman: {human_input}\nAI:"

    def __init__(
        self,
        model_path: str,
        system_prompt: str,
        initial_message: Optional[str] = None,
        logger: logging.Logger = None,
    ):
        super().__init__(initial_message)
        self.prompt_template = f"{system_prompt}\n\n{self.DEFAULT_PROMPT_TEMPLATE}"
        self.logger = logger or logging.getLogger(__name__)
        self.memory = [f"AI: {initial_message}"] if initial_message else []
        self.llm = Model(ggml_model=model_path, log_level=logging.NOTSET)

    def create_prompt(self, human_input):
        history = "\n".join(self.memory[-5:])
        return self.prompt_template.format(history=history, human_input=human_input)

    def get_memory_entry(self, human_input, response):
        return f"Human: {human_input}\nAI: {response}"

    def respond(
        self,
        human_input,
    ) -> tuple[str, bool]:
        self.logger.debug("LLM responding to human input")
        prompt = self.create_prompt(human_input)
        response = self.llm.generate(prompt, n_predict=55)[(len(prompt) + 1):]
        if "Human:" in response:
            response = response.split("Human:")[0]
        else:
            for sentence_ending in self.SENTENCE_ENDINGS:
                if sentence_ending in response:
                    response = response.split(sentence_ending)[0]
                    break
        self.memory.append(self.get_memory_entry(human_input, response))
        self.logger.debug(f"LLM response: {response}")
        return response, False


if __name__ == "__main__":
    chat_responder = LlamaCPPAgent(
        system_prompt="The AI is having a pleasant conversation about life.",
        model_path="/Users/ajayraj/src/gpt4all/gpt4all-lora-quantized-converted.bin",
    )
    while True:
        response = chat_responder.respond(input("Human: "))[0]
        print(f"AI: {response}")

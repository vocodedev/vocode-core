import threading
from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult
import re

from vocode.turn_based.output_device.speaker_output import SpeakerOutput
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer


class VocodeCallbackHandler(AsyncCallbackHandler):
    """Custom CallbackHandler."""

    def __init__(self, synthesizer: BaseSynthesizer) -> None:
        super().__init__()
        self.output_device = SpeakerOutput.from_default_device()
        self.synthesizer = synthesizer

    def _speak_in_thread(self, text: str) -> None:
        thread = threading.Thread(target=lambda: self.output_device.send_audio(self.synthesizer.synthesize(text)))
        thread.start()

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        pass

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        pass

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        pass

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        pass

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        pass

    def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        pass

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        pass

    def on_agent_action(
        self, action: AgentAction, color: Optional[str] = None, **kwargs: Any
    ) -> Any:
        try:
            thought = action.log.split("Action:")[0].replace("Thought: ", "")
            self._speak_in_thread(thought)
        except:
            print("BEGIN LOG\n{}\nEND LOG".format(action.log))

    def on_tool_end(
        self,
        output: str,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        pass

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        pass

    def on_text(
        self,
        text: str,
        color: Optional[str] = None,
        end: str = "",
        **kwargs: Optional[str],
    ) -> None:
        pass

    def on_agent_finish(
        self, finish: AgentFinish, color: Optional[str] = None, **kwargs: Any
    ) -> None:
        try:
            final_answer = finish.log.split("Final Answer:")[1].strip()
            self._speak_in_thread(final_answer)
        except:
            pass
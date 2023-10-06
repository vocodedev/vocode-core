import logging
from typing import Optional

from vocode.utils.context_tracker.context_tracker import BaseContextTrackerConfig, BaseContextTracker
from vocode.utils.context_tracker.open_ai_context_tracker import OpenAIContextTrackerConfig, OpenAIContextTracker


class ContextTrackerFactory:
    @staticmethod
    def create_context_tracker(
            transcriber_config: BaseContextTrackerConfig,
            logger: Optional[logging.Logger] = None,
    ) -> BaseContextTracker:
        logger.debug(f"Creating context tracker of type {transcriber_config.type}")
        if isinstance(transcriber_config, OpenAIContextTrackerConfig):
            return OpenAIContextTracker(transcriber_config, logger=logger)

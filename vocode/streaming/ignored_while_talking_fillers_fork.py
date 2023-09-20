"""
These are fillers a non-talking listener may say when talking to a person on a phone to indicate they are listening and following the conversation, but not wanting to interrupt:
"""
import logging
from logging import Logger

import numpy as np

from vocode.streaming.json_cache_proxy import JsonCacheProxy
from vocode.streaming.openai_embedding import openai_embed

IGNORED_WHILE_TALKING_FILLERS = [
    "uh",
    "um",
    "mmhm",
    "Mhmm",
    "mm-mm",
    "uh-uh",
    "uh-huh",
    "nuh-uh",
    "Hey",
    "Hm.",
    "Huh.",
    "Mm.",
    "Oh.",
    "Aha.",
    "Uh-huh.",
    "Mm-hmm.",
    "Uh-uh.",
    "Mhmm.",
    "Oof",
    "Whoa",
    "Woah",
    "Wow",
    "Eek",
    "Ahem",
    "Uh-hum",
    "Eh-heh",
    "Erm",
    "Er",
    "Eh",
    "Ah",
    "hehe",
    "haha",
    "fuu",

    # en confirmatory
    "Yeah",
    "Okey",
    "Okay",
    "Interesting",
    "Right",
    "Really?",
    "Thanks",
    "Yes",
    "Yup",
    "Yeh",
    "Sure",
    "Agree",
    "That's right",
    "I see",
    "Understood",
    "Got it",
    "Go ahead",
    "I'm listening",
    "Perfect",
    "Excellent",
    "Definitely",
    "Exactly",
    "ok",

    # cz confirmatory
    "Jo",
    "Dobře",
    "dobrá",
    "Rozumím",
    "Zajímavé",
    "Správně",
    "Opravdu?",
    "Děkuji",
    "Ano",
    "Jo",
    "Tak",
    "Určitě",
    "Souhlasím",
    "To je pravda",
    "Chápu",
    "Rozumím",
    "Poslouchám",
    "Perfektní",
    "Výborné",
    "Rozhodně",
    "Přesně",
    "Super",
    "Supr",
    "oukej",


    # sk confirmatory
    "Áno",
    "Dobre",
    "V poriadku",
    "Zaujímavé",
    "Správne",
    "Naozaj?",
    "Ďakujem",
    "Áno",
    "Iste",
    "Súhlasím",
    "To je pravda",
    "Chápem",
    "Rozumiem",
    "Pokračuj",
    "Počúvam",
    "Perfektne",
    "Výborne",
    "Určite",
    "Presne tak",
    "jaj",

]


class OpenAIEmbeddingOverTalkingFillerDetector:

    def __init__(self, cache_storage_path: str = JsonCacheProxy.DEFAULT_CACHE_STORAGE_PATH, thresh_hold=0.91, logger: Logger = None):
        self.cache_openai_embed = JsonCacheProxy('openai-embeddings-fillers', func=openai_embed, postprocess_func=np.array, cache_storage_path=cache_storage_path)
        if logger is None:
            logger = logging.getLogger(__name__)

        self.logger = logger
        self.thresh_hold = thresh_hold

    def normalize(self, text: str):
        return text.strip(" .,")

    def detect_filler(self, text: str):
        if len(text) < 20:
            embedding = openai_embed(self.normalize(text))
            for filler in IGNORED_WHILE_TALKING_FILLERS:
                similarity = np.dot(embedding, self.cache_openai_embed(self.normalize(filler)))
                if similarity > self.thresh_hold:
                    self.logger.info(
                        f"Ignoring filler {text} similar to filler {filler} with similarity {similarity}.")
                    return True

        return False

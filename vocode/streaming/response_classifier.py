import io
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from vocode.streaming.json_cache_proxy import JsonCacheProxy
from vocode.streaming.openai_embedding import openai_embed



POSITIVE_RESPONSES = [
    "Ano",
    "Jo",
    "Určitě",
    "Stoprocentně",
    "Jasně",
    "Tak",
    "Určitě",
    "Souhlasím",
    "To je pravda",
    "Přesně",
    "oukej",
    "Absolutně",
    "Nepochybně",
    "Přijímám",
    "Jistě",
    "Plně souhlasím",
    "Souhlas",
    "Ano, prosím",
    "Beru to",
    "Jsem pro",
    "Zní to dobře"
]

NEGATIVE_RESPONSES = [
    "Ne",
    "Nikoliv",
    "To nejde",
    "Nemám zájem",
    "Nechci",
    "Nechci nic",
    "Nemohu",
    "Nemůžu souhlasit",
    "Odmítám",
    "Nepotřebuji",
    "Nepřijímám",
    "Nelíbí se mi to",
    "Nesouhlasím",
    "Ne, děkuji",
    "Odpouštím si",
    "Nelze",
    "Vylučuji to",
    "To nechci",
    "Rozhodně ne",
    "Absolutně ne",
    "Nepokusím se",
    "Nejsem pro",
    "Nechci to",
    "Odmítám to",
    "Neberu to",
    "Nedokážu to",
    "To odmítám",
    "Ne, prosím",
    "Asi ne",
    "Zatím ne",
    "Možná později",
]

CONFUSED_RESPONSES = [
    "Nevím",
    "Nechápu",
    "Nerozumím",
    "Nerozumím otázce",
    "To mi nedává smysl",
    "Ztratil jsem se",
    "Nevím, co odpovědět",
    "Nevím, co si o tom myslet",
    "Jsem zmatený",
    "Nejsem si jistý",
    "To je pro mě nové",
    "Potřebuji více informací",
    "Nerozumím, co přesně mi chceš říct",
    "Mohli byste to formulovat jinak?",
    "Nejsem si jistý, zda tomu rozumím",
    "To je pro mě složité",
    "Nejsem si jistý, co mi chceš říct",
]

QUESTIONS = [
    "Kdo?",
    "Co?",
    "Kde?",
    "Kdy?",
    "Jak?",
    "Kam?"
    "Kdo?",
    "Proč?",
    "Komu?",
    "Čím?",
    "Kolik?",
    "Odkud?",
    "Který?",
    "Jaké?",
    "Jaký?",
    "S kým?",
    "Na co?",
    "Nad čím?",
    "Podle čeho?",
    "Bez čeho?",
    "S čím?",
    "Do kdy?",
    "Za co?",
    "V čem?",
    "Přes co?",
    "Pro koho?"
    "Jak to myslíte?",
    "Zeptám se",
    "Proč?",
    "Za jak dlouho?",
    "Kolik stojí?",
    "Kdo to zorganizoval?",
    "Co se stalo?",
    "Který den?",
    "Proč to děláš?",
    "Jak to funguje?",
    "Který to je?",
    "Je to bezpečné?",
    "Kam jsi šel?",
    "Co děláš?",
    "Jaké to je?",
    "Kdy přijdeš?",
    "Jak to víš?",
    "Kdo je tvůj oblíbený?",
    "Proč jsme tady?",
    "Co to znamená?",
    "Jak se to jmenuje?",
    "Co jsi řekl?",
    "Co to znamená?",
    "Mohl bys to vysvětlit?",
    "Mohu požádat o více informací?",
    "Můžeš to vysvětlit podrobněji?",
]

NEUTRAL_RESPONSES = [
    "Já jsem z koberovic."
    "Auto bude pro moji manzelku.",
    "Přijedu v pět hodin.",
    "Bydlím v Praze.",
    "Teď auto nemám.",
    "Tady Petr",
]

# FIXME init this in a better way


@dataclass
class ClassifiedResponse:
    is_positive: bool
    is_negative: bool
    is_question: bool
    max_similarity: float
    max_similarity_response: str


class   OpenaiEmbeddingsResponseClassifier:

    def __init__(self, cache_storage_path=JsonCacheProxy.DEFAULT_CACHE_STORAGE_PATH, logger=None):
        if logger is None:
            logger = logging.getLogger(__name__)

        self.cache_openai_embeds_response = JsonCacheProxy('openai-embeddings-responses',
                                                           func=openai_embed,
                                                           postprocess_func=np.array,
                                                           cache_storage_path=cache_storage_path)

    def classify_response(self, user_message: str):
        """
        Classify agent message and user message to positive or negative response, contextual or non-contextual question.
        """
        # TODO use agent_message

        input_embedding = openai_embed(user_message)
        # compare with the reference embeddings:
        all_reference_responses = POSITIVE_RESPONSES + NEUTRAL_RESPONSES + NEGATIVE_RESPONSES + QUESTIONS
        # similarities = np.zeros(len(all_reference_responses), dtype=np.float32)
        max_similarity = -1
        max_similarity_response = None
        # question_similarity_boost = 1.01
        question_similarity_boost = 1.0
        # TODO replace for loop with vectorized multiply
        for comparison_text in all_reference_responses:
            comparison_embedding = self.cache_openai_embeds_response(comparison_text)
            similarity = np.dot(input_embedding, comparison_embedding)
            if comparison_text in QUESTIONS:
                similarity *= question_similarity_boost

            if similarity > max_similarity:
                max_similarity = similarity
                max_similarity_response = comparison_text

        is_positive = max_similarity_response in (POSITIVE_RESPONSES + NEUTRAL_RESPONSES)
        is_negative = max_similarity_response in NEGATIVE_RESPONSES
        is_question = max_similarity_response in QUESTIONS

        response = ClassifiedResponse(is_positive, is_negative, is_question, max_similarity, max_similarity_response)
        # print(f'For {user_message}\nthe response is question {is_question} and the most similar to {max_similarity_response} with similarity {max_similarity}')
        logging.debug(f'The message "{user_message}" was classified as "{response}"')
        return response


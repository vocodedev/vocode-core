from typing import List

import requests
from langchain.agents import tool

WORDNIK_URL_WITH_KEY = "https://api.wordnik.com/v4/words.json/wordOfTheDay?api_key=d52b63b6880f17811310d0fbd3b0d3a8ef163a248f58dc831"


@tool("word_of_the_day")
def word_of_the_day(placeholder: str) -> List[dict]:
    """Gets today's word of the day"""
    response = requests.get(WORDNIK_URL_WITH_KEY).json()
    return response

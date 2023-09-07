import openai

import vocode
from vocode.streaming.models.agent import AZURE_OPENAI_DEFAULT_API_TYPE


def openai_embed(text: str) -> list:
    open_ai_dict = {}
    open_ai_dict["api_type"] = AZURE_OPENAI_DEFAULT_API_TYPE
    open_ai_dict["api_base"] = vocode.getenv('AZURE_OPENAI_API_BASE')
    open_ai_dict["api_version"] = "2023-03-15-preview"
    open_ai_dict["api_key"] = vocode.getenv('AZURE_OPENAI_API_KEY')

    return openai.Embedding.create(engine='text-embedding-ada-002', input=text, **open_ai_dict)['data'][0]['embedding']

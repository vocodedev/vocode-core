from typing import List, Optional
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from pydantic import BaseModel

from vocode import getenv

TEMPLATE = """
Read the following conversation classify the final emotion of the Bot as one of [{emotions}].
Output the degree of emotion as a value between 0 and 1 in the format EMOTION,DEGREE: ex. {example_emotion},0.5
            
<start>
{{transcript}}
<end>
"""


class BotSentiment(BaseModel):
    emotion: Optional[str] = None
    degree: float = 0.0


class BotSentimentAnalyser:
    def __init__(
        self,
        emotions: List[str],
        model_name: str = "text-davinci-003",
        openai_api_key: Optional[str] = None,
    ):
        self.model_name = model_name
        openai_api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.llm = OpenAI(model_name=self.model_name, openai_api_key=openai_api_key)  # type: ignore
        assert len(emotions) > 0
        self.emotions = [e.lower() for e in emotions]
        self.prompt = PromptTemplate(
            input_variables=["transcript"],
            template=TEMPLATE.format(
                emotions=",".join(self.emotions), example_emotion=self.emotions[0]
            ),
        )

    async def analyse(self, transcript: str) -> BotSentiment:
        prompt = self.prompt.format(transcript=transcript)
        response = (await self.llm.agenerate([prompt])).generations[0][0].text.strip()
        tokens = response.split(",")
        if len(tokens) != 2:
            return BotSentiment(emotion=None, degree=0.0)
        emotion, degree = tokens
        emotion = emotion.strip().lower()
        if emotion.lower() not in self.emotions:
            return BotSentiment(emotion=None, degree=0.0)
        try:
            parsed_degree = float(degree.strip())
        except ValueError:
            return BotSentiment(emotion=emotion, degree=0.5)
        return BotSentiment(emotion=emotion, degree=parsed_degree)

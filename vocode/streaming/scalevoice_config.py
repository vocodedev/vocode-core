import os
from logging import Logger

from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

from vocode.streaming.agent.gpt_summary_agent import ChatGPTSummaryAgent
from vocode.streaming.ignored_while_talking_fillers_fork import OpenAIEmbeddingOverTalkingFillerDetector
from vocode.streaming.models.agent import ChatGPTAgentConfig, AzureOpenAIConfig

SUMMARIZER_PROMPT_PREAMBLE = """You are creating summaries for telephone calls transcripts between AI voice bot and customer."""


def get_scalevoice_conversation_config(logger: Logger, summarizer_prompt_preamble: str = SUMMARIZER_PROMPT_PREAMBLE):
    """
    This is a quick hack to pass configuration to the config below.
    The disadvantage is that we have to be able to quickly change this code on changes beyond the environmental variables.
    The reason is to have the simplest and minimized changes to the Vocode's code for now and maximum flexibility

    Variables will change during import time because of loading config files, so they are extracted here at runtime.
    """

    AZURE_OPENAI_API_KEY_SUMMARY = os.environ['AZURE_OPENAI_API_KEY_SUMMARY']
    AZURE_OPENAI_API_BASE_SUMMARY = os.environ['AZURE_OPENAI_API_BASE_SUMMARY']
    PROJECT_ROOT = os.environ['PROJECT_ROOT']
    AZURE_TEXT_ANALYTICS_KEY = os.environ['AZURE_TEXT_ANALYTICS_KEY']
    AZURE_TEXT_ANALYTICS_ENDPOINT = os.environ['AZURE_TEXT_ANALYTICS_ENDPOINT']

    return dict(
        summarizer=ChatGPTSummaryAgent(logger=logger,
                                       # TODO: refactor it. RN there is a problem with standard openai auth because we have
                                       # to use uk endpoint but our 3.5 runs in western europe.
                                       key=AZURE_OPENAI_API_KEY_SUMMARY,
                                       base=AZURE_OPENAI_API_BASE_SUMMARY,
                                       agent_config=ChatGPTAgentConfig(

                                           prompt_preamble=summarizer_prompt_preamble,
                                           azure_params=AzureOpenAIConfig(
                                               api_type="azure",
                                               api_version="2023-03-15-preview",
                                               engine="gpt4"  # always use gpt4
                                           ),
                                       )) if AZURE_OPENAI_API_BASE_SUMMARY is not None else None,
        over_talking_filler_detector=OpenAIEmbeddingOverTalkingFillerDetector(PROJECT_ROOT + '/tmp/', logger=logger),
        text_analysis_client=TextAnalyticsClient(endpoint=AZURE_TEXT_ANALYTICS_ENDPOINT,
                                                 credential=AzureKeyCredential(AZURE_TEXT_ANALYTICS_KEY)),

    )

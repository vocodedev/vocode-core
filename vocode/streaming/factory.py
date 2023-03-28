from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.agent.information_retrieval_agent import InformationRetrievalAgent
from vocode.streaming.agent.llm_agent import LLMAgent
from vocode.streaming.models.agent import AgentConfig, AgentType
from vocode.streaming.models.synthesizer import SynthesizerConfig, SynthesizerType
from vocode.streaming.models.transcriber import TranscriberConfig, TranscriberType
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.streaming.synthesizer.google_synthesizer import GoogleSynthesizer
from vocode.streaming.transcriber.assembly_ai_transcriber import AssemblyAITranscriber
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.transcriber.google_transcriber import GoogleTranscriber


def create_transcriber(transcriber_config: TranscriberConfig) -> BaseTranscriber:
    if transcriber_config.type == TranscriberType.DEEPGRAM:
        return DeepgramTranscriber(transcriber_config)
    elif transcriber_config.type == TranscriberType.GOOGLE:
        return GoogleTranscriber(transcriber_config)
    elif transcriber_config.type == TranscriberType.ASSEMBLY_AI:
        return AssemblyAITranscriber(transcriber_config)
    else:
        raise Exception("Invalid transcriber config")


def create_agent(agent_config: AgentConfig) -> BaseAgent:
    if agent_config.type == AgentType.LLM:
        return LLMAgent(agent_config=agent_config)
    elif agent_config.type == AgentType.CHAT_GPT:
        return ChatGPTAgent(agent_config=agent_config)
    elif agent_config.type == AgentType.ECHO:
        return EchoAgent(agent_config=agent_config)
    elif agent_config.type == AgentType.INFORMATION_RETRIEVAL:
        return InformationRetrievalAgent(
            agent_config=agent_config,
        )
    raise Exception("Invalid agent config", agent_config.type)


def create_synthesizer(synthesizer_config: SynthesizerConfig) -> BaseSynthesizer:
    if synthesizer_config.type == SynthesizerType.GOOGLE:
        return GoogleSynthesizer(synthesizer_config)
    elif synthesizer_config.type == SynthesizerType.AZURE:
        return AzureSynthesizer(synthesizer_config)
    elif synthesizer_config.type == SynthesizerType.ELEVEN_LABS:
        return ElevenLabsSynthesizer(synthesizer_config)
    else:
        raise Exception("Invalid synthesizer config")

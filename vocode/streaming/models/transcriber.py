from enum import Enum
import re
from typing import Collection, List, Optional

from pydantic import validator

from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.models.client_backend import InputAudioConfig
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLING_RATE,
)
from .audio_encoding import AudioEncoding
from .model import TypedModel


class TranscriberType(str, Enum):
    BASE = "transcriber_base"
    DEEPGRAM = "transcriber_deepgram"
    GOOGLE = "transcriber_google"
    ASSEMBLY_AI = "transcriber_assembly_ai"
    WHISPER_CPP = "transcriber_whisper_cpp"
    REV_AI = "transcriber_rev_ai"
    AZURE = "transcriber_azure"


class EndpointingType(str, Enum):
    BASE = "endpointing_base"
    TIME_BASED = "endpointing_time_based"
    PUNCTUATION_BASED = "endpointing_punctuation_based"


class EndpointingConfig(TypedModel, type=EndpointingType.BASE):
    time_cutoff_seconds: float


class TimeEndpointingConfig(EndpointingConfig, type=EndpointingType.TIME_BASED):
    time_cutoff_seconds: float = 0.4


class PunctuationEndpointingConfig(
    EndpointingConfig, type=EndpointingType.PUNCTUATION_BASED
):
    time_cutoff_seconds: float = 0.4


class TranscriberConfig(TypedModel, type=TranscriberType.BASE.value):
    sampling_rate: int
    audio_encoding: AudioEncoding
    chunk_size: int
    language_code: str = "en-US"
    endpointing_config: Optional[EndpointingConfig] = None
    downsampling: Optional[int] = None
    min_interrupt_confidence: Optional[float] = None
    mute_during_speech: bool = False

    @validator("min_interrupt_confidence")
    def min_interrupt_confidence_must_be_between_0_and_1(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError("must be between 0 and 1")
        return v
    
    @validator("language_code")
    def language_code_must_be_supported(cls, v):
        if not cls.supports_language(v):
            raise ValueError(f"language code '{v}' not supported by {cls}")
        return v

    @classmethod
    def supports_language(cls, lang: str, supported_langs: Optional[Collection[str]] = None):
        """
        Returns true if a given lang code is supported by provided collection of supported languages.
        lang: BCP-47 lang code
        """
        supported_langs = supported_langs or ["en"]
        return (lang in supported_langs or 
                re.split(r"[-_]", lang)[0] in {re.split(r"[-_]", x)[0] for x in supported_langs})

    @classmethod
    def from_input_device(
        cls,
        input_device: BaseInputDevice,
        endpointing_config: Optional[EndpointingConfig] = None,
        **kwargs,
    ):
        return cls(
            sampling_rate=input_device.sampling_rate,
            audio_encoding=input_device.audio_encoding,
            chunk_size=input_device.chunk_size,
            endpointing_config=endpointing_config,
            **kwargs,
        )

    @classmethod
    def from_telephone_input_device(
        cls,
        endpointing_config: Optional[EndpointingConfig] = None,
        **kwargs,
    ):
        return cls(
            sampling_rate=DEFAULT_SAMPLING_RATE,
            audio_encoding=DEFAULT_AUDIO_ENCODING,
            chunk_size=DEFAULT_CHUNK_SIZE,
            endpointing_config=endpointing_config,
            **kwargs,
        )

    @classmethod
    def from_input_audio_config(cls, input_audio_config: InputAudioConfig, **kwargs):
        return cls(
            sampling_rate=input_audio_config.sampling_rate,
            audio_encoding=input_audio_config.audio_encoding,
            chunk_size=input_audio_config.chunk_size,
            downsampling=input_audio_config.downsampling,
            **kwargs,
        )


class DeepgramTranscriberConfig(TranscriberConfig, type=TranscriberType.DEEPGRAM.value):
    model: Optional[str] = None
    tier: Optional[str] = None
    version: Optional[str] = None
    keywords: Optional[list] = None

    @classmethod
    def supports_language(cls, lang: str):
        # https://developers.deepgram.com/docs/language
        return TranscriberConfig.supports_language(lang, {
            "zh", "zh-CN", "zh-TW", "da", "nl", "en", "en-AU", "en-GB", "en-IN", "en-NZ", 
            "en-US", "nl", "fr", "fr-CA", "de", "hi", "hi-Latn", "id", "it", "ja", "ko", 
            "no", "pl", "pt", "pt-BR", "pt-PT", "ru", "es", "es-419", "sv", "ta", "tr", "uk"
        })

class GoogleTranscriberConfig(TranscriberConfig, type=TranscriberType.GOOGLE.value):
    model: Optional[str] = None

    @classmethod
    def supports_language(cls, lang: str):
        # https://cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages
        return TranscriberConfig.supports_language(lang, {
            "af-ZA", "sq-AL", "am-ET", "ar-DZ", "ar-BH", "ar-EG", "ar-IQ", "ar-IL", "ar-JO", "ar-KW", 
            "ar-LB", "ar-MR", "ar-MA", "ar-OM", "ar-QA", "ar-SA", "ar-PS", "ar-TN", "ar-AE", "ar-YE", 
            "hy-AM", "az-AZ", "eu-ES", "bn-BD", "bn-IN", "bs-BA", "bg-BG", "my-MM", "ca-ES", "yue-Hant-HK", 
            "zh (cmn-Hans-CN)", "zh-TW (cmn-Hant-TW)", "hr-HR", "cs-CZ", "da-DK", "nl-BE", "nl-NL", 
            "en-AU", "en-CA", "en-GH", "en-HK", "en-IN", "en-IE", "en-KE", "en-NZ", "en-NG", "en-PK", 
            "en-PH", "en-SG", "en-ZA", "en-TZ", "en-GB", "en-US", "et-EE", "fil-PH", "fi-FI", "fr-BE", 
            "fr-CA", "fr-FR", "fr-CH", "gl-ES", "ka-GE", "de-AT", "de-DE", "de-CH", "el-GR", "gu-IN", 
            "iw-IL", "hi-IN", "hu-HU", "is-IS", "id-ID", "it-IT", "it-CH", "ja-JP", "jv-ID", "kn-IN", 
            "kk-KZ", "km-KH", "ko-KR", "lo-LA", "lv-LV", "lt-LT", "mk-MK", "ms-MY", "ml-IN", "mr-IN", 
            "mn-MN", "ne-NP", "no-NO", "fa-IR", "pl-PL", "pt-BR", "pt-PT", "pa-Guru-IN", "ro-RO", "ru-RU", 
            "rw-RW", "sr-RS", "si-LK", "sk-SK", "sl-SI", "ss-latn-za", "st-ZA", "es-AR", "es-BO", "es-CL", 
            "es-CO", "es-CR", "es-DO", "es-EC", "es-SV", "es-GT", "es-HN", "es-MX", "es-NI", "es-PA", "es-PY", 
            "es-PE", "es-PR", "es-ES", "es-US", "es-UY", "es-VE", "su-ID", "sw-KE", "sw-TZ", "sv-SE", "ta-IN", 
            "ta-MY", "ta-SG", "ta-LK", "te-IN", "th-TH", "tn-latn-za", "tr-TR", "ts-ZA", "uk-UA", "ur-IN", 
            "ur-PK", "uz-UZ", "ve-ZA", "vi-VN", "xh-ZA", "zu-ZA"
    })


class AzureTranscriberConfig(TranscriberConfig, type=TranscriberType.AZURE.value):
    
    @classmethod
    def supports_language(cls, lang: str):
        # https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support?tabs=stt
        return TranscriberConfig.supports_language(lang, { 
            "am-ET", "az-AZ", "bg-BG", "bn-IN", "bs-BA", "ca-ES", "cs-CZ", "cy-GB", "da-DK", 
            "de-AT", "de-CH", "de-DE", "el-GR", "en-AU", "en-CA", "en-GB", "en-HK", "en-IE", 
            "en-IN", "en-KE", "en-NG", "en-NZ", "en-PH", "en-SG", "en-TZ", "en-US", "en-ZA", 
            "es-AR", "es-BO", "es-CL", "es-CO", "es-CR", "es-CU", "es-DO", "es-EC", "es-ES", 
            "es-GQ", "es-GT", "es-HN", "es-MX", "es-NI", "es-PA", "es-PE", "es-PR", "es-PY", 
            "es-SV", "es-US", "es-UY", "es-VE", "et-EE", "eu-ES", "fi-FI", f"il-PH", "fr-BE", 
            "fr-CA", "fr-CH", "fr-FR", "ga-IE", "gl-ES", "gu-IN", "hi-IN", "hr-HR", "hu-HU", 
            "hy-AM", "id-ID", "is-IS", "it-IT", "ja-JP", "jv-ID", "ka-GE", "kk-KZ", "km-KH", 
            "kn-IN", "ko-KR", "lo-LA", "lt-LT", "lv-LV", "mk-MK", "ml-IN", "mn-MN", "mr-IN", 
            "ms-MY", "mt-MT", "my-MM", "nb-NO", "ne-NP", "nl-BE", "nl-NL", "pl-PL", "pt-BR", 
            "pt-PT", "ro-RO", "ru-RU", "si-LK", "sk-SK", "sl-SI", "so-SO", "sq-AL", "sr-RS", 
            "sv-SE", "sw-KE", "sw-TZ", "ta-IN", "te-IN", "th-TH", "tr-TR", "uk-UA", "uz-UZ", 
            "vi-VN", "wuu-CN", "yue-CN", "zh-CN", "zh-CN-sichuan", "zh-HK", "zh-TW", "zu-ZA"})


class AssemblyAITranscriberConfig(
    TranscriberConfig, type=TranscriberType.ASSEMBLY_AI.value
):
    buffer_size_seconds: float = 0.1
    word_boost: Optional[List[str]] = None

    @classmethod
    def supports_language(cls, lang: str):
        # https://airtable.com/embed/shr53TWU5reXkAmt2/tblf7O4cffFndmsCH
        # Streaming only supports English
        return TranscriberConfig.supports_language(lang, { "en" }) 

class WhisperCPPTranscriberConfig(
    TranscriberConfig, type=TranscriberType.WHISPER_CPP.value
):
    buffer_size_seconds: float = 1
    libname: str
    fname_model: str

    @classmethod
    def supports_language(cls, lang: str):
        # https://help.openai.com/en/articles/7031512-whisper-api-faq
        return TranscriberConfig.supports_language(lang, {
            "af", "ar", "hy", "az", "be", "bs", "bg", "ca", "zh", "hr", "cs", "da", "nl", "en", "et", "fi",
            "fr", "gl", "de", "el", "he", "hi", "hu", "is", "id", "it", "ja", "kn", "kk", "ko", "lv", "lt",
            "mk", "ms", "mr", "mi", "ne", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw",
            "sv", "tl", "ta", "th", "tr", "uk", "ur", "vi", "cy"})

class RevAITranscriberConfig(TranscriberConfig, type=TranscriberType.REV_AI.value):
    
    @classmethod
    def supports_language(cls, lang: str):
        # https://www.rev.ai/languages
        # Only streaming languages are listed below
        return TranscriberConfig.supports_language(lang, {
            "en", "fr", "de", "it", "ko", "cmn", "zh-cmn", "pt", "es"
        }) 

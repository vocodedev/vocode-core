from pydantic import BaseModel, Field, validator, constr, confloat, conint
from typing import Optional, Union, List
from typing_extensions import Literal

from .connect_endpoints import ConnectEndpoints
from .input_types import InputTypes
from .pay_prompts import PayPrompts

from deprecated import deprecated


class Ncco:
    class Action(BaseModel):
        action: str = None

    class Record(Action):
        """Use the record action to record a call or part of a call."""

        action = Field('record', const=True)
        format: Optional[Literal['mp3', 'wav', 'ogg']]
        split: Optional[Literal['conversation']]
        channels: Optional[conint(ge=1, le=32)]
        endOnSilence: Optional[conint(ge=3, le=10)]
        endOnKey: Optional[constr(regex='^[0-9*#]$')]
        timeOut: Optional[conint(ge=3, le=7200)]
        beepStart: Optional[bool]
        eventUrl: Optional[Union[List[str], str]]
        eventMethod: Optional[constr(to_upper=True)]

        @validator('channels')
        def enable_split(cls, v, values):
            if values['split'] is None:
                values['split'] = 'conversation'
            return v

        @validator('eventUrl')
        def ensure_url_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

    class Conversation(Action):
        """You can use the conversation action to create standard or moderated conferences,
        while preserving the communication context.
        Using conversation with the same name reuses the same persisted conversation."""

        action = Field('conversation', const=True)
        name: str
        musicOnHoldUrl: Optional[Union[List[str], str]]
        startOnEnter: Optional[bool]
        endOnExit: Optional[bool]
        record: Optional[bool]
        canSpeak: Optional[List[str]]
        canHear: Optional[List[str]]
        mute: Optional[bool]

        @validator('musicOnHoldUrl')
        def ensure_url_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

        @validator('mute')
        def can_mute(cls, v, values):
            if 'canSpeak' in values and values['canSpeak'] is not None:
                raise ValueError('Cannot use mute option if canSpeak option is specified.')
            return v

    class Connect(Action):
        """You can use the connect action to connect a call to endpoints such as phone numbers or a VBC extension."""

        action = Field('connect', const=True)
        endpoint: Union[dict, ConnectEndpoints.Endpoint, List[dict]]
        from_: Optional[constr(regex=r'^[1-9]\d{6,14}$')]
        randomFromNumber: Optional[bool]
        eventType: Optional[Literal['synchronous']]
        timeout: Optional[int]
        limit: Optional[conint(le=7200)]
        machineDetection: Optional[Literal['continue', 'hangup']]
        advancedMachineDetection: Optional[dict]
        eventUrl: Optional[Union[List[str], str]]
        eventMethod: Optional[constr(to_upper=True)]
        ringbackTone: Optional[str]

        @validator('endpoint')
        def validate_endpoint(cls, v):
            if type(v) is dict:
                return [ConnectEndpoints.create_endpoint_model_from_dict(v)]
            elif type(v) is list:
                return [ConnectEndpoints.create_endpoint_model_from_dict(v[0])]
            else:
                return [v]

        @validator('from_')
        def set_from_field(cls, v, values):
            values['from'] = v

        @validator('randomFromNumber')
        def check_from_not_set(cls, v, values):
            if v is True and 'from' in values:
                if values['from'] is not None:
                    raise ValueError(
                        'Cannot set a "from" ("from_") field and also the "randomFromNumber" = True option'
                    )
            return v

        @validator('eventUrl')
        def ensure_url_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

        @validator('advancedMachineDetection')
        def validate_advancedMachineDetection(cls, v):
            if 'behavior' in v and v['behavior'] not in ('continue', 'hangup'):
                raise ValueError(
                    'advancedMachineDetection["behavior"] must be one of: "continue", "hangup".'
                )
            if 'mode' in v and v['mode'] not in ('detect, detect_beep'):
                raise ValueError(
                    'advancedMachineDetection["mode"] must be one of: "detect", "detect_beep".'
                )
            return v

        class Config:
            smart_union = True

    class Talk(Action):
        """The talk action sends synthesized speech to a Conversation."""

        action = Field('talk', const=True)
        text: constr(max_length=1500)
        bargeIn: Optional[bool]
        loop: Optional[conint(ge=0)]
        level: Optional[confloat(ge=-1, le=1)]
        language: Optional[str]
        style: Optional[int]
        premium: Optional[bool]

    class Stream(Action):
        """The stream action allows you to send an audio stream to a Conversation."""

        action = Field('stream', const=True)
        streamUrl: Union[List[str], str]
        level: Optional[confloat(ge=-1, le=1)]
        bargeIn: Optional[bool]
        loop: Optional[conint(ge=0)]

        @validator('streamUrl')
        def ensure_url_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

    class Input(Action):
        """Collect digits or speech input by the person you are are calling."""

        action = Field('input', const=True)
        type: Union[
            Literal['dtmf', 'speech'],
            List[Literal['dtmf']],
            List[Literal['speech']],
            List[Literal['dtmf', 'speech']],
        ]
        dtmf: Optional[Union[InputTypes.Dtmf, dict]]
        speech: Optional[Union[InputTypes.Speech, dict]]
        eventUrl: Optional[Union[List[str], str]]
        eventMethod: Optional[constr(to_upper=True)]

        @validator('type', 'eventUrl')
        def ensure_value_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

        @validator('dtmf')
        def ensure_input_object_is_dtmf_model(cls, v):
            if type(v) is dict:
                return InputTypes.create_dtmf_model(v)
            else:
                return v

        @validator('speech')
        def ensure_input_object_is_speech_model(cls, v):
            if type(v) is dict:
                return InputTypes.create_speech_model(v)
            else:
                return v

    class Notify(Action):
        """Use the notify action to send a custom payload to your event URL."""

        action = Field('notify', const=True)
        payload: dict
        eventUrl: Union[List[str], str]
        eventMethod: Optional[constr(to_upper=True)]

        @validator('eventUrl')
        def ensure_url_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

    @deprecated(version='3.2.3', reason='The Pay NCCO action has been deprecated.')
    class Pay(Action):
        """The pay action collects credit card information with DTMF input in a secure (PCI-DSS compliant) way."""

        action = Field('pay', const=True)
        amount: confloat(ge=0)
        currency: Optional[constr(to_lower=True)]
        eventUrl: Optional[Union[List[str], str]]
        prompts: Optional[Union[List[PayPrompts.TextPrompt], PayPrompts.TextPrompt, dict]]
        voice: Optional[Union[PayPrompts.VoicePrompt, dict]]

        @validator('amount')
        def round_amount(cls, v):
            return round(v, 2)

        @validator('eventUrl')
        def ensure_url_in_list(cls, v):
            return Ncco._ensure_object_in_list(v)

        @validator('prompts')
        def ensure_text_model(cls, v):
            if type(v) is dict:
                return PayPrompts.create_text_model(v)
            else:
                return v

        @validator('voice')
        def ensure_voice_model(cls, v):
            if type(v) is dict:
                return PayPrompts.create_voice_model(v)
            else:
                return v

    @staticmethod
    def build_ncco(*args: Action, actions: List[Action] = None) -> str:
        ncco = []
        if actions is not None:
            for action in actions:
                ncco.append(action.dict(exclude_none=True))
        for action in args:
            ncco.append(action.dict(exclude_none=True))
        return ncco

    @staticmethod
    def _ensure_object_in_list(obj):
        if type(obj) != list:
            return [obj]
        else:
            return obj

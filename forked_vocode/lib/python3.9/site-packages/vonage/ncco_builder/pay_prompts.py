from pydantic import BaseModel, validator
from typing import Optional, Dict
from typing_extensions import Literal


class PayPrompts:
    class VoicePrompt(BaseModel):
        language: Optional[str]
        style: Optional[int]

    class TextPrompt(BaseModel):
        type: Literal['CardNumber', 'ExpirationDate', 'SecurityCode']
        text: str
        errors: Dict[
            Literal[
                'InvalidCardType',
                'InvalidCardNumber',
                'InvalidExpirationDate',
                'InvalidSecurityCode',
                'Timeout',
            ],
            Dict[Literal['text'], str],
        ]

        @validator('errors')
        def check_valid_error_format(cls, v, values):
            if values['type'] == 'CardNumber':
                allowed_values = {'InvalidCardType', 'InvalidCardNumber', 'Timeout'}
                cls.check_allowed_values(v, allowed_values, values['type'])
            elif values['type'] == 'ExpirationDate':
                allowed_values = {'InvalidExpirationDate', 'Timeout'}
                cls.check_allowed_values(v, allowed_values, values['type'])
            elif values['type'] == 'SecurityCode':
                allowed_values = {'InvalidSecurityCode', 'Timeout'}
                cls.check_allowed_values(v, allowed_values, values['type'])
            return v

        def check_allowed_values(errors, allowed_values, prompt_type):
            for key in errors:
                if key not in allowed_values:
                    raise ValueError(
                        f'Value "{key}" is not a valid error for the "{prompt_type}" prompt type.'
                    )

    @classmethod
    def create_voice_model(cls, dict) -> VoicePrompt:
        return cls.VoicePrompt.parse_obj(dict)

    @classmethod
    def create_text_model(cls, dict) -> TextPrompt:
        return cls.TextPrompt.parse_obj(dict)

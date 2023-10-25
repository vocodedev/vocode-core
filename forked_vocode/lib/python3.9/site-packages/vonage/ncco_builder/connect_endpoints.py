from pydantic import BaseModel, HttpUrl, AnyUrl, Field, constr
from typing import Optional, Dict
from typing_extensions import Literal


class ConnectEndpoints:
    class Endpoint(BaseModel):
        type: str = None

    class PhoneEndpoint(Endpoint):
        type = Field('phone', const=True)
        number: constr(regex=r'^[1-9]\d{6,14}$')
        dtmfAnswer: Optional[constr(regex='^[0-9*#p]+$')]
        onAnswer: Optional[Dict[str, HttpUrl]]

    class AppEndpoint(Endpoint):
        type = Field('app', const=True)
        user: str

    class WebsocketEndpoint(Endpoint):
        type = Field('websocket', const=True)
        uri: AnyUrl
        contentType: Literal['audio/l16;rate=16000', 'audio/l16;rate=8000']
        headers: Optional[dict]

    class SipEndpoint(Endpoint):
        type = Field('sip', const=True)
        uri: str
        headers: Optional[dict]

    class VbcEndpoint(Endpoint):
        type = Field('vbc', const=True)
        extension: str

    @classmethod
    def create_endpoint_model_from_dict(cls, d) -> Endpoint:
        if d['type'] == 'phone':
            return cls.PhoneEndpoint.parse_obj(d)
        elif d['type'] == 'app':
            return cls.AppEndpoint.parse_obj(d)
        elif d['type'] == 'websocket':
            return cls.WebsocketEndpoint.parse_obj(d)
        elif d['type'] == 'sip':
            return cls.WebsocketEndpoint.parse_obj(d)
        elif d['type'] == 'vbc':
            return cls.WebsocketEndpoint.parse_obj(d)
        else:
            raise ValueError(
                'Invalid "type" specified for endpoint object. Cannot create a ConnectEndpoints.Endpoint model.'
            )

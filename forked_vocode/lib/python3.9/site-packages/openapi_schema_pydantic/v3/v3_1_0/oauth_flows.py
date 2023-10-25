from typing import Optional

from pydantic import BaseModel, Extra

from .oauth_flow import OAuthFlow


class OAuthFlows(BaseModel):
    """
    Allows configuration of the supported OAuth Flows.
    """

    implicit: Optional[OAuthFlow] = None
    """
    Configuration for the OAuth Implicit flow
    """

    password: Optional[OAuthFlow] = None
    """
    Configuration for the OAuth Resource Owner Password flow
    """

    clientCredentials: Optional[OAuthFlow] = None
    """
    Configuration for the OAuth Client Credentials flow.
    
    Previously called `application` in OpenAPI 2.0.
    """

    authorizationCode: Optional[OAuthFlow] = None
    """
    Configuration for the OAuth Authorization Code flow.
    
    Previously called `accessCode` in OpenAPI 2.0.
    """

    class Config:
        extra = Extra.ignore

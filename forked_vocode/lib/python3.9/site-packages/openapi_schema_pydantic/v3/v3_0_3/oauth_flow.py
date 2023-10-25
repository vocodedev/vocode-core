from typing import Dict, Optional, Union

from pydantic import AnyUrl, BaseModel, Extra


class OAuthFlow(BaseModel):
    """
    Configuration details for a supported OAuth Flow
    """

    authorizationUrl: Optional[Union[AnyUrl, str]] = None
    """
    **REQUIRED** for `oauth2 ("implicit", "authorizationCode")`.
    The authorization URL to be used for this flow.
    This MUST be in the form of a URL.
    """

    tokenUrl: Optional[Union[AnyUrl, str]] = None
    """
    **REQUIRED** for `oauth2 ("password", "clientCredentials", "authorizationCode")`.
    The token URL to be used for this flow.
    This MUST be in the form of a URL.
    """

    refreshUrl: Optional[Union[AnyUrl, str]] = None
    """
    The URL to be used for obtaining refresh tokens. This MUST be in the form of a URL.
    """

    scopes: Dict[str, str] = ...
    """
    **REQUIRED**. The available scopes for the OAuth2 security scheme.
    A map between the scope name and a short description for it.
    The map MAY be empty.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "examples": [
                {
                    "authorizationUrl": "https://example.com/api/oauth/dialog",
                    "scopes": {"write:pets": "modify pets in your account", "read:pets": "read your pets"},
                },
                {
                    "authorizationUrl": "https://example.com/api/oauth/dialog",
                    "tokenUrl": "https://example.com/api/oauth/token",
                    "scopes": {"write:pets": "modify pets in your account", "read:pets": "read your pets"},
                },
                {
                    "authorizationUrl": "/api/oauth/dialog",  # issue #5: allow relative path
                    "tokenUrl": "/api/oauth/token",  # issue #5: allow relative path
                    "refreshUrl": "/api/oauth/token",  # issue #5: allow relative path
                    "scopes": {"write:pets": "modify pets in your account", "read:pets": "read your pets"},
                },
            ]
        }

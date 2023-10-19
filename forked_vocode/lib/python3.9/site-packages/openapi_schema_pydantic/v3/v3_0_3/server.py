from typing import Dict, Optional

from pydantic import BaseModel, Extra

from .server_variable import ServerVariable


class Server(BaseModel):
    """An object representing a Server."""

    url: str = ...
    """
    **REQUIRED**. A URL to the target host.
    
    This URL supports Server Variables and MAY be relative,
    to indicate that the host location is relative to the location where the OpenAPI document is being served.
    Variable substitutions will be made when a variable is named in `{`brackets`}`.
    """

    description: Optional[str] = None
    """
    An optional string describing the host designated by the URL.
    [CommonMark syntax](https://spec.commonmark.org/) MAY be used for rich text representation.
    """

    variables: Optional[Dict[str, ServerVariable]] = None
    """
    A map between a variable name and its value.
    
    The value is used for substitution in the server's URL template.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "examples": [
                {"url": "https://development.gigantic-server.com/v1", "description": "Development server"},
                {
                    "url": "https://{username}.gigantic-server.com:{port}/{basePath}",
                    "description": "The production API server",
                    "variables": {
                        "username": {
                            "default": "demo",
                            "description": "this value is assigned by the service provider, "
                            "in this example `gigantic-server.com`",
                        },
                        "port": {"enum": ["8443", "443"], "default": "8443"},
                        "basePath": {"default": "v2"},
                    },
                },
            ]
        }

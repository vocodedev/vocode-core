from typing import Optional

from pydantic import AnyUrl, BaseModel, Extra


class License(BaseModel):
    """
    License information for the exposed API.
    """

    name: str = ...
    """
    **REQUIRED**. The license name used for the API.
    """

    url: Optional[AnyUrl] = None
    """
    A URL to the license used for the API.
    MUST be in the format of a URL.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {"examples": [{"name": "Apache 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0.html"}]}

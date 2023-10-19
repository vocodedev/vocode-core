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

    identifier: Optional[str] = None
    """
    An [SPDX](https://spdx.org/spdx-specification-21-web-version#h.jxpfx0ykyb60) license expression for the API.
    The `identifier` field is mutually exclusive of the `url` field.
    """

    url: Optional[AnyUrl] = None
    """
    A URL to the license used for the API.
    This MUST be in the form of a URL.
    The `url` field is mutually exclusive of the `identifier` field.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "examples": [
                {"name": "Apache 2.0", "identifier": "Apache-2.0"},
                {"name": "Apache 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0.html"},
            ]
        }

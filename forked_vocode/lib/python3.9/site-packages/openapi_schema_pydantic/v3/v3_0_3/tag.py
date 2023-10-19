from typing import Optional

from pydantic import BaseModel, Extra

from .external_documentation import ExternalDocumentation


class Tag(BaseModel):
    """
    Adds metadata to a single tag that is used by the [Operation Object](#operationObject).
    It is not mandatory to have a Tag Object per tag defined in the Operation Object instances.
    """

    name: str = ...
    """
    **REQUIRED**. The name of the tag.
    """

    description: Optional[str] = None
    """
    A short description for the tag.
    [CommonMark syntax](https://spec.commonmark.org/) MAY be used for rich text representation.
    """

    externalDocs: Optional[ExternalDocumentation] = None
    """
    Additional external documentation for this tag.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {"examples": [{"name": "pet", "description": "Pets operations"}]}

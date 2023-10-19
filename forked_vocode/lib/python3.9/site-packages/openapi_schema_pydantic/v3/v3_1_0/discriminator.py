from typing import Dict, Optional

from pydantic import BaseModel, Extra


class Discriminator(BaseModel):
    """
    When request bodies or response payloads may be one of a number of different schemas,
    a `discriminator` object can be used to aid in serialization, deserialization, and validation.

    The discriminator is a specific object in a schema which is used to inform the consumer of the specification
    of an alternative schema based on the value associated with it.

    When using the discriminator, _inline_ schemas will not be considered.
    """

    propertyName: str = ...
    """
    **REQUIRED**. The name of the property in the payload that will hold the discriminator value.
    """

    mapping: Optional[Dict[str, str]] = None
    """
    An object to hold mappings between payload values and schema names or references.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "examples": [
                {
                    "propertyName": "petType",
                    "mapping": {
                        "dog": "#/components/schemas/Dog",
                        "monster": "https://gigantic-server.com/schemas/Monster/schema.json",
                    },
                }
            ]
        }

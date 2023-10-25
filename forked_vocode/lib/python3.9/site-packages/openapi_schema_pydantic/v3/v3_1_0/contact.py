from typing import Optional

from pydantic import AnyUrl, BaseModel, Extra


class Contact(BaseModel):
    """
    Contact information for the exposed API.
    """

    name: Optional[str] = None
    """
    The identifying name of the contact person/organization.
    """

    url: Optional[AnyUrl] = None
    """
    The URL pointing to the contact information.
    MUST be in the form of a URL.
    """

    email: Optional[str] = None
    """
    The email address of the contact person/organization.
    MUST be in the form of an email address.
    """

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "examples": [
                {"name": "API Support", "url": "http://www.example.com/support", "email": "support@example.com"}
            ]
        }

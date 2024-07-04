from typing import List

from langchain.agents import tool

CONTACTS = [{"name": "Ajay", "phone": "+15555555555"}]


@tool("get_all_contacts")
def get_all_contacts(placeholder: str) -> List[dict]:
    """Get contacts."""
    return CONTACTS

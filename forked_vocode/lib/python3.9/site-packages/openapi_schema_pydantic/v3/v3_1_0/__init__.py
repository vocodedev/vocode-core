"""
OpenAPI v3.1.0 schema types, created according to the specification:
https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.1.0.md

The type orders are according to the contents of the specification:
https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.1.0.md#table-of-contents
"""

from .open_api import OpenAPI
from .info import Info
from .contact import Contact
from .license import License
from .server import Server
from .server_variable import ServerVariable
from .components import Components
from .paths import Paths
from .path_item import PathItem
from .operation import Operation
from .external_documentation import ExternalDocumentation
from .parameter import Parameter
from .request_body import RequestBody
from .media_type import MediaType
from .encoding import Encoding
from .responses import Responses
from .response import Response
from .callback import Callback
from .example import Example
from .link import Link
from .header import Header
from .tag import Tag
from .reference import Reference
from .schema import Schema
from .discriminator import Discriminator
from .xml import XML
from .security_scheme import SecurityScheme
from .oauth_flows import OAuthFlows
from .oauth_flow import OAuthFlow
from .security_requirement import SecurityRequirement

# resolve forward references
Encoding.update_forward_refs(Header=Header)
Schema.update_forward_refs()

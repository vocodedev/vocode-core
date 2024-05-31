import os

from fastapi import Response
from jinja2 import Environment, FileSystemLoader

DEFAULT_TEMPLATE_ENVIRONMENT = Environment(
    loader=FileSystemLoader("%s/templates/" % os.path.dirname(__file__))
)


def render_template(template_name: str, template_environment: Environment, **kwargs):
    template = template_environment.get_template(template_name)
    return template.render(**kwargs)


def get_connection_twiml(
    call_id: str,
    base_url: str,
    template_environment: Environment = DEFAULT_TEMPLATE_ENVIRONMENT,
):
    return Response(
        render_template(
            template_name="twilio_connect_call.xml",
            template_environment=template_environment,
            base_url=base_url,
            id=call_id,
        ),
        media_type="application/xml",
    )

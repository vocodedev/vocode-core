from pydantic import AnyUrl

from openapi_schema_pydantic import SecurityScheme


def test_security_scheme_issue_5():
    """https://github.com/kuimono/openapi-schema-pydantic/issues/5"""

    security_scheme_1 = SecurityScheme(type="openIdConnect", openIdConnectUrl="https://example.com/openIdConnect")
    assert isinstance(security_scheme_1.openIdConnectUrl, AnyUrl) or isinstance(security_scheme_1.openIdConnectUrl, str)
    assert security_scheme_1.json(by_alias=True, exclude_none=True) == (
        '{"type": "openIdConnect", "openIdConnectUrl": "https://example.com/openIdConnect"}'
    )

    security_scheme_2 = SecurityScheme(type="openIdConnect", openIdConnectUrl="/openIdConnect")
    assert isinstance(security_scheme_2.openIdConnectUrl, str)
    assert security_scheme_2.json(by_alias=True, exclude_none=True) == (
        '{"type": "openIdConnect", "openIdConnectUrl": "/openIdConnect"}'
    )

    security_scheme_3 = SecurityScheme(type="openIdConnect", openIdConnectUrl="openIdConnect")
    assert isinstance(security_scheme_3.openIdConnectUrl, str)
    assert security_scheme_3.json(by_alias=True, exclude_none=True) == (
        '{"type": "openIdConnect", "openIdConnectUrl": "openIdConnect"}'
    )

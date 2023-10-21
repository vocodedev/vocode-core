import logging

from pydantic import BaseModel, Extra
from pydantic.schema import schema

from openapi_schema_pydantic import Schema, Reference


def test_schema():
    schema = Schema.parse_obj(
        {
            "title": "reference list",
            "description": "schema for list of reference type",
            "allOf": [{"$ref": "#/definitions/TestType"}],
        }
    )
    logging.debug(f"schema.allOf={schema.allOf}")
    assert schema.allOf
    assert isinstance(schema.allOf, list)
    assert isinstance(schema.allOf[0], Reference)
    assert schema.allOf[0].ref == "#/definitions/TestType"


def test_issue_4():
    """https://github.com/kuimono/openapi-schema-pydantic/issues/4"""

    class TestModel(BaseModel):
        test_field: str

        class Config:
            extra = Extra.forbid

    schema_definition = schema([TestModel])
    assert schema_definition == {
        "definitions": {
            "TestModel": {
                "title": "TestModel",
                "type": "object",
                "properties": {"test_field": {"title": "Test Field", "type": "string"}},
                "required": ["test_field"],
                "additionalProperties": False,
            }
        }
    }

    # allow "additionalProperties" to have boolean value
    result = Schema.parse_obj(schema_definition["definitions"]["TestModel"])
    assert result.additionalProperties is False

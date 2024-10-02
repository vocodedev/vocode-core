from abc import ABC
from typing import Any, Dict

from pydantic import BaseModel, ValidationError, model_validator


class AdaptiveObject(BaseModel, ABC):
    """An abstract object that may be one of several concrete types."""

    @model_validator(mode="wrap")
    @classmethod
    def _resolve_adaptive_object(cls, data: dict, handler) -> Any:
        if not isinstance(data, dict):
            return handler(data)
        # if cls is not abstract, there's nothing to do
        if ABC not in cls.__bases__:
            return handler(data)

        # try to validate the data for each possible type
        for subcls in cls._find_all_possible_types():
            try:
                # return the first successful validation
                return subcls.model_validate(data)
            except ValidationError:
                continue

        raise ValidationError(
            "adaptive-object",
            "unable to resolve input",
        )

    @classmethod
    def _find_all_possible_types(cls):
        """Recursively generate all possible types for this object."""

        # any concrete class is a possible type
        if ABC not in cls.__bases__:
            yield cls

        # continue looking for possible types in subclasses
        for subclass in cls.__subclasses__():
            yield from subclass._find_all_possible_types()

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(serialize_as_any=True, **kwargs)

    def model_dump_json(self, **kwargs) -> str:
        return super().model_dump_json(serialize_as_any=True, **kwargs)

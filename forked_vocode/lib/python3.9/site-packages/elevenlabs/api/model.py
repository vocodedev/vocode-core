from __future__ import annotations

from typing import List, Optional

from .base import API, Listable, api_base_url_v1


class Model(API):
    model_id: str
    name: Optional[str] = None
    token_cost_factor: Optional[float] = None
    description: Optional[str] = None


class Models(Listable, API):
    models: List[Model]

    @classmethod
    def from_api(cls) -> Models:
        url = f"{api_base_url_v1}/models"
        response = cls.get(url).json()
        return cls(models=response)

    @property
    def items(self):
        return self.models

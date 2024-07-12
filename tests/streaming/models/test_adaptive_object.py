from abc import ABC
from typing import Any, Literal

from vocode.streaming.models.adaptive_object import AdaptiveObject


class B(AdaptiveObject, ABC):
    type: Any


class SubB1(B):
    type: Literal["sub_b1"] = "sub_b1"
    x: int


class SubB2(B):
    type: Literal["sub_b2"] = "sub_b2"
    y: int


class A(AdaptiveObject, ABC):
    type: Any
    b: B


class SubA1(A):
    type: Literal["sub_a1"] = "sub_a1"
    x: int


class SubA2(A):
    type: Literal["sub_a2"] = "sub_a2"
    y: int


def test_serialize():
    sub_a1 = SubA1(b=SubB1(x=2), x=1)
    assert sub_a1.model_dump() == {"b": {"type": "sub_b1", "x": 2}, "type": "sub_a1", "x": 1}


def test_deserialize():
    d = {"b": {"type": "sub_b1", "x": 2}, "type": "sub_a1", "x": 1}
    sub_a1 = A.model_validate(d)
    assert isinstance(sub_a1, SubA1)
    assert isinstance(sub_a1.b, SubB1)
    assert sub_a1.b.x == 2
    assert sub_a1.x == 1

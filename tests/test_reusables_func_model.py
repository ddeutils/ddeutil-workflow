from __future__ import annotations

from inspect import Parameter, signature
from typing import Annotated, get_type_hints

import pytest
from ddeutil.workflow import Result
from ddeutil.workflow.reusables import (
    create_model_from_caller,
)
from pydantic import BaseModel, Field, SecretStr, ValidationError, create_model
from typing_extensions import TypedDict


class Kwargs(TypedDict):  # pragma: no cov
    foo: str
    bar: str


def dummy_func(
    source: str, result: Result, *args, limit: int = 5, **kwargs: Kwargs
):  # pragma: no cov
    ...


class Auth(BaseModel):  # pragma: no cov
    url: str
    token: SecretStr


class Address(BaseModel):  # pragma: no cov
    name: str
    post_num: int


class User(BaseModel):  # pragma: no cov
    name: str
    address: Address
    age: int = Field(gt=0)


def dummy_model_func(
    auth: Auth,
    user: User,
    _exec: str,
    limit: int = 5,
    **kwargs,
):  # pragma: no cov
    ...


def test_make_model_from_argument():
    """Create Pydantic Model from function arguments.

    Refs:
    - https://github.com/lmmx/pydantic-function-models
    - https://docs.pydantic.dev/1.10/usage/models/#dynamic-model-creation
    """
    type_hints: dict = get_type_hints(dummy_func)
    print(type_hints)
    model = create_model("ArgsFunc", **type_hints)
    print(model)
    arg_instance = model.model_validate(
        {
            "source": "some-source",
            "limit": 10,
            "result": Result(),
            "kwargs": {"foo": "baz", "bar": "baz"},
        }
    )
    print(arg_instance)
    print("----")

    with pytest.raises(ValidationError):
        model.model_validate({"source": []})

    with pytest.raises(ValidationError):
        model.model_validate({"limit": "10"})

    sig = signature(dummy_func)
    print(sig.parameters)
    for name in sig.parameters:
        param: Parameter = sig.parameters[name]
        print(name, ":", param)
        print(
            f"\t> default: {param.default}\n"
            f"\t> kind: {param.kind}\n"
            f"\t> annotation: {param.annotation} ({type(param.annotation)})"
        )
        print("===")


class Default(BaseModel):  # pragma: no cov
    name: str
    limit: Annotated[
        int,
        Field(default=10, gt=0),
    ]


def test_dump_exclude_unset():
    assert "limit" not in Default.model_validate({"name": "tom"}).model_dump(
        exclude_defaults=True
    )
    assert "limit" not in Default.model_validate({"name": "tom"}).model_dump(
        exclude_unset=True
    )

    assert "limit" in Default.model_validate(
        {"name": "tom", "limit": 1}
    ).model_dump(exclude_defaults=True)
    assert "limit" in Default.model_validate(
        {"name": "tom", "limit": 1}
    ).model_dump(exclude_unset=True)

    # NOTE: Exclude because `limit` value equal to default value.
    assert "limit" not in Default.model_validate(
        {"name": "tom", "limit": 10}
    ).model_dump(exclude_defaults=True)


def test_create_model_from_caller():
    model = create_model_from_caller(dummy_func)
    arg_instance = model.model_validate(
        {
            "source": "some-source",
            "result": Result(),
            "outer-key": "should not pass to model",
        }
    )
    print(arg_instance)
    print(dict(arg_instance))
    print(arg_instance.model_dump(exclude_defaults=True, exclude_unset=True))
    print("--")

    model = create_model_from_caller(dummy_model_func)
    print(model.model_fields)
    arg_instance = model.model_validate(
        {
            "auth": {
                "url": "https://example.com/data",
                "token": "foo",
            },
            "user": {
                "name": "tom",
                "age": 1,
                "address": {"name": "no where", "post_num": 0},
            },
            "exec": "SELECT * FROM self",
        }
    )
    print(arg_instance)
    print(dict(arg_instance))
    print(
        arg_instance.model_dump(
            mode="python", exclude_defaults=True, exclude_unset=True
        )
    )

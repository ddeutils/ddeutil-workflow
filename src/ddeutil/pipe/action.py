# -------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# --------------------------------------------------------------------------

import inspect
import logging
from typing import (
    Any,
    Callable,
    Optional,
)

from ddeutil.core.base import isinstance_check
from ddeutil.node.exceptions import NodeArgumentError

logger = logging.getLogger(__name__)


class BaseActionType:
    """Base Action Type object for parsing parameters from configuration data
    to any action subclass object
    """

    __slots__ = ("_props",)

    @classmethod
    def receive(cls, properties: dict):
        """Return Base Action Type object"""
        return cls(properties=properties)

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return f"<{self.__class__.__name__}.receive(properties={self.props})>"

    def __init__(self, properties: Optional[dict] = None):
        """Main initialize of the base action type."""
        self._props: dict = {}
        try:
            for k, _typing in self.__annotations__.items():
                if k.startswith("_"):
                    continue
                try:
                    value: Any = properties.get(k, getattr(self, k))
                except AttributeError:
                    value: Any = properties[k]
                if not isinstance_check(value, _typing):
                    raise TypeError(
                        f"type of {k!r} for {self.__class__.__name__} does "
                        f"not match with {_typing}"
                    )
                self._props[k] = value
        except KeyError as key:
            raise NodeArgumentError(
                str(key), "action type does not exists"
            ) from key

    @property
    def props(self) -> dict:
        """Return the dictionary of properties."""
        return self._props

    def action(self, _input: Any, **kwargs) -> Any:
        raise NotImplementedError(self.__class__.__name__)


class BaseAction:
    """Base Action object that use for create sub-action type object."""

    __slots__ = (
        "_act_type",
        "_act_props",
    )

    @classmethod
    def from_data(cls, data: dict):
        if not (_type := data.pop("type", None)):
            raise AttributeError(
                "The key `type` does not exists in input dictionary data"
            )
        return cls(action_type=_type, properties=data)

    def __init__(self, action_type: str, properties: Optional[dict] = None):
        if (act_type := getattr(self, action_type, None)) is None:
            raise AttributeError(
                f"Action type: {action_type!r} does not exists or not support by "
                f"{self.__class__.__name__!r}"
            )
        self._act_type: BaseActionType = act_type
        # TODO: filter key for the action type input argument.
        self._act_props: dict = properties or {}

    def __str__(self):
        return str(self._act_type)

    def __repr__(self):
        _props: str = (
            f", properties={self._act_props}" if self._act_props else ""
        )
        return (
            f"<{self.__class__.__name__}(action_type={self._act_type}{_props})>"
        )

    @property
    def type(self) -> BaseActionType:
        """Return action type instance which initialize from the receive method."""
        return self._act_type.receive(self._act_props)

    @property
    def arguments(self) -> list:
        """Return the input argument of the action method."""
        return inspect.getfullargspec(self.type.action).args[1:]

    def action(self, _input: Any, **kwargs) -> Any:
        """Return action result from the action type object."""
        try:
            _f: Callable = self.type.action
            _inspect_f: inspect.FullArgSpec = inspect.getfullargspec(_f)

            # Check len of arguments more than 2 that mean there are value
            # other than `self` and `input`.
            if len(_args := _inspect_f.args) <= 2:
                return _f(_input)

            _kwargs: dict = {}
            for _arg in _args[2:]:
                if _arg in kwargs:
                    _kwargs[_arg] = kwargs.pop(_arg)
                elif _arg not in self._act_props:
                    raise NodeArgumentError(
                        _arg,
                        f"type: {_inspect_f.annotations[_arg]} does not exists "
                        f"in input argument of action method for "
                        f"{self.type.__class__.__name__}",
                    )
            return _f(_input, **_kwargs)
        except NotImplementedError as err:
            raise NodeArgumentError(
                str(err),
                f"this type does not support in {self.__class__.__name__} object.",
            ) from err

    class SelectColumn(BaseActionType):
        columns: list

        def action(self, _input: Any, **kwargs) -> Any: ...

    class Filter(BaseActionType):
        condition: str

        def action(self, _input: Any, **kwargs) -> Any: ...

    class RenameColumn(BaseActionType):
        columns: dict

        def action(self, _input: Any, **kwargs) -> Any: ...

    class RenameAllColumn(BaseActionType):
        append: bool = False
        prefix: bool = False
        columns: list
        pattern: str

        def action(self, _input: Any, **kwargs) -> Any: ...

    class AddColumn(BaseActionType):
        columns: dict

        def action(self, _input: Any, **kwargs) -> Any: ...

    class Distinct(BaseActionType):
        columns: list

        def action(self, _input: Any, **kwargs) -> Any: ...

    class DropColumn(BaseActionType):
        columns: list

        def action(self, _input: Any, **kwargs) -> Any: ...

    class DropDuplicate(BaseActionType):
        columns: Optional[list] = None

        def action(self, _input: Any, **kwargs) -> Any: ...

    class OrderBy(BaseActionType):
        columns: list

        def action(self, _input: Any, **kwargs) -> Any: ...

    class Limit(BaseActionType):
        numbers: int

        def action(self, _input: Any, **kwargs) -> Any: ...

    class GroupBy(BaseActionType):
        columns: list
        aggregate: dict
        sort: bool = True

        def action(self, _input: Any, **kwargs) -> Any: ...

    class Join(BaseActionType):
        other: Any
        on: str
        how: str

        def action(self, _input: Any, other: Optional[Any] = None) -> Any: ...

    class Union(BaseActionType):
        others: list[Any]

        def action(self, _input: Any, others: Optional[Any] = None) -> Any: ...

    class Intersect(BaseActionType):
        def action(self, _input: Any, **kwargs) -> Any: ...

    class Except(BaseActionType):
        def action(self, _input: Any, **kwargs) -> Any: ...

    class Repartition(BaseActionType):
        def action(self, _input: Any, **kwargs) -> Any: ...

    class Coalesce(BaseActionType):
        def action(self, _input: Any, **kwargs) -> Any: ...

    class Sequence(BaseActionType):
        sk_source: str
        sk_columns: list

        def action(self, _input: Any, **kwargs) -> Any: ...

    class SCD(BaseActionType):
        def action(self, _input: Any, **kwargs) -> Any: ...

    class NA(BaseActionType):
        def action(self, _input: Any, **kwargs) -> Any: ...

    class CallYaml:
        name: str

        def action(self, _input: Any, **kwargs) -> Any: ...

    class NameTransformation: ...

    class Collect: ...

    class Watermark: ...

    class Partition:
        condition: str

    class Router:
        conditions: list

    class DataQuality(BaseActionType):
        dq_function: str
        columns: list[Any]

        def action(self, _input: Any, **kwargs) -> Any: ...


# Register the sub-action class of base-action object.
SelectColumn = BaseAction.SelectColumn

Filter = BaseAction.Filter

RenameColumn = BaseAction.RenameColumn

RenameAllColumn = BaseAction.RenameAllColumn

AddColumn = BaseAction.AddColumn

Distinct = BaseAction.Distinct

DropColumn = BaseAction.DropColumn

DropDuplicate = BaseAction.DropDuplicate

OrderBy = BaseAction.OrderBy

Limit = BaseAction.Limit

GroupBy = BaseAction.GroupBy

Join = BaseAction.Join

Union = BaseAction.Union

Intersect = BaseAction.Intersect

Except = BaseAction.Except

Repartition = BaseAction.Repartition

Coalesce = BaseAction.Coalesce

Sequence = BaseAction.Sequence

SCD = BaseAction.SCD

NA = BaseAction.NA

CallYaml = BaseAction.CallYaml

NameTransformation = BaseAction.NameTransformation

Collect = BaseAction.Collect

Watermark = BaseAction.Watermark

Partition = BaseAction.Partition

Router = BaseAction.Router

DataQuality = BaseAction.DataQuality


__all__ = [
    "BaseAction",
    "SelectColumn",
    "Filter",
    "RenameColumn",
    "RenameAllColumn",
    "AddColumn",
    "Distinct",
    "DropColumn",
    "DropDuplicate",
    "OrderBy",
    "Limit",
    "GroupBy",
    "Join",
    "Union",
    "Intersect",
    "Except",
    "Repartition",
    "Coalesce",
    "Sequence",
    "SCD",
    "NA",
    "CallYaml",
    "NameTransformation",
    "Collect",
    "Watermark",
    "Partition",
    "Router",
    "DataQuality",
]

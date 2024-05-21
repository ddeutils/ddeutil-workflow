"""
Reference:
    * https://github.com/LarsHill/metadict
"""

from __future__ import annotations

import contextlib
import copy
import keyword
import re
import warnings
from collections.abc import (
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
)
from re import Pattern
from typing import (
    Any,
    Optional,
    TypeVar,
)

from typing_extensions import Self


def _warning(
    message,
    category=UserWarning,
    filename="",
    lineno=-1,
    file=None,
    line="",
):
    """Monkey patch `warnings` to show UserWarning without the line information
    of warnings call.
    """
    msg = warnings.WarningMessage(
        message, category, filename, lineno, file, line
    )
    print(f"{msg.category.__name__}: {msg.message}")


warnings.showwarning = _warning

KT = TypeVar("KT")
VT = TypeVar("VT")

# NOTE: regex to enforce python variable/attribute syntax
ALLOWED_VAR_SYNTAX: Pattern = re.compile(r"[a-zA-Z_]\w*")


def complies_variable_syntax(name: Any) -> bool:
    """Checks whether a given object is a string which complies the python
    variable syntax.
    """
    if not isinstance(name, str) or keyword.iskeyword(name):
        return False
    name_cleaned = "".join(re.findall(ALLOWED_VAR_SYNTAX, name))
    return name_cleaned == name


class MetaDict(MutableMapping[KT, VT], dict):
    """Class that extends `dict` to access and assign keys via attribute dot
    notation.

    Examples:
        >>> d = MetaDict({'foo': {'bar': [{'a': 1}, {'a': 2}]}})
        >>> d.foo.bar[1].a
        2
        >>> d["foo"]["bar"][1]["a"]
        2
        >>> d.bar = 'demo'
        >>> d.bar
        'demo'

        `MetaDict` inherits from MutableMapping to avoid overwriting all `dict`
    methods. In addition, it inherits from `dict` to pass the quite common
    `isinstance(obj, dict) check.

        Also, inheriting from `dict` enables json encoding/decoding without a
    custom encoder.
    """

    def __init__(self, *args, nested_assign: bool = False, **kwargs) -> None:
        # NOTE: check that 'nested_assign' is  of type bool
        if not isinstance(nested_assign, bool):
            raise TypeError(
                "Keyword argument 'nested_assign' must be an instance of "
                "type 'bool'"
            )

        # NOTE: init internal attributes and data store
        self.__dict__["_data"]: dict[KT, VT] = {}
        self.__dict__["_nested_assign"] = nested_assign
        self.__dict__["_parent"] = kwargs.pop("_parent", None)
        self.__dict__["_key"] = kwargs.pop("_key", None)

        # update state of data store
        self.update(*args, **kwargs)

        # call `dict` constructor with stored data to enable object encoding
        # (e.g. `json.dumps()`) that relies on `dict`
        dict.__init__(self, self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[KT]:
        return iter(self._data)

    def __setitem__(self, key: KT, value: VT) -> None:
        # show a warning if the assigned key or attribute is used internally
        # (e.g `items`, `keys`, etc.)
        try:
            self.__getattribute__(key)
            key_is_protected = True
        except (AttributeError, TypeError):
            key_is_protected = False
        if key_is_protected:
            warnings.warn(
                f"'{self.__class__.__name__}' object uses '{key}' internally. "
                f"'{key}' can only be accessed via `obj['{key}']`.",
                stacklevel=2,
            )

        # set key recursively
        self._data[key] = self._from_object(value)

        # update parent when nested keys or attributes are assigned
        parent = self.__dict__.pop("_parent", None)
        key = self.__dict__.get("_key", None)
        if parent is not None:
            parent[key] = self._data

    def __getitem__(self, key: KT) -> VT:
        try:
            value = self._data[key]
        except KeyError:
            if self.nested_assign:
                return self.__missing__(key)
            raise

        return value

    def __missing__(self, key: KT) -> Self:
        return self.__class__(
            _parent=self, _key=key, nested_assign=self._nested_assign
        )

    def __delitem__(self, key: KT) -> None:
        del self._data[key]

    def __setattr__(self, attr: str, val: VT) -> None:
        self[attr] = val

    def __getattr__(self, key: KT) -> VT:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{key}'"
            ) from None

    def __delattr__(self, key: KT) -> None:
        try:
            del self[key]
        except KeyError:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{key}'"
            ) from None

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return repr(self._data)

    @staticmethod
    def repack_args(cls: type, state: dict) -> MetaDict:
        """Repack and rename keyword arguments stored in state before feeding
        to class constructor
        """
        _data = state.pop("_data")
        _nested_assign = state.pop("_nested_assign")
        return cls(_data, nested_assign=_nested_assign, **state)

    def __reduce__(self) -> tuple:
        """Return state information for pickling."""
        return MetaDict.repack_args, (self.__class__, self.__dict__)

    def __dir__(self) -> Iterable[str]:
        """Extend dir list with accessible dict keys (enables autocompletion
        when using dot notation)
        """
        dict_keys = [
            key for key in self._data.keys() if complies_variable_syntax(key)
        ]
        return dir(type(self)) + dict_keys

    def copy(self) -> Self:
        return self.__copy__()

    def __copy__(self) -> Self:
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(
            {k: copy.copy(v) for k, v in self.__dict__.items()}
        )
        return result

    @classmethod
    def fromkeys(
        cls,
        iterable: Iterable[KT],
        value: Optional[VT] = None,
    ) -> Self:
        """Constructor MetaDict form keys iterator.

        Examples:
            >>> def iter_keys() -> Iterable[str]:
            ...     for i in range(3):
            ...         yield f"k{i}"
            >>> MetaDict.fromkeys(iterable=iter_keys())
            {'k0': None, 'k1': None, 'k2': None}
        """
        return cls({key: value for key in iterable})

    def to_dict(self) -> dict:
        return MetaDict._to_object(self._data)

    @staticmethod
    def _to_object(obj: Any) -> Any:
        """Recursively converts all nested MetaDicts to dicts."""

        if isinstance(obj, (list, tuple, set)):
            if MetaDict._contains_mapping(obj):
                value = type(obj)(MetaDict._to_object(x) for x in obj)
            else:
                value = obj
        elif isinstance(obj, Mapping):
            value = {k: MetaDict._to_object(v) for k, v in obj.items()}
        else:
            value = obj

        return value

    def _from_object(self, obj: Any) -> Any:
        """Recursively converts all nested dicts to MetaDicts."""

        if isinstance(obj, (list, tuple, set)):
            if MetaDict._contains_mapping(obj):
                value = type(obj)(self._from_object(x) for x in obj)
            else:
                value = obj
        elif isinstance(obj, MetaDict):
            value = obj
        elif isinstance(obj, Mapping):
            value = self.__class__(
                {k: self._from_object(v) for k, v in obj.items()},
                nested_assign=self._nested_assign,
            )
        else:
            value = obj

        return value

    def _set_nested_assignment(self, val: bool):
        self.__dict__["_nested_assign"] = val
        for value in self.values():
            if isinstance(value, (list, tuple, set)):
                for elem in value:
                    if isinstance(elem, MetaDict):
                        elem._set_nested_assignment(val)
            elif isinstance(value, MetaDict):
                value._set_nested_assignment(val)

    def enable_nested_assignment(self):
        self._set_nested_assignment(True)

    def disable_nested_assignment(self):
        self._set_nested_assignment(False)

    @contextlib.contextmanager
    def enabling_nested_assignment(self):
        """Context manager which temporarily enables nested key/attribute
        assignment.
        """
        nested_assign = self.nested_assign
        if not nested_assign:
            self.enable_nested_assignment()
        try:
            yield self
        finally:
            if not nested_assign:
                self.disable_nested_assignment()

    @property
    def nested_assign(self):
        return self._nested_assign

    @staticmethod
    def _contains_mapping(
        iterable: Iterable, ignore: Optional[type] = None
    ) -> bool:
        """Recursively checks whether an Iterable contains an instance of
        Mapping.
        """
        for x in iterable:
            if isinstance(x, Mapping):
                if ignore is None or not isinstance(x, ignore):
                    return True
            elif isinstance(x, (list, set, tuple)):
                return MetaDict._contains_mapping(x, ignore)
        return False

    # NOTE: Add the following inherited methods from collections.abc.Mapping
    # directly to make pycharm happy to checking.
    # (removing an annoying warning for dict unpacking)
    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def keys(self):
        """D.keys() -> a set-like object providing a view on D's keys"""
        return KeysView(self)

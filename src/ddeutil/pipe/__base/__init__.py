from typing import (
    Protocol,
    TypeVar,
)

ObjectType = TypeVar("ObjectType", bound="ObjectProtocol")


class ObjectProtocol(Protocol):
    parameters: dict

    @classmethod
    def from_data(cls, data: dict) -> ObjectType: ...

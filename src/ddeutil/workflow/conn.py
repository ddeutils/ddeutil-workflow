# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Annotated, Optional

from ddeutil.io import Params
from ddeutil.model.conn import Conn as ConnModel
from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import SecretStr
from typing_extensions import Self

from .__types import DictData, TupleStr
from .loader import SimLoad

EXCLUDED_EXTRAS: TupleStr = ("type",)


class BaseConn(BaseModel):
    """Base Conn (Connection) Model"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    pwd: Optional[str] = None
    endpoint: str
    extras: Annotated[
        DictData,
        Field(default_factory=dict, description="Extras mapping of parameters"),
    ]

    @classmethod
    def from_loader(
        cls,
        name: str,
        params: Params,
        externals: DictData,
    ) -> Self:
        """Construct Connection with Loader object with specific config name.

        :param name:
        :param params:
        :param externals:
        """
        loader: SimLoad = SimLoad(name, params=params, externals=externals)
        filter_data = {
            k: loader.data.pop(k)
            for k in loader.data.copy()
            if k not in cls.model_fields and k not in EXCLUDED_EXTRAS
        }
        if "url" in loader.data:
            url: ConnModel = ConnModel.from_url(loader.data.pop("url"))
            return cls(
                host=url.host,
                port=url.port,
                user=url.user,
                pwd=url.pwd,
                endpoint=url.port,
                # NOTE: This order will show that externals this the top level.
                extras=(url.options | filter_data | externals),
            )
        return cls.model_validate(
            obj={
                "extras": externals,
                **loader.data,
            }
        )


class Conn(BaseConn):
    """Conn (Connection) Model"""


class SSHCred(BaseModel):
    ssh_host: str
    ssh_user: str
    ssh_password: Optional[SecretStr] = Field(default=None)
    ssh_private_key: Optional[str] = Field(default=None)
    ssh_port: int = Field(default=22)


class S3Cred(BaseModel):
    aws_access_key: str
    aws_access_secret_key: SecretStr
    region: str = Field(default="ap-southeast-1")
    role_arn: Optional[str] = Field(default=None)
    role_name: Optional[str] = Field(default=None)
    mfa_serial: Optional[str] = Field(default=None)


class AZServPrinCred(BaseModel):
    tenant: str
    client_id: str
    secret_id: SecretStr


class GoogleCred(BaseModel):
    google_json_path: str

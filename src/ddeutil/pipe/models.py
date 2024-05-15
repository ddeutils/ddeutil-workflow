# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from typing import Any, Optional

from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    model_validator,
)


class BaseLoaderModel(BaseModel):
    type: str
    props: dict[str, Any] = Field(
        default_factory=dict,
        validate_default=True,
    )

    @model_validator(mode="after")
    def root_validate(self):
        return self


class SSHModel(BaseModel):
    ssh_host: str
    ssh_user: str
    ssh_password: Optional[SecretStr] = Field(default=None)
    ssh_private_key: Optional[SecretStr] = Field(default=None)
    ssh_port: int = Field(default=22)


class ConnModel(BaseLoaderModel):
    endpoint: str
    ssh_tunnel: Optional[SSHModel] = Field(default=None)


class ConnFullModel(BaseLoaderModel):
    drivername: str
    host: str
    port: Optional[int] = Field(default=None)
    username: str
    password: SecretStr
    database: str
    ssh_tunnel: Optional[SSHModel] = Field(default=None)


class ConnFullPostgresModel(ConnFullModel):
    drivername: str = Field(default="postgres")


class S3CredentialModel(ConnModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: Optional[str] = Field(default="ap-southeast-1")
    role_arn: Optional[str] = Field(default=None)
    role_name: Optional[str] = Field(default=None)
    mfa_serial: Optional[str] = Field(default=None)

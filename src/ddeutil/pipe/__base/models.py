from typing import Any, Optional, get_type_hints

from ddeutil.core import merge_dict
from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    model_validator,
)

DRIVER_TCP_PORT = {
    "postgres": 5432,
    "mssql": 1433,
    "mysql": 3306,
}


class ModifiedBaseModel(BaseModel):
    def __init__(self, **data: Any) -> None:
        registered, not_registered = self.filter_data(data)
        super().__init__(**registered)
        self.__dict__["props"] = merge_dict(
            self.__dict__["props"],
            not_registered,
        )

    @classmethod
    def filter_data(cls, data) -> tuple[dict[str, Any], dict[str, Any]]:
        registered_attr = {}
        not_registered_attr = {}
        annots = get_type_hints(cls)
        for k, v in data.items():
            if k in annots:
                registered_attr[k] = v
            else:
                not_registered_attr[k] = v
        return registered_attr, not_registered_attr


class BaseLoaderModel(ModifiedBaseModel):
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


# def make_conn_model(data):
#     rs: Optional[Union[ConnModel, ConnDBModel]] = None
#     for model in (
#             ConnModel,
#             ConnDBModel,
#     ):
#         try:
#             rs = model.model_validate(data)
#         except ValidationError:
#             continue
#     if rs is None:
#         raise ConnectionArgumentError(
#             "configuration",
#             "data from config file does not match any Connection Models"
#         )
#     return rs

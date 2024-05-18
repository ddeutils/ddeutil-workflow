import contextlib
from collections import deque
from collections.abc import Iterator
from ftplib import FTP
from stat import S_ISDIR, S_ISREG
from typing import (
    Any,
    Optional,
)

import paramiko
from paramiko.sftp_attr import SFTPAttributes
from pydantic import BaseModel, Field, SecretStr, field_validator
from sshtunnel import BaseSSHTunnelForwarderError, SSHTunnelForwarder


class SSHModel(BaseModel):
    hostname: str
    username: str
    password: SecretStr = Field(default=SecretStr(None))
    private_key: SecretStr = Field(default=SecretStr(None))
    private_key_password: SecretStr = Field(default=SecretStr(None))
    port: int = Field(default=22)

    @field_validator("port", mode="before")
    @classmethod
    def set_port(cls, v: Optional[int]) -> int:
        return v or 22


class FTPServer:
    def __init__(
        self,
        hostname,
        username,
        password,
        port: int = 21,
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

    def fpt_connect(self):
        return FTP(
            host=self.hostname,
            user=self.username,
            passwd=self.password,
        )


class WrapSFTPClient:
    """Wrapped SFTP Client Class"""

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "WrapSFTPClient":
        ssh: SSHModel = SSHModel.model_validate(data)
        return cls(
            hostname=ssh.hostname,
            username=ssh.username,
            port=ssh.port,
            password=ssh.password.get_secret_value(),
            private_key=ssh.private_key.get_secret_value(),
            private_key_password=ssh.private_key_password.get_secret_value(),
        )

    def __init__(
        self,
        hostname: str,
        username: Optional[str] = None,
        port: Optional[int] = None,
        *,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        private_key_password: Optional[str] = None,
    ):
        self.hostname = hostname
        self.username: str = username or ""
        self.port: int = port or 22
        self.password = password

        # Private key path like, ``/home/user/.ssh/id_rsa``.
        self.private_key = private_key

        # If this private key have password, private_key passphrase.
        self.private_key_password = private_key_password

    def get(self, remote_path, local_path):
        with self.ssh_tunnel() as sftp:
            sftp.get(remote_path, local_path)

    def put(self, remote_path, local_path):
        with self.ssh_tunnel() as sftp:
            sftp.put(remote_path, local_path)

    # def read_csv(self, path):
    #     with self.ssh_tunnel_pass() as sftp:
    #         with sftp.open(path, "r+", bufsize=32768) as f:
    #             # Download CSV contents from SFTP to memory
    #             df = pd.read_csv(f)
    #
    #             # Modify as you need (just an example)
    #             df.at[0, 'Name'] = 'changed'
    #
    #             # Upload the in-memory data back to SFTP
    #             f.seek(0)
    #             df.to_csv(f, index=False)
    #
    #             # Truncate the remote file in case the new version of the
    #             # contents is smaller
    #             f.truncate(f.tell())
    #
    # def to_csv(self, path):
    #     # Upload the in-memory data back to SFTP
    #     with self.ssh_tunnel_pass() as sftp:
    #         with sftp.open(path, "w", bufsize=32768) as f:
    #             df.to_csv(f, index=False)

    @contextlib.contextmanager
    def ssh_tunnel(self) -> Iterator:
        try:
            with SSHTunnelForwarder(
                (self.hostname, self.port),
                ssh_username=self.username,
                ssh_password=self.password,
                ssh_pkey=self.private_key,
                ssh_private_key_password=self.private_key_password,
                local_bind_address=("0.0.0.0", 5000),
                # Use a suitable remote_bind_address
                remote_bind_address=("127.0.0.1", 22),
            ) as tunnel:
                tunnel.check_tunnels()
                client = paramiko.SSHClient()
                if self.private_key:
                    client.load_system_host_keys()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    "127.0.0.1",
                    port=tunnel.local_bind_port,
                    **(
                        {
                            "username": self.username,
                            "password": self.password,
                            "allow_agent": False,
                            "look_for_keys": False,
                        }
                        if self.password
                        else {}
                    ),
                )
                with client.open_sftp() as sftp:
                    yield sftp
                client.close()
        except BaseSSHTunnelForwarderError as err:
            raise ValueError(
                "This config data does not connect to the Server"
            ) from err

    def glob(self, pattern: str) -> Iterator[str]:
        with self.ssh_tunnel() as sftp:
            # List files matching the pattern on the SFTP server
            f: SFTPAttributes
            for f in sftp.listdir_attr(pattern):
                yield pattern + f.filename

    def walk(
        self,
        path: str,
    ):
        dirs_to_explore = deque([path])
        list_of_files = deque([])
        with self.ssh_tunnel() as sftp:
            while len(dirs_to_explore) > 0:
                current_dir = dirs_to_explore.popleft()
                for entry in sftp.listdir_attr(current_dir):
                    current_file_or_dir = current_dir + "/" + entry.filename
                    if S_ISDIR(entry.st_mode):
                        dirs_to_explore.append(current_file_or_dir)
                    elif S_ISREG(entry.st_mode):
                        list_of_files.append(current_file_or_dir)
        return list(list_of_files)

    @staticmethod
    def isdir(path: SFTPAttributes):
        try:
            return S_ISDIR(path.st_mode)
        except OSError:
            # Path does not exist, so by definition not a directory
            return False

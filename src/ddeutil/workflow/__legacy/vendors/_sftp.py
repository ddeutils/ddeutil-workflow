import contextlib
from collections import deque
from collections.abc import Iterator
from ftplib import FTP
from stat import S_ISDIR, S_ISREG
from typing import Optional

try:
    import paramiko
    from paramiko.sftp_attr import SFTPAttributes
    from sshtunnel import BaseSSHTunnelForwarderError, SSHTunnelForwarder
except ImportError:
    raise ImportError(
        "Please install paramiko and sshtunnel packages before using"
    ) from None


class FTPServer:
    def __init__(
        self,
        host,
        user,
        pwd,
        port: int = 21,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.pwd = pwd

    def fpt_connect(self):
        return FTP(
            host=self.host,
            user=self.user,
            passwd=self.pwd,
        )


class WrapSFTPClient:
    """Wrapped SFTP Client Class"""

    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        *,
        pwd: Optional[str] = None,
        private_key: Optional[str] = None,
        private_key_password: Optional[str] = None,
    ):
        self.host: str = host
        self.user: str = user or ""
        self.port: int = port or 22
        self.pwd: Optional[str] = pwd

        # Private key path like, ``/home/user/.ssh/id_rsa``.
        self.private_key = private_key

        # If this private key have password, private_key passphrase.
        self.private_key_pwd = private_key_password

    def get(self, remote_path, local_path):
        with self.ssh_tunnel() as sftp:
            sftp.get(remote_path, local_path)

    def put(self, remote_path, local_path):
        with self.ssh_tunnel() as sftp:
            sftp.put(remote_path, local_path)

    @contextlib.contextmanager
    def ssh_tunnel(self) -> Iterator:
        try:
            with SSHTunnelForwarder(
                (self.host, self.port),
                ssh_username=self.user,
                ssh_password=self.pwd,
                ssh_pkey=self.private_key,
                ssh_private_key_password=self.private_key_pwd,
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
                            "username": self.user,
                            "password": self.pwd,
                            "allow_agent": False,
                            "look_for_keys": False,
                        }
                        if self.pwd
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
            # NOTE: List files matching the pattern on the SFTP server
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
            # NOTE: Path does not exist, so by definition not a directory
            return False

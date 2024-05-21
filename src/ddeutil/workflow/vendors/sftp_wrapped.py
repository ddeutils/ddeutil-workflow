import contextlib
from collections import deque
from collections.abc import Generator, Iterator
from ftplib import FTP
from stat import S_ISDIR, S_ISREG
from typing import Optional

try:
    import paramiko
    from paramiko import SFTPAttributes, SFTPClient
    from sshtunnel import BaseSSHTunnelForwarderError, SSHTunnelForwarder
except ImportError:
    raise ImportError(
        "Please install paramiko and sshtunnel packages before using,\n\t\t"
        "$ pip install paramiko sshtunnel"
    ) from None


class WrapFTP:
    """Wrapped FTP Client.

        FTP (File Transfer Protocol) is the standard for transferring files
    between the Client and Server is one of the most popular formats.

        But there is a disadvantage that the data sent and received is not
    encrypted. There is an opportunity for a third party to read the information
    along the transferring.
    """

    def __init__(
        self,
        host: str,
        user: str,
        pwd: str,
        port: int = 21,
    ):
        self.host: str = host
        self.port: int = port
        self.user: str = user
        self.pwd: str = pwd

    def fpt_connect(self):
        return FTP(
            host=self.host,
            user=self.user,
            passwd=self.pwd,
        )


class WrapSFTP:
    """Wrapped SFTP Client.

        SFTP (Secure File Transfer Protocol) it is a standard that helps
    increase security in file transfers. By encrypting data and commands before
    transferring files between the client and server with SSH (Secure Shell),
    we can be confident that the data we upload/download can be done safely.

        It cannot be accessed by third parties or if the information is
    obtained, it is encrypted and cannot be read.

    See-Also:

        This object will wrap the [Paramiko](https://www.paramiko.org/) package
    with my connection interface.
    """

    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        *,
        pwd: Optional[str] = None,
        private_key: Optional[str] = None,
        private_key_password: Optional[str] = None,
    ) -> None:
        self.host: str = host
        self.user: str = user or ""
        self.port: int = port or 22
        self.pwd: Optional[str] = pwd

        # Private key path like, ``/home/user/.ssh/id_rsa``.
        self.private_key = private_key

        # If this private key have password, private_key passphrase.
        self.private_key_pwd = private_key_password

    def get(self, remote_path, local_path):
        with self.transport_client() as sftp:
            sftp.get(remote_path, local_path)

    def put(self, remote_path, local_path):
        with self.transport_client() as sftp:
            sftp.put(remote_path, local_path)

    def rm(self, remote_path: str):
        with self.transport_client() as sftp:
            sftp.remove(remote_path)

    def mkdir(self, remote_path: str):
        with self.transport_client() as sftp:
            sftp.mkdir(remote_path)

    @contextlib.contextmanager
    def ssh_tunnel(self) -> Iterator:
        try:
            with SSHTunnelForwarder(
                (self.host, self.port),
                ssh_username=self.user,
                ssh_password=self.pwd,
                ssh_pkey=self.private_key,
                ssh_private_key_password=self.private_key_pwd,
                local_bind_address=("0.0.0.0", 22),
                # Use a suitable remote_bind_address that able to be DB host on
                # that SSH Server.
                remote_bind_address=("127.0.0.1", self.port),
            ) as tunnel:
                tunnel.check_tunnels()
                client = paramiko.SSHClient()
                if self.private_key:
                    client.load_system_host_keys()
                # NOTE: Add SSH key to known_hosts file.
                client.set_missing_host_key_policy(
                    paramiko.MissingHostKeyPolicy()
                )

                # NOTE: Start connect to SSH Server
                client.connect(
                    "127.0.0.1",
                    port=tunnel.local_bind_port,
                    **(
                        {
                            "username": self.user,
                            "password": self.pwd,
                            "allow_agent": False,
                            "look_for_keys": False,
                            "banner_timeout": 20,
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

    @contextlib.contextmanager
    def transport_client(self) -> Generator[SFTPClient, None, None]:
        with paramiko.Transport(sock=(self.host, self.port)) as transport:
            transport.connect(
                hostkey=None,
                username=self.user,
                password=self.pwd,
            )
            with paramiko.SFTPClient.from_transport(transport) as sftp:
                yield sftp

    @contextlib.contextmanager
    def simple_client(self) -> Generator[SFTPClient, None, None]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.pwd,
        )
        with client.open_sftp() as sftp:
            yield sftp
        client.close()

    def glob(self, pattern: str) -> Iterator[str]:
        with self.transport_client() as sftp:
            try:
                # NOTE: List files matching the pattern on the SFTP server
                f: SFTPAttributes
                for f in sftp.listdir_attr(pattern):
                    yield pattern + f.filename
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Pattern {pattern!r} does not found on SFTP server"
                ) from None

    def walk(self, pattern: str) -> Iterator[str]:
        dirs: deque = deque([pattern])
        with self.transport_client() as sftp:
            while len(dirs) > 0:
                d: str = dirs.popleft()
                f: SFTPAttributes
                for f in sftp.listdir_attr(d):
                    rs: str = (
                        (d + f.filename) if d == "/" else (d + "/" + f.filename)
                    )
                    if S_ISDIR(f.st_mode):
                        dirs.append(rs)
                    elif S_ISREG(f.st_mode):
                        yield rs

    @staticmethod
    def isdir(path: SFTPAttributes):
        try:
            return S_ISDIR(path.st_mode)
        except OSError:
            # NOTE: Path does not exist, so by definition not a directory
            return False

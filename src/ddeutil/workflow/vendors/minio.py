class WarpMinio:

    def __init__(
        self,
        host: str,
        access_key: str,
        secret_access_key: str,
    ):
        self.host: str = host
        self.access_key: str = access_key
        self.secret_access_key: str = secret_access_key

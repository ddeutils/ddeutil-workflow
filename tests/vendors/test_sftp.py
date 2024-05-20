import os

from ddeutil.workflow.__legacy.vendors.sftp import WrapSFTPClient


def test_sftp():
    sftp_storage = WrapSFTPClient(
        host=os.environ["SFTP_HOST"],
        port=22,
        user=os.environ["SFTP_USER"],
        pwd=os.environ["SFTP_PASSWORD"],
    )
    # for f in sftp_storage.glob('/home/deadmin'):
    #     print(f.st_mtime, f.filename)
    for _ in sftp_storage.walk("home/deadmin"):
        print(_)

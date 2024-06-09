import os

from ddeutil.workflow.vendors.wf_sftp import WrapSFTP


def test_sftp():
    sftp = WrapSFTP(
        host=os.getenv("SFTP_HOST"),
        port=int(os.getenv("SFTP_PORT", "22")),
        user=os.getenv("SFTP_USER"),
        pwd=os.getenv("SFTP_PASS"),
    )
    for f in sftp.glob("/"):
        print(f)


def test_client():
    sftp = WrapSFTP(
        host=os.getenv("SFTP_HOST"),
        port=int(os.getenv("SFTP_PORT", "22")),
        user=os.getenv("SFTP_USER"),
        pwd=os.getenv("SFTP_PASS"),
    )
    with sftp.simple_client() as c:
        print(c)

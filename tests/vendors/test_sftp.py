import os
import unittest

from ddeutil.node.vendors.sftp import SSHModel, WrapSFTPClient


class SFTPTestCase(unittest.TestCase):
    def test_ssh_model(self):
        model: SSHModel = SSHModel.model_validate(
            {
                "hostname": "localhost",
                "username": "ec2user",
                "password": "P@ssWord",
                "port": None,
            }
        )
        self.assertEqual("P@ssWord", model.password.get_secret_value())
        self.assertEqual(None, model.private_key.get_secret_value())
        self.assertEqual(None, model.private_key_password.get_secret_value())
        self.assertEqual(22, model.port)

    def test_sftp(self):
        sftp_storage = WrapSFTPClient.from_data(
            data={
                "hostname": os.environ["SFTP_HOST"],
                "port": 22,
                "username": os.environ["SFTP_USER"],
                "password": os.environ["SFTP_PASSWORD"],
            }
        )
        # for f in sftp_storage.glob('/home/deadmin'):
        #     print(f.st_mtime, f.filename)
        for _ in sftp_storage.walk("home/deadmin"):
            print(_)

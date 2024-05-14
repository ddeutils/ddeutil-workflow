import os
import unittest

from ddeutil.node.vendors.boto import WrapBoto3Client
from dotenv import load_dotenv

load_dotenv(".../.env")


class Boto3TestCase(unittest.TestCase):
    def test_s3(self):
        boto_client = WrapBoto3Client(
            access_key_id=os.environ["AWS_ACCESS_ID"],
            secret_access_key=os.environ["AWS_ACCESS_SECRET_KEY"],
        )
        for _ in boto_client.list_objects(
            bucket="trinity-data-de-poc", prefix="glue/spark_log/"
        ):
            print(_)

    def test_s3_exists(self):
        boto_client = WrapBoto3Client(
            access_key_id=os.environ["AWS_ACCESS_ID"],
            secret_access_key=os.environ["AWS_ACCESS_SECRET_KEY"],
        )
        self.assertTrue(
            boto_client.exists(
                "trinity-data-de-poc",
                "glue/spark_log/spark-application-1652112738214.inprogress",
            )
        )
        self.assertFalse(
            boto_client.exists(
                "trinity-data-de-poc",
                "glue/spark_log/spark-application-0000000000000",
            )
        )

    def test_s3_paginate(self):
        boto_client = WrapBoto3Client(
            access_key_id=os.environ["AWS_ACCESS_ID"],
            secret_access_key=os.environ["AWS_ACCESS_SECRET_KEY"],
        )
        boto_client.paginate(
            bucket="trinity-data-de-poc", prefix="glue/spark_log/"
        )

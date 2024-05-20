import os

from ddeutil.workflow.__legacy.vendors.boto import WrapBoto3Client


def test_s3():
    boto_client = WrapBoto3Client(
        access_key_id=os.environ["AWS_ACCESS_ID"],
        secret_access_key=os.environ["AWS_ACCESS_SECRET_KEY"],
    )
    for _ in boto_client.list_objects(
        bucket="trinity-data-de-poc", prefix="glue/spark_log/"
    ):
        print(_)


def test_s3_exists():
    boto_client = WrapBoto3Client(
        access_key_id=os.environ["AWS_ACCESS_ID"],
        secret_access_key=os.environ["AWS_ACCESS_SECRET_KEY"],
    )
    assert boto_client.exists(
        "trinity-data-de-poc",
        "glue/spark_log/spark-application-1652112738214.inprogress",
    )
    assert not (
        boto_client.exists(
            "trinity-data-de-poc",
            "glue/spark_log/spark-application-0000000000000",
        )
    )


def test_s3_paginate():
    boto_client = WrapBoto3Client(
        access_key_id=os.environ["AWS_ACCESS_ID"],
        secret_access_key=os.environ["AWS_ACCESS_SECRET_KEY"],
    )
    boto_client.paginate(bucket="trinity-data-de-poc", prefix="glue/spark_log/")

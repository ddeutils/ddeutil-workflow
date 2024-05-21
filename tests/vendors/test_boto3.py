import os


def test_simple_boto3():
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id=os.getenv("MINIO_USER"),
        aws_secret_access_key=os.getenv("MINIO_PASS"),
        aws_session_token=None,
        config=boto3.session.Config(signature_version="s3v4"),
        verify=False,
    )
    print(s3.list_objects_v2(**{"Bucket": "data"}))


# def test_s3():
#     boto_client = WrapBoto3(
#         access_key_id=os.environ["AWS_ACCESS_ID"],
#         access_secret_key=os.environ["AWS_ACCESS_SECRET_KEY"],
#     )
#     for _ in boto_client.list_objects(
#         bucket="trinity-data-de-poc", prefix="glue/spark_log/"
#     ):
#         print(_)
#
#
# def test_s3_exists():
#     boto_client = WrapBoto3(
#         access_key_id=os.environ["AWS_ACCESS_ID"],
#         access_secret_key=os.environ["AWS_ACCESS_SECRET_KEY"],
#     )
#     assert boto_client.exists(
#         "trinity-data-de-poc",
#         "glue/spark_log/spark-application-1652112738214.inprogress",
#     )
#     assert not (
#         boto_client.exists(
#             "trinity-data-de-poc",
#             "glue/spark_log/spark-application-0000000000000",
#         )
#     )
#
#
# def test_s3_paginate():
#     boto_client = WrapBoto3(
#         access_key_id=os.environ["AWS_ACCESS_ID"],
#         access_secret_key=os.environ["AWS_ACCESS_SECRET_KEY"],
#     )
#     boto_client.paginate(bucket="trinity-data-de-poc", prefix="glue/spark_log/")

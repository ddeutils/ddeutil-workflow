from typing import Any, Optional

try:
    import boto3
    import botocore.exceptions
except ImportError:
    raise ImportError(
        "Please install boto3 package if want to use boto wrapped object.\n\t\t"
        "$ pip install boto3"
    ) from None


class WrapBoto3:
    """Difference in boto3 between resource, client, and session
    docs: https://stackoverflow.com/questions/42809096/
        difference-in-boto3-between-resource-client-and-session

    .. config::

        ~/.aws/credentials

        [my-user]
        aws_access_key_id = AKIAxxx
        aws_secret_access_key = xxx

        [my-role]
        source_profile = my-user
        role_arn = arn:aws:iam::123456789012:role/the-role

        ~/.aws/config

        [profile my-role]
        region = ap-southeast-2
    """

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        region_name: Optional[str] = None,
        *,
        role_session_name: Optional[str] = None,
        role_arn: Optional[str] = None,
        mfa_serial: Optional[str] = None,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region_name: str = region_name or "ap-southeast-1"

        # Optional for session.
        self.role_session_name: str = role_session_name or "AssumeRoleSession"
        self.role_arn = role_arn
        self.mfa_serial = mfa_serial

        # Create credential
        self.cred = self.make_cred()

    def make_cred(self) -> dict[str, str]:
        if self.role_arn is None:
            return {
                "AccessKeyId": self.access_key_id,
                "SecretAccessKey": self.secret_access_key,
            }
        # NOTE: A low-level client representing AWS Security Token Service (STS)
        # >>> sess = boto3.session.Session(
        # ...   aws_access_key_id=ARN_ACCESS_KEY,
        # ...   aws_secret_access_key=ARN_SECRET_KEY
        # ... )
        # >>> sts_client = sess.client('sts')
        sts_client = boto3.client(
            service_name="sts",
            region_name=self.region_name,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )
        mfa_optional: dict[str, str] = {}
        if self.mfa_serial:
            mfa_otp: str = str(input("Enter the MFA code: "))
            mfa_optional = (
                {"SerialNumber": self.mfa_serial, "TokenCode": mfa_otp},
            )
        assumed_role = sts_client.assume_role(
            RoleArn=self.role_arn,
            RoleSessionName=self.role_session_name,
            DurationSeconds=3600,
            **mfa_optional,
        )
        # NOTE: From the response that contains the assumed role, get the
        # temporary credentials that can be used to make subsequent API calls
        return assumed_role["Credentials"]

    @property
    def session(self):
        """Can use by
        ``s3 = self.session.client('s3')``
        ``s3 = self.session.resource('s3')``
        """
        return boto3.session.Session(
            aws_access_key_id=self.cred["AccessKeyId"],
            aws_secret_access_key=self.cred["SecretAccessKey"],
            aws_session_token=self.cred.get("SessionToken"),
        )

    @property
    def s3(self):
        return boto3.client(
            service_name="s3",
            region_name=self.region_name,
            aws_access_key_id=self.cred["AccessKeyId"],
            aws_secret_access_key=self.cred["SecretAccessKey"],
            aws_session_token=self.cred.get("SessionToken"),
        )

    def list_objects(self, bucket: str, prefix: str):
        objs: list[dict[str, Any]] = []
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        while True:
            resp = self.s3.list_objects_v2(**kwargs)
            for obj in resp["Contents"]:
                objs.append(obj)
            try:
                kwargs["ContinuationToken"] = resp["NextContinuationToken"]
            except KeyError:
                break
        return objs

    def paginate(
        self,
        bucket: str,
        prefix: str,
        *,
        marker: Optional[str] = None,
        search: Optional[str] = None,
    ):
        """
        .. docs:
            - https://boto3.amazonaws.com/v1/documentation/api/latest/
                guide/paginators.html

        .. search::
            - "Contents[?Size > `100`][]"
            - "Contents[?contains(LastModified, `'"2022-01-01"'`)]"
            - "Contents[?LastModified>=`YYYY-MM-DD`].Key"
            - "DeleteMarkers[?LastModified>=`2020-07-07T00:00:00`
                && IsLatest==`true`].[Key,VersionId]"
        """
        paginator = self.s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=bucket,
            Prefix=prefix,
            PaginationConfig={
                # 'MaxItems': 10,
                "PageSize": 10,
                "StartingToken": marker,
            },
        )

        for page in page_iterator:
            print("# This is new page")
            print("Contents Count:", len(page["Contents"]))
            if "NextContinuationToken" in page.keys():
                print(page["NextContinuationToken"])

        # filtered_iterator = page_iterator.search("Contents[?Size > `100`][]")
        # for key_data in filtered_iterator:
        #     print(key_data)

        # page_iterator = paginator.paginate(
        #     Bucket=bucket,
        #     Prefix=prefix,
        #     PaginationConfig={
        #         'MaxItems': 10,
        #         'PageSize': 10,
        #         'StartingToken': marker
        #     }
        # )

    def exists(self, bucket: str, prefix: str) -> bool:
        try:
            self.s3.head_object(Bucket=bucket, Key=prefix)
            return True
        except botocore.exceptions.ClientError as err:
            if err.response["Error"]["Code"]:
                return False
            raise

from datetime import datetime
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


def dotenv_setting():
    if not (de := Path("../.env")).exists():
        env_str: str = dedent(
            """
            SFTP_HOST='50.100.200.123'
            SFTP_USER='bastion'
            SFTP_PASSWORD='P@ssW0rd'

            AWS_ACCESS_ID='dummy_access_id'
            AWS_ACCESS_SECRET_KEY='dummy_access_secret_key'
            """
        ).strip()
        de.write_text(env_str)
    load_dotenv("../.env")


def str2dt(value):
    return datetime.fromisoformat(value).replace(
        tzinfo=ZoneInfo("Asia/Bangkok")
    )

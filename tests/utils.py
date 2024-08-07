import logging
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

OUTSIDE_PATH: Path = Path(__file__).parent.parent


def dotenv_setting() -> None:
    env_path: Path = OUTSIDE_PATH / ".env"
    if not env_path.exists():
        logging.warning("Dot env file does not exists")
        # NOTE: for ROOT_PATH value on the different OS:
        #   * Windows: D:\user\path\...\ddeutil-workflow
        #   * Ubuntu: /home/runner/work/ddeutil-workflow/ddeutil-workflow
        env_str: str = dedent(
            f"""
            WORKFLOW_ROOT_PATH={OUTSIDE_PATH.resolve()}
            WORKFLOW_CORE_REGISTRY="ddeutil.workflow,tests"
            WORKFLOW_CORE_PATH_CONF=tests/conf

            SFTP_HOST='50.100.200.123'
            SFTP_USER='bastion'
            SFTP_PASSWORD='P@ssW0rd'

            AWS_ACCESS_ID='dummy_access_id'
            AWS_ACCESS_SECRET_KEY='dummy_access_secret_key'
            """
        ).strip()
        env_path.write_text(env_str)
    load_dotenv(env_path)


def str2dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Bangkok"))

# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from .utils import dotenv_setting, dump_yaml_context

dotenv_setting()


@pytest.fixture(scope="session")
def root_path() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_path(root_path) -> Path:
    return root_path / "tests"


@pytest.fixture(scope="session")
def conf_path(test_path: Path) -> Path:
    return test_path / "conf"


@pytest.fixture(scope="session", autouse=True)
def create_cron_yaml(conf_path: Path):
    with dump_yaml_context(
        conf_path / "demo/02_cron.yml",
        data="""
        every_5_minute_bkk:
          type: Crontab
          cronjob: "*/5 * * * *"
          timezone: "Asia/Bangkok"

        every_minute_bkk:
          type: Crontab
          cronjob: "* * * * *"
          timezone: "Asia/Bangkok"

        every_2_minute_bkk:
          type: Crontab
          cronjob: "*/2 * * * *"
          timezone: "Asia/Bangkok"

        every_3_minute_bkk:
          type: Crontab
          cronjob: "*/3 * * * *"
          timezone: "Asia/Bangkok"

        every_hour_bkk:
          type: Crontab
          cronjob: "0 * * * *"
          timezone: "Asia/Bangkok"

        every_day_noon:
          type: Crontab
          interval: "monthly"
          day: "monday"
          time: "12:00"
          timezone: "Etc/UTC"

        aws_every_5_minute_bkk:
          type: CrontabYear
          cronjob: "*/5 * * * * 2024"
          timezone: "Asia/Bangkok"
        """,
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def create_workflow_yaml(conf_path: Path):
    with dump_yaml_context(
        conf_path / "demo/01_workflow.yml",
        data="""
        wf-scheduling:
          type: Workflow
          on:
            - 'every_3_minute_bkk'
            - 'every_minute_bkk'
          params:
            asat-dt: datetime
          jobs:
            condition-job:
              stages:
                - name: "Empty stage"
                - name: "Call-out"
                  echo: "Hello ${{ params.asat-dt | fmt('%Y-%m-%d') }}"

        wf-scheduling-agent:
          type: Workflow
          params:
            name: str
            asat-dt: datetime
          jobs:
            condition-job:
              stages:
                - name: "Call Out"
                  id: "call-out"
                  echo: "Hello ${{ params.name }}: ${{ params.asat-dt | fmt('%Y-%m-%d') }}"
        """,
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def create_schedule_yaml(conf_path: Path):
    with dump_yaml_context(
        conf_path / "demo/03_schedule.yml",
        data="""
        schedule-wf:
          type: Schedule
          desc: |
            # First Schedule template

            The first schedule config template for testing scheduler function able to
            use it
          workflows:
            - name: 'wf-scheduling'
              on: ['every_3_minute_bkk', 'every_minute_bkk']
              params:
                asat-dt: "${{ release.logical_date }}"

        schedule-common-wf:
          type: Schedule
          workflows:
            - name: 'wf-scheduling'
              on: 'every_3_minute_bkk'
              params:
                asat-dt: "${{ release.logical_date }}"

        schedule-multi-on-wf:
          type: Schedule
          workflows:
            - name: 'wf-scheduling-agent'
              on: ['every_minute_bkk', 'every_3_minute_bkk']
              params:
                name: "Foo"
                asat-dt: "${{ release.logical_date }}"

        schedule-every-minute-wf:
          type: Schedule
          workflows:
            - name: 'wf-scheduling-agent'
              on: 'every_minute_bkk'
              params:
                name: "Foo"
                asat-dt: "${{ release.logical_date }}"

        schedule-every-minute-wf-parallel:
          type: Schedule
          workflows:
            - alias: 'agent-01'
              name: 'wf-scheduling-agent'
              on: 'every_minute_bkk'
              params:
                name: "First"
                asat-dt: "${{ release.logical_date }}"
            - alias: 'agent-02'
              name: 'wf-scheduling-agent'
              on: 'every_minute_bkk'
              params:
                name: "Second"
                asat-dt: "${{ release.logical_date }}"
        """,
    ):
        yield


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Ref: https://guicommits.com/parallelize-pytest-tests-github-actions/"""
    # 👇 Make these vars optional so locally we don't have to set anything
    current_worker = int(os.getenv("GITHUB_WORKER_ID", 0)) - 1
    total_workers = int(os.getenv("GITHUB_TOTAL_WORKERS", 0))

    # 👇 If there's no workers we can affirm we won't split
    if total_workers:
        # 👇 Decide how many tests per worker
        num_tests = len(items)
        matrix_size = math.ceil(num_tests / total_workers)

        # 👇 Select the test range with start and end
        start = current_worker * matrix_size
        end = (current_worker + 1) * matrix_size

        # 👇 Set how many tests are going to be deselected
        deselected_items = items[:start] + items[end:]
        config.hook.pytest_deselected(items=deselected_items)

        # 👇 Set which tests are going to be handled
        items[:] = items[start:end]
        print(f" Executing {start} - {end} tests")

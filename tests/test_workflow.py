import shutil
from datetime import datetime
from pathlib import Path

import pytest
from ddeutil.workflow import SKIP, SUCCESS, Job, Result, Workflow
from ddeutil.workflow.errors import WorkflowError
from ddeutil.workflow.event import Event
from pydantic import ValidationError

from .utils import dump_yaml, dump_yaml_context


def test_workflow():
    job: Job = Job(
        stages=[
            {"name": "Run Hello World", "run": "print(f'Hello {x}')\n"},
            {
                "name": "Run Sequence and use var from Above",
                "id": "run-stage",
                "run": (
                    "print(f'Receive x from above with {x}')\n\n" "x: int = 1\n"
                ),
            },
        ],
    )
    workflow: Workflow = Workflow(
        name="manual-workflow",
        jobs={
            "demo-run": job,
            "next-run": {
                "stages": [
                    {
                        "name": "Set variable and function",
                        "run": (
                            "var: str = 'Foo'\n"
                            "def echo() -> None:\n\tprint(f'Echo {var}')\n"
                        ),
                    },
                    {"name": "Call that variable", "run": "echo()\n"},
                ]
            },
        },
    )

    assert workflow.name == "manual-workflow"

    set_job_id = job.model_copy()
    set_job_id.id = "demo-run"
    assert workflow.job("demo-run") == set_job_id

    # NOTE: Raise ValueError when get a job with ID that does not exist.
    with pytest.raises(ValueError):
        workflow.job("not-found-job-id")

    # NOTE: Raise when name of workflow include any template parameter syntax.
    with pytest.raises(ValidationError):
        Workflow(name="manual-workflow-${{ params.test }}")

    with pytest.raises(ValidationError):
        Workflow(name="manual-workflow-${{ matrix.name }}")

    # NOTE: Raise because type of params does not valid.
    with pytest.raises(ValidationError):
        Workflow.model_validate(
            obj={
                "name": "manual-workflow",
                "jobs": {"demo-run": job},
                "params": (1, 2, 3),
            }
        )


def test_workflow_bypass_extras():
    job: Job = Job(
        stages=[{"name": "Echo", "id": "echo", "echo": "Hello World"}]
    )
    event = Event.model_validate(
        obj={
            "schedule": [
                {
                    "cronjob": "* * * * *",
                    "timezone": "Asia/Bangkok",
                },
                {
                    "cronjob": "* * * * * 2025",
                    "timezone": "Asia/Bangkok",
                },
            ]
        }
    )

    # NOTE: Test passing extra value from workflow is work.
    workflow: Workflow = Workflow(
        name="manual-workflow",
        on=event,
        jobs={"first-job": job, "second-job": job},
        extras={"registries": ["foo", "bar"]},
    )
    assert workflow.jobs["first-job"].extras == {}

    # NOTE: Bypass extras to job model.
    assert workflow.job("first-job").extras == {"registries": ["foo", "bar"]}
    assert workflow.job("second-job").extras == {"registries": ["foo", "bar"]}

    assert workflow.job("first-job").stages[0].extras == {}

    # NOTE: Bypass extras to stage model.
    assert workflow.job("first-job").stage("echo").extras == {
        "registries": ["foo", "bar"]
    }


def test_workflow_on():

    # NOTE: Raise when the on field receive duplicate values.
    with pytest.raises(ValidationError):
        Workflow.model_validate(
            {
                "name": "tmp-wf-scheduling-raise",
                "on": {
                    "schedule": [
                        {"cronjob": "2 * * * *"},
                        {"cronjob": "2 * * * *"},
                    ],
                },
            }
        )

    # NOTE: Raise if values on the on field reach the maximum value.
    with pytest.raises(ValidationError):
        Workflow(
            name="tmp-wf-on-reach-max-value",
            on={
                "schedule": [
                    {"cronjob": "2 * * * *"},
                    {"cronjob": "3 * * * *"},
                    {"cronjob": "4 * * * *"},
                    {"cronjob": "5 * * * *"},
                    {"cronjob": "6 * * * *"},
                    {"cronjob": "7 * * * *"},
                    {"cronjob": "8 * * * *"},
                    {"cronjob": "9 * * * *"},
                    {"cronjob": "10 * * * *"},
                    {"cronjob": "11 * * * *"},
                    {"cronjob": "12 * * * *"},
                ],
            },
        )

    # NOTE: Raise if values on the on field have multiple timezone.
    with pytest.raises(ValidationError):
        Workflow(
            name="tmp-wf-on-multiple-tz",
            on={
                "schedule": [
                    {"cronjob": "2 * * * *", "timezone": "UTC"},
                    {"cronjob": "3 * * * *", "timezone": "Asia/Bangkok"},
                ],
            },
        )


def test_workflow_desc():
    workflow = Workflow.from_conf(name="wf-run-common")
    assert workflow.desc == (
        "## Run Python Workflow\n\nThis is a running python workflow\n"
    )
    print(workflow.created_at.tzinfo)
    assert workflow.created_at < datetime.now()


def test_workflow_from_conf_without_job():
    workflow = Workflow(name="wf-without-jobs")
    rs: Result = workflow.execute({})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS, "params": {}, "jobs": {}}


def test_workflow_from_conf_override(test_path):
    conf_path: Path = test_path / "mock_conf"
    conf_path.mkdir(exist_ok=True)
    (conf_path / "demo").mkdir(exist_ok=True)

    with dump_yaml_context(
        conf_path / "demo/01_99_wf_test_override_config.yml",
        data="""
        tmp-wf-override-conf:
          type: Workflow
          param: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello"
                  echo: "Hello ${{ params.name }}"

        tmp-wf-override-conf-trigger:
          type: Workflow
          params: {name: str}
          jobs:
            trigger-job:
              stages:
                - name: "Trigger override"
                  id: trigger-stage
                  trigger: tmp-wf-override-conf
                  params:
                    name: ${{ params.name }}
        """,
    ):
        workflow = Workflow.from_conf(
            name="tmp-wf-override-conf", extras={"conf_path": conf_path}
        )
        rs: Result = workflow.execute(params={"name": "foo"})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {"name": "foo"},
            "jobs": {
                "first-job": {
                    "status": SUCCESS,
                    "stages": {
                        "1926515049": {"outputs": {}, "status": SUCCESS}
                    },
                }
            },
        }

        workflow = Workflow.from_conf(
            name="tmp-wf-override-conf-trigger", extras={"conf_path": conf_path}
        )
        stage = workflow.job(name="trigger-job").stage("trigger-stage")
        assert stage.extras == {"conf_path": conf_path}

        rs: Result = workflow.execute(params={"name": "bar"})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {"name": "bar"},
            "jobs": {
                "trigger-job": {
                    "status": SUCCESS,
                    "stages": {
                        "trigger-stage": {
                            "status": SUCCESS,
                            "outputs": {
                                "params": {"name": "bar"},
                                "jobs": {
                                    "first-job": {
                                        "status": SUCCESS,
                                        "stages": {
                                            "1926515049": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            }
                                        },
                                    }
                                },
                            },
                        }
                    },
                }
            },
        }

    shutil.rmtree(conf_path)


def test_workflow_from_conf_raise(test_path):
    test_file = test_path / "conf/demo/01_01_wf_run_raise.yml"

    # NOTE: Raise for type of workflow does not valid.
    dump_yaml(
        test_file,
        data={
            "wf-run-from-loader-raise": {
                "type": "Crontab",
                "jobs": {
                    "first-job": {
                        "stages": [{"name": "Echo next", "echo": "Hello World"}]
                    }
                },
            }
        },
    )

    # Note: Raise because the type of config data does not match with model.
    with pytest.raises(ValueError):
        Workflow.from_conf(name="wf-run-from-loader-raise")

    # NOTE: Raise if type of the on field does not valid with str or dict.
    dump_yaml(
        test_file,
        data={
            "wf-run-from-loader-raise": {
                "type": "Workflow",
                "on": {
                    "schedule": [
                        ["* * * * *"],
                        ["* * 1 0 0"],
                    ],
                },
                "jobs": {
                    "first-job": {
                        "stages": [{"name": "Echo next", "echo": "Hello World"}]
                    }
                },
            }
        },
    )

    with pytest.raises(ValidationError):
        Workflow.from_conf(name="wf-run-from-loader-raise")

    with pytest.raises(ValidationError):
        Workflow.from_conf(
            name="wf-run-from-loader-raise",
            path=test_path / "conf",
        )

    # NOTE: Raise if value of the on field does not parse to the CronJob obj.
    dump_yaml(
        test_file,
        data={
            "wf-run-from-loader-raise": {
                "type": "Workflow",
                "jobs": {
                    "first-job": {
                        "needs": ["not-found"],
                        "stages": [
                            {"name": "Echo next", "echo": "Hello World"}
                        ],
                    }
                },
            }
        },
    )

    with pytest.raises(WorkflowError):
        Workflow.from_conf(name="wf-run-from-loader-raise")

    with pytest.raises(WorkflowError):
        Workflow.from_conf(
            name="wf-run-from-loader-raise",
            path=test_path / "conf",
        )

    # NOTE: Remove the testing file on the demo path.
    test_file.unlink(missing_ok=True)


def test_workflow_condition():
    workflow = Workflow(
        name="tmp-wf-condition",
        params={"name": "str"},
        jobs={
            "condition-job": {
                "stages": [
                    {
                        "name": "Condition Stage",
                        "id": "condition-stage",
                        "if": '"${{ params.name }}" == "foo"',
                        "run": (
                            "message: str = 'Hello World'\n" "print(message)\n"
                        ),
                    }
                ]
            }
        },
    )
    rs: Result = workflow.execute(params={"name": "bar"})
    assert rs.context == {
        "status": SKIP,
        "params": {"name": "bar"},
        "jobs": {
            "condition-job": {
                "status": SKIP,
                "stages": {
                    "condition-stage": {"outputs": {}, "status": SKIP},
                },
            },
        },
    }

    rs: Result = workflow.execute(params={"name": "foo"})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"name": "foo"},
        "jobs": {
            "condition-job": {
                "status": SUCCESS,
                "stages": {
                    "condition-stage": {
                        "status": SUCCESS,
                        "outputs": {"message": "Hello World"},
                    }
                },
            },
        },
    }


def test_workflow_parameterize(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_parameterize.yml",
        data="""
        tmp-wf-params-required:
          type: Workflow
          params:
            name: {type: str, required: True}
          jobs:
            first-job:
              stages:
                - name: Echo
                  echo: "Hello ${{ params.name }}"
        """,
    ):
        workflow: Workflow = Workflow.from_conf(name="tmp-wf-params-required")

        assert workflow.parameterize({"name": "foo"}) == {
            "params": {"name": "foo"},
            "jobs": {},
        }

        # NOTE: Raise if passing parameter that does not set on the workflow.
        with pytest.raises(WorkflowError):
            workflow.parameterize({"foo": "bar"})


def test_workflow_detail(test_path):
    workflow = Workflow.from_conf(
        "stream-workflow", path=test_path / "conf/example"
    )
    print(workflow.detail())


def test_workflow_markdown(test_path):
    workflow = Workflow.from_conf(
        "stream-workflow", path=test_path / "conf/example"
    )
    md_file: Path = test_path / "stream-workflow.md"
    with md_file.open(mode="w") as f:
        f.write(workflow.md())

    md_file.unlink(missing_ok=True)

import pytest
from ddeutil.workflow import FAILED, SUCCESS, Result, Workflow
from ddeutil.workflow.stages import CallStage, Stage
from pydantic import ValidationError

from ..utils import dump_yaml_context


def test_call_stage_exec_necessary_args():
    stage: Stage = CallStage.model_validate(
        {
            "name": "Necessary argument do not pass",
            "id": "private-args",
            "uses": "tasks/private-args-task@demo",
            "with": {"params": {"run_mode": "T"}},
        }
    )
    # NOTE: Raise because necessary args do not pass.
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": (
                "Necessary params, (_exec, params, ), does not "
                "set to args. It already set ['params']."
            ),
        },
    }


def test_call_stage_exec(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_return_type.yml",
        data="""
        tmp-wf-call-return-type:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Private args should pass"
                  id: args-private
                  uses: tasks/private-args-task@demo
                  with:
                    params:
                      run_mode: "T"
                    exec: "Test this arge should pass"
            second-job:
              stages:
                - name: "Extract & Load Local System"
                  id: extract-load
                  uses: tasks/simple-task@demo
                  with:
                    source: src
                    sink: sink
                - name: "Extract & Load Local System"
                  id: async-extract-load
                  uses: tasks/simple-task-async@demo
                  with:
                    source: src
                    sink: sink
                - name: "Extract & Load Local System"
                  id: extract-load-raise-type
                  uses: tasks/simple-task@demo
                  with:
                    source: 1
                    sink: sink
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-return-type")

        stage: Stage = workflow.job("second-job").stage("extract-load")
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {"records": 1, "status": SUCCESS}

        stage: Stage = workflow.job("second-job").stage("async-extract-load")
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {"records": 1, "status": SUCCESS}

        stage: Stage = workflow.job("first-job").stage("args-private")
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {
            "exec": "Test this arge should pass",
            "params": {"run_mode": "T"},
            "status": SUCCESS,
        }

        # NOTE: Raise because type of args not valid.
        stage: Stage = workflow.job("second-job").stage(
            "extract-load-raise-type"
        )
        rs = stage.handler_execute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "StageError",
                "message": (
                    "Validate argument from the caller function raise invalid "
                    "type."
                ),
            },
        }

        stage: Stage = CallStage.model_validate(
            {
                "name": "Return with Pydantic Model",
                "id": "return-model",
                "uses": "tasks/gen-type@demo",
                "with": {
                    "args1": "foo",
                    "args2": "conf/path",
                    "args3": {"name": "test", "data": {"input": "hello"}},
                },
            }
        )
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "name": "foo",
            "data": {"key": "value"},
        }


def test_call_stage_exec_raise():
    # NOTE: Raise because invalid return type.
    stage: Stage = CallStage(
        name="Type not valid",
        uses="tasks/return-type-not-valid@raise",
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "message": (
                "Return type: 'return-type-not-valid@raise' can not "
                "serialize, you must set return be `dict` or Pydantic "
                "model."
            ),
            "name": "TypeError",
        },
    }

    # NOTE: Raise because call does not valid.
    stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": (
                "Call 'tasks-foo-bar' does not match with the call regex format."
            ),
        },
    }

    # NOTE: Raise because call does not register.
    stage: Stage = CallStage(
        name="Not register",
        uses="tasks/abc@foo",
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "NotImplementedError",
            "message": "`REGISTERS.tasks.registries` not implement registry: 'abc'.",
        },
    }

    # NOTE: Raise because passing special arguments.
    with pytest.raises(ValidationError):
        CallStage.model_validate(
            {
                "name": "Type not valid",
                "uses": "tasks/return-type-not-valid@raise",
                "with": {"result": "foo"},
            }
        )


@pytest.mark.asyncio
async def test_call_stage_axec(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_return_type.yml",
        data="""
        tmp-wf-call-return-type:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Necessary argument do not pass"
                  id: args-necessary
                  uses: tasks/private-args-task@demo
                  with:
                    params:
                      run_mode: "T"
            second-job:
              stages:
                - name: "Extract & Load Local System"
                  id: extract-load
                  uses: tasks/simple-task@demo
                  with:
                    source: src
                    sink: sink
                - name: "Extract & Load Local System"
                  id: async-extract-load
                  uses: tasks/simple-task-async@demo
                  with:
                    source: src
                    sink: sink
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-return-type")

        stage: Stage = workflow.job("second-job").stage("extract-load")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == SUCCESS
        assert rs.context == {"records": 1, "status": SUCCESS}

        stage: Stage = workflow.job("second-job").stage("async-extract-load")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == SUCCESS
        assert rs.context == {"records": 1, "status": SUCCESS}

        # NOTE: Raise because invalid return type.
        stage: Stage = CallStage(
            name="Type not valid", uses="tasks/return-type-not-valid@raise"
        )
        rs: Result = await stage.handler_axecute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "TypeError",
                "message": "Return type: 'return-type-not-valid@raise' can not serialize, you must set return be `dict` or Pydantic model.",
            },
        }

        # NOTE: Raise because necessary args do not pass.
        stage: Stage = workflow.job("first-job").stage("args-necessary")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "ValueError",
                "message": "Necessary params, (_exec, params, ), does not set to args. It already set ['params'].",
            },
        }

        stage: Stage = workflow.job("first-job").stage("args-necessary")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "ValueError",
                "message": (
                    "Necessary params, (_exec, params, ), does not set to "
                    "args. It already set ['params']."
                ),
            },
        }

        # NOTE: Raise because call does not valid.
        stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "ValueError",
                "message": "Call 'tasks-foo-bar' does not match with the call regex format.",
            },
        }

        stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "ValueError",
                "message": "Call 'tasks-foo-bar' does not match with the call regex format.",
            },
        }

        # NOTE: Raise because call does not register.
        stage: Stage = CallStage(name="Not register", uses="tasks/abc@foo")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "NotImplementedError",
                "message": "`REGISTERS.tasks.registries` not implement registry: 'abc'.",
            },
        }

        stage: Stage = CallStage.model_validate(
            {
                "name": "Return with Pydantic Model",
                "id": "return-model",
                "uses": "tasks/gen-type@demo",
                "with": {
                    "args1": "foo",
                    "args2": "conf/path",
                    "args3": {"name": "test", "data": {"input": "hello"}},
                },
            }
        )
        rs: Result = await stage.handler_axecute({})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "name": "foo",
            "data": {"key": "value"},
        }

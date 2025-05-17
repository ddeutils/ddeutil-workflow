from inspect import isfunction

import pytest
from ddeutil.workflow import FAILED, SUCCESS, Result, Workflow
from ddeutil.workflow.stages import PyStage, Stage


def test_py_stage_exec_raise():
    stage: PyStage = PyStage(
        name="Raise Error Inside",
        id="raise-error",
        run="raise ValueError('Testing raise error inside PyStage!!!')",
    )

    rs = stage.handler_execute(params={"x": "Foo"})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": "Testing raise error inside PyStage!!!",
        },
    }

    output = stage.set_outputs(rs.context, {})
    assert output == {
        "stages": {
            "raise-error": {
                "status": FAILED,
                "outputs": {},
                "errors": {
                    "name": "ValueError",
                    "message": "Testing raise error inside PyStage!!!",
                },
            },
        },
    }


def test_py_stage_exec():
    stage: PyStage = PyStage(
        name="Run Sequence and use var from Above",
        id="run-var",
        vars={"x": "${{ stages.hello-world.outputs.x }}"},
        run=(
            "print(f'Receive x from above with {x}')\n\n"
            "# Change x value\nx: int = 1\n"
            'result.trace.info("Log from result object inside PyStage!!!")'
        ),
    )
    rs: Result = stage.handler_execute(
        params={
            "params": {"name": "Author"},
            "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
        }
    )
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS, "locals": {"x": 1}, "globals": {}}

    output = stage.set_outputs(rs.context, to={})
    assert output == {
        "stages": {"run-var": {"outputs": {"x": 1}, "status": SUCCESS}}
    }


def test_py_stage_exec_create_func():
    stage: PyStage = PyStage(
        name="Set variable and function",
        id="create-func",
        run=(
            "var_inside: str = 'Create Function Inside'\n"
            'def echo(var: str) -> None:\n\tprint(f"Echo {var}")\n'
            "echo(var_inside)"
        ),
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == SUCCESS

    output = stage.set_outputs(rs.context, {})
    assert isfunction(output["stages"]["create-func"]["outputs"]["echo"])
    assert (
        output["stages"]["create-func"]["outputs"]["var_inside"]
        == "Create Function Inside"
    )


def test_py_stage_exec_create_object():
    workflow: Workflow = Workflow.from_conf(name="wf-run-python-filter")
    stage: Stage = workflow.job("create-job").stage(stage_id="create-stage")
    rs: Result = stage.handler_execute(params={})
    assert rs.status == SUCCESS

    output = stage.set_outputs(rs.context, to={})
    assert len(output["stages"]["create-stage"]["outputs"]) == 1


@pytest.mark.asyncio
async def test_py_stage_axec_not_raise():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")

    rs: Result = await stage.handler_axecute(params={"x": "Foo"})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": "Testing raise error inside PyStage!!!",
        },
    }

    output = stage.set_outputs(rs.context, {})
    assert output == {
        "stages": {
            "raise-error": {
                "status": FAILED,
                "outputs": {},
                "errors": {
                    "name": "ValueError",
                    "message": "Testing raise error inside PyStage!!!",
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_py_stage_axec_with_vars():
    stage: Stage = (
        Workflow.from_conf(name="wf-run-common")
        .job("demo-run")
        .stage("run-var")
    )
    rs: Result = await stage.handler_axecute(
        params={
            "params": {"name": "Author"},
            "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
        }
    )
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS, "locals": {"x": 1}, "globals": {}}

    output = stage.set_outputs(rs.context, to={})
    assert output == {
        "stages": {"run-var": {"outputs": {"x": 1}, "status": SUCCESS}}
    }

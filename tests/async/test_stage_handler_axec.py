import pytest
from ddeutil.workflow import (
    FAILED,
    SUCCESS,
    BashStage,
    CallStage,
    EmptyStage,
    RaiseStage,
    Result,
    Stage,
    StageError,
    Workflow,
)

from ..utils import dump_yaml_context


@pytest.mark.asyncio
async def test_empty_stage_axec():
    stage: EmptyStage = EmptyStage(name="Empty Stage")
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}

    stage: EmptyStage = EmptyStage(name="Empty Stage", echo="hello world")
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage", echo="hello world", sleep=5.01
    )
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage",
        echo=(
            "Hello World\nThis is the newline message.\nI want to test newline "
            "string doing well."
        ),
        sleep=0.01,
    )
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}


@pytest.mark.asyncio
async def test_bash_stage_axec():
    stage: BashStage = BashStage(name="Bash Stage", bash='echo "Hello World"')
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS


@pytest.mark.asyncio
async def test_bash_stage_axec_raise():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Test Raise Error case with failed" >&2;\n' "exit 1;",
    )

    # NOTE: Raise error from bash that force exit 1.
    with pytest.raises(StageError):
        await stage.handler_axecute({}, raise_error=True)

    rs: Result = await stage.handler_axecute({}, raise_error=False)
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "StageError",
            "message": (
                "Subprocess: Test Raise Error case with failed\n"
                "---( statement )---\n"
                '```bash\necho "Test Raise Error case with failed" >&2;\n'
                "exit 1;\n"
                "```"
            ),
        }
    }


@pytest.mark.asyncio
async def test_raise_stage_axec():
    stage: RaiseStage = RaiseStage.model_validate(
        {"name": "Raise Stage", "raise": "This is test message error"}
    )
    rs: Result = await stage.handler_axecute(params={}, raise_error=False)
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "StageError",
            "message": "This is test message error",
        },
    }

    with pytest.raises(StageError):
        await stage.handler_axecute(params={}, raise_error=True)


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
                  uses: tasks/mssql-proc@odbc
                  with:
                    params:
                      run_mode: "T"
                      run_date: 2024-08-01
                      source: src
                      target: tgt
            second-job:
              stages:
                - name: "Extract & Load Local System"
                  id: extract-load
                  uses: tasks/el-csv-to-parquet@polars-dir
                  with:
                    source: src
                    sink: sink
                - name: "Extract & Load Local System"
                  id: async-extract-load
                  uses: tasks/async-el-csv-to-parquet@polars-dir
                  with:
                    source: src
                    sink: sink
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-return-type")

        stage: Stage = workflow.job("second-job").stage("extract-load")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == SUCCESS
        assert {"records": 1} == rs.context

        stage: Stage = workflow.job("second-job").stage("async-extract-load")
        rs: Result = await stage.handler_axecute({})
        assert rs.status == SUCCESS
        assert rs.context == {"records": 1}

        # NOTE: Raise because invalid return type.
        with pytest.raises(StageError):
            stage: Stage = CallStage(
                name="Type not valid", uses="tasks/return-type-not-valid@raise"
            )
            await stage.handler_axecute({}, raise_error=True)

        # NOTE: Raise because necessary args do not pass.
        with pytest.raises(StageError):
            stage: Stage = workflow.job("first-job").stage("args-necessary")
            await stage.handler_axecute({}, raise_error=True)

        stage: Stage = workflow.job("first-job").stage("args-necessary")
        rs: Result = await stage.handler_axecute({}, raise_error=False)
        assert rs.status == FAILED
        assert rs.context == {
            "errors": {
                "name": "ValueError",
                "message": (
                    "Necessary params, (_exec, params, result, ), does not set to args, "
                    "['result', 'params']."
                ),
            },
        }

        # NOTE: Raise because call does not valid.
        with pytest.raises(StageError):
            stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
            await stage.handler_axecute({}, raise_error=True)

        stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
        rs: Result = await stage.handler_axecute({}, raise_error=False)
        assert rs.status == FAILED
        assert rs.context == {
            "errors": {
                "name": "ValueError",
                "message": "Call 'tasks-foo-bar' does not match with the call regex format.",
            },
        }

        # NOTE: Raise because call does not register.
        with pytest.raises(StageError):
            stage: Stage = CallStage(name="Not register", uses="tasks/abc@foo")
            await stage.handler_axecute({})

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
        assert rs.context == {"name": "foo", "data": {"key": "value"}}


@pytest.mark.asyncio
async def test_py_stage_axec_not_raise():
    workflow: Workflow = Workflow.from_conf(
        name="wf-run-common", extras={"stage_raise_error": False}
    )
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")

    rs: Result = await stage.handler_axecute(params={"x": "Foo"})
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "ValueError",
            "message": "Testing raise error inside PyStage!!!",
        }
    }

    output = stage.set_outputs(rs.context, {})
    assert output == {
        "stages": {
            "raise-error": {
                "outputs": {},
                "errors": {
                    "name": "ValueError",
                    "message": "Testing raise error inside PyStage!!!",
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_stage_py_axec_with_vars():
    stage: Stage = (
        Workflow.from_conf(name="wf-run-common")
        .job("demo-run")
        .stage("run-var")
    )
    rs = stage.set_outputs(
        (
            await stage.handler_axecute(
                params={
                    "params": {"name": "Author"},
                    "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
                }
            )
        ).context,
        to={},
    )
    assert rs == {"stages": {"run-var": {"outputs": {"x": 1}}}}

from threading import Event

import pytest
from ddeutil.workflow import CANCEL, FAILED, SUCCESS, Result
from ddeutil.workflow.stages import CallStage, Stage
from pydantic import ValidationError


def test_call_stage_validate_args():
    with pytest.raises(ValidationError):
        CallStage.model_validate(
            {
                "name": "Special argument should not pass",
                "uses": "tasks/special-args-task@demo",
                "with": {"result": "${{ params.foo }}"},
            }
        )

    with pytest.raises(ValidationError):
        CallStage.model_validate(
            {
                "name": "Necessary argument should not pass",
                "uses": "tasks/special-args-task@demo",
                "with": {"extras": "${{ params.foo }}"},
            }
        )

    with pytest.raises(ValidationError):
        CallStage.model_validate(
            {
                "name": "Necessary argument should not pass",
                "uses": "tasks/special-args-task@demo",
                "with": (("test", "value"), ("foo", "bar")),
            }
        )


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
    rs: Result = stage.execute({})
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

    stage: Stage = CallStage.model_validate(
        {
            "name": "Necessary argument do not pass",
            "id": "private-args",
            "uses": "tasks/private-args-task-not-special@demo",
            "with": {"params": {"run_mode": "T"}},
        }
    )
    rs: Result = stage.execute({})
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


def test_call_stage_exec():
    stage: Stage = CallStage.model_validate(
        obj={
            "name": "Extract & Load Local System",
            "id": "second-job",
            "uses": "tasks/simple-task@demo",
            "with": {"source": "src", "sink": "sink"},
        }
    )
    rs: Result = stage.execute({})
    assert rs.status == SUCCESS
    assert rs.context == {"records": 1, "status": SUCCESS}

    stage: Stage = CallStage.model_validate(
        obj={
            "name": "Extract & Load Local System",
            "uses": "tasks/simple-task-async@demo",
            "with": {"source": "src", "sink": "sink"},
        }
    )
    rs: Result = stage.execute({})
    assert rs.status == SUCCESS
    assert rs.context == {"records": 1, "status": SUCCESS}

    stage: Stage = CallStage.model_validate(
        obj={
            "name": "Private args should pass",
            "id": "args-private",
            "uses": "tasks/private-args-task@demo",
            "with": {
                "params": {"run_mode": "T"},
                "exec": "Test this arge should pass",
            },
        }
    )
    rs: Result = stage.execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "exec": "Test this arge should pass",
        "params": {"run_mode": "T"},
        "status": SUCCESS,
    }


def test_call_stage_exec_pydantic():
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
    rs: Result = stage.execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "name": "foo",
        "data": {"key": "value"},
    }


def test_call_stage_exec_raise():
    # NOTE: Raise because type of args not valid.
    stage: Stage = CallStage.model_validate(
        obj={
            "name": "Extract & Load Local System",
            "uses": "tasks/simple-task@demo",
            "with": {"source": 1, "sink": "sink"},
        }
    )
    rs = stage.execute({})
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

    # NOTE: Raise because invalid return type.
    stage: Stage = CallStage(
        name="Type not valid",
        uses="tasks/return-type-not-valid@raise",
    )
    rs: Result = stage.execute({})
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
    rs: Result = stage.execute({})
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
    rs: Result = stage.execute({})
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


def test_call_stage_exec_cancel():
    event = Event()
    event.set()
    stage: Stage = CallStage(
        name="Type not valid",
        uses="tasks/return-type-not-valid@raise",
    )
    rs: Result = stage.execute({}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "StageCancelError",
            "message": "Execution was canceled from the event before start parallel.",
        },
    }


@pytest.mark.asyncio
async def test_call_stage_axec():
    stage: Stage = CallStage.model_validate(
        obj={
            "name": "Extract & Load Local System",
            "id": "second-job",
            "uses": "tasks/simple-task@demo",
            "with": {"source": "src", "sink": "sink"},
        }
    )
    rs: Result = await stage.axecute({})
    assert rs.status == SUCCESS
    assert rs.context == {"records": 1, "status": SUCCESS}

    stage: Stage = CallStage.model_validate(
        obj={
            "name": "Extract & Load Local System",
            "uses": "tasks/simple-task-async@demo",
            "with": {"source": "src", "sink": "sink"},
        }
    )
    rs: Result = await stage.axecute({})
    assert rs.status == SUCCESS
    assert rs.context == {"records": 1, "status": SUCCESS}

    # NOTE: Raise because invalid return type.
    stage: Stage = CallStage(
        name="Type not valid",
        uses="tasks/return-type-not-valid@raise",
    )
    rs: Result = await stage.axecute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "TypeError",
            "message": (
                "Return type: 'return-type-not-valid@raise' can not "
                "serialize, you must set return be `dict` or Pydantic model."
            ),
        },
    }


@pytest.mark.asyncio
async def test_call_stage_axec_necessary_args():
    stage: Stage = CallStage.model_validate(
        {
            "name": "Necessary argument do not pass",
            "id": "private-args",
            "uses": "tasks/private-args-task@demo",
            "with": {"params": {"run_mode": "T"}},
        }
    )
    # NOTE: Raise because necessary args do not pass.
    rs: Result = await stage.axecute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": (
                "Necessary params, (_exec, params, ), does not set to args. "
                "It already set ['params']."
            ),
        },
    }

    stage: Stage = CallStage.model_validate(
        {
            "name": "Necessary argument do not pass",
            "id": "private-args",
            "uses": "tasks/private-args-task-not-special@demo",
            "with": {"params": {"run_mode": "T"}},
        }
    )
    rs: Result = await stage.axecute({})
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


@pytest.mark.asyncio
async def test_call_stage_axec_raise(test_path):
    # NOTE: Raise because call does not valid.
    stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
    rs: Result = await stage.axecute({})
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
    rs: Result = await stage.axecute({})
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
    rs: Result = await stage.axecute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "name": "foo",
        "data": {"key": "value"},
    }


@pytest.mark.asyncio
async def test_call_stage_axec_cancel():
    event = Event()
    event.set()
    stage: Stage = CallStage(
        name="Type not valid",
        uses="tasks/return-type-not-valid@raise",
    )
    rs: Result = await stage.axecute({}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "StageCancelError",
            "message": "Execution was canceled from the event before start parallel.",
        },
    }


def test_validate_model_args():
    stage: Stage = CallStage.model_validate(
        {
            "name": "Test validate model args",
            "uses": "tasks/private-args-task@demo",
            "with": {"exec": "test"},
        }
    )
    args = stage.validate_model_args(
        stage.get_caller({})(),
        stage.args | {"params": {}, "result": Result(), "extras": {}},
        "demo",
    )
    assert "_exec" in args

    args = stage.validate_model_args(
        "test",
        stage.args | {"params": {}, "result": Result(), "extras": {}},
        "demo",
    )
    assert "exec" in args

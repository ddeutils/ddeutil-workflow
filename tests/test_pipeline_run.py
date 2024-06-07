import ddeutil.workflow.pipeline as pipe
import pytest


def test_pipe_stage_py_raise():
    pipeline = pipe.Pipeline.from_loader(name="run_python", externals={})
    stage = pipeline.job("raise-run").stage(stage_id="raise-error")
    assert stage.id == "raise-error"
    with pytest.raises(pipe.PyException):
        stage.execute(params={"x": "Foo"})


def test_pipe_stage_py():
    # NOTE: Get stage from the specific pipeline.
    pipeline = pipe.Pipeline.from_loader(name="run_python", externals={})
    stage: pipe.PyStage = pipeline.job("demo-run").stage(stage_id="run-var")
    assert stage.id == "run-var"

    # NOTE: Start execute with manual stage parameters.
    rs = stage.execute(
        params={
            "params": {"name": "Author"},
            "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
        }
    )
    assert {
        "params": {"name": "Author"},
        "stages": {
            "hello-world": {"outputs": {"x": "Foo"}},
            "run-var": {"outputs": {"x": 1}},
        },
    } == rs


def test_pipe_stage_py_func():
    pipeline = pipe.Pipeline.from_loader(
        name="run_python_with_params", externals={}
    )
    stage: pipe.PyStage = pipeline.job("second-job").stage(
        stage_id="create-func"
    )
    assert stage.id == "create-func"
    # NOTE: Start execute with manual stage parameters.
    rs = stage.execute(params={})
    assert ("var_inside", "echo") == tuple(
        rs["stages"]["create-func"]["outputs"].keys()
    )


def test_pipe_job_py():
    pipeline = pipe.Pipeline.from_loader(name="run_python", externals={})
    demo_job: pipe.Job = pipeline.job("demo-run")

    # NOTE: Job params will change schema structure with {"params": { ... }}
    rs = demo_job.execute(params={"params": {"name": "Foo"}})
    assert {
        "matrix": {},
        "params": {"name": "Foo"},
        "stages": {
            "hello-world": {"outputs": {"x": "New Name"}},
            "run-var": {"outputs": {"x": 1}},
        },
    } == rs


@pytest.mark.skipif(True, reason="Because subprocess call on different OS")
def test_pipe_stage_shell():
    pipeline = pipe.Pipeline.from_loader(name="run_python", externals={})
    echo_env: pipe.Job = pipeline.job("shell-run").stage("echo-env")
    rs = echo_env.execute({})
    assert {
        "stages": {
            "echo-env": {
                "outputs": {
                    "return_code": 0,
                    "stdout": '"Hello World";;;;echo "Hello $Env:USER_SH";\n',
                    "stderr": "",
                },
            },
        },
    } == rs


def test_subprocess_shell():
    import subprocess
    from textwrap import dedent

    rs = subprocess.run(
        [
            "powershell",
            dedent(
                """
                echo "Hello World";
                echo "Next line";
            """
            ).strip(),
        ],
        capture_output=True,
        text=True,
        shell=True,
    )
    print(rs)


def test_pipe_params_py():
    pipeline = pipe.Pipeline.from_loader(
        name="run_python_with_params",
        externals={},
    )
    rs = pipeline.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        }
    )
    assert ("printing", "setting-x", "create-func", "call-func") == tuple(
        rs["stages"].keys()
    )

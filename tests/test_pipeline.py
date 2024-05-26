from ddeutil.workflow.pipeline import Job, Pipeline


def test_pipe_model():
    data = {
        "demo-run": {
            "stages": [
                {"name": "Run Hello World", "run": "print(f'Hello {x}')\n"},
                {
                    "name": "Run Sequence and use var from Above",
                    "run": (
                        "print(f'Receive x from above with {x}')\n\n"
                        "x: int = 1\n"
                    ),
                },
            ]
        },
        "next-run": {
            "stages": [
                {
                    "name": "Set variable and function",
                    "run": (
                        "var_inside: str = 'Inside'\n"
                        "def echo() -> None:\n"
                        '  print(f"Echo {var_inside}"\n'
                    ),
                },
                {"name": "Call that variable", "run": "echo()\n"},
            ]
        },
    }
    p = Pipeline(jobs=data)
    assert "Run Hello World" == p.jobs.get("demo-run").stages[0].name
    assert (
        "Run Sequence and use var from Above"
        == p.jobs.get("demo-run").stages[1].name
    )


def test_pipe_load_run_py(params_simple):
    pipeline = Pipeline.from_loader(name="run_python", externals={})
    demo_job: Job = pipeline.job("demo-run")
    print(demo_job.stages)

    next_run: Job = pipeline.job("next-run")
    print(next_run)

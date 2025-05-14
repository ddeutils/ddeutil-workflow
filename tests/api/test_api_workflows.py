from src.ddeutil.workflow.conf import api_config


def test_workflows_get_by_name(client):
    response = client.get(f"{api_config.prefix_path}/workflows/wf-run-common")
    assert response.status_code == 200
    assert response.json() == {
        "name": "wf-run-common",
        "desc": "## Run Python Workflow\n\nThis is a running python workflow\n",
        "params": {"name": {"type": "str"}},
        "on": [{"cronjob": "*/5 * * * *", "timezone": "Asia/Bangkok"}],
        "jobs": {
            "demo-run": {
                "id": "demo-run",
                "stages": [
                    {
                        "id": "hello-world",
                        "name": "Run Hello World",
                        "run": "print(f'Hello {x}')\nx: str = 'New Name'\n",
                        "vars": {"x": "${{ params.name }}"},
                    },
                    {
                        "id": "run-var",
                        "name": "Run Sequence and use var from Above",
                        "run": "print(f'Receive x from above with {x}')\n\n# Change x value\nx: int = 1\n",
                        "vars": {"x": "${{ stages.hello-world.outputs.x }}"},
                    },
                ],
            },
            "raise-run": {
                "id": "raise-run",
                "stages": [
                    {
                        "id": "raise-error",
                        "name": "Raise Error Inside",
                        "run": "raise ValueError('Testing raise error inside PyStage!!!')",
                    },
                ],
            },
            "next-run": {
                "id": "next-run",
                "stages": [
                    {
                        "name": "Set variable and function",
                        "run": "var_inside: str = 'Inside'\ndef echo() -> None:\n  print(f\"Echo {var_inside}\"\n",
                    },
                    {"name": "Call that variable", "run": "echo()"},
                    {"name": "Final of Next running job"},
                ],
            },
            "bash-run": {
                "id": "bash-run",
                "stages": [
                    {
                        "id": "echo",
                        "name": "Echo hello world",
                        "bash": 'echo "Hello World";\nVAR=\'Foo\';\necho "Variable $VAR";\n',
                    },
                ],
            },
            "bash-run-env": {
                "id": "bash-run-env",
                "stages": [
                    {
                        "id": "echo-env",
                        "name": "Echo hello world",
                        "bash": 'echo "Hello World";\nVAR=\'Foo\';\necho "Variable $$VAR";\necho "ENV $$PASSING";\n',
                        "env": {"PASSING": "Bar"},
                    },
                    {
                        "id": "raise-error",
                        "name": "Raise Error inside bash",
                        "bash": "printf '%s\\n' \"Test Raise Error case with failed\" >&2;\nexit 1;\n",
                    },
                ],
            },
        },
    }

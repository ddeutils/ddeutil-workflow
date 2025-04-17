from src.ddeutil.workflow.conf import api_config


def tests_route_job_execute(client):
    response = client.post(
        f"{api_config.prefix_path}/job/execute/",
        json={
            "result": {"run_id": "1234", "parent_run_id": "4567"},
            "job": {
                "stages": [
                    {"name": "Empty first", "echo": "hello world"},
                    {"name": "Empty second", "echo": "hello foo"},
                ]
            },
            "params": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "message": "Execute job via RestAPI.",
        "result": {"run_id": "1234", "parent_run_id": "4567"},
        "job": {
            "stages": [
                {"name": "Empty first", "echo": "hello world"},
                {"name": "Empty second", "echo": "hello foo"},
            ],
        },
        "params": {},
        "context": {"jobs": {}},
    }

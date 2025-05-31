from src.ddeutil.workflow.conf import api_config


def tests_route_job_execute(client):
    response = client.post(
        f"{api_config.prefix_path}/job/execute/",
        json={
            "result": {"run_id": "1234", "parent_run_id": "4567"},
            "job": {
                "id": "first-job",
                "stages": [
                    {"name": "Empty first", "echo": "hello world"},
                    {"name": "Empty second", "echo": "hello foo"},
                ],
            },
            "params": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "message": "Execute job via RestAPI successful.",
        "result": {"run_id": "1234", "parent_run_id": "4567"},
        "job": {
            "id": "first-job",
            "stages": [
                {"name": "Empty first", "echo": "hello world"},
                {"name": "Empty second", "echo": "hello foo"},
            ],
        },
        "params": {},
        "context": {
            "jobs": {
                "first-job": {
                    "status": "SUCCESS",
                    "stages": {
                        "0207202496": {"outputs": {}, "status": "SUCCESS"},
                        "0433802983": {"outputs": {}, "status": "SUCCESS"},
                    },
                },
            },
        },
    }


def tests_route_job_execute_not_pass_job_id(client):
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
    assert response.status_code == 500
    assert response.json() == {
        "message": "This job do not set the ID before setting execution output.",
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

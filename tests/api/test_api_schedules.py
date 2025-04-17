from src.ddeutil.workflow.conf import api_config


def test_schedules_get_by_name(client):
    response = client.get(f"{api_config.prefix_path}/schedules/schedule-wf")
    assert response.status_code == 200
    assert response.json() == {
        "desc": (
            "# First Schedule template\n\n"
            "The first schedule config template for testing scheduler "
            "function able to\nuse it\n"
        ),
        "workflows": [
            {
                "alias": "wf-scheduling",
                "name": "wf-scheduling",
                "on": [
                    {"cronjob": "*/3 * * * *", "timezone": "Asia/Bangkok"},
                    {"cronjob": "* * * * *", "timezone": "Asia/Bangkok"},
                ],
                "params": {"asat-dt": "${{ release.logical_date }}"},
            }
        ],
    }

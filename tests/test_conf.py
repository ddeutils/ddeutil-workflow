import json
import os


def test_config_loading():
    v = os.getenv("WORKFLOW_APP_STOP_BOUNDARY_DELTA")
    print(v)
    print(json.loads(v))

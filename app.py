import uvicorn

from src.ddeutil.workflow.api import app
from src.ddeutil.workflow.conf import LOGGING_CONFIG

if __name__ == "__main__":
    uvicorn.run(app, log_config=LOGGING_CONFIG)

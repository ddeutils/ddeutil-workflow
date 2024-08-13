import logging
from datetime import datetime

from ddeutil.workflow.pipeline import Pipeline
from dotenv import load_dotenv

load_dotenv("../.env")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)8.8s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f'../logs/poke-{datetime.now().isoformat().replace(":", "-")}.log',
            encoding="utf-8",
        ),
    ],
)


if __name__ == "__main__":
    pipe = Pipeline.from_loader(name="pipe-scheduling", externals={})
    pipe.poke(params={"name": "FOO"})

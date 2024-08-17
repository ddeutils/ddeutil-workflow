import logging

from ddeutil.workflow.pipeline import Pipeline
from dotenv import load_dotenv

load_dotenv("../.env")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)8.8s] %(message)s",
    handlers=[logging.StreamHandler()],
)


def test_pipeline_poke():
    # pipe = Pipeline.from_loader(name="pipe-scheduling", externals={})
    # pipe.poke(params={"name": "FOO"})
    pipe = Pipeline.from_loader(name="pipe-run-matrix-fail-fast", externals={})
    rs = pipe.poke(params={"name": "FOO"})
    print(rs)
    # assert ["[CORE]: Start Execute: pipe-run-matrix-fail-fast"] == rs

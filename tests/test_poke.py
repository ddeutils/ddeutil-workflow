import logging

from ddeutil.workflow.pipeline import Pipeline

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)8.8s] %(message)s",
    handlers=[logging.StreamHandler()],
)


def test_pipeline_poke():
    pipe = Pipeline.from_loader(name="pipe-run-matrix-fail-fast", externals={})
    pipe.poke(params={"name": "FOO"})


def test_pipe_poke_with_release_params():
    pipe = Pipeline.from_loader(name="pipe-scheduling", externals={})
    pipe.poke(params={"asat-dt": "${{ release.logical_date }}"})

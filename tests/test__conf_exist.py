from pathlib import Path

from ddeutil.io.__base import YamlFl


def test_read_data(conf_path: Path):
    assert YamlFl(path=conf_path / "demo/04_00_pipe_run.yml").read()
    assert YamlFl(path=conf_path / "demo/04_10_pipe_task.yml").read()
    assert YamlFl(path=conf_path / "demo/04_20_pipe_task_metrix.yml").read()
    assert YamlFl(path=conf_path / "demo/04_30_pipe_trigger.yml").read()
    assert YamlFl(path=conf_path / "demo/05_schedules.yml").read()

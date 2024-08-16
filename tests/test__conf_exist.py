from pathlib import Path

from ddeutil.io.__base import YamlFl


def test_read_data(conf_path: Path):
    assert YamlFl(path=conf_path / "demo/01_00_pipe_run.yml").read()
    assert YamlFl(path=conf_path / "demo/01_10_pipe_task.yml").read()
    assert YamlFl(path=conf_path / "demo/01_20_pipe_metrix.yml").read()
    assert YamlFl(path=conf_path / "demo/01_30_pipe_trigger.yml").read()
    assert YamlFl(path=conf_path / "demo/02_schedules.yml").read()
    assert YamlFl(path=conf_path / "demo/03_poking.yml").read()

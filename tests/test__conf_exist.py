from pathlib import Path

from ddeutil.io.__base import YamlFl


def test_read_data(test_path: Path):
    assert YamlFl(path=test_path / "conf/demo/04_00_pipe_run.yml").read()
    assert YamlFl(path=test_path / "conf/demo/04_10_pipe_el.yml").read()
    assert YamlFl(path=test_path / "conf/demo/04_20_pipe_transform.yml").read()
    assert YamlFl(path=test_path / "conf/demo/04_30_pipe_etl.yml").read()
    assert YamlFl(path=test_path / "conf/demo/05_schedules.yml").read()

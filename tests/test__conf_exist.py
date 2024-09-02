from pathlib import Path

from ddeutil.io.__base import YamlFl


def test_read_data(conf_path: Path):
    assert YamlFl(path=conf_path / "demo/01_00_wf_run.yml").read()
    assert YamlFl(path=conf_path / "demo/01_10_wf_task.yml").read()
    assert YamlFl(path=conf_path / "demo/01_20_wf_metrix.yml").read()
    assert YamlFl(path=conf_path / "demo/01_30_wf_trigger.yml").read()
    assert YamlFl(path=conf_path / "demo/02_on.yml").read()
    assert YamlFl(path=conf_path / "demo/03_schedule.yml").read()

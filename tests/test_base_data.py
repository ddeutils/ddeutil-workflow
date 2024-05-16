from pathlib import Path

from ddeutil.io.__base.files import YamlFl


def test_read_data(data_path: Path):
    assert YamlFl(path=data_path / "conf/demo/01_conn.yml").read()
    assert YamlFl(path=data_path / "conf/demo/02_ds.yml").read()
    assert YamlFl(path=data_path / "conf/demo/04_01_pipe_simple.yml").read()
    assert YamlFl(path=data_path / "conf/demo/04_02_pipe_complex.yml").read()

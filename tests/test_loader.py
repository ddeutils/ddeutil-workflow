import ddeutil.workflow.loader as ld


def test_loader(conf_path):
    loader = ld.Loader.config()
    assert conf_path == loader.engine.paths.conf

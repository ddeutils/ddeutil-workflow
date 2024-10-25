import ddeutil.workflow.conf as conf


def test_conf_engine():
    engine = conf.Engine(
        registry=conf.config.regis_hook,
        registry_filter=conf.config.regis_filter,
    )
    assert ["src.ddeutil.workflow", "tests"] == engine.registry
    assert ["ddeutil.workflow.utils"] == engine.registry_filter

    engine = conf.Engine.model_validate(
        obj={
            "registry": "ddeutil.workflow",
            "registry_filter": "ddeutil.workflow.utils",
        },
    )
    assert ["ddeutil.workflow"] == engine.registry
    assert ["ddeutil.workflow.utils"] == engine.registry_filter

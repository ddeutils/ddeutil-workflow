import ddeutil.workflow.loader as ld


def test_conn_init(params):
    load: ld.BaseLoad = ld.BaseLoad.from_register(
        name="demo:conn_local_file",
        params=params,
        externals={
            "audit_date": "2024-01-01 00:12:45",
        },
    )
    print(load.data)

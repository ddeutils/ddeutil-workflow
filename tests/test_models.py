import ddeutil.node.base.models as md


def test_conn():
    _data = {
        "type": "objects.connection.LocalSystem",
        "endpoint": "file:///${APP_PATH}/data/demo/landing",
        "timeout": 10,
        "key": "value",
        "ssh_tunnel": {
            "ssh_host": "@secrets{pg_uat_ssh_host}",
            "ssh_user": "@secrets{pg_uat_ssh_user}",
            "ssh_private_key": "@secrets{pg_uat_ssh_private_key}",
            "ssh_port": "22",
        },
    }
    _model = md.ConnModel.model_validate(_data)
    assert 10 == _model.props["timeout"]
    assert "value" == _model.props["key"]


def test_conn_full_sqlite():
    _data = {
        "type": "object.connection.PostgresDB",
        "username": "pgadmin",
        "password": "P@ssW0rD",
        "host": "localhost",
        "port": "5432",
        "database": "pgprod",
    }
    _model = md.ConnFullPostgresModel.model_validate(_data)
    assert "postgres" == _model.drivername

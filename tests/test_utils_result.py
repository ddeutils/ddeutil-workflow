from ddeutil.workflow.utils import ReResult, Result


def test_result_default():
    rs = Result()
    rs2 = Result()
    assert 2 == rs.status
    assert {} == rs.context
    assert rs == rs2


def test_result_context():
    data = {
        "params": {
            "source": "src",
            "target": "tgt",
        }
    }
    rs = Result(context=data)
    rs.context.update({"additional-key": "new-value-to-add"})
    assert {
        "params": {"source": "src", "target": "tgt"},
        "additional-key": "new-value-to-add",
    } == rs.context


def test_re_result_context():
    main_rs = ReResult()
    print(main_rs)

    sub_rs = ReResult(
        status=1,
        context={
            "jobs": {
                "first-job": {
                    "stages": {
                        "stage-id-1": {"outputs": {}},
                    },
                },
            },
        },
    )
    print(sub_rs)
    main_rs.receive(sub_rs)
    print(main_rs)

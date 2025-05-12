from ddeutil.workflow.reusables import mark_secret


def test_mark_secret():
    assert mark_secret("foo", mark=False) == "foo"
    assert mark_secret("foo-bar", mark=True) == "*******"
    assert mark_secret(
        {
            "aws_secret_key": "foo-bar",
            "context": {"foo": 1},
        }
    ) == {"aws_secret_key": "*******", "context": {"foo": 1}}

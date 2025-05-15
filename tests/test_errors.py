from ddeutil.workflow.errors import BaseError


def test_errors_base_error():
    error = BaseError(
        message="This is a base workflow error.",
        context={"key": "value"},
    )
    assert str(error) == "This is a base workflow error."
    assert error.context == {"key": "value"}

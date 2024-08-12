from ddeutil.workflow.utils import param2template


def test_param2template():
    value = param2template("${{ params.src }}", {"params": {"src": "foo"}})
    assert "foo" == value


def test_param2template_with_filter():
    value = param2template(
        "${{ params.value | abs }}", {"params": {"value": -5}}
    )
    assert "5" == value

import ddeutil.workflow.utils as utils


def test_gen_id():
    assert "99914b932bd37a50b983c5e7c90ae93b" == utils.gen_id("{}")
    assert "99914b932bd37a50b983c5e7c90ae93b" == utils.gen_id(
        "{}", sensitive=False
    )

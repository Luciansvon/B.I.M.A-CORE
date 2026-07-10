from core.dashboard_server import _token_status_message


def test_dashboard_token_status_never_contains_token_material() -> None:
    token = "super-secret-dashboard-token"

    configured = _token_status_message(configured=True)
    generated = _token_status_message(configured=False)

    assert token not in configured
    assert token not in generated
    assert "Bearer" not in configured
    assert "Bearer" not in generated
    assert "loaded from environment" in configured
    assert "temporary token generated" in generated

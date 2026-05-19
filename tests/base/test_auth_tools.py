from stocksonar.tools.auth_tools import _logout_url


def test_logout_url_uses_realm_and_redirect():
    url = _logout_url()
    assert "/realms/stocksonar/protocol/openid-connect/logout" in url
    assert "redirect_uri=" in url

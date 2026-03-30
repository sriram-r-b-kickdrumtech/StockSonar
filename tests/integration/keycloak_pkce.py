"""Authorization Code + PKCE against Keycloak (browser-free, for integration tests)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx

try:
    from bs4 import BeautifulSoup
except ImportError as e:  # pragma: no cover
    raise ImportError("integration tests need beautifulsoup4: pip install beautifulsoup4") from e


def pkce_verifier_and_challenge() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _redirect_uri_match(redirect_uri: str, url: str) -> bool:
    a, b = urlparse(redirect_uri), urlparse(url)
    return (a.scheme, a.netloc, a.path.rstrip("/")) == (b.scheme, b.netloc, b.path.rstrip("/"))


def _parse_code(url: str, redirect_uri: str, expected_state: str) -> str | None:
    if not _redirect_uri_match(redirect_uri, url):
        return None
    qs = parse_qs(urlparse(url).query)
    states = qs.get("state") or []
    if states and states[0] != expected_state:
        raise RuntimeError("OAuth state mismatch")
    codes = qs.get("code") or []
    return codes[0] if codes else None


def _parse_login_form(html: str, page_url: str) -> tuple[str, dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="kc-form-login") or soup.find("form")
    if form is None:
        raise RuntimeError("Could not find Keycloak login form")
    action = form.get("action")
    if not action:
        raise RuntimeError("Login form has no action")
    post_url = urljoin(page_url, action)
    data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "text").lower()
        if itype in ("checkbox", "radio") and not inp.get("checked"):
            continue
        data[name] = inp.get("value") or ""
    for btn in form.find_all("button"):
        if (btn.get("type") or "").lower() != "submit":
            continue
        name = btn.get("name")
        if name:
            data[name] = btn.get("value") or (btn.get_text() or "").strip()
    # Keycloak v2 theme: empty hidden credentialId breaks the POST (HTTP 400) — omit if blank.
    if data.get("credentialId") == "":
        del data["credentialId"]
    if "login" not in data:
        sub = form.find("button", attrs={"name": "login", "type": "submit"})
        if sub is not None:
            data["login"] = sub.get("value") or (sub.get_text() or "").strip() or "Sign In"
    return post_url, data


def _manual_cookie_header_from_responses(responses: list[httpx.Response]) -> str | None:
    """Merge ``Set-Cookie`` name=value pairs from responses into a ``Cookie`` header.

    Keycloak (even on plain HTTP) often emits ``Secure`` cookies. httpx refuses to attach
    those to ``http://`` requests, which yields Keycloak's *Cookie not found* (HTTP 400).
    """
    by_name: dict[str, str] = {}
    for r in responses:
        for key, val in r.headers.raw:
            if key.lower() != b"set-cookie":
                continue
            line = val.decode("latin-1")
            nv = line.split(";", 1)[0].strip()
            if "=" not in nv:
                continue
            name, value = nv.split("=", 1)
            by_name[name.strip()] = value.strip()
    if not by_name:
        return None
    return "; ".join(f"{n}={v}" for n, v in by_name.items())


def _browser_headers_for_post(post_url: str, referer: str) -> dict[str, str]:
    parsed = urlparse(post_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "User-Agent": "Mozilla/5.0 (StockSonar-OAuth-IntegrationTest) Chrome/120.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": referer,
        "Origin": origin,
    }


def _exchange_code(
    client: httpx.Client,
    token_endpoint: str,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    tr = client.post(
        token_endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    tr.raise_for_status()
    return tr.json()


def obtain_tokens_authorization_code_pkce(
    *,
    keycloak_base: str,
    realm: str,
    client_id: str,
    redirect_uri: str,
    username: str,
    password: str,
    scopes: str = "openid profile email",
) -> dict[str, Any]:
    """
    OAuth 2.0 Authorization Code + PKCE (S256) against Keycloak, without a browser.

    ``keycloak_base`` example: ``http://localhost:8090`` (host-mapped Keycloak in docker-compose).
    """
    keycloak_base = keycloak_base.rstrip("/")
    verifier, challenge = pkce_verifier_and_challenge()
    state = secrets.token_urlsafe(24)

    auth_endpoint = f"{keycloak_base}/realms/{realm}/protocol/openid-connect/auth"
    token_endpoint = f"{keycloak_base}/realms/{realm}/protocol/openid-connect/token"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{auth_endpoint}?{urlencode(params)}"

    default_headers = {
        "User-Agent": "Mozilla/5.0 (StockSonar-OAuth-IntegrationTest) Chrome/120.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    auth_responses: list[httpx.Response] = []
    with httpx.Client(timeout=60.0, follow_redirects=False, headers=default_headers) as client:
        r = client.get(auth_url)
        auth_responses.append(r)
        for _ in range(32):
            if r.status_code in (301, 302, 303, 307):
                loc = r.headers.get("location")
                if not loc:
                    break
                next_url = urljoin(str(r.url), loc)
                code = _parse_code(next_url, redirect_uri, state)
                if code:
                    return _exchange_code(
                        client, token_endpoint, client_id, redirect_uri, code, verifier
                    )
                r = client.get(next_url)
                auth_responses.append(r)
                continue
            if r.status_code == 200 and "kc-form-login" in (r.text or ""):
                break
            raise RuntimeError(
                f"Unexpected response during auth (status={r.status_code}, url={r.url})"
            )
        else:
            raise RuntimeError("Too many redirects before Keycloak login page")

        login_page_url = str(r.url)
        post_url, form_data = _parse_login_form(r.text, login_page_url)
        form_data["username"] = username
        form_data["password"] = password

        # Keycloak 26 rejects the login POST (400) if Referer is the authenticate URL;
        # browsers send the OIDC /auth entry as Referer (matches curl/manual flows).
        post_headers = _browser_headers_for_post(post_url, referer=auth_endpoint)
        manual_cookie = _manual_cookie_header_from_responses(auth_responses)
        if manual_cookie:
            post_headers["Cookie"] = manual_cookie
        r = client.post(post_url, data=form_data, headers=post_headers, follow_redirects=False)
        for _ in range(32):
            if r.status_code in (301, 302, 303, 307):
                loc = r.headers.get("location")
                if not loc:
                    break
                next_url = urljoin(str(r.url), loc)
                code = _parse_code(next_url, redirect_uri, state)
                if code:
                    return _exchange_code(
                        client, token_endpoint, client_id, redirect_uri, code, verifier
                    )
                r = client.get(next_url, headers=default_headers)
                continue
            if r.status_code == 200 and "kc-form-login" in (r.text or ""):
                raise RuntimeError("Keycloak login failed (still on login page)")
            if r.status_code >= 400:
                snippet = (r.text or "")[:1200].replace("\n", " ")
                raise RuntimeError(
                    f"Keycloak login POST failed (status={r.status_code}, url={r.url}): {snippet}"
                )
            raise RuntimeError(
                f"No authorization redirect after login (status={r.status_code}, url={r.url})"
            )

        raise RuntimeError("Too many redirects after Keycloak login")

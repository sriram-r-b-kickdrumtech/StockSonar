# StockSonar

Production-style **MCP server** for Indian market data, mutual funds, news, and **PS2: Portfolio Risk & Alert Monitor** tools — with **OAuth 2.1 resource-server** metadata (Keycloak), **Redis** caching & rate limits, and **tiered scopes** mapped from Keycloak realm roles.

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add GNEWS_API_KEY from https://gnews.io/
```

### Run MCP (Streamable HTTP)

```bash
export PYTHONPATH=src
python -m stocksonar.server
```

- MCP endpoint: `http://localhost:8000/mcp` (see `STREAMABLE_HTTP_PATH`). By default **`MCP_JSON_RESPONSE=true`**: Streamable HTTP returns JSON per request so tier **rate limits** can surface as **HTTP 429** with **`Retry-After`** (see `stocksonar.middleware.http_rate_limit`). Clients must send **`Accept: application/json`** for MCP POSTs in that mode.
- Health: `http://localhost:8000/health`
- Protected resource metadata: `/.well-known/oauth-protected-resource` (via FastMCP / Keycloak integration)

### Docker Compose (Keycloak + Redis + MCP)

```bash
export GNEWS_API_KEY=your_key
docker compose up --build
```

Wait for Keycloak at **http://localhost:8090** (admin / admin). Port **8090** is used so **8080 stays free** for other apps. Realm `stocksonar` is imported with users:

| User    | Password     | Realm role     |
|---------|--------------|----------------|
| `free`  | `freepass`   | `tier-free`    |
| `premium` | `premiumpass` | `tier-premium` |
| `analyst` | `analystpass` | `tier-analyst` |

Client: `stocksonar-mcp` (public, direct access grants for demos).

Keycloak stores state in the **`keycloak_data`** volume. Demo users include email and names so the password grant works on Keycloak 24+. If you still see **`Account is not fully set up`**, wipe and re-import: `docker compose down -v && docker compose up -d keycloak`.

### Get an access token (password grant — demo only)

```bash
curl -s -X POST 'http://localhost:8090/realms/stocksonar/protocol/openid-connect/token' \
  -d 'client_id=stocksonar-mcp' \
  -d 'username=analyst' \
  -d 'password=analystpass' \
  -d 'grant_type=password' | jq -r .access_token
```

Use the token as `Authorization: Bearer …` on MCP HTTP requests.

### Static auth (no Keycloak)

In `.env`:

```env
AUTH_MODE=static
STATIC_TOKENS_JSON={"demo":{"client_id":"c","scopes":["market:read","mf:read","news:read","portfolio:read","portfolio:write","portfolio:risk","research:generate"],"sub":"demo-user"}}
```

Then call MCP with `Authorization: Bearer demo`.

## Tiers & scopes

Realm roles `tier-free`, `tier-premium`, `tier-analyst` expand to OAuth scopes (see `src/stocksonar/auth/scopes.py`).

- **Free**: `market:read`, `mf:read`, `news:read`, `portfolio:read`, `portfolio:write`
- **Premium**: + `fundamentals:read`, `technicals:read`, `macro:read`, `portfolio:risk`
- **Analyst**: + `filings:*`, `macro:historical`, `research:generate`

## Tests

```bash
export PYTHONPATH=src
pytest tests/ -q
```

- `tests/base/` — base layer
- `tests/ps2/` — portfolio / risk / cross-source

## API keys

| Variable | Register at |
|----------|-------------|
| `GNEWS_API_KEY` | https://gnews.io/ |
| `FINNHUB_API_KEY` | https://finnhub.io/ (optional) |
| `ALPHA_VANTAGE_API_KEY` | https://www.alphavantage.co/ (optional) |

No keys required for Yahoo Finance (yfinance), jugaad-data / NSE, or MFapi.in.

## Disclaimer

All outputs include a non-advice disclaimer. Data is aggregated from third-party sources; verify before use.

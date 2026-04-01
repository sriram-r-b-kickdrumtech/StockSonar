# StockSonar

Indian markets **MCP server** (FastMCP): quotes, mutual funds, news, macro, filings, watchlist, and **PS2 portfolio risk** tools with Keycloak OAuth 2.1, Redis, and structured JSON responses (`source`, `disclaimer`, `timestamp`, `data`).

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Docker** | For Redis + Keycloak + MCP container |
| **Python 3.11+** | Matches `.cursorrules`; Docker image uses 3.12 |
| **`.env`** | Copy from [`.env.example`](.env.example); set at least `GNEWS_API_KEY` for news/sentiment tools |
| **Virtualenv** | Use repo **`.venv`** (see [`.cursorrules`](.cursorrules)) |

```bash
cd StockSonar
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## One-command stack (production-like)

From the repo root:

```bash
docker compose up -d --build
```

| Service | URL / port |
|---------|------------|
| **MCP (HTTP + `/mcp`)** | http://localhost:8000 |
| **MCP health** | http://localhost:8000/health |
| **Keycloak** | http://localhost:8090 (admin / admin) |
| **Redis** | Internal only (`redis:6379` in Compose); host apps use `REDIS_URL` in `.env` if you run MCP on the host |

The MCP container reads `.env` if present (optional). After **first** start, wait ~30–60s for Keycloak to import the realm.

### Fresh Keycloak volume (401 / missing `aud`)

If tokens fail JWT validation, reset volumes and re-import:

```bash
docker compose down -v
docker compose up -d --build
```

---

## Run MCP on your host (optional)

Useful for debugging without rebuilding the image:

```bash
export REDIS_URL=redis://localhost:6379/0   # only if you publish Redis; Compose default does not
export PYTHONPATH=src
python -m stocksonar.server
```

With default Compose, Redis is **not** exposed on `localhost:6379`; prefer the **mcp-server** container for a turnkey demo.

---

## Test users (Keycloak)

Defined in [`keycloak/stocksonar-realm.json`](keycloak/stocksonar-realm.json):

| Username | Password | Tier |
|----------|----------|------|
| `free` | `freepass` | Free scopes |
| `premium` | `premiumpass` | + Premium (e.g. `portfolio:risk`, `macro:read`) |
| `analyst` | `analystpass` | + Analyst (`research:generate`, filings, cross-source) |

Client: **`stocksonar-mcp`** (public client, direct access grant enabled for password grant demos).

---

## Automated E2E & judge demo (Python + log files)

All commands assume **`.venv` activated** and repo root as cwd.

### 1) Stack health (blocking probes)

Retries Keycloak OIDC discovery + MCP `/health`:

```bash
python scripts/check_stack_health.py
python scripts/check_stack_health.py --retries 10 --pause 3
```

Exit code **0** = ready for demos. Logs every attempt to stdout.

### 2) **Judge demo** (recommended for PS2 + auth story)

Runs:

- Quick stack check  
- **Tier probes**: `free` / `premium` / `analyst` calling tools that should **allow** or **deny** per scopes  
- **Analyst PS2 flow**: skewed portfolio → health → risk tools → `portfolio_risk_report` → `what_if_analysis` → `refresh_market_overview` → reads `market://`, `macro://`, `portfolio://…` resources → lists PS2 prompts  

**By default** output is mirrored to **console and** a timestamped file under `logs/`:

```bash
python scripts/run_judge_demo.py
```

Custom log path:

```bash
python scripts/run_judge_demo.py --log-file logs/judge_run_1.log
```

Console only (no file):

```bash
python scripts/run_judge_demo.py --no-log-file
```

### Interactive PS2 (manual, full visibility)

Menu-driven shell: call each PS2 tool and resource yourself, see **full pretty-printed JSON** and **latency (ms)** per call. Supports **in-session user switch** (free / premium / analyst) with a fresh MCP connection.

```bash
python scripts/ps2_interactive.py
python scripts/ps2_interactive.py --username premium
python scripts/ps2_interactive.py --log-file logs/ps2_session.log
```

Uses the same env vars as other scripts (`MCP_BASE_URL`, `TOKEN_URL`, `KEYCLOAK_*`). For `free`, `premium`, or `analyst` usernames, passwords default to the realm (`freepass`, `premiumpass`, `analystpass`).

Resource subscriptions / push notifications are not shown in this shell; use the automated judge demo or an MCP client that subscribes to resources.

Skip tier section (faster, only analyst story):

```bash
python scripts/run_judge_demo.py --skip-tiers
```

Environment (optional):

| Variable | Purpose |
|----------|---------|
| `MCP_BASE_URL` | Default `http://localhost:8000` |
| `STREAMABLE_HTTP_PATH` | Default `/mcp` |
| `TOKEN_URL` | Keycloak token endpoint |
| `KEYCLOAK_CLIENT_ID` | Default `stocksonar-mcp` |
| `KEYCLOAK_USER` / `KEYCLOAK_PASSWORD` | Used for **analyst** PS2 section (override per run if needed) |
| `STOCKSONAR_KEYCLOAK_BASE` | For stack check inside the script |

### 3) Call **every** MCP tool + read resources (full sweep)

Uses password grant (default **analyst**). Optional automatic log file:

```bash
export KEYCLOAK_USER=analyst
export KEYCLOAK_PASSWORD=analystpass
python scripts/call_all_mcp_tools.py
```

Save full transcript:

```bash
python scripts/call_all_mcp_tools.py --save-log
# or
python scripts/call_all_mcp_tools.py --log-file logs/full_tool_sweep.log
```

### 4) Integration tests (PKCE + MCP prompts) with log file

Requires the same Docker stack:

```bash
python scripts/run_integration_tests.py --save-log
```

Forward extra pytest args after `--`:

```bash
python scripts/run_integration_tests.py --save-log -- -v -k pkce
```

Or plain pytest:

```bash
PYTHONPATH=src pytest tests/integration -v -m integration
```

### 5) Unit tests (no Docker)

```bash
PYTHONPATH=src pytest tests -m "not integration" -q
```

---

## Log files

- Default judge logs: `logs/stocksonar_judge_demo_<UTC_timestamp>.log`  
- Full tool sweep: `logs/stocksonar_all_tools_<UTC_timestamp>.log` (with `--save-log`)  
- Integration: `logs/pytest_integration_<UTC_timestamp>.log` (with `--save-log`)  

`logs/*.log` is **gitignored**; the folder is kept via [`logs/.gitkeep`](logs/.gitkeep).

---

## Using StockSonar with LLMs (Gemini CLI / Cursor / Claude Code)

StockSonar is a standard MCP server — any MCP-compatible LLM client can connect and use all tools, resources, and prompts.

### Quick start (static tokens — no Keycloak login needed)

Switch the server to **static-token mode** so the LLM client can authenticate with a simple bearer token header instead of an OAuth browser flow:

```bash
# Restart MCP server with static tokens
docker compose down mcp-server
docker compose --env-file .env.llm up -d --build mcp-server
```

This reads `.env.llm` which sets `AUTH_MODE=static` and defines three tokens:

| Token | Tier | All PS2 tools? |
|-------|------|----------------|
| `analyst-token` | Analyst | Yes — full access |
| `premium-token` | Premium | Risk tools only |
| `free-token` | Free | Basic portfolio + market |

### Gemini CLI (free, recommended)

The repo includes `.gemini/settings.json` pre-configured for StockSonar.

**1. Install Gemini CLI** (if not already):

```bash
npm install -g @anthropic/gemini-cli
# or
npx @anthropic/gemini-cli
```

**2. Start the server in static-token mode** (see above), then:

```bash
cd StockSonar
gemini
```

Gemini CLI auto-discovers `.gemini/settings.json` and connects to StockSonar. Verify with:

```
/mcp
```

You should see `stocksonar (CONNECTED)` with all tools listed. Then use tools naturally:

```
> Get the stock quote for RELIANCE
> Add TCS, INFY, HDFCBANK to my portfolio and run a health check
> Generate a full portfolio risk report
> What would happen if RBI cuts rates by 50bps?
```

**One-liner alternative** (skip the config file):

```bash
gemini mcp add --transport http stocksonar http://localhost:8000/mcp \
  --header "Authorization: Bearer analyst-token" --trust
```

**MCP Prompts as slash commands** — StockSonar prompts work as Gemini CLI slash commands:

```
/morning_risk_brief
/rebalance_suggestions
/earnings_exposure
```

### Cursor

`.cursor/mcp.json` is already configured with the static `analyst-token`. After starting the server in static-token mode:

1. Open the repo in Cursor
2. Go to **Settings → MCP** and verify `stocksonar` shows as connected (green dot)
3. In Agent mode, ask Cursor to use StockSonar tools

### Claude Code / Claude Desktop

The repo includes `.mcp.json` at the root for Claude Code. Edit it to add the static token header:

```json
{
  "mcpServers": {
    "stocksonar": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer analyst-token"
      }
    }
  }
}
```

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stocksonar": {
      "command": "npx",
      "args": [
        "-y", "@anthropic/mcp-remote",
        "http://localhost:8000/mcp",
        "--header", "Authorization: Bearer analyst-token"
      ]
    }
  }
}
```

### Other MCP clients

Any client that speaks MCP over streamable-http works. Point it at `http://localhost:8000/mcp` with header `Authorization: Bearer analyst-token` (static mode) or use the Keycloak OAuth flow.

### Switching back to Keycloak auth

```bash
docker compose down mcp-server
docker compose up -d --build mcp-server   # uses default .env / no env-file override
```

### Available tools for the LLM

| Category | Tools |
|----------|-------|
| **Market** | `get_stock_quote`, `get_price_history`, `get_index_data`, `refresh_market_overview` |
| **Portfolio** | `add_to_portfolio`, `remove_from_portfolio`, `get_portfolio_summary` |
| **PS2 Risk** | `portfolio_health_check`, `check_concentration_risk`, `check_mf_overlap`, `check_macro_sensitivity`, `detect_sentiment_shift` |
| **Cross-source** | `portfolio_risk_report`, `what_if_analysis`, `cross_reference_signals` |
| **Resources** | `market://overview`, `macro://snapshot`, `portfolio://{user}/holdings`, `portfolio://{user}/alerts`, `portfolio://{user}/risk_score` |
| **Prompts** | `morning_risk_brief`, `rebalance_suggestions`, `earnings_exposure` |

---

## Architecture (short)

- **Auth**: Keycloak JWTs; scopes from realm roles ([`src/stocksonar/auth/scopes.py`](src/stocksonar/auth/scopes.py)).  
- **Rate limits**: Redis sliding window + optional HTTP 429 for JSON MCP responses.  
- **PS2**: Portfolio store in Redis, risk tools, `portfolio://…` + `market://overview` + `macro://snapshot` resources, resource update notifications on portfolio changes and `refresh_market_overview`.  
- **Problem statements**: See [`docs/problem_statement.md`](docs/problem_statement.md).

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| MCP 401 / invalid token | `docker compose down -v` and bring stack up again; confirm `KEYCLOAK_AUDIENCE=account` in `.env` |
| News / sentiment errors | Set `GNEWS_API_KEY` in `.env`; watch `GNEWS_DAILY_QUOTA` |
| `check_stack_health` fails | Wait longer; increase `--retries` / `--pause`; confirm ports 8000 and 8090 |
| Import errors running scripts | Run from repo root; use `.venv/bin/python` |

---

## License / disclaimer

Outputs include a configurable **disclaimer** ([`src/stocksonar/config.py`](src/stocksonar/config.py)); not financial advice.

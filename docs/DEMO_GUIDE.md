# StockSonar PS2 — Demo Guide (Judges)

This document is a step-by-step script for demonstrating StockSonar's PS2 (Portfolio Risk & Alert Monitor) to judges. It covers every evaluation criterion from the problem statement.

---

## Pre-Demo Checklist

```bash
# 1. Start the full stack (one command)
docker compose up -d --build

# 2. Wait for Keycloak (~30-60s on first boot)
curl -sf http://localhost:8090/realms/stocksonar/.well-known/openid-configuration > /dev/null && echo "READY"

# 3. Verify MCP server
curl -s http://localhost:8000/health | python3 -m json.tool
```

| Service | URL |
|---------|-----|
| MCP server (streamable HTTP) | `http://localhost:8000/mcp` |
| MCP health endpoint | `http://localhost:8000/health` |
| Keycloak admin console | `http://localhost:8090` (admin / admin) |

---

## Demo Flow Overview

```
SECTION 1: Auth Flow & Discovery (Authentication & Authorisation — 25%)
SECTION 2: Free Tier — basics + permission boundary
SECTION 3: Premium Tier — risk tools + permission boundary
SECTION 4: Analyst Tier — full PS2 story + cross-source reasoning
SECTION 5: Resources & Subscriptions
SECTION 6: Prompts (slash commands)
```

---

## Connecting with Gemini CLI

```bash
cd StockSonar
gemini
```

Gemini CLI auto-discovers `.gemini/settings.json` which points to `http://localhost:8000/mcp`. On first connect it performs the full OAuth flow:

1. MCP server returns **401** with `WWW-Authenticate` header containing `resource_metadata` URL
2. Gemini CLI fetches `/.well-known/oauth-protected-resource/mcp` — discovers Keycloak as authorization server
3. Browser opens to Keycloak login page (OAuth 2.1 + PKCE)
4. User authenticates, Keycloak issues JWT with realm roles
5. Gemini CLI presents Bearer token to MCP server
6. Server validates signature, expiry, audience (`account`), extracts scopes from realm roles

Verify connection: `/mcp` should show `stocksonar (CONNECTED)`.

### Switching users between sections

```bash
# 1. Log out of Keycloak in browser
open "http://localhost:8090/realms/stocksonar/protocol/openid-connect/logout?redirect_uri=http://localhost:8090"

# 2. Clear cached tokens
rm -f ~/.gemini/mcp-oauth-tokens.json

# 3. Re-authenticate in Gemini CLI
/mcp auth stocksonar
# → Browser opens, log in as the new user
```

---

## SECTION 1: Auth Flow Demo (show judges the 401 → discovery → login → tools)

**What to show:** The OAuth 2.1 + PKCE flow is real and standards-compliant.

```bash
# Show the 401 with resource_metadata URL
curl -s -D- http://localhost:8000/mcp 2>&1 | head -5

# Show the Protected Resource Metadata (RFC 9728)
curl -s http://localhost:8000/.well-known/oauth-protected-resource/mcp | python3 -m json.tool

# Show Keycloak OIDC discovery
curl -s http://localhost:8090/realms/stocksonar/.well-known/openid-configuration | python3 -m json.tool | head -15
```

**Talking points:**
- Server returns `401 Unauthorized` with `WWW-Authenticate: Bearer ... resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource/mcp"`
- Resource metadata advertises Keycloak as the `authorization_server` and lists all 16 supported scopes
- Auth server is **separate** from MCP server (Resource Server pattern)
- PKCE is mandatory (`code_challenge_method=S256` in the auth URL)
- JWT audience bound to `account` (RFC 8707)

---

## SECTION 2: Free Tier (`free` / `freepass`)

**Purpose:** Show basic capabilities + demonstrate permission boundary.

### 2A. Market data (should work)

```
Get the stock quote for RELIANCE and TCS using the MCP tools.
```

### 2B. Portfolio CRUD (should work)

```
Add RELIANCE (10 shares, avg price 2400), TCS (5 shares, avg price 3500), and INFY (15 shares, avg price 1600) to my portfolio. Then show me get_portfolio_summary.
```

### 2C. News (should work)

```
Get the latest company news for RELIANCE using get_company_news with max_results=3.
```

### 2D. Permission boundary — MUST SHOW

```
Run portfolio_health_check on my portfolio.
```

> **Expected:** 403 insufficient_scope. Free tier lacks `portfolio:risk`.
> **Talking point:** Tool-level scope enforcement — free users discover fewer tools than analysts (tier-aware capability negotiation).

---

## SECTION 3: Premium Tier (`premium` / `premiumpass`)

> Switch user (see instructions above)

### 3A. Build a diversified portfolio

```
Add these to my portfolio:
- RELIANCE, 50 shares at 2400
- TCS, 30 shares at 3500
- INFY, 20 shares at 1600
- HDFCBANK, 40 shares at 1550
- SBIN, 25 shares at 780
- ITC, 60 shares at 440

Then show get_portfolio_summary.
```

### 3B. Health check (should work — premium has portfolio:risk)

```
Run portfolio_health_check. What concentration or sector risks are flagged?
```

> **Talking point:** Flags single stocks >20% or sectors >40%. Alerts persisted to Redis, available via `portfolio://alerts` resource.

### 3C. Concentration risk

```
Run check_concentration_risk. Which stocks or sectors breach thresholds?
```

### 3D. MF overlap — MUST SHOW for PS2

```
Run check_mf_overlap for my portfolio.
```

> **Expected:** Shows which holdings overlap with popular large-cap mutual fund schemes (data from MFapi.in). "Your banking exposure is higher than you think."

### 3E. Macro sensitivity

```
Run check_macro_sensitivity. Which holdings are sensitive to RBI rate changes?
```

> **Talking point:** Pulls live RBI data, flags Financials (rate-sensitive) and IT (forex-sensitive) holdings.

### 3F. Sentiment shift detection

```
Run detect_sentiment_shift. Compare 7-day vs 30-day news sentiment for my holdings.
```

> **Talking point:** Uses GNews API with date-range filtering, lexicon scoring on article titles. Compares sentiment windows.

### 3G. Permission boundary — MUST SHOW

```
Run portfolio_risk_report.
```

> **Expected:** 403 insufficient_scope. Premium lacks `research:generate` (analyst-only).

```
Run what_if_analysis with rbi_rate_change_bps=-25.
```

> **Expected:** 403. Cross-source tools are analyst-only.

---

## SECTION 4: Analyst Tier (`analyst` / `analystpass`)

> Switch user (see instructions above)

### 4A. Build a skewed portfolio (interesting risk results)

```
Add these to my portfolio:
- RELIANCE, 100 shares at 2400
- TCS, 10 shares at 3500
- INFY, 5 shares at 1600
- HDFCBANK, 80 shares at 1550
- SBIN, 15 shares at 780
- ITC, 200 shares at 440
- BAJFINANCE, 3 shares at 6800

Show get_portfolio_summary.
```

### 4B. Full risk sweep

```
Run all five risk tools on my portfolio and summarize:
1. portfolio_health_check
2. check_concentration_risk
3. check_mf_overlap
4. check_macro_sensitivity
5. detect_sentiment_shift
```

### 4C. Portfolio risk report — MUST SHOW (cross-source reasoning)

```
Generate a portfolio_risk_report.
```

> **This is the PS2 "must-show cross-source moment."** The tool combines:
> - Current prices [Yahoo Finance / NSE]
> - Sector mapping [derived from holdings]
> - Macro indicators [RBI DBIE]
> - News sentiment [GNews API]
> - MF overlap [MFapi.in]
> - Fundamentals (PE, market cap) [Yahoo Finance]
>
> Into a single structured risk narrative with citations from each source.

### 4D. What-if analysis — MUST SHOW

```
Run what_if_analysis with rbi_rate_change_bps=-50 to simulate a 50bps RBI rate cut.
```

> **Talking point:** Cross-references each holding's rate sensitivity with historical Nifty reactions to past easing. Shows affected sectors (Financials benefit, IT neutral).

```
Now run what_if_analysis with rbi_rate_change_bps=25 for a rate hike scenario.
```

### 4E. Cross-reference signals

```
Run cross_reference_signals for RELIANCE. Does price action confirm or contradict the news?
```

> **Talking point:** Pulls from 3+ APIs (NSE quote, GNews sentiment, MFapi overlap), explicitly states confirm vs contradict.

### 4F. Invalid symbol validation

```
Try to add XYZFAKE with 10 shares at 500.
```

> **Expected:** Server rejects it — validates against Yahoo Finance.

---

## SECTION 5: MCP Resources

```
Read these MCP resources:
- market://overview
- macro://snapshot
- portfolio://holdings
- portfolio://alerts
- portfolio://risk_score
```

> **Talking point:** Resources are auth-scoped. `portfolio://` URIs are per-user (keyed to JWT `sub`). Resource subscriptions fire `notifications/resources/updated` when risk tools update alerts or `refresh_market_overview` is called.

### Refresh and observe notification

```
Call refresh_market_overview to invalidate the cache and trigger a resource update notification.
```

---

## SECTION 6: MCP Prompts

Prompts are tier-gated and work as slash commands in Gemini CLI:

```
/morning_risk_brief
```

> Generates a daily brief: portfolio value, overnight news per holding, macro changes, risk flags.

```
/rebalance_suggestions
```

> Analyzes concentration risks and produces illustrative trim/tilt ideas.

```
/earnings_exposure
```

> Maps holdings to upcoming earnings dates and assesses timing risk.

---

## Evaluation Criteria Checklist

### MCP Server Design & Compliance (25%)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Correct tools, resources, prompts with schemas | Done | 30+ tools, 5 resources, 3 prompts |
| Streamable HTTP transport | Done | `http://localhost:8000/mcp` |
| Tier-aware capability negotiation | Done | Free sees fewer tools than Analyst |
| Structured JSON responses | Done | Every tool returns `{source, disclaimer, timestamp, data}` |
| Pagination | Done | `get_price_history`, `get_company_news` support cursor/page |
| Error handling | Done | Graceful degradation on upstream failures |
| Caching | Done | TTL-based per data type (quote 60s, news 30min, financials 24h) |

### Authentication & Authorisation (25%)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| OAuth 2.1 + PKCE | Done | Keycloak public client, `code_challenge_method=S256` |
| Protected Resource Metadata (RFC 9728) | Done | `/.well-known/oauth-protected-resource/mcp` |
| Bearer token validation (signature, expiry, aud) | Done | `JWTVerifier` with JWKS, issuer, audience=`account` |
| 401 with WWW-Authenticate + resource_metadata | Done | See Section 1 demo |
| Tiered access (3 tiers) | Done | Free / Premium / Analyst with 16 scopes |
| Rate limiting with 429 + Retry-After | Done | Redis sliding window, HTTP middleware |
| Auth server separate from MCP | Done | Keycloak on :8090, MCP on :8000 |
| Upstream API key isolation | Done | Keys in server `.env`, never in responses |

### Cross-Source Reasoning (25%)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Combines data from multiple APIs | Done | `portfolio_risk_report` uses 5+ sources |
| Confirms/contradicts across sources | Done | `cross_reference_signals` explicit verdicts |
| Specific evidence citations | Done | Source fields cite API names |
| Adds insight beyond individual APIs | Done | Risk narrative, what-if scenarios |

### System Design (15%)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Caching strategy | Done | Redis, TTL per data type |
| Rate limiting (per-user, per-tier) | Done | Redis sorted-set sliding window |
| Upstream quota awareness | Done | GNews daily quota cap |
| Token validation | Done | JWKS + issuer + audience |
| Audit logging | Done | JSON audit log per tool call |

### Demo & Usability (10%)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Works with MCP client | Done | Gemini CLI + Cursor |
| Auth flow → discovery → tools → boundary → upgrade | Done | This guide covers all |
| Docker Compose (one command) | Done | `docker compose up -d --build` |
| Clear setup instructions | Done | README.md + this guide |

---

## Test Users Quick Reference

| Username | Password | Tier | Key scopes |
|----------|----------|------|------------|
| `free` | `freepass` | Free | `market:read`, `news:read`, `portfolio:read/write`, `mf:read` |
| `premium` | `premiumpass` | Premium | + `fundamentals:read`, `technicals:read`, `macro:read`, `portfolio:risk`, `news:sentiment` |
| `analyst` | `analystpass` | Analyst | + `filings:read/deep`, `macro:historical`, `research:generate` |

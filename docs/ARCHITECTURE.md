# StockSonar — Architecture & Technical Documentation

## Overview

StockSonar is a production-grade MCP (Model Context Protocol) server for Indian financial intelligence. It wraps free Indian financial APIs into structured MCP primitives (tools, resources, prompts) with OAuth 2.1 authentication, tiered authorization, Redis caching, and cross-source reasoning.

**Use case:** PS2 — Portfolio Risk & Alert Monitor.

---

## System Architecture

```mermaid
graph TB
    subgraph Client["MCP Client (LLM)"]
        GeminiCLI["Gemini CLI / Cursor / Claude Desktop"]
    end

    subgraph Keycloak["Keycloak :8090<br/>(Authorization Server)"]
        KC_Realm["Realm: stocksonar"]
        KC_Client["Client: stocksonar-mcp<br/>(public, PKCE)"]
        KC_Users["Users:<br/>free → tier-free<br/>premium → tier-premium<br/>analyst → tier-analyst"]
        KC_OIDC["/.well-known/<br/>openid-configuration"]
    end

    subgraph MCP["MCP Server :8000 (FastMCP)"]
        direction TB
        subgraph AuthLayer["Auth Layer"]
            JWT["JWTVerifier<br/>(JWKS, issuer, audience)"]
            RoleMap["RoleMappingJWTVerifier<br/>realm role → OAuth scopes"]
            ScopeCheck["require_scopes()<br/>per-tool enforcement"]
            JWT --> RoleMap --> ScopeCheck
        end
        subgraph Middleware["Middleware"]
            RateLimit["Rate Limiter<br/>(Redis sliding window)"]
            HTTP429["HTTP 429 Rewriter"]
            Audit["Audit Logger<br/>(JSON structured)"]
        end
        subgraph ToolLayer["Tool / Resource / Prompt Layer"]
            Tools["30+ Tools"]
            Resources["5 Resources"]
            Prompts["3 Prompts"]
        end
        AuthLayer --> Middleware --> ToolLayer
    end

    subgraph DataStores["Data & Upstream"]
        Redis[("Redis<br/>Cache · Rate Limits<br/>Portfolios · Alerts")]
        subgraph FreeAPIs["Upstream APIs (no key)"]
            YF["Yahoo Finance"]
            NSE["NSE India"]
            MFapi["MFapi.in"]
            RBI["RBI DBIE"]
        end
        subgraph KeyedAPIs["Upstream APIs (key required)"]
            GNews["GNews API"]
            Finnhub["Finnhub"]
            AV["Alpha Vantage"]
        end
    end

    GeminiCLI -- "1. GET /mcp → 401<br/>2. OAuth 2.1 + PKCE" --> Keycloak
    Keycloak -- "JWT with<br/>realm roles" --> MCP
    GeminiCLI -- "3. Bearer JWT<br/>(every request)" --> MCP
    ToolLayer --> Redis
    ToolLayer --> FreeAPIs
    ToolLayer --> KeyedAPIs

    style Client fill:#e3f2fd,stroke:#1565c0,color:#0d1117
    style Keycloak fill:#fff3e0,stroke:#e65100,color:#0d1117
    style MCP fill:#e8f5e9,stroke:#2e7d32,color:#0d1117
    style DataStores fill:#f3e5f5,stroke:#6a1b9a,color:#0d1117
    style AuthLayer fill:#c8e6c9,stroke:#388e3c,color:#0d1117
    style Middleware fill:#c8e6c9,stroke:#388e3c,color:#0d1117
    style ToolLayer fill:#c8e6c9,stroke:#388e3c,color:#0d1117
```

---

## OAuth 2.1 Authentication Flow

### The full flow step-by-step

```mermaid
sequenceDiagram
    participant C as MCP Client<br/>(Gemini CLI)
    participant M as MCP Server<br/>(:8000)
    participant K as Keycloak<br/>(:8090)
    participant B as Browser

    Note over C,K: Phase 1 — Discovery
    C->>M: 1. GET /mcp
    M-->>C: 2. 401 Unauthorized<br/>WWW-Authenticate: Bearer<br/>resource_metadata="/.well-known/oauth-protected-resource/mcp"

    C->>M: 3. GET /.well-known/oauth-protected-resource/mcp
    M-->>C: 4. JSON: { authorization_servers: ["localhost:8090/..."],<br/>scopes_supported: [...] }

    C->>K: 5. GET /.well-known/openid-configuration
    K-->>C: 6. OIDC metadata (auth_endpoint, token_endpoint, ...)

    Note over C,K: Phase 2 — OAuth 2.1 + PKCE
    C->>B: 7. Open browser → Keycloak login
    Note right of B: code_challenge_method=S256
    B->>K: 8. User enters credentials<br/>(e.g. analyst / analystpass)
    K-->>B: 9. Redirect with authorization code
    B-->>C: Authorization code via callback

    C->>K: 10. POST /token<br/>(code + code_verifier)
    K-->>C: 11. JWT access token<br/>(contains realm_access.roles)

    Note over C,M: Phase 3 — Authenticated MCP Session
    C->>M: 12. POST /mcp<br/>Authorization: Bearer JWT
    Note right of M: 13. Validate JWT:<br/>• JWKS signature<br/>• issuer match<br/>• audience = "account"<br/>• expiry check<br/>• Extract realm roles<br/>• Map roles → scopes
    M-->>C: 14. MCP response (tools discovered)
```

### Key standards implemented

| Standard | Implementation |
|----------|---------------|
| **OAuth 2.1 + PKCE** | Keycloak public client `stocksonar-mcp`, `code_challenge_method=S256` |
| **RFC 9728** (Protected Resource Metadata) | `/.well-known/oauth-protected-resource/mcp` endpoint |
| **RFC 8707** (Resource Indicators) | JWT `aud` claim bound to `account` |
| **Bearer Token (RFC 6750)** | All requests validated via `Authorization: Bearer <JWT>` |
| **401 with Discovery** | `WWW-Authenticate` header includes `resource_metadata` URL |

---

## Keycloak Configuration

### Realm: `stocksonar`

Defined in `keycloak/stocksonar-realm.json`, auto-imported on first boot via `--import-realm`.

```json
{
  "realm": "stocksonar",
  "accessTokenLifespan": 28800,
  "sslRequired": "none"
}
```

### Client: `stocksonar-mcp`

```json
{
  "clientId": "stocksonar-mcp",
  "publicClient": true,
  "directAccessGrantsEnabled": true,
  "standardFlowEnabled": true,
  "redirectUris": ["*"],
  "protocolMappers": [{
    "name": "access-token-audience-account",
    "protocolMapper": "oidc-audience-mapper",
    "config": {
      "included.client.audience": "account",
      "access.token.claim": "true"
    }
  }]
}
```

- **Public client** — no client secret (PKCE required)
- **Direct access grants** — enabled for password-grant test scripts
- **Audience mapper** — ensures `aud: "account"` in every access token (server validates this)

### Users and Realm Roles

| Username | Password | Realm Role | Mapped Scopes |
|----------|----------|------------|---------------|
| `free` | `freepass` | `tier-free` | `market:read`, `mf:read`, `news:read`, `portfolio:read`, `portfolio:write`, `watchlist:read`, `watchlist:write` |
| `premium` | `premiumpass` | `tier-premium` | All Free + `fundamentals:read`, `technicals:read`, `macro:read`, `portfolio:risk`, `news:sentiment` |
| `analyst` | `analystpass` | `tier-analyst` | All Premium + `filings:read`, `filings:deep`, `macro:historical`, `research:generate` |

### Role-to-Scope Mapping

Keycloak issues JWTs with `realm_access.roles`. The MCP server's `RoleMappingJWTVerifier` extracts roles from the JWT claims and maps them to OAuth-style scopes:

```mermaid
graph LR
    subgraph JWT["JWT Claims"]
        Roles["realm_access.roles:<br/>[&quot;tier-analyst&quot;]"]
    end

    subgraph Server["MCP Server"]
        Verifier["RoleMappingJWTVerifier"]
        Mapper["scopes_for_realm_roles()"]
        Verifier --> Mapper
    end

    subgraph Scopes["Effective Scopes (16)"]
        S1["market:read"]
        S2["portfolio:read / :write / :risk"]
        S3["fundamentals:read"]
        S4["technicals:read"]
        S5["macro:read / :historical"]
        S6["news:read / :sentiment"]
        S7["filings:read / :deep"]
        S8["research:generate"]
        S9["mf:read, watchlist:*"]
    end

    Roles --> Verifier
    Mapper --> Scopes

    style JWT fill:#fff3e0,stroke:#e65100,color:#0d1117
    style Server fill:#e8f5e9,stroke:#2e7d32,color:#0d1117
    style Scopes fill:#e3f2fd,stroke:#1565c0,color:#0d1117
```

Each tool is registered with `@mcp.tool(auth=require_scopes("scope:name"))`. FastMCP checks the token's scopes before execution.

---

## Authorization: Tiered Access Control

### Scope Design (16 scopes)

| Scope | Purpose | Free | Premium | Analyst |
|-------|---------|:----:|:-------:|:-------:|
| `market:read` | Quotes, price history, indices, movers | Y | Y | Y |
| `mf:read` | Mutual fund NAV, search, comparison | Y | Y | Y |
| `news:read` | Company/market news articles | Y | Y | Y |
| `portfolio:read` | Read portfolio holdings | Y | Y | Y |
| `portfolio:write` | Add/remove portfolio holdings | Y | Y | Y |
| `watchlist:read` | Read watchlist | Y | Y | Y |
| `watchlist:write` | Modify watchlist | Y | Y | Y |
| `fundamentals:read` | Financial statements, ratios | - | Y | Y |
| `technicals:read` | Technical indicators, options | - | Y | Y |
| `macro:read` | RBI rates, inflation (current) | - | Y | Y |
| `portfolio:risk` | Risk tools (health check, concentration) | - | Y | Y |
| `news:sentiment` | Sentiment analysis | - | Y | Y |
| `filings:read` | List company filings | - | - | Y |
| `filings:deep` | Retrieve full filing documents | - | - | Y |
| `macro:historical` | Full historical macro time series | - | - | Y |
| `research:generate` | Cross-source reasoning tools | - | - | Y |

### PS2 Tool-to-Tier Mapping

| Tool | Scope Required | Free | Premium | Analyst |
|------|---------------|:----:|:-------:|:-------:|
| `add_to_portfolio` | `portfolio:write` + `portfolio:read` | Y | Y | Y |
| `remove_from_portfolio` | `portfolio:write` + `portfolio:read` | Y | Y | Y |
| `get_portfolio_summary` | `portfolio:read` | Y | Y | Y |
| `portfolio_health_check` | `portfolio:risk` | - | Y | Y |
| `check_concentration_risk` | `portfolio:risk` | - | Y | Y |
| `check_mf_overlap` | `portfolio:risk` | - | Y | Y |
| `check_macro_sensitivity` | `portfolio:risk` | - | Y | Y |
| `detect_sentiment_shift` | `portfolio:risk` | - | Y | Y |
| `portfolio_risk_report` | `research:generate` | - | - | Y |
| `what_if_analysis` | `research:generate` | - | - | Y |
| `cross_reference_signals` | `research:generate` | - | - | Y |

### Enforcement Points

```mermaid
flowchart TD
    A["Request arrives<br/>POST /mcp + Bearer JWT"] --> B{"HTTP Layer<br/>Starlette Middleware"}
    B -- "No token / expired /<br/>bad signature" --> B1["401 Unauthorized<br/>+ WWW-Authenticate"]
    B -- "Token valid" --> C{"FastMCP Layer<br/>require_scopes()"}
    C -- "Missing required scope" --> C1["403 Forbidden<br/>insufficient_scope"]
    C -- "Scopes OK" --> D{"Tool Layer<br/>enforce_tool_policies()"}
    D -- "Rate limit exceeded" --> D1["429 Too Many Requests<br/>+ Retry-After header"]
    D -- "Within limits" --> E["Tool Executes"]
    E --> F["Audit Log<br/>(user_id, tier, tool, timestamp)"]
    F --> G["ok_response()<br/>{source, disclaimer,<br/>timestamp, data}"]

    style B1 fill:#ffcdd2,stroke:#c62828,color:#0d1117
    style C1 fill:#ffcdd2,stroke:#c62828,color:#0d1117
    style D1 fill:#fff3e0,stroke:#e65100,color:#0d1117
    style G fill:#c8e6c9,stroke:#2e7d32,color:#0d1117
```

---

## Rate Limiting

### Mechanism

Redis sorted set per user (`ratelimit:{user_sub}`), scored by Unix timestamp. 1-hour sliding window.

| Tier | Limit | Redis Key Example |
|------|-------|-------------------|
| Free | 30 req/hour | `ratelimit:77aa51f3-...` |
| Premium | 150 req/hour | `ratelimit:88bb62g4-...` |
| Analyst | 500 req/hour | `ratelimit:99cc73h5-...` |

### How 429 is returned

```mermaid
sequenceDiagram
    participant Tool as Tool Function
    participant Guard as tool_guard.py
    participant Redis as Redis<br/>(Sorted Set)
    participant FastMCP as FastMCP<br/>Framework
    participant MW as http_rate_limit.py<br/>(ASGI Middleware)
    participant Client as MCP Client

    Tool->>Guard: enforce_tool_policies()
    Guard->>Redis: ZREMRANGEBYSCORE + ZCARD<br/>ratelimit:{user_sub}
    Redis-->>Guard: count = 31 (limit = 30)
    Guard->>Guard: Raise RateLimitToolError<br/>(retry_after=2847)
    Guard-->>FastMCP: MCP tool error response<br/>(__STOCKSONAR_RATE_LIMIT__ retry_after=2847)
    FastMCP-->>MW: HTTP 200 with error body
    MW->>MW: Detect rate-limit marker<br/>Rewrite response
    MW-->>Client: HTTP 429<br/>Retry-After: 2847<br/>JSON-RPC error code -32029
```

---

## Upstream API Integration

### Data Sources (6 integrated)

| Source | Module | Data Type | Auth | TTL |
|--------|--------|-----------|------|-----|
| **Yahoo Finance** (`yfinance`) | `upstream/yfinance_client.py` | Market data, quotes, fundamentals | No key | 60s (quotes) |
| **NSE India** (`jugaad-data`) | `upstream/nse.py` | Indices, top movers, equity quotes | No key | 60s |
| **MFapi.in** | `upstream/mfapi.py` | Mutual fund NAV, scheme search | No key | 1h |
| **GNews** | `upstream/news.py` | News articles, sentiment | API key | 30min |
| **RBI DBIE** (`jugaad-data`) | `upstream/macro.py` | Repo rate, CPI, forex, GDP | No key | 1h |
| **BSE India** | `upstream/filings_upstream.py` | Corporate filings | No key | 24h |

### API Key Isolation

- All upstream API keys are stored in server-side `.env` / container environment variables
- Keys are **never** exposed in tool responses or to MCP clients
- The `Settings` class loads them via `pydantic-settings` from environment
- `.env` is gitignored; `.env.example` documents required keys with sign-up links

### Upstream Quota Awareness

- **GNews:** Server tracks daily call count via `gnews_quota.py` (Redis counter, default cap: 90/day to stay under 100/day free tier)
- **NSE India:** Rate-limited by source; wrapped in `asyncio.to_thread` to avoid blocking
- **yfinance:** Unofficial, no hard quota; `get_quote()` wrapped in try/except for invalid tickers

### Caching Strategy

| Data Type | TTL | Storage |
|-----------|-----|---------|
| Stock quotes | 60 seconds | Redis |
| News articles | 30 minutes | Redis |
| Financial statements | 24 hours | Redis |
| Mutual fund NAV | 1 hour | Redis |
| Index data | 60 seconds | Redis |
| Macro snapshot | 1 hour | Process-local + Redis |
| Filings metadata | 24 hours | Redis |

All caching uses `RedisCache` with type-based keys (`{data_type}:{identifier}`) and configurable TTLs in `Settings`.

---

## MCP Primitive Design Decisions

### Why Tools vs Resources vs Prompts?

| Primitive | When to use | StockSonar examples |
|-----------|-------------|---------------------|
| **Tool** | Active computation, API calls, side effects | `get_stock_quote`, `add_to_portfolio`, `portfolio_risk_report` |
| **Resource** | Read-only state snapshots, subscriptions | `portfolio://holdings`, `market://overview`, `macro://snapshot` |
| **Prompt** | LLM instruction templates that orchestrate multiple tools | `morning_risk_brief`, `rebalance_suggestions` |

**Tools** are the primary interface — they take parameters, call upstream APIs, apply business logic, and return structured JSON. Every tool output includes `{source, disclaimer, timestamp, data}`.

**Resources** expose persisted state (portfolio holdings in Redis, computed risk scores, cached market snapshots). They support subscriptions — the server fires `notifications/resources/updated` when underlying data changes (e.g., after `portfolio_health_check` updates alerts).

**Prompts** are meta-instructions for the LLM. They don't call APIs directly — they tell the LLM *which tools to call and how to synthesize results*. This keeps the server as a data provider (structured JSON) while the LLM handles narrative.

### Tool Response Format

Every tool returns:

```json
{
  "source": "Yahoo Finance + NSE India (jugaad-data)",
  "disclaimer": "Information is for informational purposes only and is not financial advice.",
  "timestamp": "2026-04-04T10:21:52.123456+00:00",
  "data": { ... }
}
```

- `source` — cites exactly which upstream API(s) provided the data
- `disclaimer` — configurable, always present (not financial advice)
- `timestamp` — UTC ISO 8601
- `data` — structured payload (never free-form text)

---

## Cross-Source Reasoning

### `portfolio_risk_report` (the PS2 differentiator)

Combines data from 5+ sources in a single tool call:

```mermaid
graph LR
    subgraph Sources["Data Sources"]
        YF["Yahoo Finance<br/>LTP, PE, Market Cap"]
        NSE["NSE / Holdings<br/>Sector mapping"]
        RBI["RBI DBIE<br/>Repo rate, CPI"]
        GN["GNews<br/>News + sentiment"]
        MF["MFapi.in<br/>MF overlap"]
        YF2["Yahoo Finance<br/>Quarterly income"]
    end

    subgraph Tool["portfolio_risk_report"]
        Combine["Cross-source<br/>aggregation"]
    end

    subgraph Output["Structured Output"]
        V["Holdings valuation<br/>(LTP, allocation_pct, sector)"]
        R["Risk flags<br/>(concentration, sector tilt)"]
        MA["Macro assessment<br/>(adverse_macro, reasons)"]
        NS["News summary<br/>per holding"]
        MO["MF overlap count<br/>+ scheme names"]
        FS["Fundamentals slice<br/>(PE, market cap, income)"]
        NR["Narrative with<br/>source citations"]
    end

    YF --> Combine
    NSE --> Combine
    RBI --> Combine
    GN --> Combine
    MF --> Combine
    YF2 --> Combine
    Combine --> Output

    style Sources fill:#e3f2fd,stroke:#1565c0,color:#0d1117
    style Tool fill:#fff3e0,stroke:#e65100,color:#0d1117
    style Output fill:#e8f5e9,stroke:#2e7d32,color:#0d1117
```

### `what_if_analysis`

Simulates RBI rate change scenarios:

```mermaid
graph LR
    subgraph Inputs["Inputs"]
        Rate["rbi_rate_change_bps<br/>(e.g. -50)"]
        Holdings["Portfolio holdings<br/>sector classification"]
        Rules["Sensitivity rules<br/>Financials: +1.5%/-25bps<br/>IT: -0.5%/-25bps"]
        Nifty["Yahoo Finance<br/>Historical Nifty returns<br/>around past easing"]
        Macro["Macro snapshot<br/>Current RBI repo rate"]
    end

    subgraph WhatIf["what_if_analysis"]
        Sim["Scenario<br/>simulation"]
    end

    subgraph Out["Output"]
        Impact["Per-holding impact<br/>(sector, sensitivity,<br/>estimated_pct_change)"]
        Hist["Historical reaction<br/>(Nifty around rate cuts)"]
        Sum["Scenario summary"]
    end

    Rate --> Sim
    Holdings --> Sim
    Rules --> Sim
    Nifty --> Sim
    Macro --> Sim
    Sim --> Out

    style Inputs fill:#e3f2fd,stroke:#1565c0,color:#0d1117
    style WhatIf fill:#fff3e0,stroke:#e65100,color:#0d1117
    style Out fill:#e8f5e9,stroke:#2e7d32,color:#0d1117
```

### `cross_reference_signals`

Explicit confirm/contradict analysis:

```mermaid
graph LR
    subgraph APIs["Data Sources"]
        YF["Yahoo Finance<br/>Price change % today"]
        GN["GNews<br/>News + lexicon sentiment"]
        MF["MFapi.in<br/>MF scheme overlap"]
    end

    subgraph XRef["cross_reference_signals"]
        Analyze["Confirm /<br/>contradict<br/>analysis"]
    end

    subgraph Signals["Output Signals"]
        PS["Price signal<br/>(up/down/flat)"]
        SS["Sentiment signal<br/>(positive/negative)"]
        MS["MF signal<br/>(high/medium/low)"]
        Confirm["Confirmations<br/>'Price up + sentiment<br/>positive → confirmed'"]
        Contra["Contradictions<br/>'Price down but sentiment<br/>positive → divergence'"]
    end

    YF --> Analyze
    GN --> Analyze
    MF --> Analyze
    Analyze --> Signals

    style APIs fill:#e3f2fd,stroke:#1565c0,color:#0d1117
    style XRef fill:#fff3e0,stroke:#e65100,color:#0d1117
    style Signals fill:#e8f5e9,stroke:#2e7d32,color:#0d1117
```

---

## Resource Subscriptions (PS2 Key Differentiator)

### How it works

```mermaid
sequenceDiagram
    participant RT as Risk Tool<br/>(e.g. portfolio_health_check)
    participant MA as merge_risk_alerts()
    participant Redis as Redis
    participant Notify as notify_portfolio_resources_updated()
    participant Client as MCP Client<br/>(subscribed)

    RT->>RT: Compute risk flags
    RT->>MA: Pass new alerts
    MA->>Redis: Upsert alerts<br/>(precedence merging,<br/>max 30, 24h TTL)
    RT->>Notify: ctx, user_id
    Notify-->>Client: ResourceUpdatedNotification<br/>portfolio://{user_id}/holdings
    Notify-->>Client: ResourceUpdatedNotification<br/>portfolio://{user_id}/alerts
    Notify-->>Client: ResourceUpdatedNotification<br/>portfolio://{user_id}/risk_score
    Client->>Redis: Re-read updated resources
    Redis-->>Client: Latest alerts & risk score
```

Similarly, `refresh_market_overview` invalidates the market cache and fires `notify_market_overview_updated` for `market://overview` subscribers.

### Alert Merging

```mermaid
flowchart LR
    subgraph Producers["Alert Producers"]
        HC["portfolio_health_check"]
        CR["check_concentration_risk"]
        MS["check_macro_sensitivity"]
        SS["detect_sentiment_shift"]
        MO["check_mf_overlap"]
    end

    subgraph Merge["merge_risk_alerts()"]
        Key["Composite key<br/>(type + symbol/sector)"]
        Prec["Precedence rules<br/>health_check wins<br/>on duplicates"]
        Cap["Cap: max 30 alerts<br/>sorted by type"]
    end

    subgraph Redis["Redis"]
        Store[("portfolio:{user}/alerts<br/>TTL: 24 hours")]
    end

    HC -- "HEALTH_SOURCE<br/>(authoritative)" --> Merge
    CR --> Merge
    MS --> Merge
    SS --> Merge
    MO --> Merge
    Merge --> Store

    style Producers fill:#e3f2fd,stroke:#1565c0,color:#0d1117
    style Merge fill:#fff3e0,stroke:#e65100,color:#0d1117
    style Redis fill:#ffcdd2,stroke:#c62828,color:#0d1117
```

- Each alert has a composite key (type + symbol/sector)
- Alerts from `portfolio_health_check` are authoritative (won't be overwritten by other tools)
- Maximum 30 alerts retained, sorted by type
- Alerts expire after 24 hours (Redis TTL)

---

## Audit Logging

Every tool invocation is logged as a structured JSON line:

```json
{
  "event": "tool_call",
  "tool_name": "portfolio_health_check",
  "user_id": "77aa51f3-c038-4157-8427-bff97e8e0d12",
  "tier": "analyst",
  "success": true,
  "detail": {},
  "timestamp": "2026-04-04T10:21:52.123456"
}
```

Failed calls (rate limit exceeded) include `detail.error` and `detail.retry_after`.

---

## Docker Compose Deployment

### Services & Network Topology

```mermaid
graph TB
    subgraph DockerNet["Docker Compose Network"]
        Redis[("Redis :6379<br/>Alpine 7<br/>Cache · Rate Limits<br/>Portfolio Store")]
        KC["Keycloak :8080<br/>v26.0<br/>OAuth 2.1 AuthZ Server"]
        MCP_S["MCP Server :8000<br/>Python 3.12<br/>FastMCP StockSonar"]

        MCP_S -- "redis:6379<br/>(internal)" --> Redis
        MCP_S -- "JWKS validation<br/>keycloak:8080<br/>(internal)" --> KC
    end

    subgraph Host["Host Machine"]
        H_KC["Host :8090<br/>(Keycloak UI)"]
        H_MCP["Host :8000<br/>(MCP endpoint)"]
    end

    KC -. "port mapping<br/>8080 → 8090" .-> H_KC
    MCP_S -. "port mapping<br/>8000 → 8000" .-> H_MCP

    style DockerNet fill:#e3f2fd,stroke:#1565c0,color:#0d1117
    style Host fill:#f3e5f5,stroke:#6a1b9a,color:#0d1117
    style Redis fill:#ffcdd2,stroke:#c62828,color:#0d1117
    style KC fill:#fff3e0,stroke:#e65100,color:#0d1117
    style MCP_S fill:#c8e6c9,stroke:#2e7d32,color:#0d1117
```

- Redis is **internal only** — not exposed to the host
- Keycloak maps 8080 → host 8090 (avoids port conflicts)
- MCP server connects to Redis at `redis:6379` and validates JWTs against Keycloak's JWKS at `keycloak:8080`
- MCP server's issuer config uses `localhost:8090` (what the client sees) while JWKS URI uses `keycloak:8080` (internal, faster)

### One-command start

```bash
docker compose up -d --build
```

---

## Project Structure

```
StockSonar/
├── docker-compose.yml              # Redis + Keycloak + MCP server
├── Dockerfile                      # Python 3.12 slim image
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata, pytest config
├── .env.example                    # Environment variable documentation
├── .env.llm                        # Static-token auth mode for local LLM dev
├── .gemini/settings.json           # Gemini CLI MCP config
├── .cursor/mcp.json                # Cursor MCP config
├── .mcp.json                       # Claude Code MCP config
├── keycloak/
│   └── stocksonar-realm.json       # Realm, users, roles, client config
├── src/stocksonar/
│   ├── server.py                   # FastMCP entrypoint, lifespan, health route
│   ├── config.py                   # pydantic-settings (env vars → Settings)
│   ├── auth/
│   │   ├── provider.py             # Build RemoteAuthProvider (Keycloak or static)
│   │   ├── role_verifier.py        # JWT realm roles → OAuth scopes
│   │   └── scopes.py              # Scope definitions, tier mapping
│   ├── cache/
│   │   └── redis_cache.py          # TTL-based Redis cache (get/set/delete JSON)
│   ├── middleware/
│   │   ├── tool_guard.py           # Rate limit check + audit per tool call
│   │   ├── rate_limiter.py         # Redis sorted-set sliding window
│   │   ├── http_rate_limit.py      # ASGI middleware: rewrite to HTTP 429
│   │   └── audit.py               # Structured JSON audit logging
│   ├── services/
│   │   ├── portfolio.py            # PortfolioStore (Redis CRUD for holdings/alerts)
│   │   ├── portfolio_alerts.py     # Alert normalization and precedence merging
│   │   ├── market_overview.py      # Cached market overview builder
│   │   └── watchlist.py            # WatchlistStore (Redis)
│   ├── tools/
│   │   ├── register.py             # Registers all tools, resources, prompts
│   │   ├── market.py               # get_stock_quote, get_price_history, get_index_data, ...
│   │   ├── portfolio.py            # add/remove/summary/health_check
│   │   ├── portfolio_metrics.py    # Shared valuation helpers
│   │   ├── risk.py                 # concentration, MF overlap, macro, sentiment
│   │   ├── cross_source.py         # portfolio_risk_report, what_if, cross_reference
│   │   ├── news_tools.py           # company_news, market_news, sentiment
│   │   ├── fundamentals_tools.py   # financial statements, ratios, shareholding
│   │   ├── technicals_tools.py     # indicators, option chains
│   │   ├── macro_tools.py          # macro snapshot, historical series
│   │   ├── mutual_funds.py         # search, NAV, compare
│   │   ├── filings_tools.py        # list filings, get document
│   │   ├── watchlist_tools.py      # add/remove/list watchlist
│   │   ├── aliases_ps2.py          # Thin aliases (get_rbi_rates, get_inflation_data, ...)
│   │   ├── prompts_ps2.py          # morning_risk_brief, rebalance, earnings_exposure
│   │   ├── resources_portfolio.py  # portfolio:// resources
│   │   ├── resources_market_macro.py # market:// + macro:// resources
│   │   └── resources_watchlist.py  # watchlist:// resources
│   ├── upstream/
│   │   ├── yfinance_client.py      # Yahoo Finance wrapper
│   │   ├── nse.py                  # NSE India (jugaad-data)
│   │   ├── news.py                 # GNews API client + sentiment lexicon
│   │   ├── macro.py                # RBI macro data
│   │   ├── macro_historical.py     # Historical macro time series
│   │   ├── mfapi.py                # MFapi.in mutual fund client
│   │   ├── fundamentals_data.py    # Company fundamentals (yfinance)
│   │   ├── filings_upstream.py     # BSE filings
│   │   ├── technicals_data.py      # Technical indicators
│   │   └── gnews_quota.py          # GNews daily quota tracking
│   ├── util/
│   │   ├── response.py             # ok_response() — standard output format
│   │   ├── notifications.py        # Resource update notifications
│   │   └── pagination.py           # Cursor-based pagination helper
│   └── exceptions.py              # RateLimitToolError, custom exceptions
├── tests/
│   ├── ps2/                        # PS2-specific unit tests
│   └── integration/                # PKCE + live MCP integration tests
├── scripts/
│   ├── ps2_interactive.py          # Interactive menu-driven PS2 shell
│   ├── run_judge_demo.py           # Automated judge demo script
│   ├── call_all_mcp_tools.py       # Full tool sweep
│   ├── check_stack_health.py       # Stack readiness probe
│   ├── run_integration_tests.py    # pytest wrapper with logging
│   └── e2e_common.py              # Shared E2E utilities
├── docs/
│   ├── DEMO_GUIDE.md              # Step-by-step demo script for judges
│   ├── ARCHITECTURE.md            # This file
│   ├── gemini_test_prompts.md     # Copy-paste prompts for Gemini CLI testing
│   └── problem_statement.md       # PS2 requirements breakdown
└── logs/                          # Auto-generated demo/test logs (gitignored)
```

---

## API Reference

### Tools (30+)

#### Portfolio Management (all tiers)

| Tool | Parameters | Scope | Description |
|------|-----------|-------|-------------|
| `add_to_portfolio` | `symbol`, `quantity`, `avg_buy_price` | `portfolio:write` + `portfolio:read` | Add/update holding (validates symbol via Yahoo Finance) |
| `remove_from_portfolio` | `symbol` | `portfolio:write` + `portfolio:read` | Remove a holding |
| `get_portfolio_summary` | — | `portfolio:read` | Value, P&L, allocation with live quotes |

#### PS2 Risk Detection (premium+)

| Tool | Parameters | Scope | Description |
|------|-----------|-------|-------------|
| `portfolio_health_check` | — | `portfolio:risk` | Concentration + sector exposure snapshot |
| `check_concentration_risk` | — | `portfolio:risk` | Flag single stock >20% or sector >40% |
| `check_mf_overlap` | — | `portfolio:risk` | Check holdings overlap with popular MF schemes |
| `check_macro_sensitivity` | — | `portfolio:risk` | Flag rate/forex sensitive holdings + macro conditions |
| `detect_sentiment_shift` | — | `portfolio:risk` | 7-day vs 30-day news sentiment comparison |

#### Cross-Source Reasoning (analyst only)

| Tool | Parameters | Scope | Description |
|------|-----------|-------|-------------|
| `portfolio_risk_report` | — | `research:generate` | Full cross-source risk narrative (5+ APIs) |
| `what_if_analysis` | `rbi_rate_change_bps` | `research:generate` | Rate change scenario simulation |
| `cross_reference_signals` | `symbol` | `research:generate` | Confirm/contradict across price, news, MF |

#### Market Data (free+)

| Tool | Parameters | Scope | Description |
|------|-----------|-------|-------------|
| `get_stock_quote` | `ticker` | `market:read` | Live quote (LTP, change, volume, P/E, 52W) |
| `get_price_history` | `ticker`, `start`, `end`, `interval`, `cursor`, `limit` | `market:read` | Historical OHLCV (paginated) |
| `get_index_data` | `index_name` | `market:read` | Nifty 50, Bank Nifty, sectoral indices |
| `get_top_gainers_losers` | `exchange` | `market:read` | Today's top movers |
| `refresh_market_overview` | — | `portfolio:risk` | Invalidate market cache + notify subscribers |

*(Additional tools: `get_technical_indicators`, `get_options_chain`, `get_financial_statements`, `get_shareholding_structure`, `get_corporate_actions`, `get_earnings_calendar`, `search_mutual_funds`, `get_fund_nav`, `compare_mutual_funds`, `get_company_news`, `get_market_news`, `analyze_news_sentiment`, `get_macro_snapshot_tool`, `get_macro_historical_series`, `list_company_filings`, `get_filing_document`, `add_watchlist_symbol`, `remove_watchlist_symbol`, `list_watchlist`, `get_rbi_rates`, `get_inflation_data`, `get_news_sentiment`)*

### Resources (5)

| URI Pattern | Scope | Description |
|-------------|-------|-------------|
| `portfolio://{user_id}/holdings` | `portfolio:risk` | User's current portfolio |
| `portfolio://{user_id}/alerts` | `portfolio:risk` | Active risk alerts |
| `portfolio://{user_id}/risk_score` | `portfolio:risk` | Overall risk score |
| `market://overview` | `macro:read` | Nifty, Bank Nifty, top movers |
| `macro://snapshot` | `macro:read` | RBI rates, CPI, macro indicators |

### Prompts (3)

| Name | Parameters | Scope | Description |
|------|-----------|-------|-------------|
| `morning_risk_brief` | — | `portfolio:read` + `news:read` + `macro:read` | Daily portfolio risk briefing |
| `rebalance_suggestions` | `focus_sector` (optional) | `portfolio:risk` | Concentration-based rebalancing ideas |
| `earnings_exposure` | — | `portfolio:read` + `fundamentals:read` | Map holdings to upcoming earnings |

---

## Security Summary

| Concern | Implementation |
|---------|---------------|
| Token validation | JWKS signature + issuer + audience + expiry |
| Scope enforcement | `require_scopes()` on every tool/resource/prompt |
| API key isolation | Server `.env` only, never in responses |
| Rate limiting | Per-user Redis sliding window, HTTP 429 + Retry-After |
| Audit trail | JSON-structured log per tool invocation |
| PKCE | Mandatory for all MCP clients (public client) |
| Upstream failures | Graceful degradation (return cached data or clear error) |
| Input validation | Symbol validation via Yahoo Finance before portfolio add |

# Remote MCP demo (`jarvis-kd.duckdns.org`)

HTTPS stack on DuckDNS. Use these files to connect **Gemini CLI**, **Claude Code**, and **Claude Desktop** from your Mac.

| Client | Config file |
|--------|-------------|
| Gemini CLI | `.gemini/settings.json` ← copy from [gemini.settings.example.json](gemini.settings.example.json) |
| Claude Code | `.mcp.json` ← copy from [claude.mcp.example.json](claude.mcp.example.json) |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` — see **[CLAUDE_DESKTOP_SETUP.md](CLAUDE_DESKTOP_SETUP.md)** |

**Server URL:** `https://jarvis-kd.duckdns.org/mcp`  
**Keycloak (browser):** `https://jarvis-kd.duckdns.org` (same host; Caddy routes `/realms*`)

---

## Gemini CLI

1. From the StockSonar repo root:

   ```bash
   mkdir -p .gemini
   cp demo-remote/gemini.settings.example.json .gemini/settings.json
   ```

2. Run Gemini from the **repo root** (so it loads `.gemini/settings.json`):

   ```bash
   gemini
   ```

3. Authenticate (order matters):

   ```text
   /mcp auth stocksonar
   ```

   Browser opens Keycloak on `https://jarvis-kd.duckdns.org`. Log in (e.g. `analyst` / `analystpass`).

4. Confirm: `/mcp` shows `stocksonar (CONNECTED)`.

If you cached an old host or token:

```bash
rm -f ~/.gemini/mcp-oauth-tokens.json
```

---

## Claude Code

1. Copy the example into the repo root:

   ```bash
   cp demo-remote/claude.mcp.example.json .mcp.json
   ```

2. Restart Claude Code. Complete OAuth when prompted (Keycloak on `https://jarvis-kd.duckdns.org`).

If OAuth does not start automatically, use the **Claude Desktop + mcp-remote** flow below (same HTTPS URL).

---

## Claude Desktop

**Full steps:** [CLAUDE_DESKTOP_SETUP.md](CLAUDE_DESKTOP_SETUP.md)

Quick version:

1. **Node 18+** on your Mac (`node -v`).
2. Edit `~/Library/Application Support/Claude/claude_desktop_config.json` — merge [claude_desktop_config.snippet.json](claude_desktop_config.snippet.json) and fix the two `@/Users/...` paths to your machine.
3. `rm -rf ~/.mcp-auth`
4. Quit Claude (**Cmd+Q**), reopen → **Settings → Developer → MCP** → **stocksonar**.
5. Browser login at `https://jarvis-kd.duckdns.org`.

---

## OAuth helper files (Claude Desktop)

| File | Purpose |
|------|---------|
| [oauth_client_info.json](oauth_client_info.json) | Fixed client `stocksonar-mcp` (no DCR) |
| [oauth_client_metadata.json](oauth_client_metadata.json) | Scopes `openid profile email` only |

---

## Log out / switch user

| Method | How |
|--------|-----|
| In Claude chat | *"Use StockSonar logout_switch_user"* |
| Mac script | `./demo-remote/logout-stocksonar.sh` |
| Browser | `https://jarvis-kd.duckdns.org/auth/logout` |

Then quit Claude (**Cmd+Q**), reopen, toggle **stocksonar** in Developer → MCP.

Requires server build with `logout_switch_user` tool (rsync + `docker compose ... up -d --build`).

---

## Test users (Keycloak)

| User | Password | Tier |
|------|----------|------|
| `free` | `freepass` | market, portfolio CRUD |
| `premium` | `premiumpass` | + risk tools |
| `analyst` | `analystpass` | + `portfolio_risk_report`, `what_if_analysis` |

Tier tools come from **realm roles** in the JWT, not from extra OAuth scope strings.

---

## Verify server (from Mac)

```bash
curl -s https://jarvis-kd.duckdns.org/health
curl -s https://jarvis-kd.duckdns.org/realms/stocksonar/.well-known/openid-configuration | head -3
```

---

## EC2 checklist

- `.env` uses `https://jarvis-kd.duckdns.org` (see `.env.example`)
- Start: `docker compose -f docker-compose.yml -f deploy/docker-compose.https.yml up -d`
- Security group: **22**, **80**, **443**
- DuckDNS points at EC2 public IP: `dig +short jarvis-kd.duckdns.org`

See [docs/DEPLOY_HTTPS_DDNS.md](../docs/DEPLOY_HTTPS_DDNS.md).

# Claude Desktop + StockSonar (HTTPS)

Connect Claude Desktop to **`https://jarvis-kd.duckdns.org/mcp`** via **`mcp-remote`** (stdio bridge + Keycloak OAuth).

Use **Settings → Developer → MCP** (`claude_desktop_config.json`). Do **not** use “Add custom connector” unless you also allow Anthropic cloud IPs to reach your server.

---

## Prerequisites (Mac)

- **Node.js 18+** — `node -v`, `npx -v`
- StockSonar repo cloned (for `demo-remote/oauth_*.json` paths)
- Server healthy:

  ```bash
  curl -s https://jarvis-kd.duckdns.org/health
  ```

---

## Step 1 — Claude Desktop config file

**Path (macOS):**

`~/Library/Application Support/Claude/claude_desktop_config.json`

Create the file if it does not exist. Merge this into `"mcpServers"` (keep any other servers you already have):

```json
{
  "mcpServers": {
    "stocksonar": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://jarvis-kd.duckdns.org/mcp",
        "3334",
        "--host",
        "127.0.0.1",
        "--auth-timeout",
        "120",
        "--static-oauth-client-info",
        "@/Users/sriram/GenAIHackathon/StockSonar/demo-remote/oauth_client_info.json",
        "--static-oauth-client-metadata",
        "@/Users/sriram/GenAIHackathon/StockSonar/demo-remote/oauth_client_metadata.json"
      ]
    }
  }
}
```

### You must change

Replace **`@/Users/sriram/GenAIHackathon/StockSonar/...`** with the **absolute path** to your clone on your Mac (both lines). The `@` prefix tells `mcp-remote` to read the JSON file.

Example if repo is elsewhere:

`@/Users/you/projects/StockSonar/demo-remote/oauth_client_info.json`

Or copy from [claude_desktop_config.snippet.json](claude_desktop_config.snippet.json) and edit paths.

### What each arg does

| Arg | Why |
|-----|-----|
| `https://jarvis-kd.duckdns.org/mcp` | Remote MCP (HTTPS — no `--allow-http`) |
| `3334` | Fixed OAuth callback port on your Mac |
| `--host 127.0.0.1` | Callback listener host (must match Keycloak redirect URIs) |
| `--auth-timeout 120` | More time for browser login |
| `--static-oauth-client-info` | Use Keycloak client `stocksonar-mcp` (no dynamic registration) |
| `--static-oauth-client-metadata` | Scopes `openid profile email` only (no `offline_access`) |

---

## Step 2 — Clear old OAuth cache

```bash
rm -rf ~/.mcp-auth
```

Do this whenever you change the MCP URL, Keycloak user, or config paths.

---

## Step 3 — Restart Claude Desktop

1. **Quit completely** — **Cmd+Q** (not just close the window).
2. Reopen Claude.
3. Open **Settings → Developer → MCP** (or the MCP / tools panel).
4. Enable **stocksonar** if it is toggled off.

---

## Step 4 — First connect

1. Claude starts `npx mcp-remote ...`.
2. Your browser opens **Keycloak** at `https://jarvis-kd.duckdns.org`.
3. Log in — for full demo use **`analyst`** / **`analystpass`**.
4. Browser redirects to `http://127.0.0.1:3334/oauth/callback?code=...` — leave the tab open until it finishes.
5. Claude should show **stocksonar** connected with tools.

### Test users

| User | Password | Tier |
|------|----------|------|
| `free` | `freepass` | basic tools |
| `premium` | `premiumpass` | + risk tools |
| `analyst` | `analystpass` | + PS2 report / what-if |

---

## Step 5 — Try in chat

```
Use StockSonar to get the stock quote for RELIANCE.
```

```
Add TCS and INFY to my portfolio and run portfolio_health_check.
```

As **analyst**:

```
Generate a portfolio_risk_report for my portfolio.
```

---

## Log out / switch user (from Claude)

Claude Desktop cannot clear OAuth tokens by itself. Use one of these:

### Option A — Ask Claude (after you deploy the latest server)

In chat:

```text
Use StockSonar logout_switch_user and walk me through switching to the free tier user.
```

Claude calls the **`logout_switch_user`** tool, opens the logout link, and shows the steps.

Check who is logged in:

```text
Use StockSonar current_session
```

### Option B — One-click script (Mac)

```bash
/path/to/StockSonar/demo-remote/logout-stocksonar.sh
```

Opens Keycloak logout, clears `~/.mcp-auth`. Then **Cmd+Q** Claude and toggle **stocksonar** in MCP settings.

### Option C — Browser bookmark

Open: `https://jarvis-kd.duckdns.org/auth/logout`  
Then `rm -rf ~/.mcp-auth`, restart Claude, reconnect.

### Option D — Manual

1. Log out: `https://jarvis-kd.duckdns.org/auth/logout?go=1`
2. `rm -rf ~/.mcp-auth`
3. Quit Claude (**Cmd+Q**), reopen, toggle **stocksonar** in Developer → MCP
4. Log in as `free`, `premium`, or `analyst`

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| MCP server missing | Validate JSON (no trailing commas); restart Claude |
| `npx` not found | Install Node.js 18+ |
| `client-registration` / DCR error | Ensure `--static-oauth-client-info` + `oauth_client_info.json` |
| `offline_access` error | Use `oauth_client_metadata.json` (`openid profile email` only) |
| **`No authorization code received`** | See below |
| Connection refused / timeout | `curl https://jarvis-kd.duckdns.org/health`; check EC2 SG **443** |
| 403 on risk tools | Log in as `premium` or `analyst` |
| 403 on `portfolio_risk_report` | Need `analyst` |

Logs:

```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

Optional: add `"--debug"` to `args` in the config.

### Fix: `No authorization code received`

1. `rm -rf ~/.mcp-auth`
2. Config must use port **`3334`** and **`--host 127.0.0.1`** (see JSON above).
3. Keycloak client **stocksonar-mcp** must allow:
   - `http://127.0.0.1:3334/oauth/callback`
   - `http://localhost:3334/oauth/callback`  
   (already in `keycloak/stocksonar-realm.json` — re-import realm on EC2 if needed.)
4. Test outside Claude:

   ```bash
   npx -y mcp-remote https://jarvis-kd.duckdns.org/mcp 3334 --host 127.0.0.1 \
     --static-oauth-client-info @/Users/sriram/GenAIHackathon/StockSonar/demo-remote/oauth_client_info.json \
     --static-oauth-client-metadata @/Users/sriram/GenAIHackathon/StockSonar/demo-remote/oauth_client_metadata.json \
     --debug
   ```

   Success: **Authorization successful!** and URL contains `?code=`.

5. Do not close the browser before redirect to `127.0.0.1:3334`.

---

## 2-minute checklist

- [ ] `curl https://jarvis-kd.duckdns.org/health` OK from Mac
- [ ] `claude_desktop_config.json` has correct **absolute** `@...` paths
- [ ] `rm -rf ~/.mcp-auth` if you changed user or config
- [ ] Claude fully restarted (Cmd+Q)
- [ ] Logged in as `analyst` for full PS2 demo

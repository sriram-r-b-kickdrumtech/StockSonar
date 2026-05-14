# Remote MCP demo (EC2 URL)

Use these samples to point **Gemini CLI** or **Claude** at your StockSonar stack on AWS (`http://15.206.82.198:8000/mcp`, Keycloak on `http://15.206.82.198:8090`).

The JSON examples are set to **`15.206.82.198`**. If your instance IP changes, search-replace that host in each file.

---

## Gemini CLI

1. Copy `gemini.settings.example.json` into the project as **`.gemini/settings.json`**, or merge the `stocksonar` block into `~/.gemini/settings.json`.
2. From the project directory, run `gemini`, then:

   ```text
   /mcp auth stocksonar
   ```

   Browser should open to **Keycloak on port 8090** on the same host.

3. Confirm: `/mcp` shows `stocksonar (CONNECTED)`.

If you cached an old host, clear tokens and re-auth:

```bash
rm -f ~/.gemini/mcp-oauth-tokens.json
```

---

## Claude Code (repo `.mcp.json`)

1. Copy `claude.mcp.example.json` to the repo root as **`.mcp.json`** (or merge the `stocksonar` entry into your existing file).
2. Restart Claude Code. If the client does not complete OAuth automatically, use the **Claude Desktop + mcp-remote** pattern below or run the server in **static** auth mode with a bearer header (see main [README.md](../README.md)).

---

## Claude Desktop (optional)

Merge `claude_desktop_mcp-remote.example.json` into:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Restart Claude Desktop.

---

## Checklist on EC2

- Security group allows **8000** and **8090** from where you demo.
- `.env` on the server sets `MCP_BASE_URL`, `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_ISSUER`, and `KEYCLOAK_AUTHORIZATION_SERVER` to `http://15.206.82.198:...` (see [docs/DEPLOY_AWS_EC2.txt](../docs/DEPLOY_AWS_EC2.txt)).
- `docker compose up -d` is healthy: `curl -s http://15.206.82.198:8000/health`

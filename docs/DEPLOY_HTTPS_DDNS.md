# HTTPS with DuckDNS (`jarvis-kd.duckdns.org`)

One hostname, free TLS from **Let's Encrypt**, via **Caddy** in Docker.

| URL | Service |
|-----|---------|
| `https://jarvis-kd.duckdns.org/mcp` | StockSonar MCP |
| `https://jarvis-kd.duckdns.org/realms/stocksonar/...` | Keycloak (login + OAuth) |
| `https://jarvis-kd.duckdns.org/health` | MCP health |

Local `docker compose up` (no overlay) still uses `http://localhost:8000` and `:8090`.

---

## 1. DuckDNS

1. Create subdomain **`jarvis-kd`** at [duckdns.org](https://www.duckdns.org) → `jarvis-kd.duckdns.org`.
2. Set the IP to your EC2 **public IPv4** (panel or updater).
3. Confirm:

```bash
dig +short jarvis-kd.duckdns.org
# Must match EC2 public IP (e.g. 3.110.215.65)
```

**Keep IP updated** after stop/start (new public IP):

```bash
# On EC2 (replace token and subdomain)
curl -s "https://www.duckdns.org/update?domains=jarvis-kd&token=YOUR_DUCKDNS_TOKEN&ip="
```

Or install DuckDNS cron on the instance.

**EC2 public IP** (IMDSv2):

```bash
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/public-ipv4
# If empty: attach Elastic IP, or use:
curl -s https://checkip.amazonaws.com
```

---

## 2. AWS security group

| Port | Purpose |
|------|---------|
| 22 | SSH |
| 80 | HTTP (Let's Encrypt + redirect) |
| 443 | HTTPS |

You can **close** public **8000** and **8090** when using Caddy only.

---

## 3. `.env` on the server

In `~/StockSonar/.env`:

```env
GNEWS_API_KEY=your_key
AUTH_MODE=keycloak

MCP_BASE_URL=https://jarvis-kd.duckdns.org
KEYCLOAK_PUBLIC_URL=https://jarvis-kd.duckdns.org
KEYCLOAK_ISSUER=https://jarvis-kd.duckdns.org/realms/stocksonar
KEYCLOAK_AUTHORIZATION_SERVER=https://jarvis-kd.duckdns.org/realms/stocksonar
```

No `:8000` or `:8090` — Caddy serves on 443.

---

## 4. Start stack with HTTPS overlay

```bash
cd ~/StockSonar
docker compose -f docker-compose.yml -f deploy/docker-compose.https.yml up -d --build
docker compose -f docker-compose.yml -f deploy/docker-compose.https.yml logs -f caddy
```

Look for `certificate obtained successfully` for `jarvis-kd.duckdns.org`.

---

## 5. Verify

```bash
curl -s --max-time 10 https://jarvis-kd.duckdns.org/health
curl -s https://jarvis-kd.duckdns.org/realms/stocksonar/.well-known/openid-configuration | head
```

Test from your **Mac**, not only from EC2 (hairpin can mislead).

---

## 6. Clients (Gemini / Claude)

### Gemini (`.gemini/settings.json`)

```json
{
  "mcpServers": {
    "stocksonar": {
      "httpUrl": "https://jarvis-kd.duckdns.org/mcp",
      "trust": true,
      "timeout": 60000,
      "oauth": {
        "clientId": "stocksonar-mcp",
        "scopes": ["openid", "profile", "email"]
      }
    }
  }
}
```

### Claude Desktop

Use `https://jarvis-kd.duckdns.org/mcp` in `mcp-remote` (no `--allow-http`).

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `dig` wrong IP | Update DuckDNS; wait a few minutes |
| `curl` hangs | DNS not pointing at EC2, or SG missing 80/443 |
| Caddy `Caddyfile` mount error | `rm -rf ~/StockSonar/Caddyfile` if Docker created a directory; use `deploy/Caddyfile` |
| Cert fails | `dig` must match this server; restart caddy after DNS fix |
| Metadata `public-ipv4` empty | Use IMDSv2 token (above) or attach Elastic IP |
| OAuth issuer mismatch | All `.env` URLs use same `https://jarvis-kd.duckdns.org` host |

After changing domain in `deploy/Caddyfile`, update `.env`, rsync, `docker compose ... up -d`, restart Caddy.

# StockSonar — Gemini CLI Test Prompts

Copy-paste these prompts into Gemini CLI to exercise every part of the system.
Between sections you'll need to re-authenticate as a different Keycloak user.

**How to switch users:**

1. **Log out of Keycloak first** — open this in your browser:
   ```
   http://localhost:8090/realms/stocksonar/protocol/openid-connect/logout?redirect_uri=http://localhost:8090
   ```
2. **Delete cached tokens:**
   ```bash
   rm -f ~/.gemini/mcp-oauth-tokens.json
   ```
3. **Re-authenticate in Gemini CLI:**
   ```
   /mcp auth stocksonar
   ```
   The browser will open the Keycloak login page — enter the new user credentials.

If Keycloak still auto-logs in as the old user, use an **incognito/private window** or clear browser cookies for `localhost:8090`.

---

## SECTION 1 — Free tier (`free` / `freepass`)

### 1A. Market data (should work)

```
Get the current stock quote for RELIANCE using the MCP tools. Then get the stock quote for TCS as well. Show me both results.
```

### 1B. Portfolio basics (should work)

```
Add these stocks to my portfolio using add_to_portfolio:
- RELIANCE, 10 shares at avg price 2400
- TCS, 5 shares at avg price 3500
- INFY, 15 shares at avg price 1600
- HDFCBANK, 8 shares at avg price 1550

Then call get_portfolio_summary to show my full portfolio with current values.
```

### 1C. News (should work)

```
Get the latest company news for RELIANCE and TCS using get_company_news with max_results=3 for each. Summarize the headlines.
```

### 1D. Mutual funds (should work)

```
Search for mutual funds with the query "HDFC equity" using search_mutual_funds. Show the top 5 results.
```

### 1E. Risk tools — SHOULD FAIL (free tier blocked)

```
Run portfolio_health_check on my portfolio. What do you see?
```

> **Expected:** The tool should be denied / return an authorization error because `free` lacks the `portfolio:risk` scope.

### 1F. Fundamentals — SHOULD FAIL (free tier blocked)

```
Get the financial statements for TCS using get_financial_statements.
```

> **Expected:** Denied — `free` lacks `fundamentals:read`.

---

## SECTION 2 — Premium tier (`premium` / `premiumpass`)

> **Switch user:** `/mcp auth stocksonar` → log in as `premium` / `premiumpass`

### 2A. Build a portfolio

```
Add these stocks to my portfolio:
- RELIANCE, 50 shares at avg price 2400
- TCS, 30 shares at avg price 3500
- INFY, 20 shares at avg price 1600
- HDFCBANK, 40 shares at avg price 1550
- SBIN, 25 shares at avg price 780
- ITC, 60 shares at avg price 440

Then show me get_portfolio_summary.
```

### 2B. Portfolio health check (should work — premium has portfolio:risk)

```
Run portfolio_health_check. Are there any concentration or sector risks flagged?
```

### 2C. Concentration risk

```
Run check_concentration_risk on my portfolio. Which stocks exceed the 20% single-name threshold? Which sectors exceed 40%?
```

### 2D. Mutual fund overlap

```
Run check_mf_overlap to see if any of my holdings appear heavily in popular mutual fund schemes.
```

### 2E. Macro sensitivity

```
Run check_macro_sensitivity. Are any of my holdings sensitive to RBI rate changes or forex moves? Is the current macro environment adverse?
```

### 2F. Sentiment shift detection

```
Run detect_sentiment_shift for my portfolio. Compare the 7-day vs 30-day news sentiment for my holdings. Are there any significant shifts?
```

### 2G. Fundamentals + technicals (should work — premium tier)

```
Get the financial statements for RELIANCE using get_financial_statements, and also run get_technical_indicators for RELIANCE with period "3mo". Summarize the key metrics.
```

### 2H. Macro data (should work)

```
Call get_macro_snapshot_tool to show the latest RBI policy rates, CPI, and macro indicators. Also call get_rbi_rates as a cross-check.
```

### 2I. Cross-source tools — SHOULD FAIL (analyst only)

```
Run portfolio_risk_report for my portfolio.
```

> **Expected:** Denied — `premium` lacks `research:generate`.

```
Run what_if_analysis with rbi_rate_change_bps=-50 to simulate a 50bps rate cut.
```

> **Expected:** Denied — `premium` lacks `research:generate`.

---

## SECTION 3 — Analyst tier (`analyst` / `analystpass`)

> **Switch user:** `/mcp auth stocksonar` → log in as `analyst` / `analystpass`

### 3A. Build a skewed portfolio (for interesting risk results)

```
Add these stocks to my portfolio using add_to_portfolio:
- RELIANCE, 100 shares at avg price 2400
- TCS, 10 shares at avg price 3500
- INFY, 5 shares at avg price 1600
- HDFCBANK, 80 shares at avg price 1550
- SBIN, 15 shares at avg price 780
- ITC, 200 shares at avg price 440
- BAJFINANCE, 3 shares at avg price 6800

Then show me the full get_portfolio_summary.
```

### 3B. Full PS2 risk sweep

```
Run ALL of these risk tools on my portfolio, one by one, and summarize the findings:
1. portfolio_health_check
2. check_concentration_risk
3. check_mf_overlap
4. check_macro_sensitivity
5. detect_sentiment_shift

For each tool, show me the key flags and data points.
```

### 3C. Portfolio risk report (analyst cross-source)

```
Generate a full portfolio_risk_report. This should combine holdings valuation, news sentiment, macro indicators, mutual fund overlap, and fundamentals (PE ratio, market cap) for my top holdings. Show me everything.
```

### 3D. What-if analysis — rate cut scenario

```
Run what_if_analysis with rbi_rate_change_bps=-50 to simulate a 50 basis point RBI rate cut. What sectors benefit? What's the historical Nifty reaction to easing? How are my holdings affected?
```

### 3E. What-if analysis — rate hike scenario

```
Run what_if_analysis with rbi_rate_change_bps=25 to simulate a 25 basis point rate hike. How does this change the picture vs the rate cut scenario?
```

### 3F. Cross-reference signals for a single stock

```
Run cross_reference_signals for RELIANCE. Does the recent price action confirm or contradict the news sentiment? Are mutual funds aligned?
```

### 3G. Market overview and macro resources

```
First call refresh_market_overview to get fresh Nifty/Bank Nifty data. Then read these MCP resources:
- market://overview
- macro://snapshot

Show me the current market state and macro environment.
```

### 3H. Portfolio resources

```
Read these MCP resources for my portfolio:
- portfolio://holdings (my current holdings)
- portfolio://alerts (any active risk alerts)
- portfolio://risk_score (my portfolio risk score)

Show me all three.
```

### 3I. MCP Prompts (slash commands)

Try each of these MCP prompts (they're slash commands in Gemini CLI):

```
/morning_risk_brief
```

> Should generate a morning risk briefing using portfolio, news, and macro tools.

```
/rebalance_suggestions
```

> Should analyze concentration risks and suggest rebalancing ideas.

```
/earnings_exposure
```

> Should map holdings to upcoming earnings dates and assess timing risk.

### 3J. Filings (analyst only)

```
List the recent company filings for RELIANCE using list_company_filings. Then if any filing IDs are returned, fetch one with get_filing_document.
```

### 3K. Full tool inventory

```
List all available MCP tools using list_tools, and all available MCP prompts using list_prompts. How many tools total?
```

### 3L. Invalid symbol validation

```
Try to add a fake stock "XYZFAKE" with 10 shares at price 500 using add_to_portfolio. What happens?
```

> **Expected:** The server should reject it with a clear error saying the symbol is not found on NSE/BSE.

---

## SECTION 4 — Tier boundary probes (optional, for judges)

> These demonstrate that auth scoping is enforced. Switch users as indicated.

### 4A. Free can't do risk

> Log in as `free` / `freepass`

```
Try to call portfolio_health_check, check_concentration_risk, and detect_sentiment_shift. Report what happens for each.
```

### 4B. Premium can't do cross-source

> Log in as `premium` / `premiumpass`

```
Try to call portfolio_risk_report, what_if_analysis, and cross_reference_signals. Report what happens for each.
```

### 4C. Analyst can do everything

> Log in as `analyst` / `analystpass`

```
Call get_stock_quote for SBIN, then portfolio_health_check, then portfolio_risk_report, then what_if_analysis with rbi_rate_change_bps=-25. All four should succeed. Confirm.
```

---

## Quick reference

| User | Password | Tier | Can do |
|------|----------|------|--------|
| `free` | `freepass` | Free | Market quotes, news, portfolio CRUD, mutual funds, watchlist |
| `premium` | `premiumpass` | Premium | + Fundamentals, technicals, macro, PS2 risk tools, sentiment |
| `analyst` | `analystpass` | Analyst | + Cross-source (risk report, what-if), filings, prompts |

| Switch user in Gemini CLI | Command |
|---------------------------|---------|
| Re-authenticate | `/mcp auth stocksonar` |
| Check connection | `/mcp` |
| Clear old Keycloak session | Visit http://localhost:8090/realms/stocksonar/account → Sign Out |

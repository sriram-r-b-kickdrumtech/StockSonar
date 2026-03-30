# 🏆 AI League #3: MCP Servers for Indian

# Financial Intelligence

## Build a Production-Grade MCP Server with Real Auth &

## Cross-Source Reasoning

## 📌 Background

An Indian retail investor or analyst evaluating a stock today must manually check NSE/BSE for
live prices, visit Moneycontrol or Screener for fundamentals, open AMFI for mutual fund NAVs,
read SEBI/BSE filings for corporate announcements, track RBI data for macro indicators, and
scan financial news portals for sentiment. Each source has a different interface, different data
format, and no interoperability.
The good news: much of this data is freely available through public APIs and open data
sources. The bad news: there is no unified way for an AI assistant to discover and use all of
these capabilities together.
The **Model Context Protocol (MCP)** solves this. An MCP server wraps these existing APIs into
structured tools, resources, and prompts that any MCP-compatible client can discover and use.
But financial data is sensitive and role-dependent: a free-tier user shouldn't consume premium
API quotas, and a retail investor shouldn't see the same depth as a research analyst. This
makes authentication and authorisation essential engineering concerns.

## 🎯 The Challenge

Build a **production-grade MCP server** that wraps existing free Indian financial APIs into a
unified intelligence layer. The server exposes tools for NSE/BSE market data, fundamental
analysis, mutual fund data, news sentiment, regulatory filings, and macro-economic indicators
— all as MCP primitives (tools, resources, prompts).
The server must implement **OAuth 2.1-based authentication** and **role-based authorisation**
per the MCP authorisation specification, so different user tiers see different capabilities and rate
limits.


**Key constraint:** Spend most effort on MCP server design, auth implementation, and
cross-source reasoning — not on building financial models from scratch. The underlying data
comes from existing free APIs. Your job is to wrap them intelligently, add cross-source analysis,
and secure the whole thing properly.
⚡ **MVP Mindset:** This is a hackathon, not a production deployment. Focus your time on
the MCP server design, auth flow, and cross-source reasoning — the three things that get
judged hardest. For peripheral tasks (PDF parsing, analyst estimates, data ingestion),
take shortcuts if time consuming: hardcode sample data, use LLM extraction, mock what
you can't fetch. _A working demo with smart architecture beats a half-finished system that
tries to do everything from scratch!_

### 🔀 Choose Your Use Case

All teams build the **same base MCP server layer** (APIs, auth, tiered access, caching). What
differs is the **use case** you solve on top — this determines which tools you prioritize, what
cross-source reasoning looks like, and where your engineering depth goes.
**Pick ONE of three use cases below.** Each forces different architectural decisions. Choose
based on what excites you and where you want to push yourself.
● Shared Base Layer (Required for ALL Use Cases)

1. [PS1] USE CASE 1: Financial Research Copilot
2. [PS2] USE CASE 2: Portfolio Risk & Alert Monitor
3. [PS3] USE CASE 3: Earnings Season Command Center

## 📦 Shared Base Layer (Required for ALL Use Cases)

**This is what every team must build regardless of which use case they pick.**

### Pre-Built APIs to Integrate (Use at Least 4)

The following free APIs provide the raw data layer. Teams must integrate at least four. The
challenge is not calling these APIs — it's exposing them as well-designed MCP tools with proper
auth, error handling, caching, and cross-source reasoning on top.
**API / Source What It Provides Free Tier Modality
NSE India**
(stock-nse-india npm
/ direct)
Live quotes, indices, F&O data,
historical OHLCV, option chains, top
gainers/losers
Free, no key (rate
limited)

#### JSON,

```
Tabular
```

```
yfinance (.NS / .BO
tickers)
Historical prices, dividends, splits,
financials, balance sheet, cash flow
for NSE/BSE stocks
Free, no key
(unofficial)
Tabular,
JSON
MFapi.in Mutual fund NAV history, scheme
search, fund house data for all
AMFI-registered schemes
Free, no key JSON
Alpha Vantage (India
tickers: .BSE)
Stock prices, technicals (SMA, RSI,
MACD), fundamentals, news +
sentiment
25 req/day (free
key)
```
#### JSON,

```
Tabular
Finnhub (India
support)
Company news, earnings,
recommendations, insider
transactions
60 req/min (free
key)
```
#### JSON,

```
Text
BSE India
(bseindia.com APIs)
Corporate announcements, board
meetings, results, annual reports
(PDFs)
Free, no key PDF,
JSON
RBI DBIE
(data.rbi.org.in)
Macro data: repo rate, CPI inflation,
GDP, forex reserves, money supply
Free
(downloadable
datasets)
```
#### CSV,

#### JSON

```
data.gov.in Government open data: economic
indicators, sector-wise statistics
Free (API key
required)
```
#### JSON,

#### CSV

**NewsAPI.org /
GNews**
Indian financial news articles with
search and filtering
100 req/day (free
key)
Text,
Images
_Teams may substitute equivalent APIs (e.g., Twelve Data for technicals, Marketaux for
sentiment). The requirement is at least_ **_4 distinct data sources_** _covering at least_ **_3 data
types_** _(market data/tabular, text/news, and documents/PDFs or macro data)._

### Core Requirement: Authentication & Authorisation

**This is non-negotiable and common across all use cases.
Authentication Requirements:**
● OAuth 2.1 with PKCE — Mandatory for all MCP clients (public clients)
● Protected Resource Metadata (RFC 9728) — Serve
/.well-known/oauth-protected-resource advertising the authorisation server
and available scopes


● Bearer Token Validation — All operations validate token signature, expiry, audience
(RFC 8707), and scopes
● 401 with Discovery — Unauthenticated requests return 401 with WWW-Authenticate
header containing resource_metadata URL
**Authorisation: Tiered Access Control**
The server must enforce at least three user tiers:
**Free User Premium User Analyst
Market Data** Quotes, price
history, indices, top
movers
All Free + technicals, option
chains
All Premium +
everything
**Fundamentals** ❌ Financials, ratios, shareholding,
quarterly results, corporate
actions
All
**Mutual Funds** Search + NAV
lookup
All Free + comparison, overlap All
**News** Company news,
market news
All Free + sentiment analysis All
**Filings** ❌ ❌ Full filing retrieval
(PDFs)
**Macro** ❌ Current snapshot (RBI rates,
inflation)
Full historical
time series
**Cross-Source
Tools**
❌ ❌ All cross-source
reasoning tools
**Rate Limit** 30 calls/hour 150 calls/hour 500 calls/hour
Insufficient permissions → HTTP 403 with insufficient_scope. Rate limit exceeded →
HTTP 429 with Retry-After header.
**_Clarification on cross-source tools vs multi-API tools:_** _"Cross-source reasoning tools"
are the ones explicitly labeled as such in each use case (e.g.,
cross_reference_signals, portfolio_risk_report, earnings_verdict). Other
tools that internally call multiple APIs to serve their function (e.g., check_mf_overlap
calls MF + holdings data) are categorized by their primary scope, not as cross-source._


_Cross-source tools always require an Analyst tier. See per-use-case tier addendum tables
for specifics._
**Scope Design:**
● market:read — Live quotes, price history, indices, movers
● fundamentals:read — Financial statements, ratios, shareholding, results
● technicals:read — Technical indicators, option chains
● mf:read — Mutual fund NAV, search, comparison
● news:read — News articles and sentiment
● filings:read — List filings
● filings:deep — Retrieve full filing documents (PDFs)
● macro:read — RBI rates, inflation, forex (current)
● macro:historical — Full historical macro time series
● research:generate — Cross-source reasoning tools
● watchlist:read / watchlist:write — Personal watchlist
● portfolio:read / portfolio:write — Portfolio holdings, summaries, and risk
tools (PS2)

### Technical Requirements (All Use Cases)

**MCP Protocol Compliance:**
● Streamable HTTP transport for remote deployment
● Capability negotiation — tier-aware: Free users discover fewer tools than Analysts
● Pagination for news results, filing lists, price history
● Resource subscriptions (optional but encouraged) — notify clients when subscribed
resources change (e.g., watchlist ticker news, portfolio alerts, new filings posted). Core
to PS2; bonus for PS1/PS3.
● Structured error responses for API failures, rate limits, permission denials
**Identity Provider Integration:**
● OAuth 2.1-compliant auth server (Keycloak recommended; Auth0/Okta free tier
acceptable)
● Auth server separate from MCP server (Resource Server pattern)
● No token pass-through — MCP server manages its own upstream API keys
**API Key Management & Caching:**
● MCP server holds API keys for upstream providers in its own config — never exposed to
clients
● Rate limiting must respect both user tier limits AND upstream API quotas


● Aggressive caching: quotes cached ~60s, news ~30min, financials ~24h, filings
permanently
**Data Layer:**
● Cache for upstream API responses (TTL-based per data type)
● User data store for watchlists and cached research (scoped per user)
● Audit log: every tool invocation logged with user identity, tier, tool name, timestamp

### Constraints & Rules (All Use Cases)

```
● All tool outputs must cite their data source (e.g., "Source: NSE India", "Source: MFapi.in
scheme 125497", "Source: BSE Filing #12345")
● Tools must return structured JSON , not free-form text. The AI client handles narrative;
the server provides data
● Cross-source tools must explicitly list which sources confirmed or contradicted each
finding
● The MCP server must hold all upstream API keys internally — never expose them to
clients
● Responses must not constitute financial advice. Include appropriate disclaimers
● Handle upstream API downtime gracefully (return cached data or clear error, not crash)
```
## 🔀 [PS1] USE CASE 1: Financial Research Copilot

### "The full-stack analyst's assistant"

**_Pick this if_** _you want to build the broadest, most general-purpose financial intelligence
tool. You'll flex on breadth of integration, synthesis across many data types, and creating
an experience where an analyst can say "tell me everything about Reliance" and get a
genuinely useful answer._

### What You Build

A general-purpose research copilot. The user connects an MCP client (Claude Desktop, VS
Code), authenticates, and can run queries ranging from quick stock checks to full deep-dive
research briefs that pull data from 5+ sources.

### MCP Tools You Must Implement

**Market Data Tools:**


● get_stock_quote — Live/latest quote for an NSE/BSE ticker (LTP, change, volume,
market cap, P/E, 52W range)
● get_price_history — Historical OHLCV for a ticker over a date range
● get_index_data — Current value and composition of Nifty 50, Sensex, sectoral
indices
● get_top_gainers_losers — Today's top movers on NSE/BSE
● get_technical_indicators — SMA, EMA, RSI, MACD, Bollinger Bands for a ticker
**Fundamental Analysis Tools:**
● get_financial_statements — Income statement, balance sheet, cash flow
(annual/quarterly)
● get_key_ratios — P/E, P/B, ROE, ROCE, debt/equity, current ratio, dividend yield
● get_shareholding_pattern — Promoter, FII, DII, retail holdings over time
● get_quarterly_results — Latest quarterly results with YoY/QoQ comparison
**Mutual Fund Tools:**
● search_mutual_funds — Search schemes by name, fund house, or category
● get_fund_nav — Latest and historical NAV for a scheme
● compare_funds — Side-by-side comparison of 2-5 mutual fund schemes
**News & Sentiment Tools:**
● get_company_news — Latest news articles for a company
● get_news_sentiment — Aggregated sentiment for a company over a time window
● get_market_news — Broad Indian market and sector news
**Macro & Regulatory Tools:**
● get_rbi_rates — Current repo rate, reverse repo, CRR, SLR, and historical changes
● get_inflation_data — CPI and WPI inflation time series
● get_corporate_filings — List recent BSE/NSE filings for a company
**Cross-Source Reasoning Tools (the differentiator):**
● cross_reference_signals — Pull from multiple sources, identify confirmations or
contradictions. Example: "TCS share price fell 4% [NSE], but quarterly results show 8%
revenue growth [BSE filing], and FII holding increased 2% [shareholding data]. News
sentiment is negative due to US recession fears [NewsAPI], not company-specific
issues."


```
● generate_research_brief — Synthesise price data, fundamentals, MF exposure,
news, filings, and macro context into a structured research note with evidence citations
from each source.
● compare_companies — Side-by-side comparison of 2-5 companies across price
performance, fundamentals, shareholding, news sentiment, and mutual fund exposure.
```
### MCP Resources

```
● watchlist://{user_id}/stocks — User's personal watchlist (auth-scoped)
● research://{ticker}/latest — Most recent cached research brief
● market://overview — Nifty, Sensex, Bank Nifty, top gainers/losers, FII/DII flows
summary
● macro://snapshot — Latest repo rate, CPI, GDP growth, forex reserves, USD-INR
```
### MCP Prompts

```
● quick_analysis — Fast overview: quote + key ratios + recent news for a ticker
● deep_dive — Comprehensive: pulls all available data, cross-references, generates full
research brief
● sector_scan — Compare top companies in a Nifty sector index across fundamentals
and sentiment
● morning_brief — Daily summary: market overview + watchlist updates + macro
changes + key news
```
### PS1 Tier Addendum

```
Free Premium Analyst
quick_analysis prompt ✅^ ✅^ ✅^
deep_dive, sector_scan, morning_brief
prompts
```
#### ❌ ✅ ✅

```
cross_reference_signals,
generate_research_brief,
compare_companies
```
#### ❌ ❌ ✅

### Must-Show Demo Scenario

1. **Free user** connects → asks "What's happening with HDFC Bank?" → gets quote + news
    → tries fundamentals → hits 403


2. **Premium user** runs quick_analysis for INFY → gets quote + ratios + news +
    shareholding
3. **Analyst** runs deep_dive for RELIANCE → system pulls from 5+ sources → generates
    research brief with citations from each source → saved to
    research://RELIANCE/latest

### Must-Show Cross-Source Moment

cross_reference_signals for any ticker must combine data from at least 3 different APIs
and explicitly state what confirms vs contradicts across sources.

### Must-Show Auth Boundary

A free user attempts get_financial_statements → receives 403 with
insufficient_scope → upgrades to Premium → same call succeeds.

## 🔀 [PS2] USE CASE 2: Portfolio Risk & Alert Monitor

### "Your portfolio's always-on watchdog"

**_Pick this if_** _you want to go deep on real-time state management, event-driven
architecture, and personalised intelligence. You'll build something that feels alive — it
watches, detects, and alerts. MCP resources and subscriptions become your primary
primitives, not just tools._

### What You Build

A portfolio monitoring system. The user provides their holdings (list of stocks + quantities). The
MCP server continuously monitors for risk signals — concentration, sector tilt, macro sensitivity,
sentiment shifts — and surfaces alerts. Think of it as a personal risk analyst that never sleeps.

### MCP Tools You Must Implement

**Portfolio Management Tools:**
● add_to_portfolio — Add a stock with quantity and avg buy price to user's portfolio
● remove_from_portfolio — Remove a holding
● get_portfolio_summary — Current value, P&L, allocation breakdown by stock and
sector


● portfolio_health_check — Concentration risk, sector exposure, top holdings as %
of total
**Risk Detection Tools:**
● check_concentration_risk — Flag if any single stock > 20% of portfolio or any
sector > 40%
● check_mf_overlap — Given the user's stocks, check overlap with popular large-cap
MF schemes. Are they unintentionally duplicating exposure?
● check_macro_sensitivity — Given holdings, assess which are sensitive to RBI
rate changes, inflation, forex moves. Pull current macro data and flag if conditions are
adverse.
● detect_sentiment_shift — For each holding, compare last 7-day news sentiment
vs 30-day baseline. Flag significant shifts.
**Market Data Tools (shared base):**
● get_stock_quote — Live/latest quote
● get_price_history — Historical OHLCV
● get_index_data — Index values and composition
● get_top_gainers_losers — Today's movers
**Supporting Tools:**
● get_shareholding_pattern — Promoter, FII, DII holdings
● get_company_news — Latest news for a stock
● get_news_sentiment — Aggregated sentiment
● get_rbi_rates — Current macro rates
● get_inflation_data — CPI/WPI data
● search_mutual_funds / get_fund_nav — MF data for overlap checks
**Cross-Source Reasoning Tools (the differentiator):**
● portfolio_risk_report — Pulls market data + fundamentals + macro + news + MF
overlap for entire portfolio. Produces a structured risk report: "Your portfolio is 45% IT
sector [derived from holdings]. TCS and Infosys are both in your top 5 MF schemes
[MFapi cross-ref]. RBI held rates steady [RBI DBIE], but USD-INR weakened 2% this
month [macro], which historically pressures IT margins [news correlation]."
● what_if_analysis — "What happens to my portfolio if RBI cuts rates by 25bps?"
Cross-references each holding's rate sensitivity with historical price reactions to past rate
cuts.

### MCP Resources


```
● portfolio://{user_id}/holdings — User's current portfolio (persisted,
auth-scoped)
● portfolio://{user_id}/alerts — Active risk alerts for the portfolio
● portfolio://{user_id}/risk_score — Overall portfolio risk score (updated on
each health check)
● market://overview — Market summary
● macro://snapshot — Latest macro indicators
```
### Resource Subscriptions (Key Differentiator for This Use Case)

```
● Subscribe to portfolio://{user_id}/alerts — notify client when a new risk
signal is detected (e.g., a holding's sentiment shifts negative, or concentration risk
breaches threshold)
● Subscribe to market://overview — notify on significant market moves affecting
portfolio holdings
```
### MCP Prompts

```
● morning_risk_brief — Daily: portfolio value + overnight news for holdings + any
new alerts + macro changes that affect holdings
● rebalance_suggestions — Based on current risk flags, suggest trades to reduce
concentration or sector tilt
● earnings_exposure — Which holdings have upcoming earnings? What's the risk
from each?
```
### PS2 Tier Addendum

```
Free Premium Analyst
add_to_portfolio, remove_from_portfolio,
get_portfolio_summary
```
#### ✅ ✅ ✅

```
portfolio_health_check,
check_concentration_risk
```
#### ❌ ✅ ✅

```
check_mf_overlap,
check_macro_sensitivity,
detect_sentiment_shift
```
#### ❌ ✅ ✅

```
portfolio_risk_report, what_if_analysis ❌^ ❌^ ✅^
```

```
morning_risk_brief, rebalance_suggestions
prompts
```
#### ❌ ✅ ✅

```
Resource subscriptions on
portfolio://{user_id}/alerts
```
#### ❌ ✅ ✅

### Must-Show Demo Scenario

2. **Runs portfolio_health_check** — system flags concentration risk (e.g., "38% in IT
    sector — above 30% threshold")
3. **Runs check_mf_overlap** — "HDFC Bank and ICICI Bank are in 7 of the top 10
    large-cap MF schemes. Your banking exposure is higher than you think."
4. **Runs portfolio_risk_report** — full cross-source analysis combining market data,
    macro, news sentiment, and MF overlap

### Must-Show Cross-Source Moment

portfolio_risk_report must combine: current prices [NSE], sector mapping [derived],
macro indicators [RBI], news sentiment [NewsAPI/Finnhub], and MF overlap [MFapi] — into a
single coherent risk narrative with citations.

### Must-Show Auth Boundary

```
● Free user can add portfolio and see basic summary → attempts
portfolio_risk_report → 403
● Premium user can run health check and overlap → attempts what_if_analysis →
403
● Analyst gets everything including what_if_analysis and full risk reports
```
## 🔀 [PS3] USE CASE 3: Earnings Season Command

## Center

### "The results season war room"

**_Pick this if_** _you love working with documents, temporal logic, and structured data
extraction. You'll go deep on BSE filing PDFs, build pre-vs-post earnings workflows, and
create a system that can parse a quarterly result, compare it to expectations, and explain
the market's reaction — all from raw data._


### What You Build

An earnings-focused intelligence system. Built for results season (Jan-Feb, Apr-May, Jul-Aug,
Oct-Nov), where 50+ major companies report quarterly. The system tracks the earnings
calendar, builds pre-earnings profiles, parses post-earnings filings, and cross-references the
market reaction with actual numbers.

### MCP Tools You Must Implement

**Earnings Calendar Tools:**
● get_earnings_calendar — Upcoming results dates for Nifty 50 / Nifty 500
companies (next 2 weeks). Source: BSE announcements
● get_past_results_dates — Historical results announcement dates for a company
**Pre-Earnings Analysis Tools:**
● get_eps_history — Historical EPS (quarterly) for a company with YoY/QoQ trend
● get_pre_earnings_profile — For a given ticker: last 4 quarters of results + current
key ratios + shareholding changes (did FIIs buy/sell before results?) + options activity
(put/call OI at key strikes) + recent news sentiment
● get_analyst_expectations — Consensus estimates if available from Finnhub or
Alpha Vantage. **Practical note:** Free-tier coverage for Indian stocks is limited. It is
perfectly acceptable to use historical EPS growth rate extrapolation as the estimate, or
hardcode a small set of estimates for demo purposes. Don't spend hackathon time
chasing data that doesn't exist in free APIs.
**Post-Earnings Analysis Tools:**
● get_filing_document — Retrieve the actual quarterly result filing PDF from BSE
● parse_quarterly_filing — Extract revenue, profit, EPS, margins from the filing
PDF/HTML into structured data. **Practical note:** BSE filing PDFs have inconsistent
formats across companies. Teams may use LLM-based PDF extraction (send PDF
content to LLM with a structured output prompt) rather than building custom parsers. The
focus is on MCP integration and cross-source reasoning, not building a PDF parsing
engine from scratch.
● compare_actual_vs_expected — Actual numbers [from filing] vs estimates [from
pre-earnings]. Beat/miss/inline verdict with magnitude.
● get_post_results_reaction — Price change on results day and next 2 trading
days [NSE price data]. Volume spike detection.
**Cross-Source Reasoning Tools (the differentiator):**


● earnings_verdict — The full picture: "Infosys reported Q3 revenue of ₹41,764 Cr
(+5.2% YoY) [BSE Filing #12345], beating consensus estimate of ₹41,200 Cr [Finnhub].
EPS came in at ₹16.43 vs expected ₹15.90. However, the stock dropped 3.1% on
results day [NSE]. FII holding had already decreased 1.8% in the prior quarter
[shareholding data], and management commentary on deal pipeline was cautious [news
sentiment]. The sell-off appears pre-positioned and guidance-driven, not results-driven."
● earnings_season_dashboard — Across all companies reporting this week: who
beat, who missed, sector-wise trends, aggregate market reaction.
● compare_quarterly_performance — Side-by-side: 2-4 companies in the same
sector, same quarter. Revenue growth, margin trends, market reaction, shareholding
changes.
**Supporting Tools (shared base):**
● get_stock_quote, get_price_history, get_index_data
● get_key_ratios, get_shareholding_pattern
● get_option_chain — Full option chain with Greeks for a given stock/index and expiry
(used in get_pre_earnings_profile for options activity)
● get_company_news, get_news_sentiment
● get_rbi_rates (for context on banking/NBFC earnings)
● search_mutual_funds / get_fund_nav (for MF exposure changes around results)

### MCP Resources

```
● earnings://calendar/upcoming — Next 2 weeks of earnings dates
● earnings://{ticker}/latest — Most recent parsed quarterly result for a ticker
● earnings://{ticker}/history — Last 8 quarters of structured results data
● filing://{ticker}/{filing_id} — Parsed BSE filing content as structured
resource
● market://overview — Market summary
```
### MCP Prompts

```
● earnings_preview — Pre-results: historical EPS trend + estimates + shareholding
shifts + options activity + sentiment. "Here's what to expect from TCS results tomorrow."
● results_flash — Post-results: parse filing + beat/miss verdict + market reaction +
quick take. "Infosys beat on revenue, missed on margins, stock down 2%."
● sector_earnings_recap — "How did IT sector do this earnings season?" Aggregate
across Infosys, TCS, Wipro, HCL Tech.
● earnings_surprise_scan — Scan recent results for biggest positive/negative
surprises vs expectations.
```

### PS3 Tier Addendum

```
Free Premium Analyst
get_earnings_calendar,
get_past_results_dates
```
#### ✅ ✅ ✅

```
get_eps_history,
get_pre_earnings_profile,
get_analyst_expectations
```
#### ❌ ✅ ✅

```
get_post_results_reaction,
compare_actual_vs_expected
```
#### ❌ ✅ ✅

```
get_filing_document,
parse_quarterly_filing
```
#### ❌ ❌ ✅

```
earnings_verdict,
earnings_season_dashboard,
compare_quarterly_performance
```
#### ❌ ❌ ✅

```
earnings_preview, results_flash prompts ❌^ ✅^ ✅^
sector_earnings_recap,
earnings_surprise_scan prompts
```
#### ❌ ❌ ✅

### Must-Show Demo Scenario (e.g., "INFY") → system pulls EPS history,

### shareholding changes, options data, news sentiment → structured preview

2. **Post-earnings:** Run results_flash after a company has reported → system fetches
    BSE filing → parses revenue/profit/EPS → compares to estimates → checks market
    reaction → delivers verdict
3. **Cross-company:** Run compare_quarterly_performance for TCS vs INFY for the
    same quarter → side-by-side on all dimensions

### Must-Show Cross-Source Moment


earnings_verdict must combine: parsed filing data [BSE PDF], price reaction [NSE],
shareholding changes [BSE/NSE], news sentiment [NewsAPI/Finnhub], and estimates
[Finnhub/Alpha Vantage] — into a single narrative explaining the "why" behind the market's
reaction.

### Must-Show Auth Boundary

```
● Free user asks about upcoming earnings → gets calendar → tries
get_filing_document → 403
● Premium user gets pre-earnings profile with ratios and shareholding → tries
earnings_verdict (cross-source) → 403
● Analyst runs full earnings_verdict and sector_earnings_recap
```
## 📊 Evaluation Criteria (Same for All Use Cases)

### MCP Server Design & Compliance (25%)

```
● Correct tools, resources, and prompts with proper schemas
● Streamable HTTP transport, capability negotiation, tier-aware tool discovery
● Error handling, pagination, caching
● Tools return structured JSON — server provides data, client handles narrative
```
### Authentication & Authorisation (25%)

```
● OAuth 2.1 + PKCE working end-to-end
● Protected Resource Metadata endpoint correctly configured
● Tiered access enforced across tools, resources, and prompts
● Rate limiting per tier with proper 429 responses
● Proper 401/403 with WWW-Authenticate for step-up auth
● Auth server separated from MCP server
● Upstream API key isolation
```
### Cross-Source Reasoning Quality (25%)

```
● Do cross-source tools genuinely combine data from multiple APIs?
● Are contradictions and confirmations across sources explicitly identified?
● Are evidence citations specific (e.g., "NSE: RELIANCE LTP ₹2,456", "BSE Filing ID
12345: Q3 revenue ₹2.3L Cr")?
● Does the cross-source output add insight beyond what any individual API provides?
```

### System Design & Technical Depth (15%)

```
● Caching strategy (appropriate TTLs, upstream quota awareness)
● Rate limiting (per-user, per-tier, upstream-aware)
● Token validation, error handling for upstream failures (graceful degradation)
● Audit logging
```
### Demo & Usability (10%)

```
● Works with at least one MCP client (Claude Desktop, VS Code, or custom)
● Demo covers: auth flow → tool discovery → use tools → permission boundary → tier
upgrade
● Clear setup instructions and API documentation
```
## 🖥 Deployment Requirement

The MCP server must be runnable as a remote server over HTTP:
● Hosted server accessible over HTTP (localhost or cloud-deployed)
● Docker Compose setup (MCP server + auth server + cache/DB)
● README with setup instructions and list of required API keys with sign-up links
**Bonus points for:**
● One-command Docker Compose (MCP server + Keycloak + Redis)
● Working integration with Claude Desktop demonstrated live
● .env.example with clear instructions for obtaining free API keys
● Health-check endpoint showing upstream API status and remaining quotas

## 📦 Expected Deliverables

1. **Working MCP Server** — Deployed and testable with at least one MCP client, with full
    OAuth flow and tier-based access
2. **Architecture Diagram** — MCP server components, auth flow (client → auth server →
    token → MCP server), upstream API integration, caching layer, tier → scope →
    permission mapping
3. **Technical Explanation** covering:
    ○ MCP primitive design decisions (what's a tool vs. resource vs. prompt and why)
    ○ OAuth 2.1 implementation: auth server choice, PKCE, token validation
    ○ Tier-based access control: scope definitions, enforcement points


```
○ Upstream API integration: key management, caching, rate limiting, quota
management
○ Cross-source reasoning: how signals from different APIs are combined
○ Security: token audience binding, API key isolation, audit logging
```
4. **API Documentation** — Complete reference of all tools (input/output schemas),
    resources (URI patterns), prompts (with arguments), and scope requirements for each
    operation



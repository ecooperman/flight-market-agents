# Flight Market Agents

A small demo: fan out N concurrent "agents," each pricing the same flight
route in a different market's currency, then aggregate and compare. Built to
show async orchestration (fan-out, concurrent I/O, streaming partial
results) more than to be a real product.

## What this actually does (and doesn't)

Each agent calls [SerpApi's Google Flights engine](https://serpapi.com/google-flights-api)
for the identical origin/destination/date, but requests the price in a
different currency (`currency=JPY`, `GBP`, `INR`, etc.), then converts that
back to USD so the numbers are comparable. Currency-of-sale pricing
genuinely doesn't track FX 1:1, so real differences do show up here — but
**how much of that is genuine currency-of-sale pricing vs. SerpApi/Google
simply applying a spot FX conversion under the hood is an open question we
haven't verified.** Treat the multi-currency numbers as illustrative, not
as proof of a specific pricing mechanism, unless you dig into it further.

This is **not** the "same flight, cheaper if you pretend to search from
Japan" consumer-personalization effect you see on travel sites — that
effect lives in front-end revenue management tied to your apparent
location/browsing history, not a currency query param, and would require
automated querying against sites whose terms of service prohibit exactly
that. No proxies, VPNs, or IP/country spoofing are involved anywhere in
this code.

### Why not Amadeus anymore

This project originally used the Amadeus Flight Offers Search API.
**Amadeus fully decommissioned its free self-service developer portal on
July 17, 2026** — existing keys were disabled, new registrations paused a
month prior. Their Enterprise API is still around but is a sales-contract
product, not viable for a personal project. See
[PhocusWire's coverage](https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers)
if you're curious. SerpApi's Google Flights engine is the replacement:
self-service, real live pricing (not cached), a free tier, and a `currency`
param that preserves the original multi-market comparison concept.

## Two market-data modes

- **Mock mode (default)** — `USE_MOCK_DATA=true` in `.env`. Generates
  plausible fake fares locally with a staggered artificial delay per
  market, so you can run and demo the whole concurrent-agent flow
  instantly with zero setup. Every mocked result is labeled `"source":
  "mock"` in the API response and the UI.
- **Live mode** — `USE_MOCK_DATA=false` plus a real `SERPAPI_KEY`. Calls
  the real Google Flights engine via SerpApi.

## Two orchestration modes -- this is the part worth reading

The UI has two buttons, and they demonstrate genuinely different things:

- **"Run concurrent agents"** (`app/orchestrator.py`, `POST /api/compare`
  and `GET /api/compare/stream`) — a *fixed* async fan-out. It always
  queries all six markets, every time, via `asyncio.gather` /
  `asyncio.as_completed`. This is "agent" in the older, pre-LLM sense:
  concurrent workers, no reasoning involved. Good concurrency plumbing,
  not an AI agent.

- **"Run AI agent"** (`app/agent.py`, `GET /api/agent/compare/stream`) —
  a real tool-use loop against Claude. The model is given one tool,
  `search_market_price` (which just calls the same `run_market_agent()`
  underneath), and *decides for itself* which markets are worth checking
  for the given route, calls several in parallel when it wants to, and
  writes the final recommendation in its own words -- rather than you
  reading the lowest number off a board. Watch the board on a run: some
  rows may stay marked "Skipped" because the model chose not to check
  them. That's the actual routing/tool-use decision the job postings in
  this space are asking about.

This mode requires a real `ANTHROPIC_API_KEY` in `.env` (get one at
[console.anthropic.com](https://console.anthropic.com)) and makes real,
billed calls to the Claude API -- small cost per run, but not free like
mock market data. `AGENT_MODEL` defaults to `claude-sonnet-5`; swap it for
whatever model you want to demo against.

The loop itself (`run_pricing_agent` in `app/agent.py`) is the standard
Anthropic tool-use pattern: call the model, check `stop_reason` /
`tool_use` blocks, execute whatever tools it asked for (concurrently, via
`asyncio.gather`, reusing the same underlying market-search function as
the non-agent mode), feed the results back as `tool_result` blocks, and
repeat until the model stops calling tools and just answers. Capped at
`MAX_AGENT_STEPS = 4` so a confused run can't loop forever.

## Setup

```bash
cd flight-market-agents
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env already works as-is in mock mode - no keys needed to try it out.
uvicorn app.main:app --reload --port 8050
```

Then open http://127.0.0.1:8050.

## Going live with real fares

1. Sign up for free at [serpapi.com](https://serpapi.com) — no card
   required for the free 250-searches/month plan. Grab your key from the
   dashboard.
2. Put it in `.env` as `SERPAPI_KEY` and set `USE_MOCK_DATA=false`.
3. That's it — no test/production split, no approval wait, no OAuth
   dance. Every search is billed against your monthly quota (each market
   in a "Run concurrent agents" pass, or each date in a "Scan date range"
   pass, is one search), so mind the quota if you're iterating a lot
   during dev. $25/mo buys 1,000 searches if you outgrow the free tier.

## Where the concurrency actually shows up

`app/orchestrator.py` has two entry points:

- `compare_all_markets()` — `asyncio.gather` over all agents, returns once
  everything's done. Used by `POST /api/compare`.
- `stream_market_agents()` — `asyncio.as_completed` over the same tasks,
  yielding each result the instant it finishes as a Server-Sent Event.
  Used by `GET /api/compare/stream`, which is what the UI actually calls —
  watch the board and you'll see rows settle out of order, which is the
  visible proof the agents are running in parallel rather than one after
  another.

## FX rates

`app/markets.py` has static, approximate FX rates for demo purposes. Swap
in a live FX API (e.g. `open.er-api.com`, `exchangerate.host`) before
relying on these numbers for anything real.

## Cheapest day to fly

"Scan date range" (`GET /api/dates/scan/stream`, `scan_dates_stream()` in
`app/orchestrator.py`) is the same fan-out-and-stream concurrency pattern
as the market comparison, just varying the departure date instead of the
currency: one agent per day in a range (up to 21), fired concurrently,
streamed back as they land, cheapest one highlighted. It's a single
currency per scan (no FX math needed) and works in both mock and live
mode. This is the actual "when should I book" feature — the AI agent mode
(`app/agent.py`) doesn't use it yet; it's still market-only.

## Deploy

Follows the same pattern as the other apps in this directory — see
`../DEPLOYMENT.md`. Port `8050`, service name `flight-market-agents`,
intended hostname `flights.evancooperman.com`. `deploy/flight-market-agents.service`
and `.github/workflows/deploy.yml` are already set up.

Unlike the other apps here, this one has no database, but it does have
secrets in `.env` — which is gitignored, so it never travels with `git
pull`. The droplet needs its own `.env` created once, by hand, and left
alone; ordinary deploys (`git pull` + `pip install`) don't touch it.

### One-time droplet setup

1. **GitHub secrets** — on the `flight-market-agents` repo: `DO_HOST`,
   `DO_USER=deploy`, `DO_SSH_KEY` (same values as your other app repos).

2. **Sudoers** — add this app's service to the `deploy` user's narrow
   restart-only sudo rights:
   ```bash
   sudo visudo -f /etc/sudoers.d/deploy-restart
   ```
   Add `flight-market-agents` to the existing line, e.g.:
   ```
   deploy ALL=(root) NOPASSWD: /bin/systemctl restart time-management, /bin/systemctl restart social-planning, /bin/systemctl restart gifts, /bin/systemctl restart resume, /bin/systemctl restart flight-market-agents
   ```
   Then verify: `sudo visudo -c`.

3. **Clone + venv + secrets**:
   ```bash
   sudo -iu deploy
   cd /opt/apps
   git clone https://github.com/<your-github-user>/flight-market-agents.git
   cd flight-market-agents
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   vi .env   # fill in real values - USE_MOCK_DATA=false and/or real API keys, as wanted
   exit      # back to your own sudo-capable user
   ```
   Mock mode (`USE_MOCK_DATA=true`, the `.env.example` default) needs no
   real keys at all if you'd rather stand it up first and add live
   credentials later.

4. **systemd unit**:
   ```bash
   sudo cp /opt/apps/flight-market-agents/deploy/flight-market-agents.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now flight-market-agents
   curl -m 5 http://127.0.0.1:8050   # sanity check before wiring up the tunnel
   ```

5. **cloudflared ingress** — add to `/etc/cloudflared/config.yml`, *above*
   the catch-all `- service: http_status:404` line:
   ```yaml
     - hostname: flights.evancooperman.com
       service: http://localhost:8050
   ```
   Then route DNS and restart:
   ```bash
   sudo cloudflared tunnel route dns home-apps flights.evancooperman.com
   sudo systemctl restart cloudflared
   ```

6. **Access** — nothing to do if you're still on the wildcard Access
   application (`*.evancooperman.com`); it already covers this hostname.

7. **Cache Rule (bypass)** — Caching → Cache Rules → add
   `flights.evancooperman.com` to the existing bypass rule (or create one).

8. Push to `main` — CI takes it from here on future updates. Since this
   repo has no `.git` yet, that's `git init`, add the GitHub remote, then
   push, same as you did for `gifts`.

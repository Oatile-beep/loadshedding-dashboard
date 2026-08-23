# Load Shedding Dashboard

A Streamlit dashboard for South African load shedding data, powered by the
[EskomSePush API](https://eskomsepush.gumroad.com/l/api) (v3).

## Features

- **National Status** — current load shedding stage and upcoming stage changes
- **My Area** — search any suburb by name or GPS coordinates, and see which
  grid blocks (loadshedding / load reduction schedules) apply to it
- **Trends** — two real, honestly-scoped datasets:
  - *Live stage log*: every time the app checks national status, it logs the
    result locally. Builds a genuine growing dataset over time — charts appear
    once there's more than one entry.
  - *Historical*: real outage timestamps (not just block IDs) from the
    open-source [eskom-calendar](https://github.com/beyarkay/eskom-calendar)
    project. As of writing this only covers a single ~2-day window in
    **May 2025** (the project's maintainer notes load shedding "seems to have
    stopped"), so treat it as a snapshot of the last known bout, not a
    multi-year archive. Data used under CC BY-NC-SA 4.0 — credit: eskom-calendar.
- **API Quota** — shows daily usage if the endpoint is available; otherwise
  explains the current free-tier limitation clearly instead of erroring
- **Save your area** — pin your area once, and it's remembered across restarts
  (stored locally in `saved_area.json`, never committed to git)

Requests are cached (10 min–1 hr depending on endpoint) so normal use stays
well within the free tier's daily limit.

### A note on the live log and deployment

The live stage log (`stage_log.csv`) and saved area (`saved_area.json`) are
plain local files — this is what makes them simple and free, but it means:

- **Running locally**: they persist forever between runs. Great for building
  up real history over weeks/months.
- **Streamlit Community Cloud**: the filesystem resets on every redeploy
  (e.g. every time you `git push` an update, or after periods of inactivity
  put the app to sleep). The deployed log will reset more often than your
  local one. For a dashboard you check often, this is fine; for serious
  long-term trend-building, run it locally or upgrade to a real database
  later (SQLite on a persistent volume, or a free tier of Supabase/Postgres).

### A note on the API (v3.0 Migration)

* **All Endpoints on v3.0:** As of September 2026, API v2.0 is fully switched off. All calls (`/status`, `/areas_search`, `/areas_nearby`, `/area`) use the `/business/3.0/` base URL path.
* **Quota Tracking:** The retired `/allowance` endpoint has been replaced with dynamic quota tracking. API rate limits and daily call counts are read directly from `x-account-quota-remaining` and `x-account-quota-limit` HTTP response headers.
* **Schedule IDs:** Area queries in v3 use simplified schedule IDs (e.g., `eskde-10` rather than the legacy `eskde-10-fourways` format).

## Setup (local)

1. **Get an API token**
   Sign up at https://eskomsepush.gumroad.com/l/api (free tier: pay-what-you-want,
   $0 is fine; documented as 50 requests/day).

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**
   ```bash
   streamlit run app.py
   ```
   Opens at `http://localhost:8501`.

4. **In the app**
   - Paste your token into the sidebar (skip this if deploying with secrets — see below)
   - Search for your suburb by name, or use the GPS fields for more precise
     results on small suburbs/townships that don't have a clean text match
   - Click "📌 Save this as my area" once you find the right one — it'll be
     pre-selected every time you reopen the app

## Deploying to Streamlit Community Cloud (free)

1. Push this folder to a GitHub repo (the `.gitignore` already excludes
   your token and saved area — don't remove those exclusions)
2. Go to https://share.streamlit.io, connect the repo, set `app.py` as the entry point
3. In the app's **Settings → Secrets**, add:
   ```toml
   ESP_API_TOKEN = "your-token-here"
   ```
   The app automatically detects and uses this — no code changes needed, and
   the sidebar token field disappears once secrets are set, so anyone you
   share the deployed link with can use it without seeing your token.

## Disclaimer

Not affiliated with Eskom or EskomSePush. Respect the
[EskomSePush API License Agreement](https://sepush.co.za/license-agreement) —
don't share your token, and keep requests to a single IP at a time.

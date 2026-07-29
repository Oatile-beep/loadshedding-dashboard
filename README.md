# Load Shedding Dashboard

A Streamlit dashboard for South African load shedding data, powered by the
[EskomSePush API](https://eskomsepush.gumroad.com/l/api) (v3).

## Features

- **National Status** — current load shedding stage and upcoming stage changes
- **My Area** — search any suburb by name or GPS coordinates, and see which
  grid blocks (loadshedding / load reduction schedules) apply to it
- **API Quota** — shows daily usage if the endpoint is available; otherwise
  explains the current free-tier limitation clearly instead of erroring
- **Save your area** — pin your area once, and it's remembered across restarts
  (stored locally in `saved_area.json`, never committed to git)

Requests are cached (10 min–1 hr depending on endpoint) so normal use stays
well within the free tier's daily limit.

## A note on the API (important context)

EskomSePush has restructured their API since most tutorials online were
written. As of testing (July 2026):

- **v3** (`business/3.0`) is required for `areas_search` and `areas_nearby` —
  the old v2 versions of these now return `410 Gone` (search) or a
  "deprecated" error (nearby), since the docs moved without a matching redirect.
- **v2** (`business/2.0`) still serves `/status` largely unchanged, but its
  `/allowance` (quota check) endpoint currently 404s under both versions —
  it appears to have been retired without a documented replacement. The app
  handles this gracefully rather than erroring.
- v3's `/area` endpoint returns which grid **blocks** apply to an area
  (e.g. `eskdo-11` for loadshedding, `eskomkwazulunatallr-e` for load
  reduction) but not ready-made event timestamps the way v2 used to. For
  exact time slots, check the [EskomSePush app](https://sepush.co.za/)
  directly with the area name this dashboard finds for you.

If EskomSePush changes their API again, `BASE_URL` and `BASE_URL_V2` near the
top of `app.py` are the two places to look first.

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

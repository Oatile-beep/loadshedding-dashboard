"""
Load Shedding Dashboard — powered by the EskomSePush API (v3)
Run with: streamlit run app.py
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
from datetime import datetime, timedelta, timezone

# ── Config ────────────────────────────────────────────────────────────────
# Confirmed live and working (tested 2026-07-29): v3 area search/nearby are
# free-tier; v2's areas_search/areas_nearby have been retired (410/deprecated).
BASE_URL = "https://developer.sepush.co.za/business/3.0"
BASE_URL_V2 = "https://developer.sepush.co.za/business/2.0"  # /allowance only exists here, not in v3
_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_AREA_FILE = os.path.join(_DIR, "saved_area.json")
STAGE_LOG_FILE = os.path.join(_DIR, "stage_log.csv")
# Real historical event data (start/end timestamps, not just block IDs), published
# free & unrestricted by the open-source eskom-calendar project. As of testing
# (2026-07-29) this covers a single ~2-day window (13-15 May 2025) — the project's
# maintainer notes loadshedding "seems to have stopped", so this is the last known
# bout, not a multi-year archive. CC BY-NC-SA — attribution required, see README.
HISTORICAL_CSV_URL = "https://github.com/beyarkay/eskom-calendar/releases/download/latest/machine_friendly.csv"
st.set_page_config(page_title="Load Shedding Dashboard", page_icon="⚡", layout="wide")


# ── Saved-area persistence (local file, no token stored) ────────────────────
def load_saved_area():
    if os.path.exists(SAVED_AREA_FILE):
        try:
            with open(SAVED_AREA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_area(area: dict):
    with open(SAVED_AREA_FILE, "w") as f:
        json.dump(area, f)


def clear_saved_area():
    if os.path.exists(SAVED_AREA_FILE):
        os.remove(SAVED_AREA_FILE)


# ── Live stage-log persistence (local CSV, builds real data over time) ──────
def log_current_stage(stage: str):
    """Append a (timestamp, stage) row, but only if 30+ min since the last entry
    or the stage actually changed — avoids flooding the log on every page reload."""
    now = datetime.now(timezone.utc)
    if os.path.exists(STAGE_LOG_FILE):
        try:
            df = pd.read_csv(STAGE_LOG_FILE, parse_dates=["timestamp"])
            if not df.empty:
                last = df.iloc[-1]
                last_ts = pd.to_datetime(last["timestamp"])
                if last_ts.tzinfo is None:
                    last_ts = last_ts.tz_localize("UTC")
                recent = (now - last_ts) < timedelta(minutes=30)
                same_stage = str(last["stage"]) == str(stage)
                if recent and same_stage:
                    return  # nothing new to log
        except (pd.errors.EmptyDataError, KeyError):
            pass
    header = not os.path.exists(STAGE_LOG_FILE)
    with open(STAGE_LOG_FILE, "a") as f:
        if header:
            f.write("timestamp,stage\n")
        f.write(f"{now.isoformat()},{stage}\n")


def load_stage_log():
    if os.path.exists(STAGE_LOG_FILE):
        try:
            df = pd.read_csv(STAGE_LOG_FILE, parse_dates=["timestamp"])
            return df if not df.empty else None
        except pd.errors.EmptyDataError:
            return None
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def load_historical_data():
    df = pd.read_csv(HISTORICAL_CSV_URL, parse_dates=["start", "finsh"])
    return df


# ── API helpers ───────────────────────────────────────────────────────────
def _headers(token: str) -> dict:
    return {"token": token}


@st.cache_data(ttl=600, show_spinner=False)
def get_allowance(token: str):
    r = requests.get(f"{BASE_URL}/allowance", headers=_headers(token), timeout=10)
    if r.status_code == 404:
        # /allowance isn't on v3 yet — fall back to v2, which still serves it.
        r = requests.get(f"{BASE_URL_V2}/allowance", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=600, show_spinner=False)
def get_status(token: str):
    r = requests.get(f"{BASE_URL}/status", headers=_headers(token), timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=3600, show_spinner=False)
def search_areas(token: str, text: str):
    r = requests.get(
        f"{BASE_URL}/areas_search", headers=_headers(token), params={"text": text}, timeout=10
    )
    r.raise_for_status()
    return r.json().get("areas", [])


@st.cache_data(ttl=3600, show_spinner=False)
def nearby_areas(token: str, lat: float, lon: float):
    r = requests.get(
        f"{BASE_URL}/areas_nearby", headers=_headers(token),
        params={"lat": lat, "lon": lon}, timeout=10,
    )
    r.raise_for_status()
    return r.json().get("areas", [])


@st.cache_data(ttl=600, show_spinner=False)
def get_area_info(token: str, area_id: str):
    r = requests.get(f"{BASE_URL}/area", headers=_headers(token), params={"id": area_id}, timeout=10)
    r.raise_for_status()
    return r.json()


# ── Sidebar ───────────────────────────────────────────────────────────────
st.sidebar.title("⚡ Settings")

# On Streamlit Community Cloud, set ESP_API_TOKEN in the app's Secrets instead
# of typing it in every visit. Locally (no secrets.toml file), this safely
# falls through to the manual sidebar field below.
try:
    token = st.secrets["ESP_API_TOKEN"]
except (KeyError, FileNotFoundError):
    token = ""
except Exception:
    token = ""  # covers StreamlitSecretNotFoundError when no secrets.toml exists at all

if token:
    st.sidebar.success("Using API token from app secrets.")
else:
    token = st.sidebar.text_input(
        "EskomSePush API Token", type="password",
        help="Get one at https://eskomsepush.gumroad.com/l/api",
    )

if not token:
    st.sidebar.warning("Enter your API token to fetch live data.")

st.sidebar.divider()

saved_area = load_saved_area()
selected_area = None

if saved_area:
    st.sidebar.subheader("📌 Saved area")
    st.sidebar.success(f"{saved_area['name']} — {saved_area.get('municipality', '')}, {saved_area.get('province', '')}")
    selected_area = saved_area
    if st.sidebar.button("Forget saved area"):
        clear_saved_area()
        st.rerun()
    st.sidebar.divider()

st.sidebar.subheader("Find a different area" if saved_area else "Find your area")
area_query = st.sidebar.text_input("Search suburb / town", placeholder="e.g. Empangeni")

st.sidebar.caption("Or search by GPS coordinates (more precise for small suburbs):")
col_lat, col_lon = st.sidebar.columns(2)
lat_input = col_lat.text_input("Latitude", placeholder="-28.854")
lon_input = col_lon.text_input("Longitude", placeholder="31.847")

results = []

if token and area_query:
    try:
        results = search_areas(token, area_query)
    except requests.HTTPError as e:
        st.sidebar.error(f"Area search failed: {e}")
elif token and lat_input and lon_input:
    try:
        results = nearby_areas(token, float(lat_input), float(lon_input))
    except requests.HTTPError as e:
        st.sidebar.error(f"Nearby search failed: {e}")
    except ValueError:
        st.sidebar.error("Latitude/longitude must be numbers.")

if results:
    labels = [f"{a['name']} — {a.get('municipality', '')}, {a.get('province', '')}" for a in results]
    choice = st.sidebar.selectbox("Matching areas", labels)
    picked = results[labels.index(choice)]
    selected_area = picked
    if st.sidebar.button("📌 Save this as my area"):
        save_area(picked)
        st.rerun()
elif (area_query or (lat_input and lon_input)) and token:
    st.sidebar.info("No matching areas found.")

# Manual area ID fallback
manual_id = st.sidebar.text_input("...or paste an Area ID directly", placeholder="za_kzn_dc28_vulindlela_ypa8")
if manual_id:
    selected_area = {"id": manual_id, "name": manual_id, "municipality": "", "province": ""}
    if st.sidebar.button("📌 Save this ID as my area"):
        save_area(selected_area)
        st.rerun()


# ── Header ────────────────────────────────────────────────────────────────
st.title("⚡ Load Shedding Dashboard")
st.caption("Live outage stage, area lookup and quota — data from EskomSePush")

if not token:
    st.info("Add your API token in the sidebar to begin.")
    st.stop()

tab_overview, tab_schedule, tab_trends, tab_quota = st.tabs(
    ["🇿🇦 National Status", "📍 My Area", "📈 Trends", "📊 API Quota"]
)

# ── Tab 1: National status ───────────────────────────────────────────────
with tab_overview:
    try:
        status = get_status(token)
        eskom = status.get("status", {}).get("eskom", {})
        stage = eskom.get("stage", "0")
        next_stages = eskom.get("next_stages", [])

        log_current_stage(stage)  # feeds the live history in the Trends tab

        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Current National Stage", f"Stage {stage}")
            updated = eskom.get("stage_updated")
            if updated:
                st.caption(f"Last updated: {updated}")

        with col2:
            if next_stages:
                df_next = pd.DataFrame(next_stages)
                st.write("**Upcoming stage changes**")
                st.dataframe(df_next, use_container_width=True, hide_index=True)
            else:
                st.write("No upcoming stage changes reported.")

    except requests.HTTPError as e:
        st.error(f"Could not fetch national status: {e}")

# ── Tab 2: Area lookup ───────────────────────────────────────────────────
with tab_schedule:
    if not selected_area:
        st.info("Search for an area, search by GPS, or paste an Area ID in the sidebar.")
    else:
        try:
            info = get_area_info(token, selected_area["id"])

            st.subheader(info.get("name", selected_area["name"]))
            st.caption(f"{info.get('municipality', '')}, {info.get('province', '')}")

            schedules = info.get("schedules", [])
            if schedules:
                df = pd.DataFrame(schedules)
                df["type"] = df["type"].replace({
                    "loadshedding": "Load shedding",
                    "load_reduction": "Load reduction",
                })
                st.write("**Grid blocks / schedules that apply to this area**")
                st.dataframe(
                    df.rename(columns={"id": "Schedule ID", "type": "Type", "auto_enabled": "Auto-enabled"}),
                    use_container_width=True, hide_index=True,
                )
                st.caption(
                    "The free API confirms which grid blocks apply here, along with the current "
                    "national stage above — but exact time-slot schedules for a specific block aren't "
                    "exposed on the free tier. For exact times, check the "
                    "[EskomSePush app](https://sepush.co.za/) with this area name, or your "
                    "municipality's official load shedding schedule."
                )
            else:
                st.success("No load shedding or load reduction schedules linked to this area.")

        except requests.HTTPError as e:
            st.error(f"Could not fetch area info: {e}")

# ── Tab 3: Trends ─────────────────────────────────────────────────────────
with tab_trends:
    st.subheader("📡 Live stage history")
    st.caption("Logged automatically each time this dashboard runs — builds real data over time.")

    log_df = load_stage_log()
    if log_df is None or len(log_df) < 2:
        st.info(
            "Not enough logged data yet — check back after visiting the dashboard a few more "
            "times (spaced 30+ minutes apart). Every visit adds one data point."
        )
        if log_df is not None:
            st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        fig_log = go.Figure()
        fig_log.add_trace(go.Scatter(
            x=log_df["timestamp"], y=log_df["stage"].astype(int),
            mode="lines+markers", line_shape="hv", name="Stage",
        ))
        fig_log.update_layout(
            title="National stage over time (as logged by this app)",
            yaxis_title="Stage", xaxis_title="",
            yaxis=dict(dtick=1),
        )
        st.plotly_chart(fig_log, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Time spent at each stage (of logged checks)**")
            counts = log_df["stage"].value_counts().sort_index()
            st.bar_chart(counts)
        with col_b:
            st.write("**Recent log entries**")
            st.dataframe(log_df.tail(10).iloc[::-1], use_container_width=True, hide_index=True)

        first_logged = log_df["timestamp"].min()
        st.caption(f"Logging since {first_logged.strftime('%Y-%m-%d %H:%M')} · {len(log_df)} entries recorded.")

    st.divider()
    st.subheader("🗓️ Last known load shedding period")
    st.caption(
        "Real historical outage timestamps (not just block IDs) from the open-source "
        "[eskom-calendar](https://github.com/beyarkay/eskom-calendar) project. As of now, this "
        "covers a single ~2-day window in **May 2025** — its maintainer notes load shedding "
        "appears to have stopped, so this is the last recorded bout rather than a multi-year "
        "archive. Data used under CC BY-NC-SA 4.0, credit: eskom-calendar."
    )

    try:
        hist = load_historical_data()
        area_filter = st.text_input(
            "Filter by area name (partial match)", placeholder="e.g. kwazulu-natal, ethekwini, ballito"
        )
        filtered = hist[hist["area_name"].str.contains(area_filter, case=False)] if area_filter else hist

        if filtered.empty:
            st.info("No matching areas in this dataset for that filter.")
        else:
            st.caption(f"{filtered['area_name'].nunique()} areas, {len(filtered)} outage events in this window.")

            top_areas = filtered["area_name"].value_counts().head(15)
            fig_areas = px.bar(
                top_areas, orientation="h",
                title="Outage events by area (top 15 in this window)",
                labels={"value": "Number of events", "index": "Area"},
            )
            fig_areas.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
            st.plotly_chart(fig_areas, use_container_width=True)

            dur_mins = (filtered["finsh"] - filtered["start"]).dt.total_seconds() / 60
            col_c, col_d, col_e = st.columns(3)
            col_c.metric("Avg. outage length", f"{dur_mins.mean():.0f} min")
            col_d.metric("Most common stage", str(filtered["stage"].mode().iloc[0]))
            col_e.metric("Events shown", len(filtered))

            with st.expander("View raw events"):
                st.dataframe(
                    filtered[["area_name", "start", "finsh", "stage"]].sort_values("start"),
                    use_container_width=True, hide_index=True,
                )

    except Exception as e:
        st.warning(f"Could not load historical data: {e}")

# ── Tab 4: Quota ──────────────────────────────────────────────────────────
with tab_quota:
    try:
        allowance = get_allowance(token).get("allowance", {})
        count = allowance.get("count", 0)
        limit = allowance.get("limit", 50)
        remaining = max(limit - count, 0)

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=count,
            title={"text": "API calls used today"},
            gauge={
                "axis": {"range": [0, limit]},
                "bar": {"color": "#e74c3c" if count > limit * 0.8 else "#2ecc71"},
            },
        ))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"{remaining} of {limit} calls remaining today. Checking allowance is free and doesn't use quota.")

    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            st.info(
                "Quota checking isn't available on the current free API version — EskomSePush "
                "appears to have retired the `/allowance` endpoint. The free tier is documented as "
                "50 requests/day; this dashboard caches results (10–60 min per tab) to stay well "
                "within that without needing to check live."
            )
        else:
            st.error(f"Could not fetch quota info: {e}")

st.divider()
st.caption("Built with Streamlit · Data via [EskomSePush](https://sepush.co.za) · Not affiliated with Eskom or EskomSePush.")

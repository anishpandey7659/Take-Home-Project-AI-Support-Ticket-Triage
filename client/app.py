"""Ticket classifier — AI Support Triage Dashboard (Streamlit).

Run with:  streamlit run app.py
"""
import copy
import json
import re
import time
from datetime import datetime
from html import escape
from urllib.parse import urlparse
import os
import altair as alt
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Ticket classifier · Support Triage",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded",  # keep the sidebar open on first load
)

# ───────────────────────── Tokens ─────────────────────────
GREEN, INK, MUTE, PAPER, LINE = "#1F4D3A", "#23272B", "#6B7076", "#FAF7F2", "#E6E1D6"
URG = ["Critical", "High", "Medium", "Low"]
CATS = ["Billing", "Technical", "Account", "Feedback", "Other"]
SENT = ["Angry", "Frustrated", "Neutral", "Happy"]
NEG = {"Angry", "Frustrated"}
BADGE = {  # (text, background)
    "Critical": ("#8A2C2C", "#F5E1DD"), "High": ("#93561A", "#F6E8D2"),
    "Medium": ("#6E6420", "#F1EDD0"), "Low": ("#2F5D46", "#E1EDE5"),
    "Angry": ("#8A2C2C", "#F5E1DD"), "Frustrated": ("#93561A", "#F6E8D2"),
    "Neutral": ("#555B61", "#ECEAE4"), "Happy": ("#2F5D46", "#E1EDE5"),
}
COLORS = {"Critical": "#8A2C2C", "High": "#C98A3B", "Medium": "#B9AE5A", "Low": "#6E9C80",
          "Angry": "#8A2C2C", "Frustrated": "#C98A3B", "Neutral": "#A9ACAF", "Happy": "#4C8566"}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Instrument+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"], .stApp {{ font-family:'Instrument Sans',system-ui,sans-serif; color:{INK}; }}
.stApp {{ background:{PAPER}; }}

/* Header: keep it (it holds the sidebar toggle) but make it invisible chrome */
header[data-testid="stHeader"] {{ background:transparent; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
footer, #MainMenu {{ visibility:hidden; }}
/* Make sure the sidebar open/close controls always stay visible (names vary by version) */
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {{ visibility:visible !important; display:flex !important; }}
[data-testid="stExpandSidebarButton"] *, [data-testid="stSidebarCollapsedControl"] *,
[data-testid="collapsedControl"] * {{ color:{INK} !important; }}

.block-container {{ padding:3rem 2.5rem 4rem; max-width:1280px; }}
h1,h2,h3,.serif {{ font-family:'Newsreader',Georgia,serif !important; color:{INK}; letter-spacing:-.01em; }}
h1 {{ font-size:2.3rem !important; font-weight:500 !important; margin:0 !important; padding:0 !important; }}
h3 {{ font-size:1.25rem !important; font-weight:500 !important; }}
[data-testid="stSidebar"] {{ background:#F2EEE5; border-right:1px solid {LINE}; }}
[data-testid="stSidebar"] .brand {{ font-family:'Newsreader',serif; font-size:1.55rem; color:{GREEN}; font-weight:600; margin:.2rem 0 .1rem; }}
[data-testid="stSidebar"] .tag {{ color:{MUTE}; font-size:.82rem; margin-bottom:1.6rem; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ gap:.15rem; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{ padding:.55rem .8rem; border-radius:8px; width:100%; }}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child,
[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {{ display:none !important; }}
[data-testid="stSidebar"] [role="radiogroup"] label p {{ color:{INK} !important; font-size:.98rem; }}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background:#E8E3D8; }}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{ background:{GREEN} !important; }}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ color:#fff !important; font-weight:600; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"], [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color:{MUTE} !important; }}
.stApp p, .stApp label, .stApp li {{ color:{INK}; }}
.stApp .stButton button p {{ color:inherit; }}
.sub {{ color:{MUTE}; font-size:.95rem; margin:.35rem 0 1.6rem; }}
.card {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:1.1rem 1.25rem; box-shadow:0 1px 2px rgba(35,39,43,.04); }}
.kpi .v {{ font-family:'Newsreader',serif; font-size:2.6rem; line-height:1.05; font-weight:500; }}
.kpi .l {{ color:{MUTE}; font-size:.9rem; margin-top:.2rem; }}
.kpi .n {{ color:{MUTE}; font-size:.78rem; margin-top:.5rem; border-top:1px solid {LINE}; padding-top:.45rem; }}
.badge {{ display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.78rem; font-weight:600; white-space:nowrap; }}
.tag-cat {{ display:inline-block; padding:.12rem .6rem; border-radius:6px; font-size:.78rem; border:1px solid {LINE}; color:#454A50; background:#fff; }}
.th {{ color:{MUTE}; font-size:.8rem; font-weight:600; padding:.3rem 0; border-bottom:1px solid {INK}; }}
.cell {{ font-size:.9rem; line-height:1.4; padding:.35rem 0; }}
.tid {{ font-weight:600; color:{GREEN}; }}
.msg {{ font-family:'Newsreader',serif; font-size:1.2rem; line-height:1.6; }}
.row-line {{ border-bottom:1px solid {LINE}; margin:0; }}
.stButton > button {{ border-radius:8px; border:1px solid {LINE}; background:#fff; color:{INK}; font-weight:500; }}
.stButton > button:hover {{ border-color:{GREEN}; color:{GREEN}; }}
.stButton > button[kind="primary"] {{ background:{GREEN}; border-color:{GREEN}; color:#fff; }}
.stButton > button[kind="primary"]:hover {{ background:#173B2C; color:#fff; }}
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {{ background:#fff !important; border-radius:8px !important; }}
.stProgress > div > div > div {{ background:{GREEN}; }}
@media (max-width:760px) {{ .block-container {{ padding:2.5rem 1rem 3rem; }} h1 {{ font-size:1.8rem !important; }} .th {{ display:none; }} }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ───────────────────────── Sample data ─────────────────────────
# (message, urgency, category, sentiment, reply)
SAMPLE = [
    ("The app crashed during the update and now all of my mother's medication reminders are gone. She missed her evening insulin dose because of this. Fix this immediately.", "Critical", "Technical", "Frustrated", "We're sorry this issue caused the medication reminders to disappear. We understand the seriousness of the missed dose and are treating this as a critical issue."),
    ("I have been charged twice for my Premium subscription this month. I want the duplicate charge refunded right away.", "High", "Billing", "Frustrated", "We're sorry about the duplicate charge. We'll review the billing and help process the duplicate charge refund."),
    ("How do I add a second caregiver to my father's profile? I want my sister to also get his alerts.", "Low", "Account", "Neutral", "You can add another caregiver to your father's profile through the caregiver or account settings."),
    ("Just wanted to say the new medication tracking feature is fantastic. It has made caring for my grandmother so much easier. Thank you!", "Low", "Feedback", "Happy", "Thank you for the kind feedback. We're glad the medication tracking feature has made caregiving easier."),
    ("Emergency fall alerts are NOT reaching my phone. My dad fell yesterday and I received no notification at all. This is unacceptable for a health app.", "Critical", "Technical", "Angry", "We're very sorry that the emergency fall alert did not reach your phone. We understand the seriousness of this issue and are treating it as critical."),
]

# ───────────────────────── State ─────────────────────────
# Temporary in-memory store (lives in st.session_state, so it is per browser session and is
# cleared on refresh). st.session_state.tickets is cumulative: the sample, single messages and
# every loaded batch are appended to it, and Dashboard / Tickets / Analytics all read from it.
MAX_BATCHES, MAX_TESTS = 20, 50


def mkey(msg):
    """Cache key: message text with whitespace and case normalized."""
    return " ".join(str(msg).split()).lower()


def save_batches():
    """Refresh each batch snapshot in History from the live ticket list."""
    d = st.session_state
    for b in d.mem_batches:
        b["tickets"] = copy.deepcopy([t for t in d.tickets if t["batch"] == b["id"]])


def remember_test(message, result):
    """Store a single-message test and its response, and make it reusable."""
    d = st.session_state
    d.setdefault("mem_cache", {})[mkey(message)] = dict(result)
    tests = d.setdefault("mem_tests", [])
    tests.insert(0, dict(at=datetime.now().strftime("%b %d, %H:%M:%S"), message=message, result=dict(result)))
    del tests[MAX_TESTS:]


def mk(msg, a=None):
    """Build a ticket. The id and batch are assigned when it is added to the store."""
    t = dict(id="", batch="", message=msg.strip(), urgency="", category="", sentiment="",
             suggested_reply="", status="pending", error="")
    if a:
        t.update({k: a[k] for k in ("urgency", "category", "sentiment", "suggested_reply")}, status="ready")
    return t


def add_tickets(new, source, dedupe=True, register=True):
    """Append tickets to the session store (shown on Dashboard / Tickets / Analytics).

    Messages already in the store are skipped when dedupe=True. register=True also records
    the group as a batch in History. Returns the tickets that were actually added.
    """
    d = st.session_state
    seen = {mkey(t["message"]) for t in d.tickets} if dedupe else set()
    fresh = []
    for t in new:
        k = mkey(t["message"])
        if k not in seen:
            seen.add(k)
            fresh.append(t)
    if not fresh:
        return []
    if register:
        base = datetime.now().strftime("B-%Y%m%d-%H%M%S")
        bid, n = base, 1
        while any(b["id"] == bid for b in d.mem_batches):
            n += 1
            bid = f"{base}-{n}"
        d.mem_batches.append(dict(id=bid, source=source, at=datetime.now().strftime("%b %d, %Y %H:%M"), tickets=[]))
        del d.mem_batches[:-MAX_BATCHES]
    else:
        bid = "single"
    for t in fresh:
        t["id"] = f"T-{d.next_id}"
        d.next_id += 1
        t["batch"] = bid
    d.tickets.extend(fresh)
    save_batches()
    return fresh


def sample_tickets(analyzed=True):
    if analyzed:
        return [mk(m, dict(urgency=u, category=c, sentiment=s, suggested_reply=r))
                for (m, u, c, s, r) in SAMPLE]
    return [mk(row[0]) for row in SAMPLE]


def ss_init():
    d = st.session_state
    d.setdefault("page", "Dashboard")
    d.setdefault("sel", None)
    d.setdefault("api_url", st.secrets.get("API_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")))
    d.setdefault("timeout", 120)
    d.setdefault("mode", "Batch · one request (/triage_all)")
    d.setdefault("chunk", 5)
    d.setdefault("mem_batches", [])
    d.setdefault("mem_tests", [])
    d.setdefault("mem_cache", {})
    d.setdefault("tickets", [])
    d.setdefault("next_id", 1001)
    if not d.get("seeded"):  # load the 5 samples once per session
        d.seeded = True
        add_tickets(sample_tickets(), "Sample dataset")


ss_init()

# ───────────────────────── API layer (FastAPI backend) ─────────────────────────
FIELDS = ("urgency", "category", "sentiment", "suggested_reply")
MODES = ["Batch · one request (/triage_all)", "Per ticket · isolates failures (/triage)"]


class ApiError(Exception):
    pass


def api_post(path, body):
    # tolerate a pasted full endpoint URL
    base = re.sub(r"/triage(_all)?$", "", st.session_state.api_url.strip().rstrip("/"))
    try:
        r = requests.post(base + path, json=body, timeout=st.session_state.timeout)
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Cannot reach the triage API at {base}. Check that it is running and the URL under Load data → API connection is correct.")
    except requests.exceptions.Timeout:
        raise ApiError("The triage API timed out. Retry, or raise the timeout under Load data → API connection.")
    except requests.RequestException as e:
        raise ApiError(f"Request failed: {e}")
    if r.status_code != 200:
        try:
            d = r.json().get("detail")
        except (ValueError, AttributeError):
            d = None
        if isinstance(d, list):  # FastAPI validation errors
            d = "; ".join(str(x.get("msg", x)) if isinstance(x, dict) else str(x) for x in d)
        hint = " Check the API base URL (router prefix) under Load data → API connection." if r.status_code == 404 else ""
        raise ApiError(f"{d or 'Unexpected response'} (HTTP {r.status_code} from POST {base + path}).{hint}")
    try:
        return r.json()
    except ValueError:
        raise ApiError("The API returned a response that is not valid JSON.")


def ping_backend():
    """GET /api/hello on the backend's origin. Doubles as a wake-up call for sleeping hosts (e.g. Vercel, Render).
    Returns the URL that was called so the UI can display it.
    """
    u = urlparse(st.session_state.api_url.strip())
    if not u.scheme or not u.netloc:
        raise ApiError("The API base URL is not valid. Set it under API connection .")
    url = f"{u.scheme}://{u.netloc}/api/hello"
    try:
        r = requests.get(url, timeout=60)  # cold starts on free hosts can be slow
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Cannot reach {url}. Check that the backend is running and the URL under API connection is correct.")
    except requests.exceptions.Timeout:
        raise ApiError("The backend didn't respond in 60 seconds. Click the button again; it may still be waking up.")
    except requests.RequestException as e:
        raise ApiError(f"Request failed: {e}")
    if r.status_code != 200:
        raise ApiError(f"Backend responded with HTTP {r.status_code} from GET {url}.")
    return url


def discover():
    """Read the backend's OpenAPI schema and return the base URLs that expose /triage."""
    u = urlparse(st.session_state.api_url.strip())
    origin = f"{u.scheme}://{u.netloc}"
    try:
        r = requests.get(origin + "/openapi.json", timeout=10)
        r.raise_for_status()
        paths = r.json().get("paths", {})
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Cannot reach {origin}. Check that the server is running and the host and port are correct.")
    except Exception as e:  # noqa
        raise ApiError(f"Could not read {origin}/openapi.json ({e}). The docs may be disabled; set the URL manually.")
    return [origin + p[: -len("/triage")] for p in paths if p.endswith("/triage")], origin


def clean(r):
    """Validate one TriageResult and normalize casing."""
    if not isinstance(r, dict) or any(k not in r for k in FIELDS):
        raise ApiError("The API response is missing expected fields: " + ", ".join(FIELDS))
    out = {k: str(r[k]).strip() for k in FIELDS}
    for k, allowed in (("urgency", URG), ("category", CATS), ("sentiment", SENT)):
        out[k] = out[k].title() if out[k].title() in allowed else out[k]
    return out


def analyze(targets, use_cache=True):
    """Triage tickets through the backend with live progress.

    Messages already answered earlier in this session are filled from memory without an API
    call (use_cache=False forces a fresh call). Batch mode sends the rest in chunks to
    /triage_all (size set under API connection); per-ticket mode calls /triage once per ticket.
    A failed chunk is stored per ticket so it can be retried, and the remaining chunks still run.
    """
    targets = list(targets)
    if not targets:
        return
    cache = st.session_state.setdefault("mem_cache", {})
    reused = 0
    if use_cache:
        todo = []
        for t in targets:
            hit = cache.get(mkey(t["message"]))
            if hit:
                t.update(dict(hit), status="ready", error="")
                reused += 1
            else:
                todo.append(t)
        targets = todo
    total = len(targets)
    if not total:
        save_batches()
        st.toast(f"{reused} response(s) reused from memory. No API calls were needed.")
        return

    batch_mode = st.session_state.mode == MODES[0]
    size = max(1, int(st.session_state.chunk)) if batch_mode else 1
    chunks = [targets[i:i + size] for i in range(0, total, size)]
    done = failed = 0
    started = time.time()

    with st.container(border=True):
        st.markdown("<h3>Analysis in progress</h3>", unsafe_allow_html=True)
        bar = st.progress(0.0, text=f"Starting… 0 of {total} processed")
        stats = st.empty()
        stats.caption("Waiting for the backend. The first request can take a while if it was asleep."
                      + (f" {reused} message(s) already reused from memory." if reused else ""))
        for chunk in chunks:
            first = done + failed + 1
            last = done + failed + len(chunk)
            label = f"{first}" if first == last else f"{first}–{last}"
            bar.progress((done + failed) / total, text=f"Triaging {label} of {total}…")
            try:
                if len(chunk) > 1:
                    res = api_post("/triage_all", [{"message": t["message"]} for t in chunk])
                    if not isinstance(res, list) or len(res) != len(chunk):
                        raise ApiError("The API returned a different number of results than messages sent.")
                    results = [clean(x) for x in res]  # same order as input
                else:
                    results = [clean(api_post("/triage", {"message": chunk[0]["message"]}))]
                for t, r in zip(chunk, results):
                    t.update(r, status="ready", error="")
                    cache[mkey(t["message"])] = dict(r)
                done += len(chunk)
            except ApiError as e:
                for t in chunk:
                    t.update(status="error", error=str(e))
                failed += len(chunk)
            bar.progress((done + failed) / total, text=f"{done + failed} of {total} processed")
            stats.caption(f"Analyzed {done} · Failed {failed} · Remaining {total - done - failed} · "
                          f"Reused from memory {reused} · {time.time() - started:.0f}s elapsed")
        bar.progress(1.0, text=f"Finished: {done} analyzed, {failed} failed")

    save_batches()
    st.toast(f"Analysis finished: {done} analyzed, {failed} failed"
             + (f", {reused} reused from memory." if reused else "."))


def parse_input(raw):
    """Accepts JSON (list of strings/objects) or plain text (one message per line / blank-line separated)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        parts = [p for p in re.split(r"\n\s*\n", raw.strip()) if p.strip()]
        if len(parts) <= 1:
            parts = [p for p in raw.splitlines() if p.strip()]
        return [mk(p) for p in parts]
    if isinstance(data, dict):
        data = data.get("tickets") or data.get("messages") or [data]
    if isinstance(data, str):
        data = [data]
    items = []
    for x in data:
        if isinstance(x, str):
            items.append((x, None))
        elif isinstance(x, dict):
            m = x.get("message") or x.get("text") or x.get("body") or ""
            full = all(k in x for k in FIELDS)
            items.append((str(m), x if full else None))
    return [mk(m, a) for m, a in items if m.strip()]


# ───────────────────────── Components ─────────────────────────
def badge(v):
    fg, bg = BADGE.get(v, ("#555B61", "#ECEAE4"))
    return f'<span class="badge" style="color:{fg};background:{bg}">{v}</span>' if v else ""


def cat_tag(v):
    return f'<span class="tag-cat">{v}</span>' if v else ""


def header(title, sub):
    st.markdown(f"<h1>{title}</h1><div class='sub'>{sub}</div>", unsafe_allow_html=True)


def batch_line(df):
    ready = int((df.status == "ready").sum()) if len(df) else 0
    return (f"{len(df)} tickets in this session · {ready} analyzed · "
            f"{len(st.session_state.mem_batches)} batch(es) in memory")


def kpi(col, label, value, note, accent=INK):
    col.markdown(f"<div class='card kpi'><div class='v' style='color:{accent}'>{value}</div>"
                 f"<div class='l'>{label}</div><div class='n'>{note}</div></div>", unsafe_allow_html=True)


def dist_chart(df, field, order, title):
    st.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)
    counts = df[df[field] != ""][field].value_counts().rename_axis(field).reset_index(name="Tickets")
    if counts.empty:
        st.caption("No analyzed tickets yet.")
        return
    if order:
        sort = [o for o in order if o in set(counts[field])] + sorted(set(counts[field]) - set(order))
    else:
        sort = counts.sort_values("Tickets", ascending=False)[field].tolist()
    ch = alt.Chart(counts).mark_bar(cornerRadiusEnd=3, size=18).encode(
        y=alt.Y(f"{field}:N", sort=sort, title=None, axis=alt.Axis(labelFontSize=12, domain=False, ticks=False)),
        x=alt.X("Tickets:Q", title=None, axis=alt.Axis(tickMinStep=1, grid=True, gridColor=LINE, domain=False)),
        color=(alt.value(GREEN) if field == "category" else alt.Color(
            f"{field}:N", legend=None, scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values())))),
        tooltip=[field, "Tickets"]).properties(height=max(150, 34 * len(counts))).configure(
        background="transparent").configure_view(strokeWidth=0)
    st.altair_chart(ch, width="stretch")


def open_ticket(tid):
    st.session_state.sel = tid
    st.session_state.page = "Tickets"


def ticket_row(t, cols=(0.8, 3.0, 1.0, 1.4, 1.1, 2.6, 0.7)):
    c = st.columns(cols, vertical_alignment="center")
    prev = t["message"] if len(t["message"]) < 80 else t["message"][:77] + "…"
    rep = t["suggested_reply"]
    rep = rep if len(rep) < 70 else rep[:67] + "…"
    c[0].markdown(f"<div class='cell tid'>{t['id']}</div>", unsafe_allow_html=True)
    c[1].markdown(f"<div class='cell'>{prev}</div>", unsafe_allow_html=True)
    if t["status"] == "error":
        c[2].markdown('<span class="badge" style="color:#8A2C2C;background:#F5E1DD">Failed</span>', unsafe_allow_html=True)
    elif t["status"] == "pending":
        c[2].markdown('<span class="badge" style="color:#555B61;background:#ECEAE4">Pending</span>', unsafe_allow_html=True)
    else:
        c[2].markdown(badge(t["urgency"]), unsafe_allow_html=True)
    c[3].markdown(cat_tag(t["category"]), unsafe_allow_html=True)
    c[4].markdown(badge(t["sentiment"]), unsafe_allow_html=True)
    c[5].markdown(f"<div class='cell' style='color:{MUTE}'>{rep}</div>", unsafe_allow_html=True)
    c[6].button("View", key=f"v_{t['id']}_{cols[0]}", on_click=open_ticket, args=(t["id"],))
    st.markdown("<hr class='row-line'>", unsafe_allow_html=True)


# ───────────────────────── Pages ─────────────────────────
def df_all():
    cols = ["id", "message", "urgency", "category", "sentiment", "suggested_reply", "status", "error"]
    return pd.DataFrame(st.session_state.tickets, columns=cols)


def page_dashboard():
    df = df_all()
    ok = df[df.status == "ready"]
    header("Support triage", batch_line(df))
    if df.empty:
        st.info("No tickets loaded. Open Load data to load the sample, upload JSON, paste messages, or test one message.")
        return
    n = max(len(ok), 1)
    crit, high = int((ok.urgency == "Critical").sum()), int((ok.urgency == "High").sum())
    neg = int(ok.sentiment.isin(NEG).sum())
    k = st.columns(4)
    kpi(k[0], "Total tickets", len(df), f"{len(ok)} analyzed")
    kpi(k[1], "Critical tickets", crit, f"{crit / n:.0%} of analyzed", "#8A2C2C")
    kpi(k[2], "High priority", high, f"{high / n:.0%} of analyzed", "#93561A")
    kpi(k[3], "Negative sentiment", neg, f"{neg / n:.0%} angry or frustrated", GREEN)
    failed = int((df.status == "error").sum())
    pend = int((df.status == "pending").sum())
    if failed or pend:
        st.write("")
        st.warning(f"{pend} ticket(s) awaiting analysis, {failed} failed. Run or retry them from the Tickets page.")
    st.write("")
    a, b, c = st.columns(3)
    with a:
        dist_chart(ok, "category", None, "By category")
    with b:
        dist_chart(ok, "urgency", URG, "By urgency")
    with c:
        dist_chart(ok, "sentiment", SENT, "By sentiment")
    st.markdown("<h3>Needs attention first</h3>", unsafe_allow_html=True)
    top = ok[ok.urgency == "Critical"].head(5)
    for t in top.to_dict("records"):
        ticket_row(t)
    if top.empty:
        st.caption("No critical tickets yet.")


def page_tickets():
    df = df_all()
    sel = next((t for t in st.session_state.tickets if t["id"] == st.session_state.sel), None)
    if sel:
        return ticket_detail(sel)
    header("Tickets", batch_line(df))
    todo = [t for t in st.session_state.tickets if t["status"] == "pending"]
    bad = [t for t in st.session_state.tickets if t["status"] == "error"]
    if todo or bad:
        b = st.columns([1.3, 1.3, 4])
        if todo and b[0].button(f"Analyze {len(todo)} pending", type="primary"):
            analyze(todo)
            st.rerun()
        if bad and b[1].button(f"Retry {len(bad)} failed", type="primary"):
            analyze(bad)
            st.rerun()
        if bad:
            st.error(f"{len(bad)} ticket(s) failed. Latest error: {bad[-1]['error']}")
            if st.session_state.mode == MODES[0]:
                st.caption("Batch mode fails as a whole when one message fails. Switch to per-ticket mode under Load data → API connection to isolate it.")
    f = st.columns([2.2, 1, 1, 1, 1.2])
    q = f[0].text_input("Search", placeholder="Search messages, IDs, replies", label_visibility="collapsed")
    fu = f[1].multiselect("Urgency", URG, placeholder="Urgency", label_visibility="collapsed")
    fc = f[2].multiselect("Category", [c for c in CATS if c in set(df.category)], placeholder="Category", label_visibility="collapsed")
    fs = f[3].multiselect("Sentiment", SENT, placeholder="Sentiment", label_visibility="collapsed")
    sort = f[4].selectbox("Sort", ["Urgency (high first)", "Ticket ID", "Category", "Sentiment"], label_visibility="collapsed")
    if q:
        m = (df.message.str.contains(q, case=False, regex=False)
             | df.id.str.contains(q, case=False, regex=False)
             | df.suggested_reply.str.contains(q, case=False, regex=False))
        df = df[m]
    if fu:
        df = df[df.urgency.isin(fu)]
    if fc:
        df = df[df.category.isin(fc)]
    if fs:
        df = df[df.sentiment.isin(fs)]
    key = {"Urgency (high first)": lambda s: s.map({u: i for i, u in enumerate(URG)}).fillna(9),
           "Sentiment": lambda s: s.map({u: i for i, u in enumerate(SENT)}).fillna(9)}.get(sort)
    col = {"Urgency (high first)": "urgency", "Ticket ID": "id", "Category": "category", "Sentiment": "sentiment"}[sort]
    df = df.sort_values(col, key=key, kind="stable") if key else df.sort_values(col, kind="stable")
    st.caption(f"Showing {len(df)} of {len(st.session_state.tickets)} tickets")
    h = st.columns((0.8, 3.0, 1.0, 1.4, 1.1, 2.6, 0.7))
    for x, name in zip(h, ["Ticket", "Message", "Urgency", "Category", "Sentiment", "Suggested reply", ""]):
        x.markdown(f"<div class='th'>{name}</div>", unsafe_allow_html=True)
    for t in df.to_dict("records"):
        ticket_row(t, (0.8, 3.0, 1.0, 1.4, 1.1, 2.6, 0.7))
    if df.empty:
        st.info("No tickets match these filters. Clear a filter or change your search.")


def ticket_detail(t):
    if st.button("‹ Back to tickets"):
        st.session_state.sel = None
        st.rerun()
    st.markdown(f"<h1>{t['id']}</h1>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub'>{badge(t['urgency'])} &nbsp;{cat_tag(t['category'])}&nbsp; {badge(t['sentiment'])}</div>",
                unsafe_allow_html=True)
    L, R = st.columns([1.2, 1], gap="large")
    with L:
        st.markdown("<h3>Customer message</h3>", unsafe_allow_html=True)
        st.markdown(f"<div class='card msg'>{t['message']}</div>", unsafe_allow_html=True)
        st.write("")
        st.markdown("<h3>Suggested reply</h3>", unsafe_allow_html=True)
        if t["status"] != "ready":
            st.info("This ticket hasn't been analyzed yet.")
        else:
            wkey = f"edit_{t['id']}"
            if st.session_state.get(f"editing_{t['id']}"):
                txt = st.text_area("Reply", t["suggested_reply"], height=160, key=wkey, label_visibility="collapsed")
                c = st.columns([1, 1, 4])
                if c[0].button("Save", type="primary", key=f"sv_{t['id']}"):
                    t["suggested_reply"] = txt
                    save_batches()
                    st.session_state[f"editing_{t['id']}"] = False
                    st.rerun()
                if c[1].button("Cancel", key=f"cx_{t['id']}"):
                    st.session_state[f"editing_{t['id']}"] = False
                    st.rerun()
            else:
                st.code(t["suggested_reply"], language=None, wrap_lines=True)  # hover → built-in copy button
                c = st.columns([1, 1, 4])
                if c[0].button("Edit reply", key=f"ed_{t['id']}"):
                    st.session_state[f"editing_{t['id']}"] = True
                    st.rerun()
                st.caption("Use the copy icon at the top right of the reply to copy it.")
    with R:
        st.markdown("<h3>AI analysis</h3>", unsafe_allow_html=True)
        if t["status"] == "error":
            st.error(t["error"])
        if t["status"] == "ready":
            st.markdown(f"""<div class='card'>
              <div class='cell'><b>Urgency</b><br>{badge(t['urgency'])}</div>
              <div class='cell'><b>Category</b><br>{cat_tag(t['category'])}</div>
              <div class='cell'><b>Sentiment</b><br>{badge(t['sentiment'])}</div></div>""", unsafe_allow_html=True)
            with st.expander("Raw JSON"):
                st.json({k: t[k] for k in FIELDS})
        label = "Retry analysis" if t["status"] == "error" else "Re-run analysis"
        if st.button(label, type="primary" if t["status"] != "ready" else "secondary"):
            analyze([t], use_cache=False)
            st.rerun()


def page_analytics():
    df = df_all()
    ok = df[df.status == "ready"]
    header("Analytics", batch_line(df))
    if ok.empty:
        st.info("Analyze some tickets to see analytics.")
        return
    st.markdown("<h3>Urgency by category</h3>", unsafe_allow_html=True)
    ct = ok.groupby(["category", "urgency"]).size().reset_index(name="Tickets")
    cats = ok.category.value_counts().index.tolist()
    base = alt.Chart(ct).encode(
        x=alt.X("urgency:N", sort=URG, title=None, axis=alt.Axis(orient="top", labelAngle=0)),
        y=alt.Y("category:N", sort=cats, title=None))
    heat = base.mark_rect(stroke=PAPER, strokeWidth=2, cornerRadius=3).encode(
        color=alt.Color("Tickets:Q", scale=alt.Scale(range=["#E4EDE7", GREEN]), legend=None))
    txt = base.mark_text(fontSize=13).encode(
        text="Tickets:Q", color=alt.condition(alt.datum.Tickets > 1, alt.value("#fff"), alt.value(INK)))
    st.altair_chart((heat + txt).properties(height=max(160, 38 * len(cats)))
                    .configure(background="transparent").configure_view(strokeWidth=0), width="stretch")
    a, b = st.columns(2, gap="large")
    r = ok.assign(neg=ok.sentiment.isin(NEG)).groupby("category").neg.mean().mul(100).round(0)
    r = r.sort_values(ascending=False).rename("Negative %").reset_index()
    with a:
        st.markdown("<h3>Negative sentiment by category</h3>", unsafe_allow_html=True)
        st.altair_chart(alt.Chart(r).mark_bar(color=GREEN, cornerRadiusEnd=3, size=16).encode(
            y=alt.Y("category:N", sort="-x", title=None),
            x=alt.X("Negative %:Q", title=None, scale=alt.Scale(domain=[0, 100])),
            tooltip=["category", "Negative %"]).properties(height=max(150, 32 * len(r)))
            .configure(background="transparent").configure_view(strokeWidth=0), width="stretch")
    with b:
        st.markdown("<h3>Highlights</h3>", unsafe_allow_html=True)
        top_cat = ok.category.value_counts().idxmax()
        urgent_share = ok.urgency.isin(["Critical", "High"]).mean()
        worst = r.iloc[0]
        st.markdown(f"""<div class='card cell'>
          <p><b>{top_cat}</b> is the largest category with {int((ok.category == top_cat).sum())} tickets.</p>
          <p><b>{urgent_share:.0%}</b> of analyzed tickets are Critical or High priority.</p>
          <p><b>{worst['category']}</b> has the highest share of negative sentiment ({worst['Negative %']:.0f}%).</p></div>""",
                    unsafe_allow_html=True)


def delete_batch(bid):
    d = st.session_state
    d.mem_batches = [x for x in d.mem_batches if x["id"] != bid]
    d.tickets = [t for t in d.tickets if t["batch"] != bid]  # also removes them from Tickets/Dashboard
    d.sel = None


def clear_memory():
    d = st.session_state
    d.mem_batches, d.mem_tests, d.mem_cache = [], [], {}
    d.tickets, d.sel, d.test_result = [], None, None


def memory_rows(batches, tests):
    cols = ["Source", "Ticket", "Message", "Urgency", "Category", "Sentiment", "Suggested reply"]
    rows = []
    for b in batches:
        for t in b["tickets"]:
            if t["status"] == "ready":
                rows.append([b["id"], t["id"], t["message"], t["urgency"], t["category"],
                             t["sentiment"], t["suggested_reply"]])
    for x in tests:
        r = x["result"]
        rows.append(["Single test", x["at"], x["message"], r["urgency"], r["category"],
                     r["sentiment"], r["suggested_reply"]])
    return pd.DataFrame(rows, columns=cols)


def page_history():
    batches, tests = st.session_state.mem_batches, st.session_state.mem_tests
    header("History", "Everything analyzed in this session is kept in memory so you can explore it again. "
                      "It is cleared when you refresh the page or press Clear.")
    k = st.columns(3)
    kpi(k[0], "Batches in memory", len(batches), f"latest {MAX_BATCHES} are kept")
    kpi(k[1], "Single messages", len(tests), f"latest {MAX_TESTS} are kept")
    kpi(k[2], "Reusable responses", len(st.session_state.mem_cache), "repeat messages skip the API")
    st.write("")
    tab_b, tab_t, tab_s = st.tabs(["Batches", "Single messages", "Search all"])

    with tab_b:
        if not batches:
            st.caption("No batches yet.")
        for b in reversed(batches):
            ts = b["tickets"]
            ok = [t for t in ts if t["status"] == "ready"]
            crit = sum(t["urgency"] == "Critical" for t in ok)
            with st.expander(f"{b['id']} · {b['source']} · {b['at']}"):
                st.caption(f"{len(ok)} of {len(ts)} analyzed · {crit} critical")
                c = st.columns([1.3, 1, 5])
                export = [dict(message=t["message"], **{f: t[f] for f in FIELDS}) for t in ok]
                c[0].download_button("Export JSON", data=json.dumps(export, indent=2, ensure_ascii=False),
                                     file_name=f"{b['id']}.json", mime="application/json", key=f"dl_{b['id']}")
                c[1].button("Delete", key=f"rd_{b['id']}", on_click=delete_batch, args=(b["id"],))
                if ts:
                    prev = pd.DataFrame(ts)[["id", "message", "urgency", "category", "sentiment", "status"]]
                    st.dataframe(prev, hide_index=True, width="stretch")

    with tab_t:
        if not tests:
            st.caption("No single messages yet. Use Load data → Test one message.")
        for x in tests:
            r = x["result"]
            short = x["message"] if len(x["message"]) < 70 else x["message"][:67] + "…"
            with st.expander(f"{x['at']} · {short}"):
                st.markdown(f"<div class='card msg'>{escape(x['message'])}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='sub'>{badge(r['urgency'])} &nbsp;{cat_tag(r['category'])}&nbsp; "
                            f"{badge(r['sentiment'])}</div>", unsafe_allow_html=True)
                st.code(r["suggested_reply"], language=None, wrap_lines=True)

    with tab_s:
        df = memory_rows(batches, tests)
        f = st.columns([2.4, 1, 1, 1])
        q = f[0].text_input("Search memory", placeholder="Search messages and replies",
                            label_visibility="collapsed", key="mem_q")
        fu = f[1].multiselect("Urgency", URG, placeholder="Urgency", label_visibility="collapsed", key="mem_fu")
        fc = f[2].multiselect("Category", [c for c in CATS if c in set(df.Category)], placeholder="Category",
                              label_visibility="collapsed", key="mem_fc")
        fs = f[3].multiselect("Sentiment", SENT, placeholder="Sentiment", label_visibility="collapsed", key="mem_fs")
        if q:
            df = df[df.Message.str.contains(q, case=False, regex=False)
                    | df["Suggested reply"].str.contains(q, case=False, regex=False)]
        if fu:
            df = df[df.Urgency.isin(fu)]
        if fc:
            df = df[df.Category.isin(fc)]
        if fs:
            df = df[df.Sentiment.isin(fs)]
        st.caption(f"{len(df)} matching responses across all batches and single messages")
        st.dataframe(df, hide_index=True, width="stretch")

    st.divider()
    st.button("Clear all memory", on_click=clear_memory)
    st.caption("Clears history, reusable responses and all tickets. Load the sample again from Load data.")


def page_load_data():
    header("Load data", "Load a batch of customer messages, or try a single message.")

    # ── Backend health check / wake-up ──
    st.info("Using Vercel for the backend, so it has a sleep problem. "
            "Run this button to wake it up and start exploring.")
    if st.button("Check backend", type="primary", key="ping_backend"):
        with st.spinner("Contacting the backend… the first request can take a while if it was asleep."):
            try:
                ping_backend()
                st.success("Backend is working perfectly. Start exploring messages!")
            except ApiError as e:
                st.error(str(e))
    st.divider()

    st.warning(
        "**Free-tier model, rate limited.** Please don't press Load sample or Import "
        "(upload / paste) several times in a row. Each one sends every message to the AI model "
        "and can exhaust the rate limit. To experiment, use **Test one message** instead; "
        "it makes a single API call."
    )
    tab_test, tab_sample, tab_up, tab_paste = st.tabs(
        ["Test one message", "Load sample", "Upload JSON", "Paste input"])

    with tab_test:
        st.write("Classify a single message. This uses one API call and the result is added to your tickets, "
                 "the dashboard and History.")
        msg = st.text_area("Customer message", height=140, key="test_msg",
                           placeholder="e.g. I was charged twice for my Premium subscription this month.")
        fresh = st.checkbox("Ignore memory and call the API again", key="test_fresh",
                            help="By default a message already answered in this session is reused without an API call.")
        if st.button("Analyze message", type="primary", key="test_go"):
            if not msg.strip():
                st.error("Enter a message first.")
            else:
                st.session_state.test_result = None
                res_new = None
                hit = None if fresh else st.session_state.setdefault("mem_cache", {}).get(mkey(msg))
                if hit:
                    res_new, st.session_state.test_from_memory = dict(hit), True
                else:
                    with st.spinner("Triaging…"):
                        try:
                            res_new = clean(api_post("/triage", {"message": msg.strip()}))
                            st.session_state.test_from_memory = False
                            remember_test(msg.strip(), res_new)
                        except ApiError as e:
                            st.error(str(e))
                if res_new:
                    st.session_state.test_result = res_new
                    added = add_tickets([mk(msg.strip(), res_new)], "Single message", register=False)
                    st.session_state.test_note = (f"Added to Tickets and the Dashboard as {added[0]['id']}."
                                                  if added else "This message is already in your tickets.")
        res = st.session_state.get("test_result")
        if res:
            if st.session_state.get("test_from_memory"):
                st.caption("Reused from memory. No API call was made.")
            st.caption(st.session_state.get("test_note", ""))
            st.markdown(f"""<div class='card'>
              <div class='cell'><b>Urgency</b><br>{badge(res['urgency'])}</div>
              <div class='cell'><b>Category</b><br>{cat_tag(res['category'])}</div>
              <div class='cell'><b>Sentiment</b><br>{badge(res['sentiment'])}</div></div>""",
                        unsafe_allow_html=True)
            st.write("")
            st.markdown("<h3>Suggested reply</h3>", unsafe_allow_html=True)
            st.code(res["suggested_reply"], language=None, wrap_lines=True)
            with st.expander("Raw JSON"):
                st.json(res)

    with tab_sample:
        st.write("The 5-message sample, already analyzed. This does not call the API.")
        if st.button("Load sample batch", type="primary"):
            if add_tickets(sample_tickets(), "Sample dataset"):
                st.session_state._nav = "Dashboard"
                st.rerun()
            else:
                st.info("The sample messages are already in your tickets.")
        st.caption("Want live results for the sample messages? This sends all 5 messages to the API.")
        if st.button("Load sample messages and triage with the API"):
            new = add_tickets(sample_tickets(analyzed=False), "Sample messages (live AI)", dedupe=False)
            analyze(new, use_cache=False)
            st.session_state._nav = "Dashboard"
            st.rerun()

    with tab_up:
        up = st.file_uploader("JSON file", type="json", help="A list of strings, or objects with a 'message' field.")
        if up and st.button("Import file", type="primary"):
            try:
                ts = parse_input(up.read().decode("utf-8"))
                if not ts:
                    raise ValueError("No messages found in this file.")
                new = add_tickets(ts, f"Upload · {up.name}")
                if not new:
                    raise ValueError("All of these messages are already in your tickets.")
                analyze([t for t in new if t["status"] == "pending"])
                st.session_state._nav = "Tickets"
                st.rerun()
            except Exception as e:  # noqa
                st.error(f"Could not read this file. {e}")
        st.caption("If the objects already include urgency, category, sentiment and suggested_reply, "
                   "no API call is made.")

    with tab_paste:
        raw = st.text_area("Messages", height=200,
                           placeholder="Paste JSON, or one message per line / blank-line separated.")
        if st.button("Import pasted input", type="primary"):
            ts = parse_input(raw) if raw.strip() else []
            if not ts:
                st.error("Nothing to import. Paste at least one message.")
            else:
                new = add_tickets(ts, "Pasted input")
                if not new:
                    st.info("All of these messages are already in your tickets.")
                else:
                    analyze([t for t in new if t["status"] == "pending"])
                    st.session_state._nav = "Tickets"
                    st.rerun()


# ───────────────────────── Shell ─────────────────────────
# Navigation requested from inside a page must be applied before the radio is created.
if "_nav" in st.session_state:
    st.session_state.page = st.session_state.pop("_nav")

with st.sidebar:
    st.markdown("<div class='brand'>Ticket classifier</div><div class='tag'>AI support triage</div>",
                unsafe_allow_html=True)
    st.radio("Navigate", ["Dashboard", "Tickets", "Analytics", "History", "Load data"], key="page",
             label_visibility="collapsed")
    st.write("")
    st.caption(f"Memory: {len(st.session_state.tickets)} tickets · {len(st.session_state.mem_batches)} batches · "
               f"{len(st.session_state.mem_tests)} single")

PAGES = {"Dashboard": page_dashboard, "Tickets": page_tickets,
         "Analytics": page_analytics, "History": page_history,
         "Load data": page_load_data}
PAGES[st.session_state.page]()
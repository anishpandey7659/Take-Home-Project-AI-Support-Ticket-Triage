"""Ticket classifier — AI Support Triage Dashboard (Streamlit).

Run with:  streamlit run app.py
"""
import json
import re
from datetime import datetime
from urllib.parse import urlparse

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
    ("I cannot log in. It keeps saying \"invalid credentials\" even after I reset my password twice. Please help.", "High", "Account", "Frustrated", "We're sorry you're still unable to log in after resetting your password. We'll help troubleshoot the account access issue."),
    ("Can I switch from monthly to annual billing? Is there a discount if I pay yearly?", "Low", "Billing", "Neutral", "We can help explain how to switch from monthly to annual billing and whether an annual billing discount is available."),
    ("How do I change the app language to Nepali? My mother is not comfortable reading English.", "Low", "Technical", "Neutral", "You can change the app language from the app's language or settings menu. We can guide you through the steps."),
    ("The pill scanner stopped recognising my father's medications after the latest update. It worked fine last week.", "High", "Technical", "Frustrated", "We're sorry the pill scanner stopped recognizing medications after the update. We'll help investigate the issue."),
    ("It would be great if the app could sync with my Apple Watch so I get reminders on my wrist.", "Low", "Feedback", "Neutral", "Thank you for the suggestion. Apple Watch syncing for medication reminders is useful feedback, and we'll pass it along to the team."),
    ("Someone has accessed my account and changed my mother's health records without permission. I need this account locked down immediately.", "Critical", "Account", "Frustrated", "We're sorry about the unauthorized account activity. Please secure the account immediately, and we'll help address the unauthorized changes."),
    ("The support agent who helped me last week was excellent and very patient. Really appreciate the great service.", "Low", "Feedback", "Happy", "Thank you for sharing this feedback. We're glad you had such a positive experience with our support team."),
    ("The dashboard is very slow to load. It takes almost 30 seconds every single time I open the app.", "Medium", "Technical", "Frustrated", "We're sorry the dashboard is taking so long to load. We'll help investigate the performance issue."),
    ("I cancelled my subscription last month but you are STILL charging my card. This feels like fraud and I want it stopped now.", "High", "Billing", "Angry", "We're sorry you're still being charged after cancelling your subscription. We'll review the recurring charge and help stop further billing."),
    ("Where can I download my father's health report as a PDF to share with his doctor?", "Low", "Account", "Neutral", "You can download your father's health report as a PDF from the report or health records section and share it with his doctor."),
    ("The reminder notifications arrive about 10 minutes late every time. Can this timing be fixed?", "Medium", "Technical", "Neutral", "We're sorry the reminder notifications are consistently delayed. We'll help investigate the notification timing issue."),
    ("The video call with the doctor kept dropping and we could not finish the consultation. Very frustrating.", "High", "Technical", "Frustrated", "We're sorry the video call kept dropping and interrupted the consultation. We’ll help investigate the connection issue."),
    ("I love the new interface redesign. It is much easier for my grandmother to navigate on her own now.", "Low", "Feedback", "Happy", "Thank you for the positive feedback. We're glad the new interface is easier for your grandmother to use."),
    ("Do you offer a family plan that covers multiple patients under one account?", "Low", "Billing", "Neutral", "We can help explain whether a family plan is available and how multiple patients can be covered under one account."),
    ("All of my mother's health data has disappeared from the app. Months of blood pressure and glucose logs, gone. Please help urgently, we need that history for her appointment tomorrow.", "Critical", "Technical", "Frustrated", "We're sorry that your mother's health history has disappeared. We understand that this information is needed for her appointment tomorrow and will help investigate urgently."),
]

# ───────────────────────── State ─────────────────────────
def mk(i, msg, a=None):
    t = dict(id=f"T-{1001 + i}", message=msg.strip(), urgency="", category="", sentiment="",
             suggested_reply="", status="pending", error="")
    if a:
        t.update({k: a[k] for k in ("urgency", "category", "sentiment", "suggested_reply")}, status="ready")
    return t


def load(tickets, source):
    st.session_state.tickets = tickets
    st.session_state.batch = dict(id=datetime.now().strftime("B-%Y%m%d-%H%M"), source=source,
                                  at=datetime.now().strftime("%b %d, %Y %H:%M"))
    st.session_state.sel = None


def sample_tickets(analyzed=True):
    if analyzed:
        return [mk(i, m, dict(urgency=u, category=c, sentiment=s, suggested_reply=r))
                for i, (m, u, c, s, r) in enumerate(SAMPLE)]
    return [mk(i, row[0]) for i, row in enumerate(SAMPLE)]


def ss_init():
    d = st.session_state
    d.setdefault("page", "Dashboard")
    d.setdefault("sel", None)
    d.setdefault("api_url", "http://localhost:8000/api/v1")
    d.setdefault("timeout", 120)
    d.setdefault("mode", "Batch · one request (/triage_all)")
    if "tickets" not in d:
        load(sample_tickets(), "Sample dataset")


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


def analyze(targets):
    """Triage tickets through the backend. Failures are stored per ticket so they can be retried."""
    targets = list(targets)
    if not targets:
        return
    if st.session_state.mode == MODES[0] and len(targets) > 1:
        with st.spinner(f"Triaging {len(targets)} messages…"):
            try:
                res = api_post("/triage_all", [{"message": t["message"]} for t in targets])
                if not isinstance(res, list) or len(res) != len(targets):
                    raise ApiError("The API returned a different number of results than messages sent.")
                results = [clean(x) for x in res]  # same order as input
                for t, r in zip(targets, results):
                    t.update(r, status="ready", error="")
            except ApiError as e:
                for t in targets:
                    t.update(status="error", error=str(e))
        return
    bar, note = st.progress(0.0), st.empty()
    for n, t in enumerate(targets, 1):
        note.caption(f"Triaging {t['id']} ({n} of {len(targets)})…")
        try:
            t.update(clean(api_post("/triage", {"message": t["message"]})), status="ready", error="")
        except ApiError as e:
            t.update(status="error", error=str(e))
        bar.progress(n / len(targets))
    bar.empty()
    note.empty()


def parse_input(raw):
    """Accepts JSON (list of strings/objects) or plain text (one message per line / blank-line separated)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        parts = [p for p in re.split(r"\n\s*\n", raw.strip()) if p.strip()]
        if len(parts) <= 1:
            parts = [p for p in raw.splitlines() if p.strip()]
        return [mk(i, p) for i, p in enumerate(parts)]
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
    return [mk(i, m, a) for i, (m, a) in enumerate(items) if m.strip()]


# ───────────────────────── Components ─────────────────────────
def badge(v):
    fg, bg = BADGE.get(v, ("#555B61", "#ECEAE4"))
    return f'<span class="badge" style="color:{fg};background:{bg}">{v}</span>' if v else ""


def cat_tag(v):
    return f'<span class="tag-cat">{v}</span>' if v else ""


def header(title, sub):
    st.markdown(f"<h1>{title}</h1><div class='sub'>{sub}</div>", unsafe_allow_html=True)


def batch_line(df):
    b = st.session_state.batch
    ready = int((df.status == "ready").sum()) if len(df) else 0
    return f"Batch {b['id']} · {b['source']} · loaded {b['at']} · {ready} of {len(df)} analyzed"


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
        st.info("No tickets loaded. Open Load data to load the sample batch, upload JSON, or paste messages.")
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
        st.caption("No critical tickets in this batch.")


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
            analyze([t])
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


def page_load_data():
    header("Load data", "Load a batch of customer messages, or try a single message.")
    st.warning(
        "**Free-tier model, rate limited.** Please don't press Load sample or Import "
        "(upload / paste) several times in a row. Each one sends every message to the AI model "
        "and can exhaust the rate limit. To experiment, use **Test one message** instead; "
        "it makes a single API call."
    )
    tab_test, tab_sample, tab_up, tab_paste = st.tabs(
        ["Test one message", "Load sample", "Upload JSON", "Paste input"])

    with tab_test:
        st.write("Classify a single message. This uses one API call and does not change the loaded batch.")
        msg = st.text_area("Customer message", height=140, key="test_msg",
                           placeholder="e.g. I was charged twice for my Premium subscription this month.")
        if st.button("Analyze message", type="primary", key="test_go"):
            if not msg.strip():
                st.error("Enter a message first.")
            else:
                st.session_state.test_result = None
                with st.spinner("Triaging…"):
                    try:
                        st.session_state.test_result = clean(api_post("/triage", {"message": msg.strip()}))
                    except ApiError as e:
                        st.error(str(e))
        res = st.session_state.get("test_result")
        if res:
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
        st.write("The 20-message sample batch, already analyzed. This does not call the API.")
        if st.button("Load sample batch", type="primary"):
            load(sample_tickets(), "Sample dataset")
            st.session_state._nav = "Dashboard"
            st.rerun()
        st.caption("Want live results for the sample messages? Use the Tickets page afterwards to analyze, "
                   "but remember each run sends all 20 messages to the API.")
        if st.button("Load sample messages and triage with the API"):
            load(sample_tickets(analyzed=False), "Sample messages (live AI)")
            analyze(st.session_state.tickets)
            st.session_state._nav = "Dashboard"
            st.rerun()

    with tab_up:
        up = st.file_uploader("JSON file", type="json", help="A list of strings, or objects with a 'message' field.")
        if up and st.button("Import file", type="primary"):
            try:
                ts = parse_input(up.read().decode("utf-8"))
                if not ts:
                    raise ValueError("No messages found in this file.")
                load(ts, f"Upload · {up.name}")
                analyze([t for t in ts if t["status"] == "pending"])
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
                load(ts, "Pasted input")
                analyze([t for t in ts if t["status"] == "pending"])
                st.session_state._nav = "Tickets"
                st.rerun()

    st.divider()
    with st.expander("API connection (advanced)"):
        c = st.columns([2, 1])
        st.session_state.api_url = c[0].text_input(
            "API base URL", st.session_state.api_url,
            help="Where your FastAPI router is mounted, including any prefix.")
        st.session_state.timeout = c[1].number_input("Timeout (seconds)", 10, 600, int(st.session_state.timeout), step=10)
        st.session_state.mode = st.radio(
            "Analysis mode", MODES, index=MODES.index(st.session_state.mode),
            help="Batch sends all messages in one call and fails as a whole if one fails. "
                 "Per ticket calls /triage for each message and keeps partial results.")


# ───────────────────────── Shell ─────────────────────────
# Navigation requested from inside a page must be applied before the radio is created.
if "_nav" in st.session_state:
    st.session_state.page = st.session_state.pop("_nav")

with st.sidebar:
    st.markdown("<div class='brand'>Ticket classifier</div><div class='tag'>AI support triage</div>",
                unsafe_allow_html=True)
    st.radio("Navigate", ["Dashboard", "Tickets", "Analytics", "Load data"], key="page",
             label_visibility="collapsed")
    st.write("")
    st.caption("API: " + st.session_state.api_url)

PAGES = {"Dashboard": page_dashboard, "Tickets": page_tickets,
         "Analytics": page_analytics, "Load data": page_load_data}
PAGES[st.session_state.page]()
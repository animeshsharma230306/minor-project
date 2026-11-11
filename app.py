"""AI-Based Personalized Study Planner: Streamlit front end."""
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import ai_engine as ai
import db
import scheduler as sch

load_dotenv()
st.set_page_config(page_title="AI-Based Personalized Study Planner", page_icon="🎓", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1200px}
div[data-testid="stMetric"],div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px}
div[data-testid="stMetric"]{background:#151a1b;border:1px solid #263031;padding:14px 16px;box-shadow:0 8px 24px rgba(0,0,0,.25)}
h1,h2,h3{letter-spacing:-.02em}
.demo{color:#f5a524;border:1px solid #5b4313;border-radius:99px;padding:2px 10px;font-size:12px}
</style>""", unsafe_allow_html=True)

TODAY = date.today()
PAGES = ["Home", "Dashboard", "Upload Syllabus", "My Subjects", "Study Planner",
         "Progress Tracker", "Analytics", "Settings"]


# ---------- configuration ----------
def secret(key):
    try:
        return os.getenv(key) or st.secrets.get(key)
    except Exception:
        return os.getenv(key)


def db_cfg():
    if not secret("MYSQL_HOST"):
        return None
    return dict(host=secret("MYSQL_HOST"), user=secret("MYSQL_USER") or "root",
                password=secret("MYSQL_PASSWORD") or "", database=secret("MYSQL_DATABASE") or "study_planner")


def api_key():
    return st.session_state.get("gemini_key") or secret("GEMINI_API_KEY")


def persist(full=False):
    """Best-effort save to MySQL; the app keeps working in demo mode if it fails."""
    cfg, S = db_cfg(), st.session_state.S
    if not cfg or S.get("demo"):
        return
    try:
        db.init_db(cfg)
        if full or not S.get("user_id"):
            db.save_plan(cfg, S)
        else:
            db.sync_sessions(cfg, S)
        st.session_state.db_msg = "Saved to MySQL"
    except Exception as exc:
        st.session_state.db_msg = f"MySQL unavailable ({exc.__class__.__name__}); running in memory only"


# ---------- state ----------
def make_state(name, exam, hours, subjects, topics, demo, start=None):
    S = dict(name=name, exam=exam, hours=hours, subjects=subjects, topics=topics, demo=demo, user_id=None)
    S["sessions"] = sch.build_schedule(subjects, topics, exam, hours, start)
    return S


def seed_demo():
    subs = [dict(name="Physics", priority=3, difficulty=3), dict(name="Mathematics", priority=3, difficulty=2),
            dict(name="Computer Science", priority=2, difficulty=2)]
    S = make_state("Demo Student", TODAY + timedelta(days=20), 3, subs,
                   ai.demo_topics([s["name"] for s in subs]), True, TODAY - timedelta(days=5))
    for i, x in enumerate(S["sessions"]):          # fake some history
        if x["date"] < TODAY:
            x["status"] = ("missed" if i % 6 == 2 else "pending" if i % 7 == 3
                           else "partial" if i % 9 == 4 else "done")
    return S


if "S" not in st.session_state:
    st.session_state.S = seed_demo()
if "nav" not in st.session_state:
    st.session_state.nav = "Home"
S = st.session_state.S


def goto(page):
    st.session_state.nav = page


def set_status(sid, status):
    for x in S["sessions"]:
        if x["id"] == sid:
            x["status"] = status
            st.session_state[f"chk{sid}"] = status == "done"
    persist()


def toggle(sid):
    set_status(sid, "done" if st.session_state[f"chk{sid}"] else "pending")


def do_replan():
    n = sch.reschedule(S["sessions"], S["subjects"], S["hours"], S["exam"], TODAY)
    persist()
    st.toast(f"Rescheduled {n} session(s) across upcoming days" if n else "Nothing to reschedule")


def session_row(x, key_prefix=""):
    c = st.columns([0.08, 0.5, 0.14, 0.14, 0.14])
    c[0].checkbox("done", value=x["status"] == "done", key=f"chk{x['id']}{key_prefix}",
                  label_visibility="collapsed", on_change=lambda i=x["id"], k=key_prefix: set_status(
                      i, "done" if st.session_state[f"chk{i}{k}"] else "pending"))
    note = f" · rescheduled" if x["resched"] else ""
    flag = f" · **{x['status']}**" if x["status"] in ("missed", "partial") else ""
    c[1].markdown(f"{'~~' if x['status']=='done' else ''}{x['title']}{'~~' if x['status']=='done' else ''}  \n"
                  f"<small>{x['subj']} · {x['type']} · {x['mins']} min{note}</small>{flag}", unsafe_allow_html=True)
    c[3].button("Partial", key=f"p{x['id']}{key_prefix}", on_click=set_status, args=(x["id"], "partial"))
    c[4].button("Missed", key=f"m{x['id']}{key_prefix}", on_click=set_status, args=(x["id"], "missed"))


# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### ✦ StudyPlanner AI")
    st.radio("Navigate", PAGES, key="nav", label_visibility="collapsed")
    st.divider()
    st.caption("Gemini API key (optional)")
    st.text_input("key", type="password", key="gemini_key", label_visibility="collapsed",
                  placeholder="Paste key or set GEMINI_API_KEY")
    st.caption("AI: " + ("Gemini connected" if api_key() else "demo / local parser"))
    st.caption("Database: " + (st.session_state.get("db_msg") or ("MySQL configured" if db_cfg() else "not configured (in-memory)")))
page = st.session_state.nav
if S["demo"]:
    st.markdown('<span class="demo">Demo data</span>', unsafe_allow_html=True)


# ---------- pages ----------
def home():
    st.title("AI-Based Personalized Study Planner")
    st.write("Upload your syllabus, set your exam date and daily hours, and let AI build a day-by-day plan "
             "with spaced revision that rebalances itself whenever you miss a session.")
    st.button("Get Started", type="primary", on_click=goto, args=("Upload Syllabus",))
    st.subheader("Core features")
    a, b = st.columns(2)
    a.info("**📄 Syllabus parsing and topic extraction**  \nPDF text extraction, then AI finds subjects, units, topics and prerequisites.")
    b.info("**🗓️ Adaptive scheduling engine**  \nMore time for hard, high-priority subjects; spaced repetition, revision and practice sessions.")
    a.info("**🔄 Dynamic rescheduling**  \nMark sessions done, partial or missed; unfinished work is redistributed, important topics first.")
    b.info("**📈 Progress tracking and analytics**  \nCompletion rates, overdue topics, subject-wise charts and what needs attention.")
    st.subheader("Execution workflow")
    steps = [("1. Data ingestion", "Exam date, daily hours and syllabus PDF are collected as study constraints."),
             ("2. AI analysis and parsing", "Text is extracted, subjects and topics identified, ranked by priority and complexity, and split into micro-tasks with prompt engineering."),
             ("3. Schedule generation", "An optimised timetable with daily sessions and spaced-repetition revision cycles."),
             ("4. Continuous adaptation", "Progress is logged, missed sessions detected, and the remaining plan recalculated.")]
    for col, (t, d) in zip(st.columns(4), steps):
        with col.container(border=True):
            st.markdown(f"**{t}**")
            st.caption(d)
    st.subheader("Technology stack")
    t1, t2, t3, t4 = st.columns(4)
    t1.success("**Streamlit**  \nInteractive dashboards, upload forms and planning UI.")
    t2.success("**Python + Gemini API**  \nBackend logic; Google GenAI SDK for analysis and scheduling.")
    t3.success("**PyPDF2**  \nRaw text extraction from academic PDFs.")
    t4.success("**MySQL**  \nUsers, syllabus, schedules and progress logs.")
    st.subheader("Database schema")
    st.graphviz_chart("""digraph G { rankdir=LR; bgcolor="transparent";
      node [shape=record, style=filled, fillcolor="#1c2324", color="#2dd4b0", fontcolor="#e6efed"];
      edge [color="#2dd4b0", fontcolor="#8da29f"];
      Users [label="{Users|PK user_id|name|email|daily_hours}"];
      Exams [label="{Exams|PK exam_id|FK user_id|exam_date}"];
      Subjects [label="{Subjects|PK subject_id|FK user_id|name|priority|difficulty}"];
      Topics [label="{Topics|PK topic_id|FK subject_id|unit, title|prerequisite|complexity}"];
      Study_Schedule [label="{Study_Schedule|PK schedule_id|FK topic_id, subject_id|scheduled_date|allocated_mins|status}"];
      Progress_Logs [label="{Progress_Logs|PK log_id|FK schedule_id|status|logged_at}"];
      Users -> Exams [label="1:N"]; Users -> Subjects [label="1:N"]; Subjects -> Topics [label="1:N"];
      Topics -> Study_Schedule [label="1:N"]; Study_Schedule -> Progress_Logs [label="1:N"]; }""")


def dashboard():
    st.title("Dashboard")
    st.caption(f"Welcome back, {S['name']}.")
    o = sch.overview(S, TODAY)
    for col, (l, v) in zip(st.columns(5), [("Subjects", o["subjects"]), ("Topics", o["topics"]),
                                          ("Days to exam", o["days_left"]), ("Daily hours", o["hours"]),
                                          ("Syllabus complete", f"{o['pct']}%")]):
        col.metric(l, v)
    st.progress(o["pct"] / 100)
    a, b = st.columns(2)
    with a:
        st.subheader("Last 7 days")
        st.bar_chart(pd.DataFrame(sch.weekly(S["sessions"], TODAY)).set_index("day")["rate"], color="#2dd4b0")
    with b:
        st.subheader("Upcoming tasks")
        up = sorted([x for x in sch.live(S["sessions"]) if x["date"] >= TODAY and x["status"] != "done"],
                    key=lambda x: x["date"])[:5]
        for x in up:
            st.markdown(f"- **{x['title']}**  \n  {x['date']:%a %d %b} · {x['mins']} min · {x['type']}")
    st.subheader("AI study recommendations")
    for r in sch.recommendations(S, TODAY):
        st.markdown("- " + r)
    if api_key() and st.button("Ask Gemini for coaching"):
        try:
            sp = sch.subject_progress(S, TODAY)
            st.write(ai.ai_advice(f"Exam in {o['days_left']} days, {o['pct']}% done. Subjects: {sp}", api_key()))
        except Exception as exc:
            st.error(f"Gemini request failed: {exc}")


def upload():
    st.title("Upload syllabus")
    with st.form("setup"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name", value="" if S["demo"] else S["name"])
        exam = c2.date_input("Exam date", value=TODAY + timedelta(days=21), min_value=TODAY + timedelta(days=3))
        hours = c3.number_input("Study hours per day", 1.0, 12.0, 3.0, 0.5)
        st.caption("Subjects: difficulty and priority run from 1 (low) to 3 (high). Add rows as needed.")
        subs = st.data_editor(pd.DataFrame([["Physics", 3, 3], ["Mathematics", 2, 3], ["Computer Science", 2, 2]],
                                           columns=["name", "difficulty", "priority"]),
                              num_rows="dynamic", use_container_width=True,
                              column_config={"difficulty": st.column_config.NumberColumn(min_value=1, max_value=3, step=1),
                                             "priority": st.column_config.NumberColumn(min_value=1, max_value=3, step=1)})
        pdf = st.file_uploader("Syllabus PDF", type="pdf")
        go = st.form_submit_button("Analyze and generate plan", type="primary")
    if not go:
        return
    subs = subs.dropna(subset=["name"])
    subs = subs[subs["name"].str.strip() != ""]
    if subs.empty or not name.strip():
        return st.error("Enter your name and at least one subject.")
    subjects = [dict(name=r["name"].strip(), difficulty=int(r["difficulty"]), priority=int(r["priority"]))
                for _, r in subs.iterrows()]
    text = ""
    if pdf:
        with st.spinner("Extracting text with PyPDF2..."):
            text = ai.extract_text(pdf)
        with st.expander("Extracted text preview"):
            st.text(text[:1500])
    with st.spinner("Analyzing syllabus..."):
        topics, mode = ai.analyze(text, [s["name"] for s in subjects], api_key())
    st.session_state.S = make_state(name.strip(), exam, hours, subjects, topics, mode == "demo")
    persist(full=True)
    labels = {"gemini": "Analyzed with Gemini AI", "heuristic": "Parsed with the local rule-based parser (no Gemini key)",
              "demo": "No usable text, so sample topics were generated (demo)"}
    st.success(f"{labels[mode]}: {len(topics)} topics, {len(st.session_state.S['sessions'])} sessions scheduled.")
    st.button("Open study planner", on_click=goto, args=("Study Planner",))


def subjects_page():
    st.title("My subjects")
    for r in sch.subject_progress(S, TODAY):
        with st.expander(f"{r['subject']} · {r['pct']}% · priority {r['priority']}", expanded=True):
            st.progress(r["pct"] / 100)
            for unit in dict.fromkeys(t["unit"] for t in S["topics"] if t["subj"] == r["subject"]):
                st.markdown(f"**{unit}**")
                for t in [t for t in S["topics"] if t["subj"] == r["subject"] and t["unit"] == unit]:
                    s = sch.topic_status(t, S["sessions"], TODAY)
                    pre = f"  \n<small>Prerequisite: {t['prereq']}</small>" if t["prereq"] else ""
                    st.markdown(f"- {t['title']} `{s}`{pre}", unsafe_allow_html=True)


def planner():
    st.title("Study planner")
    days = sorted({x["date"] for x in sch.live(S["sessions"])})
    default = days.index(TODAY) if TODAY in days else 0
    d = st.selectbox("Day", days, index=default, format_func=lambda d: f"{d:%a %d %b}" + (" (today)" if d == TODAY else ""))
    todays = [x for x in sch.live(S["sessions"]) if x["date"] == d]
    st.caption(f"{sum(x['mins'] for x in todays)} min planned of {int(S['hours'] * 60)} min available")
    for x in todays:
        session_row(x)
    st.button("Replan missed sessions", on_click=do_replan)


def tracker():
    st.title("Progress tracker")
    o = sch.overview(S, TODAY)
    a, b, c = st.columns(3)
    a.metric("Topics completed", o["done"]); b.metric("Pending", o["pending"]); c.metric("Overdue", o["overdue"])
    live = sch.live(S["sessions"])
    st.progress(sum(x["status"] == "done" for x in live) / max(1, len(live)))
    st.subheader("Missed and overdue sessions")
    miss = [x for x in live if x["status"] == "missed" or (x["date"] < TODAY and x["status"] == "pending")]
    st.button("Replan missed", on_click=do_replan, key="rp2")
    for x in sorted(miss, key=lambda x: x["date"]):
        session_row(x, "t")
    if not miss:
        st.success("Nothing missed. Keep going.")


def analytics():
    st.title("Analytics")
    a, b = st.columns(2)
    wk = pd.DataFrame(sch.weekly(S["sessions"], TODAY)).set_index("day")
    a.subheader("Daily completion rate (%)"); a.bar_chart(wk["rate"], color="#2dd4b0")
    b.subheader("Minutes planned vs done"); b.bar_chart(wk[["planned", "done"]])
    sp = pd.DataFrame(sch.subject_progress(S, TODAY))
    a.subheader("Subject-wise progress (%)"); a.bar_chart(sp.set_index("subject")["pct"], color="#2dd4b0")
    live = pd.DataFrame(sch.live(S["sessions"]))
    b.subheader("Planned minutes by subject"); b.bar_chart(live.groupby("subj")["mins"].sum())
    st.subheader("Session mix (spaced repetition)")
    st.bar_chart(live.groupby("type")["mins"].sum())
    st.subheader("On track vs needs attention")
    for r in sp.to_dict("records"):
        ok = r["overdue"] == 0 and r["pct"] >= 40
        st.markdown(f"- **{r['subject']}**: {r['pct']}% · " + ("on track" if ok else ":red[needs attention]"))


def settings():
    st.title("Settings")
    with st.form("settings"):
        name = st.text_input("Name", S["name"])
        exam = st.date_input("Exam date", S["exam"])
        hours = st.number_input("Study hours per day", 1.0, 12.0, float(S["hours"]), 0.5)
        if st.form_submit_button("Save and rebuild plan", type="primary"):
            S.update(name=name, exam=exam, hours=hours, user_id=None if name != S["name"] else S["user_id"])
            S["sessions"] = sch.build_schedule(S["subjects"], S["topics"], exam, hours)
            persist(full=True)
            st.success("Plan rebuilt.")
    c1, c2 = st.columns(2)
    if c1.button("Load demo data"):
        st.session_state.S = seed_demo(); st.rerun()
    who = c2.text_input("Load saved plan from MySQL by name")
    if who and db_cfg():
        try:
            loaded = db.load_plan(db_cfg(), who)
            if loaded:
                st.session_state.S = loaded; st.rerun()
            st.warning("No saved plan with that name.")
        except Exception as exc:
            st.error(f"MySQL error: {exc}")


{"Home": home, "Dashboard": dashboard, "Upload Syllabus": upload, "My Subjects": subjects_page,
 "Study Planner": planner, "Progress Tracker": tracker, "Analytics": analytics, "Settings": settings}[page]()

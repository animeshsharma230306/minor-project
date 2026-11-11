"""Adaptive scheduling, spaced repetition, rescheduling and analytics (pure Python)."""
import math
from datetime import date, timedelta

REVISION_OFFSETS = (1, 3, 7)  # spaced repetition: revise after 1, 3 and 7 days


def weight(subjects, name):
    s = next((x for x in subjects if x["name"] == name), None)
    return s["priority"] * s["difficulty"] if s else 4


def _session(sid, d, subj, tid, kind, mins, title):
    return dict(id=sid, date=d, subj=subj, tid=tid, title=title, type=kind, mins=mins,
                status="pending", moved=False, resched=False, saved=False)


def build_schedule(subjects, topics, exam, hours, start=None):
    """Day-by-day plan: harder/higher-priority topics get more minutes and go first."""
    start = start or date.today()
    days = min(90, max(4, (exam - start).days))
    budget = hours * 60 * 0.65          # leave room for revision and practice
    load, out = [0] * days, []
    last = max(1, days - 3)             # final days are reserved for practice

    def put(day, subj, tid, kind, mins, title):
        load[day] += mins
        out.append(_session(len(out) + 1, start + timedelta(day), subj, tid, kind, mins, title))

    d = 0
    for t in sorted(topics, key=lambda t: -weight(subjects, t["subj"]) * t.get("complexity", 2)):
        w = weight(subjects, t["subj"])
        mins = round((25 + w * 8 + (t.get("complexity", 2) - 2) * 5) / 5) * 5
        while d < last and load[d] + mins > budget:
            d += 1
        day = min(d, last)
        put(day, t["subj"], t["id"], "study", mins, t["title"])
        for off in REVISION_OFFSETS:
            if day + off < days - 1:
                put(day + off, t["subj"], t["id"], "revise", 15, "Revise: " + t["title"])
    for i, s in enumerate(subjects):
        put(min(days - 1, max(0, days - 3 + i % 3)), s["name"], 0, "practice", 45,
            "Practice paper: " + s["name"])
    return out


def reschedule(sessions, subjects, hours, exam, today=None):
    """Move missed, partial and overdue sessions to the earliest days with spare capacity."""
    today, cap, last = today or date.today(), hours * 60, exam - timedelta(days=1)
    todo = [s for s in sessions if not s["moved"] and (
        s["status"] in ("missed", "partial") or (s["date"] < today and s["status"] == "pending"))]
    todo.sort(key=lambda s: -weight(subjects, s["subj"]))   # important topics first
    nid = max((s["id"] for s in sessions), default=0) + 1
    for s in todo:
        mins = max(10, math.ceil(s["mins"] / 2 / 5) * 5) if s["status"] == "partial" else s["mins"]
        d = today
        while d < last and sum(x["mins"] for x in sessions if not x["moved"] and x["date"] == d) + mins > cap:
            d += timedelta(days=1)
        s["moved"] = True
        sessions.append({**s, "id": nid, "date": d, "mins": mins, "status": "pending",
                         "moved": False, "resched": True, "saved": False})
        nid += 1
    return len(todo)


def live(sessions):
    return [s for s in sessions if not s["moved"]]


def topic_status(t, sessions, today):
    ss = [s for s in sessions if s["tid"] == t["id"] and s["type"] == "study"]
    if any(s["status"] == "done" for s in ss):
        return "done"
    if any(not s["moved"] and (s["date"] < today or s["status"] == "missed") for s in ss):
        return "overdue"
    return "pending"


def overview(S, today=None):
    today = today or date.today()
    st = [topic_status(t, S["sessions"], today) for t in S["topics"]]
    n = len(st)
    return dict(subjects=len(S["subjects"]), topics=n, done=st.count("done"), overdue=st.count("overdue"),
                pending=st.count("pending"), pct=round(st.count("done") / n * 100) if n else 0,
                days_left=max(0, (S["exam"] - today).days), hours=S["hours"])


def subject_progress(S, today=None):
    today, rows = today or date.today(), []
    for s in S["subjects"]:
        ts = [t for t in S["topics"] if t["subj"] == s["name"]]
        stt = [topic_status(t, S["sessions"], today) for t in ts]
        done = stt.count("done")
        rows.append(dict(subject=s["name"], total=len(ts), done=done, overdue=stt.count("overdue"),
                         pct=round(done / len(ts) * 100) if ts else 0, priority=s["priority"]))
    return rows


def weekly(sessions, today=None):
    today, rows = today or date.today(), []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day = [s for s in live(sessions) if s["date"] == d]
        planned = sum(s["mins"] for s in day)
        done = sum(s["mins"] for s in day if s["status"] == "done")
        rows.append(dict(day=d.strftime("%a %d"), planned=planned, done=done,
                         rate=round(done / planned * 100) if planned else 0))
    return rows


def recommendations(S, today=None):
    today, out = today or date.today(), []
    o, sp = overview(S, today), sorted([r for r in subject_progress(S, today) if r["total"]], key=lambda r: r["pct"])
    if o["overdue"]:
        out.append(f"{o['overdue']} topic(s) are overdue. Press 'Replan missed' to move them into open days.")
    if sp:
        out.append(f"{sp[0]['subject']} is at {sp[0]['pct']}%, your lowest subject. Start each day with it.")
    weak = [r["subject"] for r in sp if r["priority"] == 3 and r["pct"] < 50]
    if weak:
        out.append("High-priority subjects below 50%: " + ", ".join(weak) + ". Protect those sessions.")
    load = sum(s["mins"] for s in live(S["sessions"]) if s["date"] == today and s["status"] != "done")
    out.append(f"Today holds {load} min against your {int(S['hours'] * 60)} min budget."
               + (" Replan to spread it out." if load > S["hours"] * 60 else ""))
    if o["days_left"] <= 7:
        out.append(f"Exam in {o['days_left']} days. Favour practice papers and revision over new topics.")
    return out

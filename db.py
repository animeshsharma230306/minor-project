"""MySQL persistence. Every function is best-effort; the app also works without a database."""
from pathlib import Path

import mysql.connector


def connect(cfg):
    return mysql.connector.connect(host=cfg["host"], user=cfg["user"], password=cfg["password"],
                                   database=cfg["database"], autocommit=False)


def init_db(cfg):
    boot = mysql.connector.connect(host=cfg["host"], user=cfg["user"], password=cfg["password"])
    boot.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}`")
    boot.close()
    conn = connect(cfg)
    cur = conn.cursor()
    for stmt in Path(__file__).with_name("schema.sql").read_text().split(";"):
        if stmt.strip():
            cur.execute(stmt)
    conn.commit()
    conn.close()


def save_plan(cfg, S):
    """Create or replace a student's whole plan. Rewrites ids in S to the database ids."""
    conn = connect(cfg)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM Users WHERE name=%s", (S["name"],))
    row = cur.fetchone()
    if row:
        uid = row[0]
        cur.execute("UPDATE Users SET daily_hours=%s WHERE user_id=%s", (S["hours"], uid))
        for tbl in ("Exams", "Subjects"):           # cascades to Topics, Schedule, Logs
            cur.execute(f"DELETE FROM {tbl} WHERE user_id=%s", (uid,))
    else:
        cur.execute("INSERT INTO Users (name, daily_hours) VALUES (%s,%s)", (S["name"], S["hours"]))
        uid = cur.lastrowid
    cur.execute("INSERT INTO Exams (user_id, exam_date) VALUES (%s,%s)", (uid, S["exam"]))
    sid = {}
    for s in S["subjects"]:
        cur.execute("INSERT INTO Subjects (user_id,name,priority,difficulty) VALUES (%s,%s,%s,%s)",
                    (uid, s["name"], s["priority"], s["difficulty"]))
        sid[s["name"]] = cur.lastrowid
    tmap = {}
    for t in S["topics"]:
        cur.execute("INSERT INTO Topics (subject_id,unit,title,prerequisite,complexity) VALUES (%s,%s,%s,%s,%s)",
                    (sid[t["subj"]], t["unit"], t["title"], t["prereq"], t.get("complexity", 2)))
        tmap[t["id"]] = cur.lastrowid
        t["id"] = cur.lastrowid
    for x in S["sessions"]:
        x["tid"] = tmap.get(x["tid"], 0) if x["tid"] in tmap else x["tid"]
    S["user_id"] = uid
    conn.commit()
    conn.close()
    sync_sessions(cfg, S)


def sync_sessions(cfg, S):
    """Insert new sessions, update changed ones, and log every status change."""
    conn = connect(cfg)
    cur = conn.cursor()
    cur.execute("SELECT subject_id, name FROM Subjects WHERE user_id=%s", (S["user_id"],))
    sid = {n: i for i, n in cur.fetchall()}
    for x in S["sessions"]:
        if not x["saved"]:
            cur.execute("""INSERT INTO Study_Schedule (user_id,subject_id,topic_id,scheduled_date,title,
                           session_type,allocated_mins,status,moved,rescheduled) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (S["user_id"], sid[x["subj"]], x["tid"] or None, x["date"], x["title"], x["type"],
                         x["mins"], x["status"], x["moved"], x["resched"]))
            x["id"], x["saved"] = cur.lastrowid, True
        else:
            cur.execute("SELECT status FROM Study_Schedule WHERE schedule_id=%s", (x["id"],))
            old = cur.fetchone()
            cur.execute("UPDATE Study_Schedule SET status=%s, moved=%s WHERE schedule_id=%s",
                        (x["status"], x["moved"], x["id"]))
            if old and old[0] != x["status"]:
                cur.execute("INSERT INTO Progress_Logs (schedule_id,status) VALUES (%s,%s)", (x["id"], x["status"]))
    conn.commit()
    conn.close()


def load_plan(cfg, name):
    conn = connect(cfg)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM Users WHERE name=%s", (name,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return None
    uid = u["user_id"]
    cur.execute("SELECT exam_date FROM Exams WHERE user_id=%s ORDER BY exam_id DESC LIMIT 1", (uid,))
    exam = cur.fetchone()["exam_date"]
    cur.execute("SELECT subject_id,name,priority,difficulty FROM Subjects WHERE user_id=%s", (uid,))
    subs = cur.fetchall()
    names = {s["subject_id"]: s["name"] for s in subs}
    cur.execute("""SELECT t.topic_id id, t.subject_id, t.unit, t.title, t.prerequisite prereq, t.complexity
                   FROM Topics t JOIN Subjects s USING(subject_id) WHERE s.user_id=%s""", (uid,))
    topics = [dict(id=r["id"], subj=names[r["subject_id"]], unit=r["unit"], title=r["title"],
                   prereq=r["prereq"] or "", complexity=r["complexity"]) for r in cur.fetchall()]
    cur.execute("SELECT * FROM Study_Schedule WHERE user_id=%s ORDER BY scheduled_date", (uid,))
    sessions = [dict(id=r["schedule_id"], date=r["scheduled_date"], subj=names[r["subject_id"]],
                     tid=r["topic_id"] or 0, title=r["title"], type=r["session_type"], mins=r["allocated_mins"],
                     status=r["status"], moved=bool(r["moved"]), resched=bool(r["rescheduled"]), saved=True)
                for r in cur.fetchall()]
    conn.close()
    return dict(name=name, user_id=uid, demo=False, exam=exam, hours=u["daily_hours"],
                subjects=[dict(name=s["name"], priority=s["priority"], difficulty=s["difficulty"]) for s in subs],
                topics=topics, sessions=sessions)

"""PDF text extraction (PyPDF2) and syllabus analysis (Google Gemini via the Google GenAI SDK)."""
import json
import re

import PyPDF2

MODEL = "gemini-2.5-flash"

PROMPT = """You are an academic planning assistant. Analyse the syllabus text below.
The student's subjects are: {subjects}.
Return ONLY a JSON array. Each item must have:
  "subject": one of the student's subjects (best match),
  "unit": unit or chapter name,
  "title": a micro-topic that can be studied in 30-90 minutes,
  "prerequisite": title of a topic that should be studied first, or "",
  "complexity": integer 1 (easy), 2 (medium) or 3 (hard).
Split large chapters into micro-topics. Limit to 60 items.

SYLLABUS:
{text}
"""

DEMO_BANK = [("Unit 1", "Core concepts"), ("Unit 1", "Key definitions and formulas"),
             ("Unit 1", "Worked examples"), ("Unit 2", "Problem-solving techniques"),
             ("Unit 2", "Advanced applications"), ("Unit 3", "Previous-year questions")]


def extract_text(file) -> str:
    reader = PyPDF2.PdfReader(file)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _gemini(text, subject_names, api_key):
    from google import genai
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(subjects=", ".join(subject_names), text=text[:30000]),
        config={"response_mime_type": "application/json"})
    items = json.loads(re.sub(r"^```(?:json)?|```$", "", resp.text.strip()).strip())
    return [dict(id=i + 1, subj=x.get("subject") if x.get("subject") in subject_names else subject_names[0],
                 unit=x.get("unit", "Unit 1"), title=x["title"], prereq=x.get("prerequisite", ""),
                 complexity=int(x.get("complexity", 2))) for i, x in enumerate(items)][:60]


def _heuristic(text, subject_names):
    """Offline fallback: unit headings plus comma/semicolon separated topic lists."""
    out, unit, subj, prev = [], "Unit 1", subject_names[0], ""
    for line in filter(None, (l.strip() for l in text.splitlines())):
        if len(out) >= 45:
            break
        hit = next((n for n in subject_names if len(line) < 60 and n.lower() in line.lower()), None)
        if hit and not re.search(r"[,;]", line):
            subj = hit
            continue
        rest = line
        if re.match(r"^(unit|module|chapter|section)\s*[\dIVX]+", line, re.I):
            parts = re.split(r"\s*[:\-\u2013]\s*", line)
            unit, prev, rest = parts[0][:40], "", ", ".join(parts[1:])
        for piece in re.split(r"[,;\u2022]", rest):
            piece = re.sub(r"^[\d.)\-\s]+", "", piece).strip()
            if 3 < len(piece) < 70:
                out.append(dict(id=len(out) + 1, subj=subj, unit=unit, title=piece, prereq=prev, complexity=2))
                prev = piece
    return out


def demo_topics(subject_names):
    out = []
    for n in subject_names:
        for i, (u, t) in enumerate(DEMO_BANK):
            out.append(dict(id=len(out) + 1, subj=n, unit=u, title=f"{n}: {t}",
                            prereq=out[-1]["title"] if i % 3 and out else "", complexity=1 + i % 3))
    return out


def analyze(text, subject_names, api_key=None):
    """Returns (topics, mode) where mode is 'gemini', 'heuristic' or 'demo'."""
    if api_key and text.strip():
        try:
            topics = _gemini(text, subject_names, api_key)
            if topics:
                return topics, "gemini"
        except Exception as exc:  # network, quota, bad JSON ...
            print("Gemini failed, falling back:", exc)
    if text.strip():
        topics = _heuristic(text, subject_names)
        if len(topics) >= 3:
            return topics, "heuristic"
    return demo_topics(subject_names), "demo"


def ai_advice(summary: str, api_key: str) -> str:
    from google import genai
    client = genai.Client(api_key=api_key)
    return client.models.generate_content(
        model=MODEL,
        contents="You are a study coach. In 4 short bullet points, give advice for this student:\n" + summary).text

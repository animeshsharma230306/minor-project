# AI-Based Personalized Study Planner

Streamlit + Python + Google Gemini (Google GenAI SDK) + PyPDF2 + MySQL.

## Setup
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                               # fill in your keys
streamlit run app.py
```
- **Gemini key** (free at aistudio.google.com): put in `.env` or paste in the sidebar.
- **MySQL**: install MySQL, put credentials in `.env`. Tables are created automatically from `schema.sql`.
- Without a key or database the app still runs: it uses a local rule-based parser, sample topics and in-memory state (marked as demo).

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit UI: Home, Dashboard, Upload Syllabus, My Subjects, Study Planner, Progress Tracker, Analytics, Settings |
| `ai_engine.py` | PyPDF2 text extraction, Gemini prompt for topic extraction, offline fallback |
| `scheduler.py` | Adaptive scheduling, spaced repetition (1/3/7 days), rescheduling, analytics |
| `db.py` | MySQL save/load/sync and progress logging |
| `schema.sql` | Users, Subjects, Topics, Exams, Study_Schedule, Progress_Logs |

## How it works
1. **Data ingestion**: name, exam date, daily hours, subjects with priority and difficulty, syllabus PDF.
2. **AI analysis**: PyPDF2 extracts text, Gemini returns JSON of subjects, units, micro-topics, prerequisites and complexity.
3. **Schedule generation**: minutes per topic scale with priority x difficulty x complexity; revision sessions after 1, 3 and 7 days; practice papers in the last days.
4. **Continuous adaptation**: mark sessions done, partial or missed; `Replan missed` moves them to the earliest days with spare time, highest priority first.

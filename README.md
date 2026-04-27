# 🎓 Syllabus Design Agent

> **AI-powered, OBE-aligned course design — from a single JSON file to a full audit-ready PDF syllabus.**  
> Powered by **Google Gemini 2.0 Flash** · Aligned with **NBA/NAAC · Revised Bloom's Taxonomy · UN SDGs**

---

## ▶️ Run Instantly — No Setup Needed

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mitaoehodaimlai-create/syllabus-design-agent/blob/main/SyllabusAgent_Demo.ipynb)

Click the badge above → paste your **Gemini API key** when prompted → get a complete syllabus PDF in minutes.

---

## What It Generates (15 Sections)

| # | Section | Output |
|---|---------|--------|
| 1 | Course Profile & Objectives | Paragraph + list |
| 2 | Course Outcomes (COs) | RBT-mapped table |
| 3 | SDG Alignment | Mapping table |
| 4 | Unit-wise Syllabus | Content + case study + self-learning per unit |
| 5 | Lesson Plan | Week-by-week + hour-by-hour table |
| 6 | Lab / Practical Design | Experiments + CO mapping |
| 7 | Teaching–Learning Strategy | Pedagogy + industry integration |
| 8 | Assessment Framework | CIE + ESE weightage tables |
| 9 | Assignments & Activities | Beginner / Intermediate / Advanced |
| 10 | Rubrics | Criteria-based evaluation tables |
| 11 | CO–PO–PSO Mapping | Correlation matrix |
| 12 | Question Bank | 20+ questions across Bloom's levels |
| 13 | Learning Resources | Textbooks, MOOCs, datasets, GitHub links |
| 14 | Learner Differentiation | Slow / Average / Advanced strategies |
| 15 | Cross-cutting Integration | Industry, ethics, sustainability (SDGs) |

---

## Project Structure

```
syllabus_agent/
├── main.py                   ← CLI wizard (interactive or --json)
├── agent.py                  ← Gemini streaming agent (5 batched calls)
├── prompts.py                ← All 15-section prompt templates
├── pdf_generator.py          ← Markdown → professional PDF (ReportLab)
├── models.py                 ← CourseInput dataclass
├── config.py                 ← Model settings, system instruction
├── create_admin.py           ← Seed first admin user
├── sample_input.json         ← Example: Machine Learning B.Tech
├── SyllabusAgent_Demo.ipynb  ← ▶️ Colab executable notebook
│
└── api/                      ← REST API (FastAPI + JWT auth)
    ├── app.py                ← FastAPI entry point
    ├── auth.py               ← bcrypt + JWT helpers
    ├── database.py           ← SQLite (users + uploads tables)
    ├── schemas.py            ← Pydantic request/response models
    └── routes/
        ├── auth_routes.py    ← /auth/register  /auth/login  /auth/me
        └── upload_routes.py  ← /upload/json  (admin only)
```

---

## Local CLI — Quick Start

```bash
# 1. Clone
git clone https://github.com/mitaoehodaimlai-create/syllabus-design-agent.git
cd syllabus-design-agent

# 2. Install
pip install -r requirements.txt

# 3. Set Gemini key
export GEMINI_API_KEY="your-key-here"

# 4a. Interactive wizard
python main.py

# 4b. From JSON file
python main.py --json sample_input.json

# 4c. Regenerate one section only
python main.py --json sample_input.json --regen lesson_plan
```

---

## REST API — Admin-Only Upload

```bash
# Start server
uvicorn api.app:app --reload --port 8000

# Create first admin
python create_admin.py --username admin --email admin@college.edu --password YourPassword

# Login → get token
TOKEN=$(curl -sX POST http://localhost:8000/auth/login \
  -d "username=admin&password=YourPassword" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Upload JSON → triggers background generation
JOB=$(curl -sX POST http://localhost:8000/upload/json \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_input.json" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# Poll status
curl http://localhost:8000/upload/status/$JOB -H "Authorization: Bearer $TOKEN"

# Download PDF when complete
curl http://localhost:8000/upload/download/$JOB \
  -H "Authorization: Bearer $TOKEN" -o syllabus.pdf
```

Swagger UI: `http://localhost:8000/docs`

---

## Authentication Flow

```
Register  →  bcrypt hash password  →  store in SQLite
Login     →  verify hash           →  issue JWT (8h expiry)
Upload    →  decode JWT            →  check role == "admin"  →  accept file
```

Non-admin users receive `403 Forbidden` on all upload endpoints.

---

## Get a Free Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Create API Key**
3. Copy and paste when the notebook prompts you

---

## Requirements

- Python 3.10+
- `google-genai`, `reportlab`, `fastapi`, `uvicorn`, `python-jose`, `bcrypt`, `rich`

See `requirements.txt` for pinned versions.

---

## License

MIT — free to use, modify, and distribute for academic and commercial purposes.

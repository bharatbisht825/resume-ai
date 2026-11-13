# Resume LaTeX Converter

Python FastAPI backend for converting plain-text resumes into LaTeX documents
and storing master and job-specific resumes in PostgreSQL.

## Setup

Requires Python 3.10+. On Debian or Ubuntu, install the matching venv package
first if needed:

```bash
sudo apt install python3-venv
```

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set `DATABASE_URL` in `.env` when using resume storage:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/resume_ai
```

Alternatively, configure `DATABASE_USER`, `DATABASE_PASSWORD`,
`DATABASE_HOST`, `DATABASE_PORT`, and `DATABASE_NAME`. The default database
name is `resume_ai`. [settings.py](/home/bharat-jammy/Documents/resume-ai/src/settings.py)
builds the async SQLAlchemy URL using the `asyncpg` driver. The SQLModel
entities and async engine/session setup are in
[models.py](/home/bharat-jammy/Documents/resume-ai/src/models.py) and
[database.py](/home/bharat-jammy/Documents/resume-ai/src/database.py).

The application creates the two planned tables and the one-master-per-category
unique index automatically when it starts with `DATABASE_URL` configured.

## Run

```bash
source .venv/bin/activate
uvicorn src.server:app --reload --port "${PORT:-3000}"
```

Check `http://localhost:3000/health`, then call:

```bash
curl -X POST http://localhost:3000/api/convert-to-latex \
  -H 'content-type: application/json' \
  -d '{"resume":"Jane Doe\njane@example.com\n\nEXPERIENCE\n- Built APIs with Python"}'
```

The converter accepts plain-text resumes and returns a complete LaTeX document.
It escapes LaTeX special characters and recognizes common section headings and
bullet-list lines.

## Resume storage API

Categories can be created and listed with `/api/categories`. Resumes can be
created, listed, and retrieved with `/api/resumes`. Omitting `category_id` and
`category_name` assigns a resume to the `Master` category.

Set `"is_master": true` when storing a category master. The existing master is
unmarked transactionally and retained as historical data. Job-specific resumes
should set `"is_master": false` and provide `company_name` and `job_title`.

```bash
curl -X POST http://localhost:3000/api/resumes \
  -H 'content-type: application/json' \
  -d '{
    "category_name": "Backend",
    "company_name": "Example Corp",
    "job_title": "Backend Engineer",
    "latex_source": "\\documentclass{article}\\begin{document}Resume\\end{document}"
  }'
```
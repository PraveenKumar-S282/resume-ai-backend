# ResumeAI Backend (Phases 4 and 5)

FastAPI + SQLAlchemy 2 + MySQL + Gemini. Provides every endpoint the React frontend calls, including
AI generation and PDF/DOCX export. Swagger UI: `http://localhost:8000/docs`.

## 1. Set up MySQL (local)

```sql
-- mysql -u root -p
CREATE DATABASE resume_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'resume_user'@'localhost' IDENTIFIED BY 'choose_a_password';
GRANT ALL PRIVILEGES ON resume_ai.* TO 'resume_user'@'localhost';
FLUSH PRIVILEGES;
```

Install MySQL 8: Windows (MySQL Installer), macOS (`brew install mysql && brew services start mysql`),
Ubuntu (`sudo apt install mysql-server`). If the password has special characters, URL-encode them in `DATABASE_URL`.

## 2. Install and configure

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env
```

In `.env` set at least `DATABASE_URL`, `SECRET_KEY` and `GEMINI_API_KEY`
(generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
`GEMINI_MODEL` is configurable because available model names change; check Google AI Studio for current ones.

## 3. Create the tables (migrations)

```bash
alembic upgrade head               # creates all tables
alembic current                    # should print: 0001 (head)
alembic downgrade base             # (optional) removes everything
# After changing a model:  alembic revision --autogenerate -m "describe change"  then  alembic upgrade head
```

The three resume templates are seeded automatically when the API starts.

## 4. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Frontend: in `frontend/` run `npm run dev`; Vite proxies `/api` to port 8000, so cookies work with no CORS setup.

## 5. Test

```bash
pytest                                             # 74 tests, SQLite in memory, fake AI provider, no API key needed
TEST_DATABASE_URL="mysql+pymysql://resume_user:pw@localhost/resume_ai_test?charset=utf8mb4" pytest   # same suite on MySQL
```

Create `resume_ai_test` first; the MySQL run drops and recreates its tables. The fake AI provider exists only in `tests/`.

## Architecture

```
app/
  main.py            app, CORS, origin (CSRF) check, error handlers, startup seed
  core/              config (env), security (bcrypt, JWT), errors, rate limiting
  db/                engine/session, Base, template seed
  models/            SQLAlchemy tables         schemas/   Pydantic request/response models
  api/deps.py        auth + ownership checks   api/v1/    routes (auth, profile, analyses, resumes, cover_letters, documents)
  services/          matcher, jd_analyzer, resume_service, cover_letter_service, scorer, suggestion_service, profile_service
  ai/                llm_client (Gemini), prompts, schemas (expected JSON), validator (anti-fabrication)
  documents/         docx_builder, pdf_builder, templates
  data/skill_synonyms.json   skill lexicon (aliases such as JS -> javascript)
```

### How generation stays honest
1. The profile is the only source. Prompts wrap profile and job text in tags and tell the model they are data, not instructions.
2. The model writes only a summary and bullets, keyed by real item ids. Employers, titles, dates, education, certifications and skill lists are copied from the database, never generated.
3. `ai/validator.py` flags any number or known skill in AI text that the candidate's own profile does not contain. One corrective retry is made; sentences that still fail are removed, and what was removed is stored in `scores.verification.removed`.
4. Items with no source text get no bullets. A letter with nothing supportable returns an error instead of invented content.
5. Missing required profile data returns `422 MISSING_PROFILE_DATA` with a list of what to add.

Scores (keyword, completeness, relevance) are deterministic estimates of keyword overlap, not ATS predictions.

## API summary (`/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register` `POST /auth/login` `POST /auth/logout` `GET/PATCH/DELETE /auth/me` `POST /auth/change-password` |
| Profile | `GET/PUT /profile` `GET /profile/completeness` and `GET/POST /profile/{section}`, `PATCH/DELETE /profile/{section}/{id}` for education, experience, skills, projects, certifications |
| Analysis | `POST/GET /analyses` `GET/DELETE /analyses/{id}` |
| Resumes | `POST /analyses/{id}/resumes` `GET /resumes` `GET/PATCH/DELETE /resumes/{id}` `POST /resumes/{id}/regenerate` `POST /resumes/{id}/improve` `GET /resumes/{id}/download?format=pdf|docx` |
| Cover letters | `POST /analyses/{id}/cover-letters` `GET /cover-letters` `GET/PATCH/DELETE /cover-letters/{id}` `POST .../regenerate` `GET .../download?format=pdf|docx` |
| Other | `GET /documents?type=&q=&page=&page_size=` `GET /templates` `GET /dashboard/stats` `GET /health` |

Errors: `{"error": {"code", "message", "details": [{"field", "issue"}]}}`. Statuses used: 200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 502.

## Security notes
- Passwords: bcrypt (72-byte limit enforced). Login errors are identical for unknown email and wrong password.
- Auth: JWT in an `HttpOnly` cookie (`Secure` when `COOKIE_SECURE=true`). A `Bearer` header also works, for scripts.
- CSRF: cookies are `SameSite=Lax`, and unsafe requests whose `Origin` is not same-origin or in `CORS_ORIGINS` get `403`.
- Every user-owned query is filtered by user id; another user's ids return `404`.
- Rate limits: login/register 10 per minute, generation 15 per minute (per IP, in memory).
- The Gemini key never leaves the backend.

## Deployment (Render for the API, Vercel for the frontend)
1. **Database:** use a hosted MySQL 8 instance (Render's managed database is PostgreSQL, so check current offerings or use another MySQL host). If the provider requires TLS, add its connection parameters to `DATABASE_URL`.
2. **Render web service** (root directory `backend`):
   - Build: `pip install -r requirements.txt`
   - Pre-deploy / release: `alembic upgrade head`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
   - Environment: `ENVIRONMENT=production`, `DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
     `COOKIE_SECURE=true`, `CORS_ORIGINS=https://your-app.vercel.app`
3. **Vercel** (frontend): set `VITE_API_BASE_URL=/api/v1` and replace `frontend/vercel.json` with a rewrite so the browser stays same-origin:
   ```json
   { "rewrites": [
       { "source": "/api/:path*", "destination": "https://YOUR-API.onrender.com/api/:path*" },
       { "source": "/(.*)", "destination": "/index.html" } ] }
   ```
4. Free Render instances sleep when idle, so the first request after a pause is slow.

## Verification checklist
- [ ] `alembic upgrade head` creates 11 tables plus `alembic_version`; `alembic check` reports no drift
- [ ] `GET /api/v1/health` returns `{"status":"ok"}`; `/docs` loads
- [ ] Register, log in, `GET /auth/me` works; cookie is HttpOnly; logout then `/auth/me` returns 401
- [ ] Profile sections create, edit, delete; duplicate skill returns 409
- [ ] Analysis with a real job description returns matched and missing skills (needs `GEMINI_API_KEY` for full extraction; otherwise a keyword fallback is used)
- [ ] Generating with an empty profile returns `MISSING_PROFILE_DATA`
- [ ] Resume generates, edits, saves, regenerates (version increases), downloads as PDF and DOCX
- [ ] Cover letter generates, edits, downloads
- [ ] Improve endpoint returns three scores, keywords and suggestions
- [ ] History filters, searches and paginates; deleting an analysis keeps its documents
- [ ] A second account cannot read or change the first account's data (404)

## Known limitations
- **Gemini calls are verified only with a stubbed SDK**, not against the live service (no API key or network access during development). The client code, request options and error handling are tested; prompt quality and the model name you choose need a live check.
- PDF export uses built-in fonts, so characters outside Western European text (for example Tamil) are replaced with `?`. DOCX keeps all characters.
- Rate limiting is per process and in memory; use a shared store (e.g. Redis) if you run several instances.
- No email verification or password reset yet.
- Scores and suggestions are rule-based and deterministic; they are estimates, not ATS predictions.
#   r e s u m e - a i - b a c k e n d  
 
# RAGGuard

Permission-aware RAG backend. RAGGuard sits between users and an LLM and **guarantees that a document a user isn't authorized to see never enters that LLM's context** — not "the LLM was told not to repeat it," but "the retriever never fetched it in the first place."

Authorization is evaluated by deterministic Python code against a JWT-derived identity — never by the LLM and never by a role the user claims in their message text.

> Core principle: **Unauthorized information must never enter the LLM context.**

Built from `plan(2).md` (the concrete build plan) — RBAC+ABAC policy engine, secure ingestion, defense-in-depth retrieval, heuristic prompt-injection / output-leak guards, and full audit logging.

---

## Quickstart (Fedora)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # then set a real JWT_SECRET_KEY
python scripts/seed_data.py            # departments, roles, 8 demo users
python scripts/ingest_documents.py     # embeds data/sample_docs into Chroma

python run.py    # starts on HOST/PORT from .env (default 127.0.0.1:8000)
# → http://localhost:<PORT>  (UI)   ·   /docs  (Swagger)
```

The server host/port live in `.env` (`HOST`, `PORT`) — change them there, no code edits needed. Or run `uvicorn app.main:app --reload --port 8010` to override on the command line.

Ollama must be running with the configured model (`qwen2:1.5b` by default):

```bash
ollama pull qwen2:1.5b
```

## Demo users

Every user's password is `Password123!`.

| Username      | Role               | Home dept | Can see (per YAML policy) |
|---------------|--------------------|-----------|---------------------------|
| `ceo01`       | ceo (admin)        | executive | everything (TOP_SECRET)   |
| `cfo01`       | cfo                | finance   | finance, hr, executive    |
| `cto01`       | cto                | it        | it, security, executive   |
| `hr01`        | hr_manager         | hr        | hr                        |
| `seceng01`    | security_engineer (admin) | security | security            |
| `iteng01`     | it_engineer        | it        | it                        |
| `accountant01`| accountant         | finance   | finance                   |
| `employee01`  | employee           | general   | general (PUBLIC)          |

Sample documents (`scripts/seed_data.py` → `data/sample_docs/`): revenue report (finance/CONFIDENTIAL), network architecture (it/INTERNAL), company overview (general/PUBLIC), employee salaries (hr/CONFIDENTIAL), security incident (security/RESTRICTED), acquisition strategy (executive/TOP_SECRET).

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /auth/login` | none | `{username, password}` → JWT |
| `GET /auth/me` | required | identity from token |
| `POST /chat` | required | RAG chat — `{message}` → `{answer, sources}` |
| `POST /documents` | admin | multipart upload: file + `department` + `classification` |
| `GET /documents` | required | list, filtered to the caller's allowed departments |
| `DELETE /documents/{id}` | admin | delete doc + its Chroma chunks |
| `GET /audit/logs` | admin | audit trail (filters: `user`, `decision`, `date_from`, `date_to`, paginated) |
| `GET /security/events` | admin | DENY + injection/output events |

## How the security guarantee holds

1. **Identity comes only from the JWT.** The chat request schema has no role/department field. Nothing in the request body or message text can override the verified identity.
2. **Policy-built Chroma filter.** `PolicyEngine.build_chroma_filter(role)` emits a `$or` of `$and(department, classification IN [...])` clauses so the vector DB itself only returns what the role may see.
3. **Defense-in-depth re-check.** Every chunk Chroma returns is re-validated against `PolicyEngine.can_access_document(...)` in plain Python. In correct operation this drops nothing — it exists so a filter bug, metadata typo, or future refactor can never silently leak a chunk. *This is what `test_retrieval_isolation.py` verifies by inspecting the chunk list itself, not just the final answer.*
4. **Prompt-injection heuristics** (`app/security/`) log suspicious queries/chunks but never gate access — the retriever is the guard, not the user's words. Output-guard redacts secret-like content from LLM responses before they return to the client.
5. **Audit logging** records every decision: logins, queries, uploads/deletes, denied chunks, and suspected injection/output events.

## Tests

```bash
pytest
```

35 tests including the full role × department × classification isolation matrix — a `FakeVectorStore` returns *everything* (simulating a broken filter) and asserts the re-check still lets nothing unauthorized through.

## Project layout

```
app/
  main.py            # app, router registration, static UI
  config.py          # pydantic-settings (.env)
  database.py        # SQLAlchemy engine/session
  models/            # User/Role/Department, Document, AuditLog
  schemas/           # Pydantic request/response models
  auth/              # bcrypt, JWT, get_current_user / require_admin
  policy/            # policies.yaml + PolicyEngine (RBAC+ABAC)
  ingestion/         # extract → chunk → embed
  retrieval/         # Chroma wrapper + SecureRetriever (re-check)
  security/          # query/context/output guards
  llm/               # Ollama streaming client
  audit/             # audit logger
  routers/           # auth, chat, documents, audit
  static/            # minimal UI (login, chat, admin)
scripts/             # seed_data.py, ingest_documents.py
tests/               # pytest suite (isolation matrix, auth, chat, injection)
```

## Roadmap (beyond MVP)

Per `plan(2).md` Section 13: per-document ACL overrides and richer ABAC attributes (Phase 2), ML-based injection/leak detection + behavioral alerting (Phase 3), PostgreSQL / multi-tenant / SSO / cloud (Phase 4).
# RAGuard

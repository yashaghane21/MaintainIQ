# Agent Usage Report

This report describes how an AI coding agent was used to build MaintainIQ. Everything listed under "verification" was actually run. Anything not run is listed as not run.

## Tools used

| Tool | Use |
|---|---|
| **Claude Code** (Anthropic, model Claude Opus 5.5) in the VS Code extension | Generated almost all of the code, configuration, tests and documentation from a single detailed specification prompt; ran commands; read results; fixed failures |
| Local shell (Git Bash / PowerShell on Windows 11) | Created the venv, ran pip/npm installs, ran tests, builds, servers and curl checks |
| Portable MongoDB 8.0.12 (`mongod`, downloaded by the agent to a temp folder) | Real database for manual end-to-end verification (no Atlas credentials were available) |
| Playwright with the locally installed Microsoft Edge (temp folder, not part of the repo) | Headless browser verification: page rendering, console errors, mobile layout, full UI workflow |
| Headless Edge `--print-to-pdf` | Generated a two-page test PDF to check PDF ingestion with page numbers |

## Representative prompts

The work came from one master specification (product overview, stack, folder layout, threshold rules, RAG pipeline, AI rules, HITL requirements, testing, deployment). The agent split it into a checklist and carried it out:

1. Backend core: config, DB manager (fails with 503 instead of pretending to persist), structured logging, error handlers
2. Deterministic threshold engine plus fictional threshold profiles
3. RAG: extraction, cleaning, page-aware chunking, embedders, ChromaDB
4. AI provider abstraction (Gemini plus labelled demo), strict output schema, guardrails
5. Triage orchestration, evidence model, work-order state machine with audit log
6. Seed data, fictional manuals, Pytest suite
7. React frontend (layout, 10 pages), Vitest suite, production build
8. Live end-to-end verification, then documentation

## Work delegated to AI

Effectively all implementation: backend services and API, frontend components and pages, test suites, seed data, the fictional sample manuals, deployment configs, README and this report. Design decisions were made by the agent within the specification. Examples: rules computed at issue creation, a priority floor from rule severity, evidence-ID stripping in code, no silent fallback from Gemini to demo, and a guarded `find_one_and_update` for approvals.

## Mistakes found and corrected during development

| Problem | How it was found | Fix |
|---|---|---|
| A test used a 1-character `reasoning` value, which the AI output schema (correctly) rejects | Pytest failure | Fixed the test data; schema unchanged |
| `find_one_and_update(..., ReturnDocument.AFTER)` returned `None` in mongomock when the update changed a field used in the filter (mongomock behaviour; real MongoDB returns the document) | 6 failing work-order tests | Guarded update now uses `ReturnDocument.BEFORE` (non-None = guard matched), then re-reads the document. Works on both. |
| Demo provider linked manual chunks to causes on a single shared word, which over-cited weakly related excerpts | Inspected the seeded analysis output | Requires ≥ 2 shared symptom keywords, ranked by overlap. The lockout citation now needs "lockout/tagout" rather than any "isolat…" word. |
| Retrieved excerpts started mid-sentence because the chunk overlap was cut at a word boundary | Reading live retrieval results | Overlap now starts at a sentence boundary; data re-seeded |
| Dashboard header first written with a hidden placeholder button, negative margins and a `<button>` nested inside `<a>` | Self-review right after writing it | Added a `ButtonLink` component; header uses the `actions` prop |
| A regex refactor (lazy-loading routes) also deleted the `DashboardLayout`, `ButtonLink` and `EmptyState` imports. The build still passed because undefined JSX identifiers only fail at runtime. | Reviewing the diff after the edit | Restored the imports; enabled `no-undef` / `no-unused-vars` as errors in `.oxlintrc.json` so lint catches this class of bug |
| On a 390 px viewport the issue analysis page overflowed horizontally by 33 px (section header badges did not wrap) | Playwright overflow check | Section headers now wrap |
| Chart legend text took the series colour (dataviz guideline: text uses neutral ink) | Visual review of the screenshot | Legend `formatter` renders neutral text |
| A failed analysis recorded `provider: "unknown"` when the provider could not be constructed (Gemini without a key) | Live failure-mode test | Records the configured provider name |
| README test counts were initially wrong (22/15 instead of 20/16) | Compared against `pytest -v` output | Corrected |

Rejected or avoided approaches:
- **Automatic fallback from Gemini to the demo provider on failure.** Rejected because it would hide a live-AI failure behind simulated output.
- **Treating missing sensor values as 0, or letting the LLM compute thresholds.** Rejected per the spec. Rules are pure Python.
- **Shipping torch/ChromaDB to small or serverless hosts.** Rejected: torch does not fit Render's free 512 MB, and even the ChromaDB-only dependency tree is about 400 MB installed, too large for a Vercel function. Those hosts get the flat `requirements.txt` (about 70 MB) instead, and the app reports the lexical fallback explicitly.

### Deployment target changed to Vercel serverless

The user started deploying the **backend** to Vercel. The first build failed: `could not parse requirements.txt` (Vercel's parser does not support the `-r` include). Measuring the installed dependency tree also showed that ChromaDB alone pulls in about 400 MB (kubernetes, onnxruntime, numpy), which a Vercel function cannot hold. The user chose to keep the backend on Vercel (Render was offered as the lower-effort alternative), so the agent:

- split dependencies into a flat `requirements.txt` (about 70 MB, measured), `requirements-ml.txt` (ChromaDB + Sentence Transformers) and `requirements-dev.txt`;
- added a dependency-free in-memory vector store that implements the subset of the Chroma API the service uses. It is selected automatically when ChromaDB is not installed and rebuilt from MongoDB text once per process;
- added serverless mode, detected from `VERCEL=1`: uploads are ingested within the request and no background startup thread runs;
- made embeddings `auto` with an embedder-specific minimum score. Hashing scores run lower, and a fixed 0.25 cut-off dropped relevant chunks; this was found while testing;
- replaced the legacy `builds` block in `backend/vercel.json` with `functions` + `rewrites`, and added `.vercelignore`.
- after the first successful Vercel build, every URL returned FastAPI's `{"detail":"Not Found"}`. The `x-request-id` header showed the requests reached the app, but with the rewritten path `/api/index`. Fix: the rewrite now forwards the original path (`/api/index?__path=/$1`), and `api/index.py` wraps the app in a small ASGI middleware that restores it. This is covered by `test_vercel_entry.py`.

## Code review approach

- Read the generated output after each major step (seeded analyses, retrieval scores, API responses), not just test results.
- Used the linter (oxlint with `no-undef`, `no-unused-vars`) and the production build as gates for the frontend.
- Checked guardrail behaviour live: unknown evidence IDs are stripped, priority floors apply, terminal states return 409, confirmation is required.
- Scanned the repository for secrets (`AIza…`, credentialed `mongodb+srv://`, `GEMINI_API_KEY=<value>`). None found. No `.env` files are committed, and the frontend contains no reference to the Gemini key.

## Tests actually executed

| Command | Result |
|---|---|
| `python -m pytest` (backend, Python 3.14.6) | **111 passed**: 20 threshold, 16 AI service, 15 retrieval, 22 issue API, 24 work orders, 10 knowledge API, 4 Vercel entry point. Retrieval-dependent tests run against both ChromaDB and the in-memory store. (Before the serverless change: 71 passed.) |
| `npm test` (Vitest 4) | **16 passed** across 3 files |
| `npm run build` (Vite 8) | Succeeded; route-level code splitting |
| `npx oxlint src` | 0 errors (only fast-refresh warnings for files that export helpers alongside components) |

## Manual verification actually performed

Against a real local MongoDB 8.0.12, real Sentence Transformers embeddings (`all-MiniLM-L6-v2`) and a persistent ChromaDB:

- `python -m app.seed --reset`: 5 equipment, 3 fictional manuals (16 chunks), 4 scenarios.
- **curl:** health; issue creation with °F conversion (221 °F → 105 °C critical), conflict detection, a no-rule sensor and a missing sensor; analysis (retrieval scores 0.52–0.66); PATCH edit with audit; approve without confirmation → 422; approve → 200 with approved-version snapshot; reject after approval → 409; edit after approval → 409; re-analysis after approval → 409; 404 body includes the request ID; dashboard KPIs updated.
- **PDF upload:** a 2-page PDF was ingested with page numbers preserved; a semantic search for "alignment tolerance after motor replacement" returned page 2 first; an `.html` upload was rejected with 400.
- **Failure modes on separate API instances:** `AI_PROVIDER=gemini` with no key → 502, issue status `analysis_failed`, `analysis` stays null, failed attempt recorded. Unreachable MongoDB → `/api/health` `degraded`, `POST /api/issues` → 503 "not saved".
- **Structured logs** inspected: request ID, endpoint, duration, issue/work-order IDs, retrieval status, AI provider/status and decisions are present.
- **Browser (Playwright + Edge, headless):** all 10 routes plus a 404 route rendered at 1440×900 and 390×844 with no console errors, no 5xx responses and (after the fix above) no horizontal overflow. The full UI flow ran successfully: form validation → submit → "Run triage analysis" → analysis rendered with the *Simulated* badge → review draft → edit and save (decision buttons disabled while there are unsaved edits) → approve via confirmation dialog → audit trail *Created → Edited → Approved*. Screenshots were reviewed visually.

### MongoDB Atlas

After the user created `backend/.env` with their Atlas connection string, the API connected to Atlas (`/api/health` → database `ok`). `python -m app.seed --reset` seeded the `maintainiq` database on Atlas, and the full Playwright UI workflow (report → analyse → edit → approve) passed against Atlas with no console errors.

### Serverless build (simulated locally)

A fresh virtualenv with **only** `requirements.txt` (no ChromaDB, torch or mongomock) ran `api/index.py` with `VERCEL=1` against Atlas:
- `/api/health` reported the in-memory store with 0 chunks on a cold start. The first search rebuilt 16 chunks from Atlas.
- A PDF upload returned `ingestion_status: completed` in the same response.
- The full Playwright workflow passed with no console errors. The analysis cited 4 manual excerpts using hashing retrieval.

## Not verified

- **No real Gemini API call was made** (no key available). The live provider is covered only by mocked-client unit tests.
- **No hosted deployment** to Vercel, Render or Atlas was performed. The configs were written but not exercised.
- **No deployment to Vercel's hosted infrastructure was verified.** Serverless mode was simulated locally with `VERCEL=1` and uvicorn, not Vercel's runtime.
- Vercel and Render run Python 3.12 by default; the code was only executed on Python 3.14.6.
- No load, security penetration or accessibility-audit tooling was run beyond semantic markup, labels and keyboard-accessible dialogs.

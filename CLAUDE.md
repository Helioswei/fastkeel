# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

fastkeel is currently in **design phase** — docs are finalized, no code yet. See `DESIGN.md` and `TAD.md` for the full spec.

## What fastkeel Is

A pip-installable Python backend scaffold (`pip install fastkeel`) for small-to-medium FastAPI + SQLite + JWT projects. Projects compose modules via import, not by forking a template.

```
user project (e.g., "戒了么手机-backend")
├── main.py                 # imports fastkeel, composes app from modules
├── project/                # business logic: models, routes, logic, prompts
└── config.toml             # TOML config, env overrides

        | pip install fastkeel
        v
fastkeel (this repo — the PyPI package)
├── core/        → app factory, config, SQLite, JWT, middleware (generically reusable, never edited by projects)
├── modules/     → user, social, payment, jobs (include_*() to opt in)
├── contrib/     → LLM client, SSE streaming (import on demand)
├── cli/         → `fastkeel new` to scaffold new projects
└── templates/   → Jinja2 templates for project generation
```

## Key Architecture Rules

- **`fastkeel/core/`** — never modified by projects. If a project needs to change core behavior, the abstraction boundary needs adjusting (sink to config or raise to project).
- **`fastkeel/modules/`** — configured via `Config`, never modified at source.
- **Project business logic** always goes in the generated project's `project/` directory.
- **Zero external services assumption** — defaults to SQLite WAL mode. PostgreSQL just needs `db_url` change.
- **Model extension** — no inheritance. Use `config.user_extra_fields` for dynamic columns on UserModel, or foreign keys to project-owned tables.
- **Payment verification** — channel-agnostic. Project registers verifier callbacks via `register_verifier()` (e.g., Huawei IAP, Google Play).

## Commands (planned, pending implementation)

```bash
# Build
python -m build

# Lint
ruff check .

# Test (all)
pytest

# Test (single file)
pytest tests/test_core/test_auth.py -v

# Install in dev mode
pip install -e ".[dev]"

# Publish to PyPI
twine upload dist/*
```

## CI/CD (planned)

- **test.yml** — `pytest` + `ruff check .` on push/PR, matrix across Python 3.11–3.13 on Ubuntu.
- **publish.yml** — on tagged release, `python -m build` + `twine upload dist/*` using `PYPI_TOKEN` secret.

## Implementation Roadmap (from DESIGN.md)

1. `fastkeel/core/` — app, config, db, auth, middleware
2. `user` module — device registration, login, JWT, device binding
3. `social` module — buddies, groups, invite codes
4. `payment` module — subscriptions, receipt verification, payment ledger
5. `jobs` module — APScheduler wrapper
6. `contrib/llm` — LLM client with retry + rate limiting + streaming
7. CLI `fastkeel new` + Jinja2 templates
8. CI/CD + README + PyPI release

## Version Strategy

| Version | Scope |
|---------|-------|
| 0.1.0 | core + user (MVP) |
| 0.2.0 | + social |
| 0.3.0 | + payment |
| 0.4.0 | + jobs + contrib.llm |
| 0.5.0 | + CLI + templates |
| 1.0.0 | Production release, validated against 戒了么手机 |

## Python Version

3.11+ (2026 target, modern typing syntax).

## Development Conventions

- **Async strategy**: Synchronous SQLAlchemy + `def` routes (not async). LLM client uses `httpx.Client` (sync).
- **Auth scheme**: `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` — device JWT, not password flow.
- **Error response format**: `{"error": "error_code", "detail": "human message", "code?": "optional"}`, auto-wrapped by global exception handler in middleware.
- **DB initialization**: First `include_*()` call triggers `init_db()` + `Base.metadata.create_all()`. Subsequent calls are no-ops.
- **CLI flags only for `modules/`**: `contrib/` packages have no flags — projects import them directly.

## Key Dependencies

- **FastAPI** — web framework
- **SQLAlchemy 2.0** — ORM (sync mode, stdlib `sqlite3` driver)
- **PyJWT** — JWT auth
- **APScheduler** — scheduled jobs
- **httpx** — LLM API client
- **Jinja2** — project templates (CLI)
- **Typer** — CLI framework
- **structlog** — structured logging
- **pytest** — testing
- **ruff** — linting
- **build** + **twine** — packaging/publishing
- `tomllib` — stdlib in Python 3.11+, no extra dependency needed

## Build config (hatchling)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
fastkeel = "fastkeel.cli:app"
```

## Resolved Decisions (from TAD.md §12)

All 7 TBDs resolved 2026-06-11. See TAD.md §12 for rationale.

| # | Decision | Choice |
|:-:|:---------|:-------|
| 1 | User extra fields | `ALTER TABLE ADD COLUMN` |
| 2 | Job function routing | Convention-based auto-resolve |
| 3 | Template language | Jinja2 |
| 4 | CLI framework | Typer |
| 5 | Async job persistence | SQLiteJobStore enabled by default |
| 6 | Logging | structlog |
| 7 | Dev payment verifier | Include built-in `dev` provider |

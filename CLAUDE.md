# Project Guidelines: nj-cli (Job Search Engine CLI)

## Architecture & Principles
1. Maintain strict layer separation: CLI Layer (Typer) -> Service Orchestration -> DB/Vector Storage (ChromaDB + SQLite) -> Provider Integrations.
2. Enforce strict typing and Pydantic v2 schemas for all inputs, outputs, and JSON model responses.
3. Keep all external network operations (API calls, DB queries) strictly asynchronous using `async/await`.

## Tech Stack
- **CLI Framework:** Typer
- **Package Manager:** Poetry (`pyproject.toml`, `poetry.lock`)
- **Storage:** ChromaDB (Local Embeddings) + SQLite via SQLAlchemy (Job metadata, application logs)
- **Providers:** Anthropic SDK (`AsyncAnthropic`), OpenAI / Groq SDK (`AsyncOpenAI`)
- **Model Topology:**
  - High Volume / Ranking: Haiku 4.5
  - Human-Facing Outputs (Tailoring / Letters): Sonnet 5
  - Gap Analysis / Reasoning: Opus 5
- **Quality Tools:** Ruff (`ruff = "==0.15.14"`), Pytest + Pytest-Asyncio

## Coding & Security Standards
- **Prompt Isolation:** Always wrap untrusted web data (scraped job descriptions) inside explicit `<job_description>` XML tags. Store system instructions and candidate CVs in the system prompt.
- **Resilience:** Protect external API calls with exponential backoff using `tenacity`.
- **Formatting:** Pass any raw text originating from LLM outputs through `escape_latex()` before rendering LaTeX `.tex` files.
- **Credentials:** Read environment variables via `pydantic-settings`. Never check secrets, session cookies (`li_at`), or raw keys into Git.

## Test & Workflow Constraints
- Execute `pytest` and `ruff check .` autonomously after modifying code in `nj/` or `tests/`.
- Mock all external LLM API calls in unit tests to ensure offline execution.
- Maintain regression test coverage for RAG chunking, visa matching logic, and anti-hallucination validation.

---

## Implementation Status

The sections above are the target. This section records where the code actually
stands, so a session reading this file does not assume a component exists.
Update it as items land; delete it once nothing is outstanding.

Last verified: 2026-08-16 (phase 1 + backlog complete).

| Guideline | Status | Notes |
|---|---|---|
| Typer CLI layer, thin commands | Met | One module per command in `nj/cli/`, no business logic. |
| Pydantic v2 schemas | Met | Models in `nj/models/`. Scoring responses are schema-constrained via `output_config.format` (`SCORE_SCHEMA` in `nj/prompts/scoring_v1.py`). |
| SQLite via SQLAlchemy | Met | `nj/db/`, repository pattern. Schema is created by `create_all`; Alembic is a dependency but no migrations exist. |
| **ChromaDB / vector storage** | **Not present** | No embedding store and no RAG pipeline exist. Semantic matching is TF-IDF + cosine in `nj/ml/semantic_model.py`. Any "RAG chunking" test coverage is therefore also outstanding. |
| `AsyncAnthropic` provider | Met | `nj/providers/claude.py`. |
| `AsyncOpenAI` provider | Met | `nj/providers/openai.py`, used for Groq. |
| Model topology (Haiku/Sonnet/Opus) | Met | `LLMConfig` tiers + `resolve_model()` in `nj/providers/registry.py`; commands pass `task=`. |
| Ruff pinned `==0.15.14` | Met | `ruff format` also replaces black. |
| Pytest + pytest-asyncio | Met | 555 passing, 3 skipped (opt-in prompt regression). No unit test touches the network. |
| Prompt isolation (`<job_description>`) | Met | All four JD-consuming prompts (`scoring_v1`, `tailoring_v1`, `cover_letter_v1`, `prep_v1`) fence via `nj/prompts/untrusted.py` and carry `UNTRUSTED_INPUT_NOTICE`. The fence defangs closing-tag escapes; covered by `tests/unit/test_untrusted.py`. |
| `escape_latex()` on LLM text | Met | All render paths in `nj/tailoring/renderer.py`, `prep_generator.py`, `diagnostics/renderer.py`. |
| **`tenacity` backoff** | **Deliberately not used** | The Anthropic and OpenAI SDKs already retry 408/409/429/5xx with exponential backoff (`max_retries=4` on the Claude client). Wrapping them in `tenacity` nests two retry loops and multiplies worst-case latency by the product of both. If a caller needs retries the SDK does not cover, add `tenacity` at that call site only — not around the provider. |
| `pydantic-settings` for credentials | Met | `nj/utils/secrets.py` exposes a `Settings` model; secrets are `SecretStr` so they mask in reprs and logs. `get()`/`check_all()` kept as wrappers for existing call sites. |
| Secrets never committed | Met | `.env`, `config.yaml`, `cv/*.json` gitignored; CI runs gitleaks over full history and asserts those paths stay untracked. |
| Mocked LLM calls in unit tests | Met | No unit test performs a live call. `tests/integration/test_prompt_regression.py` is opt-in via `NJ_RUN_REGRESSION_TESTS`. |
| Visa matching regression coverage | Met | `tests/unit/test_visa_filter.py` pins both historical failure directions. |
| Anti-hallucination regression coverage | Met | `tests/unit/test_anti_hallucination.py` — 19 cases over realistic CV shapes, asserting reorder/drop/reword pass and invented employer, title, institution, degree, project, certification, skill, and free-text claims fail. |

### Known-broken subsystems

Found by running the code against the 441 real jobs in `data/nj.db` on
2026-08-16. None of these are style issues; each produces confidently wrong
output.

- **H-1B intel: job-title signals are impossible with the ingested dataset.**
  `h1b_petitions.job_title` is the literal string `"H1B Employee"` for all
  154,112 rows — the parsed USCIS file is the *employer-level* datahub export,
  which carries no job titles. So `is_ml_role` is 0 on every row,
  `ml_ai_petitions` is 0 for all 87,595 companies, and anything keying off
  "ML roles filed" is dead code. Fixing it means ingesting the LCA/PERM
  disclosure data (which has job titles and wages) instead of, or alongside,
  the datahub export.
- **Sponsor tiers are miscalibrated.** 83,828 of 87,595 companies are `UNKNOWN`,
  41 are `MODERATE`, none are `STRONG`. Max `total_petitions` is 54 (Infosys),
  so thresholds written for thousand-petition employers never fire.
- **No employer entity resolution.** Amazon appears as at least three separate
  rows (`AMAZON.COM SERVICES LLC`, `AMAZON COM SERVICES LLC`,
  `AMAZON WEB SERVICES INC`), splitting its petition count. Company lookups
  from job postings match only 33 of 319 scraped employers.
- **Job sourcing needs US credentials.** Arbeitnow (German/EU) supplied 300 of
  441 jobs and is now disabled. Adzuna and JSearch supply the US roles and both
  return nothing until `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`/`JSEARCH_API_KEY` are set
  in `.env`.

### Working agreements
- Run `ruff check nj/ tests/`, `ruff format --check nj/ tests/`, and `pytest` after
  touching `nj/` or `tests/`. All three gate CI.
- Those three now run automatically via a `PostToolUse` hook
  (`.claude/settings.json` → `.claude/hooks/quality-gate.sh`). It is advisory, not
  blocking, since mid-refactor states legitimately fail; failures come back as a
  `systemMessage` so they get fixed in the same turn. Run the commands yourself if
  the hook is disabled.
- `nj-cli` is its own repository at `~/Github/nj-cli`.
- Priority order is set in the project plan: get applications out first, polish second.

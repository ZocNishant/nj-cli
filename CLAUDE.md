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

Last verified: 2026-08-17 (CV template restored; application status split).

| Guideline | Status | Notes |
|---|---|---|
| Typer CLI layer, thin commands | Met | One module per command in `nj/cli/`, no business logic. |
| Pydantic v2 schemas | Met | Models in `nj/models/`. Scoring and review responses are schema-constrained via `output_config.format` (`SCORE_SCHEMA` in `nj/prompts/scoring_v1.py`, `REVIEW_SCHEMA` in `nj/models/review.py`). |
| SQLite via SQLAlchemy | Met | `nj/db/`, repository pattern. |
| Alembic migrations | Met | `alembic/` with a baseline covering all 9 tables. URL comes from `NJ_DB_PATH`/`NJ_ALEMBIC_URL`, not the tracked ini. `render_as_batch` is on because SQLite cannot ALTER a column. `data/nj.db` was stamped at the baseline on 2026-08-17. `tests/unit/test_migrations.py` fails on ORM/migration drift. See `alembic/README`. |
| **ChromaDB / vector storage** | **Not present** | No embedding store and no RAG pipeline exist. Semantic matching is TF-IDF + cosine in `nj/ml/semantic_model.py`. Any "RAG chunking" test coverage is therefore also outstanding. |
| `AsyncAnthropic` provider | Met | `nj/providers/claude.py`. |
| `AsyncOpenAI` provider | Met | `nj/providers/openai.py`, used for Groq. |
| Model topology (Haiku/Sonnet/Opus) | Met | `LLMConfig` tiers + `resolve_model()` in `nj/providers/registry.py`; commands pass `task=`. Four tiers: `scoring` and `review` on Haiku, `tailoring` on Sonnet, `reasoning` on Opus. |
| Drafter-reviewer pipeline | Met | `nj/tailoring/drafter.py` (Sonnet) → `nj/tailoring/reviewer.py` (Haiku) → revision round, orchestrated in `tailor.py`. **The asymmetry is load-bearing:** `validate_tailored_cv` findings BLOCK, the reviewer model's findings only ADVISE. A reviewer that fails, times out, or returns nonsense degrades to the pre-existing validator guarantee and never below it. Do not promote reviewer findings to blocking — a cheap model's false positive would throw away a correct CV. |
| Ruff pinned `==0.15.14` | Met | `ruff format` also replaces black. Alembic's generated migration bodies are not format-clean; run `ruff format alembic/` after `revision --autogenerate`. |
| Pytest + pytest-asyncio | Met | 670 passing, 3 skipped (opt-in prompt regression). No unit test touches the network. |
| CV LaTeX template | Met | `templates/cv_template.tex` was a 0-byte file until 2026-08-17 and is now a working template covering all 14 placeholders in `_fill_template`. **Two traps.** (1) The substitution is a blind string replace over the whole file, *comments included* — a placeholder token written in a comment expands into live LaTeX. That is exactly how the first restored version failed. (2) The list macros are `\begingroup`, not `itemize`, because the `_render_*` helpers emit nothing for an empty section and an empty `itemize` is a hard LaTeX error; `\resumeItem` draws its own bullet for the same reason, since it is emitted both inside a list and bare. Verified against a fully empty CV. |
| `tectonic` | Required, installed | `render_cv` shells out to it (`renderer.py:115`). `brew install tectonic`. Not in `pyproject.toml` because it is not a Python package — a fresh clone renders nothing without it, and `cmd_run` swallows the failure as a `logger.warning`, so a missing binary looks like a successful run with no PDF. CI installs the pinned musl release from GitHub, not apt: tectonic is not in Ubuntu `noble` proper, only `noble-updates`/`backports`. |
| Shipped-template CI guard | Met | `tests/unit/test_renderer.py`, the `--- the shipped template ---` block: 8 tests reading `templates/cv_template.tex` itself rather than the synthetic `make_template()`. They pin the 0-byte case, placeholder coverage derived from `inspect.getsource(_fill_template)` (so a new placeholder that the template lacks fails here), a real tectonic compile, a compile with every optional section empty, and the comment-expansion trap. **"No unsubstituted placeholders" is trivially true of an empty file**, so `test_shipped_template_actually_carries_the_cv_content` is what makes that assertion mean anything — do not drop it. `NJ_REQUIRE_TECTONIC=1` in CI turns a missing compiler from a skip into a failure. All verified by mutation: each bug was reintroduced and the corresponding test observed failing. |
| Application status honesty | Met | nj cannot submit, so the pipeline writes `ApplicationStatus.GENERATED` ("CV and letter on disk, nothing sent"), never `SUBMITTED`. Only a human promotes a row, via `nj status --update-id <id> --update-status submitted`. `ACTIVE_APPLICATION_STATUSES` in `nj/models/application.py` is the single definition of "counts as an application" — the daily cap, the status dashboard, and the shell/banner counters all read it. `test_pipeline_never_writes_submitted` pins the invariant at the source level. `cmd_run` must also stamp `record.applied_at` before saving: `count_today()` filters on it, and until 2026-08-17 nothing set it, so the query matched nothing and `apply.max_per_day` never throttled a run. |
| Prompt isolation (`<job_description>`) | Met | All four JD-consuming prompts (`scoring_v1`, `tailoring_v1`, `cover_letter_v1`, `prep_v1`) fence via `nj/prompts/untrusted.py` and carry `UNTRUSTED_INPUT_NOTICE`. The fence defangs closing-tag escapes; covered by `tests/unit/test_untrusted.py`. The reviewer fences the draft it audits as `<tailored_draft>`. |
| Candidate CV in the system prompt | Met | `tailoring_v1.build_system_prompt()` and `cover_letter_v1.build_system_prompt()` carry the CV; the user turn carries only the task and the fenced posting. A posting cannot share a turn with the record it would amend. `SYSTEM_PROMPT` remains the bare-instructions fallback. `scoring_v1` still embeds candidate context in the user turn — outstanding. |
| `escape_latex()` on LLM text | Met | All render paths in `nj/tailoring/renderer.py`, `prep_generator.py`, `diagnostics/renderer.py`. `soft_skills` and unknown skill-category keys were reaching the `.tex` unescaped and now do not. URLs go through `_safe_url()` (allow-list) rather than `escape_latex`, which would break `\href`. |
| PDF page budget | Met | `verify_page_budget()` in `renderer.py` reads the compiled PDF with `pypdf` and raises `PageBudgetError` past 2 pages, keeping the file on disk to inspect. An unreadable PDF returns `None` and does not raise — a pypdf failure must not discard a valid render. |
| **`tenacity` backoff** | **Deliberately not used** | The Anthropic and OpenAI SDKs already retry 408/409/429/5xx with exponential backoff (`max_retries=4` on the Claude client). Wrapping them in `tenacity` nests two retry loops and multiplies worst-case latency by the product of both. If a caller needs retries the SDK does not cover, add `tenacity` at that call site only — not around the provider. |
| `pydantic-settings` for credentials | Met | `nj/utils/secrets.py` exposes a `Settings` model; secrets are `SecretStr` so they mask in reprs and logs. `get()`/`check_all()` kept as wrappers for existing call sites. |
| Secrets never committed | Met | `.env`, `config.yaml`, `cv/*.json` gitignored; CI runs gitleaks over full history and asserts those paths stay untracked. |
| Mocked LLM calls in unit tests | Met | No unit test performs a live call. `tests/integration/test_prompt_regression.py` is opt-in via `NJ_RUN_REGRESSION_TESTS`. |
| Visa matching regression coverage | Met | `tests/unit/test_visa_filter.py` pins both historical failure directions. |
| Stored visa labels | Met, but **re-run after any classifier change** | `jobs.visa_label` is written once at scrape time and `should_skip`/`nj search` read the stored value, so fixing `visa_filter.py` does not touch a single row. On 2026-08-17 the DB still held labels from the old substring matcher: 224 jobs read CONFIRMED when only 7 contained the word "sponsor", and two — Anduril (security clearance) and itD Tech ("unable to offer sponsorship") — were outright refusals stored as confirmed. `nj reclassify` re-derives every label, is read-only until `--apply`, and is idempotent. 247 of 470 labels changed. Run it after touching the classifier. |
| **Completeness (the other direction)** | Met, added 2026-08-17 | `validate_completeness` in `nj/tailoring/completeness.py`, BLOCKING alongside `validate_tailored_cv`. The two are mirrors: one rejects what a draft *added*, the other what it *lost*. Until this existed only addition was guarded — `anti_hallucination`'s docstring explicitly permits dropping — so a draft could omit every project and pass every gate. It did: a `[:3000]` slice in `tailoring_v1.build_system_prompt` showed the drafter 28% of an 10,874-char CV, it returned the 6 of 13 sections it could see, and the rendered PDF had empty Projects/Certifications headings and one job. Validator passed, reviewer approved, page budget passed, every log line said success. **Rule: sections and entries must survive, bullets need not** — trimming to two bullets is the tailoring the prompt asks for. Blocking is safe because the fallback (`cv_suppressed`) is complete by construction. 11 tests in `tests/unit/test_completeness.py`. |
| **Never truncate the base CV** | Met | `render_cv_for_prompt` in `nj/prompts/cv_context.py` is now the only way a CV enters a prompt. It returns every byte and logs if the CV is implausibly large; it never trims. Four prompts had been slicing it — tailoring at 3000, review and prep at 4000, diagnosis at 5000. The review one was the subtlest: the reviewer audited drafts against a CV cut at 4000 chars, so sections it could not see were indistinguishable from sections that never existed. |
| Anti-hallucination regression coverage | Met | `tests/unit/test_anti_hallucination.py` — 19 cases over realistic CV shapes, asserting reorder/drop/reword pass and invented employer, title, institution, degree, project, certification, skill, and free-text claims fail. `tests/unit/test_drafter_reviewer.py` covers the pipeline around it, including a dead reviewer and a revision that regresses. |
| **LinkedIn automation** | **Deliberately disabled** | `nj/scrapers/linkedin.py` was a cookie-authenticated Playwright scraper of the operator's own account; `nj/applying/linkedin_easy.py` was a placeholder for Easy Apply. Both are now inert stubs. Cookie-driven automation risks a checkpoint or a permanent ban on the account the operator job-hunts from, and an auto-submitted application cannot be retracted. `LinkedInScraper.scrape()` returns `[]` and keeps the `BaseScraper` contract; the constructor accepts `session_cookie` and drops it rather than storing it. `NJ_ENABLE_LINKEDIN_SCRAPER` is an opt-in gate for a *future* implementation and does not resurrect anything on its own. Do not reinstate this without asking. |

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
- **The project runs on OpenAI as of 2026-08-17**, not Claude.
  `ANTHROPIC_API_KEY` is still empty; `OPENAI_API_KEY` is set and verified.
  `config.yaml` is `provider: openai` with `gpt-5.5` for tailoring and
  reasoning and `gpt-5.4-mini` for scoring and review. Every one of those IDs
  was verified with a real completion through nj's own provider, not a
  `models.list` lookup. `gpt-5.5-pro` is **not** a chat model and 404s on
  `v1/chat/completions` — do not set it as a tier.
  **The "scoring is broken because `json_schema` is ignored" diagnosis below was
  wrong**, and is corrected here because it cost weeks. Scoring returned 0/100
  because `gpt-5.5` is a reasoning model: it spends 600-1200 tokens thinking
  before emitting a character, and that spend counts against
  `max_completion_tokens`. Measured 2026-08-17 — budget 600 → 0 chars,
  `finish_reason="length"`, 600 reasoning tokens; budget 1200 → 0 chars; budget
  2500 → works. Scoring asked for 1200 and cover letters for 600, so both
  returned the empty string, and the JSON parser had nothing to salvage. It is a
  200 OK, not an error, which is why nothing surfaced it.
  `OpenAICompatibleProvider` now learns a reasoning allowance from the first
  empty-and-truncated response and retries; see `_learn_headroom`. Four tests in
  `tests/unit/test_providers.py` pin it, verified by mutation.
  Still genuinely outstanding on this path: `complete()` ignores `json_schema`,
  `response_format` and `cache_system`, so `SCORE_SCHEMA`/`REVIEW_SCHEMA` are
  not *enforced* — but scoring parses fine without them now.
  `GROQ_API_KEY` also works as a fallback (`provider: freellmapi`,
  `freellmapi_base_url: https://api.groq.com/openai/v1`,
  `freellmapi_model: openai/gpt-oss-120b`), but `registry.py` reads the single
  `freellmapi_model` field for every task, so that path still collapses all
  four tiers onto one model. Avoid `qwen/qwen3.6-27b` — it emits raw `<think>`
  blocks into `content`.

### Working agreements
- Run `ruff check nj/ tests/`, `ruff format --check nj/ tests/`, and `pytest` after
  touching `nj/` or `tests/`. All three gate CI.
- `main` is branch-protected as of 2026-08-17. `test (3.11)`, `test (3.12)`,
  `test (3.13)` and `secrets` are required and `strict` is on, so a PR cannot
  merge on a stale branch. Direct pushes to `main` are still allowed
  (`enforce_admins: false`, no required reviews); force pushes and deletions are
  not. Renaming a CI job renames its check context and silently drops it from the
  required set — update the protection config in the same change.
- Those three now run automatically via a `PostToolUse` hook
  (`.claude/settings.json` → `.claude/hooks/quality-gate.sh`). It is advisory, not
  blocking, since mid-refactor states legitimately fail; failures come back as a
  `systemMessage` so they get fixed in the same turn. Run the commands yourself if
  the hook is disabled.
- `nj-cli` is its own repository at `~/Github/nj-cli`.
- Priority order is set in the project plan: get applications out first, polish second.
- Slash commands live in `.claude/commands/` and are tracked (the `.gitignore`
  carve-out sits next to the one for hooks): `/audit` runs every CI gate plus the
  secret checks, `/apply` runs the drafter-reviewer pipeline on one job, `/eval`
  runs the scoring and anti-hallucination regressions.
- After `alembic revision --autogenerate`, run `ruff format alembic/` and read
  the generated file — autogenerate renders a rename as a drop plus an add,
  which silently loses that column's data.

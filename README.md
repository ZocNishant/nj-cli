```
   ███╗   ██╗     ██╗
   ████╗  ██║     ██║     career intelligence
   ██╔██╗ ██║     ██║     anti-hallucination by design
   ██║╚██╗██║██   ██║
   ██║ ╚████║╚█████╔╝
   ╚═╝  ╚═══╝ ╚════╝
```

# nj — AI Career Operating System

**An open-source AI career intelligence platform for ML/AI/CV engineers.**

Not a job application bot. Not a resume spinner. A career reasoning system.

[![CI](https://github.com/ZocNishant/nj-cli/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ZocNishant/nj-cli/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-670%20passing-brightgreen)](https://github.com/ZocNishant/nj-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://python.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Why nj is different

**nj never invents your experience — and never quietly loses it.**

Every tailored CV is checked against your original, in both directions, before
it leaves your machine.

`nj/tailoring/anti_hallucination.py` catches **addition**. It compares
employers, job titles, institutions, degrees, projects, certifications and
skills as normalized sets, then scans the free text for invented years,
percentages, employers and credential words. Reordering, dropping and rewording
are allowed. Adding a claim your source CV does not contain is not.

`nj/tailoring/completeness.py` catches **omission**, which is the failure the
first validator is explicitly blind to. A model that drops your entire projects
section has invented nothing, so a set-membership check passes it happily. This
one requires every section and every entry to survive; bullets may still be
trimmed, because that is the tailoring you asked for.

Both are deterministic code, not prompt instructions, and both **block**. A
draft that fails either is rejected and redrafted; if every round fails, nj
ships your suppressed base CV, which contains no model-written prose and
therefore cannot contain a hallucination.

---

## Built for the OPT job search

Sponsorship is a hard filter, not a preference, so nj treats it as a
correctness problem rather than a keyword search.

The classifier is negation-aware and evaluates blocking language before
sponsoring language, because the naive version of this gets it wrong in both
directions at once:

| Posting says | Naive keyword match | nj |
| --- | --- | --- |
| "Must be authorized to work in the US" | BLOCKED — drops the job | UNKNOWN — OPT *is* authorization |
| "We do not sponsor employment visas" | CONFIRMED — matches "sponsor" | BLOCKED |
| "We sponsor H-1B. Must be authorized at hire." | BLOCKED | CONFIRMED |
| "Strong optimization background required" | CONFIRMED — matches "OPT" inside *optimization* | UNKNOWN |

That last row is not hypothetical. Re-running the old substring matcher over
441 real scraped jobs, 223 of the 224 marked "sponsorship confirmed" were
marked that way because the description contained the word *optimization*.

`nj search` shows the phrase that decided each label, so a misclassification is
visible before it costs you an application.

Labels are written once at scrape time, so fixing the classifier does not touch
a single stored row. `nj reclassify` re-derives every label; it is read-only
until you pass `--apply`, and it is idempotent.

---

## What it does

```
nj(openai) > diagnose    # why am I not getting interviews
nj(openai) > gaps        # what should I learn — ranked by ROI
nj(openai) > search      # find and score 100+ ML jobs
nj(openai) > explain     # why did this job score 78?
nj(openai) > prep        # I have an interview tonight
nj(openai) > exit
```

Launch `nj` and you're in a full interactive shell — msfconsole style. Every
command is available from the prompt, with tab completion and history.

---

## Features

### Career Intelligence

| Command | What it does |
| --- | --- |
| `nj diagnose` | Full CV health report — root causes of interview failure, recruiter first impression, ATS concerns, positioning mismatch |
| `nj gaps` | Skill gap analysis across all scored jobs — ranked by frequency and estimated score impact |
| `nj explain` | Exact breakdown of why a job scored the way it did — 6 sub-scores with rationale and evidence |
| `nj frame` | Reframe your best project for a specific audience: production ML, research lab, healthtech startup, big tech |
| `nj diff` | Show exactly what changed between your base CV and the tailored version — bullet by bullet |
| `nj postmortem` | Application failure patterns across everything you've sent |

### Job Discovery (6 sources)

| Source | Auth | Notes |
| --- | --- | --- |
| RemoteOK | None | Works out of the box |
| WeWorkRemotely | None — RSS | Remote ML roles |
| Arbeitnow | None — free API | Mostly German/EU. Turn off for a US-only search |
| Adzuna | Free API key | Aggregates 15+ US sources. Highest-value key to set |
| JSearch | RapidAPI key (free tier) | 30+ boards: LinkedIn, Indeed, Glassdoor, ZipRecruiter |
| USAJobs | Free API key (opt-in) | Government + research ML roles |

Adzuna and JSearch return nothing until their keys are set. Without them a run
is served mostly by Arbeitnow, which is the wrong continent for an H-1B search.
`.env.example` has step-by-step signup links for both; each has a free tier and
neither needs a card.

**LinkedIn scraping is deliberately disabled.** `nj/scrapers/linkedin.py` is an
inert stub that returns `[]` and keeps the `BaseScraper` contract. Cookie-driven
automation risks a checkpoint or a permanent ban on the account you job-hunt
from, and no code path reads a session cookie any more — nj will not ask you for
one.

### AI Scoring

- **6 explainable sub-scores** — skills, experience, role alignment, sponsorship, location, resume strength
- **Weighted scoring** — configurable per your priorities
- **Confidence score** — how certain the model is about the comparison
- **Schema-constrained output on Claude** — scores decode against a JSON Schema rather than being parsed out of prose. The OpenAI-compatible provider does not yet enforce the schema and falls back to salvaging JSON
- **Outcome calibration** — `nj calibrate --from-outcomes` sets your threshold from real interview results

### CV Tailoring

- **Drafter–reviewer pipeline** — a strong model drafts, a cheap model audits it adversarially against your base CV, and the draft is revised
- **The asymmetry is deliberate.** Deterministic validator findings *block*; the reviewer model's findings only *advise*. A cheap model's false positive must never be able to throw away a correct CV, and a reviewer that fails, times out, or returns nonsense degrades to the validator guarantee — never below it
- Keyword alignment from the job description
- Section reordering by relevance; anchor project always leads
- Irrelevant skill groups suppressed per role type
- LaTeX → PDF via tectonic, preserving your template
- **Page budget** — the compiled PDF is read back with `pypdf` and rejected past 2 pages, keeping the file on disk to inspect
- Cover letter generation (3 paragraphs, 250 words max), reviewed on the same pipeline

### Application Pipeline

- Human review queue before anything is sent (the only implemented mode)
- Quality gate blocks weak applications
- Daily rate limit, counted from the database so it survives restarts (default 5/day)
- Email notification with the tailored CV attached
- Application tracker with trajectory view
- Gmail callback detection (interview / rejection / offer signals)

### Interview Preparation

- `nj prep` generates a PDF: company brief, 8–10 technical questions with confidence ratings, STAR behavioural questions, story bank, quick reference card
- `nj watch` monitors Gmail for callbacks and tells you which `nj prep --job-id` to run

---

## Quick start

### Requirements

- Python 3.11+
- [tectonic](https://tectonic-typesetting.github.io) — LaTeX compiler. Not a
  Python package, so `poetry install` will not fetch it; without it nothing
  renders
- An API key for one provider — [OpenAI](https://platform.openai.com/api-keys),
  [Anthropic](https://console.anthropic.com), or [Groq](https://console.groq.com/keys)

```bash
# macOS
brew install tectonic

git clone https://github.com/ZocNishant/nj-cli
cd nj-cli
poetry install

# Secrets go in .env, never in config.yaml
cp .env.example .env          # add the key for your provider
cp config.example.yaml config.yaml

poetry run nj
```

### First run

```
nj(openai) > init        # setup wizard — CV, email, schedule
nj(openai) > search      # find and score jobs
nj(openai) > diagnose    # get your CV diagnosis
nj(openai) > gaps        # see what to learn
nj(openai) > review      # approve jobs before applying
nj(openai) > calibrate   # tune your score threshold
```

### Zero-cost demo (no API key needed)

```bash
poetry run nj
nj(openai) > demo
```

---

## Operating nj

This is the loop the tool is actually built around. Each stage is a separate
command on purpose: nothing generates a document you did not ask for, and
nothing claims an application you did not send.

```
  nj search  ──► scrape + score + queue      (writes: jobs, scores → data/nj.db)
      │
  nj review  ──► approve / skip, one by one  (writes: job status only)
      │
  nj tailor  ──► draft → audit → render      (writes: PDF + cover → output/)
      │
   you submit the application yourself
      │
  nj status --update-id <id> --update-status submitted
```

**1. `nj search` — find and score.** Runs every scraper whose key is set,
de-duplicates against the database, classifies sponsorship at scrape time,
scores the survivors, and leaves anything above the threshold in
`PENDING_REVIEW`. Nothing is written to `output/`.

```bash
nj search --limit 50            # score at most 50 (0 = all)
nj search --level senior        # junior | mid | senior | staff
nj search --visa sponsor        # only CONFIRMED/LIKELY sponsors
nj search --dry-run             # scrape and store, skip the scoring spend
```

**2. `nj review` — decide.** Walks the pending queue one job at a time with the
score breakdown on screen: `a` approve, `s` skip, `l` label, `v` open in
browser, `q` quit. Approving moves the job to the apply queue. It does **not**
generate anything — no model is called, no PDF is written.

**3. `nj tailor` — generate.** This is the step that costs money and produces
files.

```bash
nj tailor --job-id 716789b6     # a unique id prefix is enough
```

Prefer the stored id to a URL. Fetching a URL re-derives the posting from the
live page and cannot recover the title or company, so the tailoring runs against
whatever text the page happens to yield.

It drafts on the tailoring tier, audits the draft on the review tier, runs both
blocking validators, renders LaTeX → PDF, verifies the page budget, writes the
cover letter that was actually reviewed, and emails the bundle if
`notify.email_to` is set. `nj tailor` writes **no** application row — it does
not count against the daily cap and does not appear in `nj status`. It is the
manual, one-job path.

**4. You submit, then record it.** nj has no submit path, so the database never
claims one:

```bash
nj status                                              # what is where
nj status --update-id <id> --update-status submitted   # only a human does this
```

### `nj run` — the batched version

`nj run` is the same pipeline unattended: scrape → score → visa/threshold
filter → queue. **On the default `automation_phase: 1` it stops at the queue**
and tailors nothing, which is what makes it safe to schedule.

Raising `automation_phase` above 1 does change behaviour — the run continues
into tailoring, rendering, the quality gate, the daily rate limit, the
application record and the notification email. It still never submits:
`nj/applying/linkedin_easy.py` raises by design, so a caller cannot record a
phantom submission.

Applications logged by `nj run` are stored as `GENERATED` — "CV and letter on
disk, nothing sent" — never `SUBMITTED`. `ACTIVE_APPLICATION_STATUSES` in
`nj/models/application.py` is the single definition of "counts as an
application", read by the daily cap, the status dashboard and the shell
counters alike.

```bash
nj run --dry-run     # scrape and score, but render nothing and log no application
nj run --silent      # for cron/launchd
```

### Scheduling

`nj init` can install a recurring `nj run`. On macOS it writes a launchd agent
labelled `com.nj-cli.run` under `~/Library/LaunchAgents`; elsewhere it writes a
crontab line marked `# nj-cli`. Both are managed by `nj/scheduler/manager.py` —
setting a schedule of `0` days removes it.

### Maintenance

```bash
nj reclassify                # dry run: what the current classifier would change
nj reclassify --apply        # write the new labels (idempotent)
nj calibrate --from-outcomes # move the threshold to match real results
nj quality --job-id <id>     # run the quality gate against one job
nj enrich <url>              # instant intelligence report for any job URL
nj intel                     # query the ingested H-1B petition data
nj logs                      # tail the structured log
```

Run `nj reclassify --apply` after **any** change to the sponsorship classifier.
Labels are stored at scrape time, so a fixed classifier does not retroactively
touch a single row. When this was first run over the real database, 247 of 470
labels changed.

### What nj writes

| Path | Contents |
| --- | --- |
| `data/nj.db` | Jobs, scores, applications, outcomes, labels, graph, H-1B intel (9 tables). Gitignored |
| `output/` | `nj_<Company>_<Title>_<date>.pdf`, `_cover.txt`, `.json` — one bundle per tailored job |
| `cv/cv_base.json` | Your base CV, written by `nj init`. Gitignored, and CI asserts it stays untracked |
| `logs/nj.log` | Structured logs |
| `data/models/`, `data/intel/` | Trained local models and ingested petition data |
| `config.yaml`, `.env` | Preferences and secrets. Both gitignored |

---

## All commands

```
Intelligence:    diagnose  gaps  explain  diff  frame  postmortem
Job hunting:     search  run  review  tailor  quality  enrich  reclassify
Applications:    status  calibrate  label  watch  prep
CV management:   update-cv  update-role  update-intern
Data & models:   intel  graph  ml
System:          init  config  logs  demo  manual  help  exit
```

`nj manual` prints the full reference with every flag and example; the same
text lives in [docs/MANUAL.md](docs/MANUAL.md).

---

## Configuration

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is gitignored. Secrets belong in `.env` — the config file holds
preferences only.

```yaml
llm:
  provider: openai             # openai | claude | freellmapi
  # Tiered by what the output is for. `model` is the fallback for any unset tier.
  model: gpt-5.5
  scoring_model: gpt-5.4-mini  # ranks 50-200 jobs a run
  tailoring_model: gpt-5.5     # what a recruiter reads
  review_model: gpt-5.4-mini   # audits the drafter; keep it a different model
  reasoning_model: gpt-5.5     # diagnose / gaps / prep / frame

scoring:
  threshold: 62

visa:
  enabled: true
  status: "OPT"                # OPT | CPT | H1B | GC | citizen
  h1b_future: true
  skip_no_sponsorship: true    # drop BLOCKED jobs before scoring

apply:
  enabled: false
  max_per_day: 5
  automation_phase: 1
```

On Claude the equivalent tiers are `claude-haiku-4-5` for scoring and review,
`claude-sonnet-5` for tailoring, and `claude-opus-5` for reasoning. A full
search-and-apply cycle costs roughly $1 in API credit on those tiers: about
$0.63 to score 100 jobs on Haiku, about $0.29 to tailor five CVs and cover
letters on Sonnet.

> **Reasoning models need token headroom.** They spend tokens thinking before
> emitting a character, and that spend counts against `max_completion_tokens`.
> A budget sized for the visible answer alone comes back as a `200 OK` with an
> empty string. The OpenAI-compatible provider learns the allowance from the
> first starved response and retries, so this is handled — but it is worth
> knowing if you add a call site.

### Environment variables

Secrets and machine-local paths only. Everything else belongs in `config.yaml`.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | One per provider; set the one you configured |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna — the highest-value key for a US search |
| `JSEARCH_API_KEY` | JSearch via RapidAPI |
| `USAJOBS_API_KEY`, `USAJOBS_USER_AGENT` | USAJobs (opt-in) |
| `GMAIL_CREDENTIALS_JSON`, `SENDGRID_API_KEY` | Callback watching and outbound email |
| `NJ_DB_PATH` | Database path for Alembic; defaults to `data/nj.db` |
| `NJ_ALEMBIC_URL` | Full SQLAlchemy URL, wins over `NJ_DB_PATH`. For scratch databases |
| `NJ_REQUIRE_TECTONIC` | `1` turns "tectonic missing" from a skipped test into a failing one. CI sets it |
| `NJ_RUN_REGRESSION_TESTS` | Opt in to the live prompt-regression suite |
| `NJ_ENABLE_LINKEDIN_SCRAPER` | Gate for a *future* implementation. Does not resurrect the removed scraper |

---

## LLM Providers

| Provider | Status | Notes |
| --- | --- | --- |
| OpenAI | Implemented | Set `OPENAI_API_KEY` and `provider: openai`. Tiered per task |
| Claude (Anthropic) | Implemented | Tiered per task; prompt caching on the CV prefix; enforces JSON Schema |
| Groq / OpenAI-compatible | Implemented | Any OpenAI-shaped endpoint via `provider: freellmapi` and a base URL. Reads a single `freellmapi_model` for every task, so all four tiers collapse onto one model |

Switching providers is a config change. See
[docs/adding-a-provider.md](docs/adding-a-provider.md) to add another.

---

## Database and migrations

SQLite through SQLAlchemy, behind a repository layer, with Alembic migrations
whose baseline covers all 9 tables.

```bash
poetry run alembic upgrade head        # apply migrations
poetry run alembic current             # what this database is at
poetry run alembic revision --autogenerate -m "add x"
poetry run ruff format alembic/        # generated bodies are not format-clean
```

- The URL comes from `NJ_DB_PATH` / `NJ_ALEMBIC_URL`, not the tracked ini, so no
  operator's database path is committed.
- `render_as_batch` is on because SQLite cannot `ALTER` a column.
- `tests/unit/test_migrations.py` fails the build on ORM/migration drift.
- **Read every autogenerated migration.** Autogenerate renders a column rename
  as a drop plus an add, which silently discards that column's data.

---

## Architecture

```
nj/
  cli/          one file per command, no business logic
  models/       Pydantic models
  scrapers/     6 sources behind a BaseScraper ABC (LinkedIn is an inert stub)
  scoring/      scorer, visa filter, calibration, ghost filter, quality gate
  tailoring/    tailor (orchestration), drafter, reviewer,
                anti_hallucination, completeness,
                keyword_align, section_ranker, suppressor,
                renderer (LaTeX→PDF + page budget),
                cover_letter, prep_generator
  providers/    BaseLLMProvider, Claude (AsyncAnthropic), OpenAI-compatible
  prompts/      versioned prompt modules, untrusted-input fencing, cv_context
  db/           SQLAlchemy + repository pattern
  diagnostics/  CV diagnosis engine + PDF renderer
  analytics/    skill_gaps, outcomes, outcomes_analysis
  intel/        H-1B petition ingest and job enrichment
  graph/        career knowledge graph
  ml/           sponsorship, salary and semantic models
  scheduler/    launchd (macOS) and cron installers for unattended runs
  notify/       email notifications
  applying/     stubs only — nj does not submit
  integrations/ gmail_watcher
alembic/        migrations; baseline covers all 9 tables
```

Key decisions:

- **Repository pattern** — SQL stays behind repos so the storage engine can change
- **Alembic migrations** — the URL comes from `NJ_DB_PATH` / `NJ_ALEMBIC_URL`, not the tracked ini. `render_as_batch` is on because SQLite cannot `ALTER` a column. A test fails the build on ORM/migration drift
- **Provider abstraction** — switch LLM with one config line
- **Versioned prompts** — every score records the prompt version that produced it
- **Validation as code** — two validators, not prompt instructions, and both block
- **Untrusted input is fenced** — scraped postings go inside `<job_description>` tags, and the candidate CV lives in the system prompt. A posting must never share a turn with the record it might try to amend
- **The base CV is never truncated** — it enters every prompt whole, via `nj/prompts/cv_context.py`. Slicing it is how a drafter once saw 28% of a CV and returned only the sections it could see
- **The status a row claims is the status that happened** — the pipeline writes `GENERATED`, only a human writes `SUBMITTED`

[CLAUDE.md](CLAUDE.md) records the project standards, an implementation-status
table, and the subsystems currently known to be broken.

---

## Automation phases

| Phase | Mode | Status |
| --- | --- | --- |
| 1 (default) | Score, queue, human review, you tailor and submit | **Implemented** |
| 2 | Semi-auto — nj submits, you approve each | Not implemented |
| 3 | Full auto behind the quality gate | Not implemented |

Submission itself is not implemented at any phase, and phases 2 and 3 as
designed do not exist. What `automation_phase > 1` actually does today is
unattend the *generation* half: `nj run` continues past the review queue into
tailoring, rendering, the quality gate and the application log instead of
stopping. Everything nj produces still lands in `output/` for you to send
yourself.

**Never automated, regardless of phase:**

- Resume factual claims (enforced in code by two validators)
- Applications that fail the quality gate
- Interview communication

---

## Testing and development

```bash
poetry run pytest                            # full suite
poetry run pytest tests/unit/                # unit only
poetry run ruff check nj/ tests/             # lint
poetry run ruff format --check nj/ tests/    # formatting

NJ_RUN_REGRESSION_TESTS=true poetry run pytest tests/integration/test_prompt_regression.py
```

670 passing, 3 skipped (prompt regression, opt-in). No unit test touches the
network. CI runs the same three gates on Python 3.11, 3.12 and 3.13, plus a
coverage floor of 55% and gitleaks over full history; a separate step asserts
`.env`, `config.yaml` and `cv/cv_base.json` are untracked. `main` is
branch-protected with all four checks required and strict mode on.

CI sets `NJ_REQUIRE_TECTONIC=1` so the LaTeX template tests fail rather than
skip when no compiler is present — a silently skipped check is how a 0-byte CV
template survived for months.

Regression coverage is kept for the failures that actually shipped: visa
misclassification in both directions, CV hallucination across 19 realistic
shapes, a draft that drops content, the shipped LaTeX template (including a
real `tectonic` compile and a fully empty CV), and reasoning-token starvation.

Working on this repo with Claude Code: `.claude/commands/` holds `/audit` (every
CI gate plus the secret checks), `/apply` (the drafter-reviewer pipeline on one
job) and `/eval` (the scoring and anti-hallucination regressions). A `PostToolUse`
hook runs lint, format and tests after edits — advisory, not blocking, since
mid-refactor states legitimately fail.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `nj search` returns mostly German/EU jobs | Adzuna and JSearch keys are unset, so Arbeitnow serves the run. Set `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` and `JSEARCH_API_KEY` |
| Everything scores 0/100 | A reasoning model starved of tokens returns `200 OK` with an empty string. The OpenAI provider now learns the allowance and retries; if you added a call site, give it headroom |
| A run "succeeds" but no PDF appears | `tectonic` is not installed. `nj run` logs the render failure as a warning and carries on, so it looks like success. `brew install tectonic` |
| "CV ran to N pages (budget 2)" | The page budget rejected the render but kept the file — open the path it printed, trim, re-run |
| Sponsorship labels look wrong after a classifier fix | Labels are stored at scrape time. `nj reclassify` to preview, `--apply` to write |
| `nj status` shows nothing after `nj tailor` | By design: `nj tailor` writes files, not application rows. Only `nj run` with `apply.enabled` logs applications |
| Provider 404s on `gpt-5.5-pro` | It is not a chat model and does not serve `v1/chat/completions`. Do not set it as a tier |

---

## Known limitations

Found by running the code against the real scraped database rather than
fixtures. Each is recorded in full in [CLAUDE.md](CLAUDE.md).

- **H-1B job-title signals are dead.** The ingested USCIS datahub export is
  employer-level and carries no job titles, so `is_ml_role` is 0 on all 154,112
  rows and "ML roles filed" is dead code. Fixing it means ingesting LCA/PERM
  disclosure data.
- **Sponsor tiers are miscalibrated.** 83,828 of 87,595 companies are `UNKNOWN`
  and none reach `STRONG`; thresholds were written for thousand-petition
  employers, and the max in this dataset is 54.
- **No employer entity resolution.** Amazon appears under at least three
  different strings, splitting its petition count. Company lookups match 33 of
  319 scraped employers.
- **No vector store.** There is no ChromaDB and no RAG pipeline; semantic
  matching is TF-IDF + cosine in `nj/ml/semantic_model.py`.
- **The OpenAI path does not enforce JSON Schema.** `complete()` ignores
  `json_schema`/`response_format`, so scores are salvaged from the response
  rather than decoded against `SCORE_SCHEMA`. Scoring parses reliably without it.
- **`freellmapi` collapses the tiers.** `registry.py` reads one
  `freellmapi_model` for every task, so all four tiers land on one model.

---

## What landed recently

The 2026-08-16/17 hardening pass, in the order it happened:

**Correctness**
- Visa filter stopped discarding employers that would sponsor; regression tests
  pin both failure directions
- Stored labels became re-derivable — `nj reclassify`, dry-run by default
- The CV template was restored (it had been a 0-byte file) and guarded by 8 CI
  tests including a real `tectonic` compile and a fully empty CV
- Completeness validation added, so a draft can no longer silently drop your
  experience
- The base CV stopped being truncated into prompts — four call sites had been
  slicing it at 3000–5000 chars
- `applied_at` is stamped when an application is recorded, so the daily cap
  actually throttles

**Honesty**
- `GENERATED` split from `SUBMITTED`; the pipeline can no longer claim an
  application it did not send, and `test_pipeline_never_writes_submitted` pins it
- LinkedIn automation reduced to an inert stub; no code path reads a session
  cookie
- README and CLAUDE.md rewritten to match the code, with a status table and a
  known-broken list

**Infrastructure**
- Alembic migrations with a baseline over all 9 tables and a drift test
- Adversarial reviewer added behind the drafter, with the blocking/advisory split
- Candidate CV moved into the system prompt; postings fenced as untrusted input
- Models tiered per task across both providers; the OpenAI path learns the
  reasoning-token allowance and retries instead of returning an empty string
- CI repaired, toolchain pinned, coverage gate set to a number that is true,
  gitleaks over full history, `main` branch-protected

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

- **Adding a scraper:** extend `BaseScraper`, add tests, register in `_get_enabled_scrapers()`. See [docs/adding-a-scraper.md](docs/adding-a-scraper.md).
- **Adding an LLM provider:** extend `BaseLLMProvider`, register in `registry.py`. See [docs/adding-a-provider.md](docs/adding-a-provider.md).
- **Improving prompts:** all prompts in `nj/prompts/` are versioned modules. See [docs/prompt-engineering.md](docs/prompt-engineering.md).

---

## Roadmap

- [x] Interactive msfconsole-style shell
- [x] 6 job scrapers
- [x] Explainable 6-sub-score AI scoring
- [x] Anti-hallucination CV tailoring
- [x] Drafter–reviewer pipeline with a blocking/advisory split
- [x] Completeness validation — a draft cannot silently drop your experience
- [x] PDF page budget enforced with `pypdf`
- [x] Alembic migrations with a drift test
- [x] CV diagnosis engine and skill gap analysis
- [x] Interview prep PDF
- [x] Gmail callback detection
- [x] Outcome-calibrated threshold
- [x] Tiered models across Claude and OpenAI
- [ ] Screening-question answers in the output bundle
- [ ] Employer entity resolution for H-1B lookups
- [ ] Schema-constrained decoding on the OpenAI path
- [ ] Evaluation harness over fixture postings
- [ ] H-1B intel rebuild on LCA/PERM data (see [CLAUDE.md](CLAUDE.md))
- [ ] Read-only web dashboard
- [ ] PyPI publish

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Built by [Nishant Joshi](https://github.com/ZocNishant) ·
[LinkedIn](https://linkedin.com/in/nishant-joshi) ·
[GitHub](https://github.com/ZocNishant)

---

*"never invents your experience."*

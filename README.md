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

## All commands

```
Intelligence:    diagnose  gaps  explain  diff  frame  postmortem
Job hunting:     search  run  review  tailor  quality  enrich  reclassify
Applications:    status  calibrate  label  watch  prep
CV management:   update-cv  update-role  update-intern
Data & models:   intel  graph  ml
System:          init  config  logs  demo  manual  help  exit
```

`nj manual` prints the full reference with every flag and example.

Tailor one job by its stored id, without refetching the posting:

```bash
nj tailor --job-id 716789b6      # a unique id prefix is enough
```

Prefer this to passing a URL. Fetching a URL re-derives the posting from the
live page and cannot recover the title or company, so the tailoring runs against
whatever text the page happens to yield.

---

## Automation phases

| Phase | Mode | Status |
| --- | --- | --- |
| 1 (default) | Score + tailor + human review, you submit | **Implemented** |
| 2 | Semi-auto — nj submits, you approve each | Not implemented |
| 3 | Full auto behind the quality gate | Not implemented |

Phases 2 and 3 are design, not code — `nj/applying/linkedin_easy.py` is a stub
that raises rather than returning, so a caller cannot record a phantom
submission. Setting `automation_phase` above 1 changes no behaviour today.
Everything nj produces is written to `output/` for you to submit yourself.

Because nj cannot submit, the pipeline writes `ApplicationStatus.GENERATED` —
"CV and letter on disk, nothing sent" — and never `SUBMITTED`. Only a human
promotes a row:

```bash
nj status --update-id <id> --update-status submitted
```

**Never automated, regardless of phase:**

- Resume factual claims (enforced in code by two validators)
- Applications that fail the quality gate
- Interview communication

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

[CLAUDE.md](CLAUDE.md) records the project standards, an implementation-status
table, and the subsystems currently known to be broken.

---

## Testing

```bash
poetry run pytest                            # full suite
poetry run pytest tests/unit/                # unit only
poetry run ruff check nj/ tests/             # lint
poetry run ruff format --check nj/ tests/    # formatting

NJ_RUN_REGRESSION_TESTS=true poetry run pytest tests/integration/test_prompt_regression.py
```

670 passing, 3 skipped (prompt regression, opt-in). No unit test touches the
network. CI runs the same three gates on Python 3.11, 3.12 and 3.13, plus
gitleaks over full history.

Regression coverage is kept for the failures that actually shipped: visa
misclassification in both directions, CV hallucination across 19 realistic
shapes, a draft that drops content, the shipped LaTeX template (including a
real `tectonic` compile and a fully empty CV), and reasoning-token starvation.

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

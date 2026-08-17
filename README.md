<div align="center">

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
[![Tests](https://img.shields.io/badge/tests-567%20passing-brightgreen)](https://github.com/ZocNishant/nj-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://python.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

</div>

---

## Why nj is different

**nj never invents your experience.**

Every tailored CV is validated against your original before it leaves your
machine. If the model adds a skill you don't have, an employer you didn't work
for, a degree you didn't earn, or a metric you didn't achieve, the validator
rejects the result.

This is not a prompt instruction. `nj/tailoring/anti_hallucination.py` compares
employers, job titles, institutions, degrees, projects, certifications and
skills as normalized sets, then scans the free text for invented years,
percentages, employers and credential words. Reordering, dropping and rewording
are allowed. Adding a claim your source CV does not contain is not.

---

## Built for the OPT job search

Sponsorship is a hard filter, not a preference, so nj treats it as a
correctness problem rather than a keyword search.

The classifier is negation-aware and evaluates blocking language before
sponsoring language, because the naive version of this gets it wrong in both
directions at once:

| Posting says | Naive keyword match | nj |
|---|---|---|
| "Must be authorized to work in the US" | BLOCKED — drops the job | UNKNOWN — OPT *is* authorization |
| "We do not sponsor employment visas" | CONFIRMED — matches "sponsor" | BLOCKED |
| "We sponsor H-1B. Must be authorized at hire." | BLOCKED | CONFIRMED |
| "Strong optimization background required" | CONFIRMED — matches "OPT" inside *optimization* | UNKNOWN |

That last row is not hypothetical. Re-running the old substring matcher over
441 real scraped jobs, 223 of the 224 marked "sponsorship confirmed" were
marked that way because the description contained the word *optimization*.

`nj search` shows the phrase that decided each label, so a misclassification is
visible before it costs you an application.

---

## What it does

```
nj (claude) > diagnose    # why am I not getting interviews
nj (claude) > gaps        # what should I learn — ranked by ROI
nj (claude) > search      # find and score 100+ ML jobs
nj (claude) > explain     # why did this job score 78?
nj (claude) > prep        # I have an interview tonight
nj (claude) > exit
```

Launch `nj` and you're in a full interactive shell — msfconsole style. Every
command is available from the prompt, with tab completion and history.

---

## Features

### Career Intelligence

| Command | What it does |
|---------|-------------|
| `nj diagnose` | Full CV health report — root causes of interview failure, recruiter first impression, ATS concerns, positioning mismatch |
| `nj gaps` | Skill gap analysis across all scored jobs — ranked by frequency and estimated score impact |
| `nj explain` | Exact breakdown of why a job scored the way it did — 6 sub-scores with rationale and evidence |
| `nj frame` | Reframe your best project for a specific audience: production ML, research lab, healthtech startup, big tech |
| `nj diff` | Show exactly what changed between your base CV and the tailored version — bullet by bullet |
| `nj postmortem` | Application failure patterns across everything you've sent |

### Job Discovery (7 sources)

| Source | Auth | Notes |
|--------|------|-------|
| RemoteOK | None | Works out of the box |
| WeWorkRemotely | None — RSS | Remote ML roles |
| Arbeitnow | None — free API | Mostly German/EU. Turn off for a US-only search |
| Adzuna | Free API key | Aggregates 15+ US sources. Highest-value key to set |
| JSearch | RapidAPI key (free tier) | 30+ boards: LinkedIn, Indeed, Glassdoor, ZipRecruiter |
| USAJobs | Free API key (opt-in) | Government + research ML roles |
| LinkedIn | Session cookie | **Off by default** — automated scraping breaches LinkedIn's terms and risks the account recruiters contact you on |

Adzuna and JSearch return nothing until their keys are set. Without them a run
is served mostly by Arbeitnow, which is the wrong continent for an H-1B search.

### AI Scoring

- **6 explainable sub-scores** — skills, experience, role alignment, sponsorship, location, resume strength
- **Weighted scoring** — configurable per your priorities
- **Confidence score** — how certain the model is about the comparison
- **Schema-constrained output** — scores are decoded against a JSON Schema, not parsed out of prose
- **Outcome calibration** — `nj calibrate --from-outcomes` sets your threshold from real interview results

### CV Tailoring

- Keyword alignment from the job description
- Section reordering by relevance; anchor project always leads
- Irrelevant skill groups suppressed per role type
- **Anti-hallucination validation** — structural and free-text, described above
- LaTeX → PDF via tectonic, preserving your template
- Cover letter generation (3 paragraphs, 250 words max)

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
- [tectonic](https://tectonic-typesetting.github.io) — LaTeX compiler
- An Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

```bash
# macOS
brew install tectonic

git clone https://github.com/ZocNishant/nj-cli
cd nj-cli
poetry install

# Secrets go in .env, never in config.yaml
cp .env.example .env          # add ANTHROPIC_API_KEY
cp config.example.yaml config.yaml

poetry run nj
```

### First run

```
nj (claude) > init        # setup wizard — CV, email, schedule
nj (claude) > search      # find and score jobs
nj (claude) > diagnose    # get your CV diagnosis
nj (claude) > gaps        # see what to learn
nj (claude) > review      # approve jobs before applying
nj (claude) > calibrate   # tune your score threshold
```

### Zero-cost demo (no API key needed)

```bash
poetry run nj
nj (claude) > demo
```

---

## All commands

```
Intelligence:    diagnose  gaps  explain  diff  frame  postmortem
Job hunting:     search  run  review  tailor  quality  enrich
Applications:    status  calibrate  label  watch  prep
CV management:   update-cv  update-role  update-intern
Data & models:   intel  graph  ml
System:          init  config  logs  demo  manual  help  exit
```

`nj manual` prints the full reference with every flag and example.

---

## Automation phases

| Phase | Mode | Status |
|-------|------|--------|
| 1 (default) | Score + tailor + human review, you submit | **Implemented** |
| 2 | Semi-auto — nj submits, you approve each | Not implemented |
| 3 | Full auto behind the quality gate | Not implemented |

Phases 2 and 3 are design, not code — `nj/applying/linkedin_easy.py` is a stub.
Setting `automation_phase` above 1 changes no behaviour today. Everything nj
produces is written to `output/` for you to submit yourself.

**Never automated, regardless of phase:**

- Resume factual claims (enforced in code by the validator)
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
  provider: claude
  # Tiered by what the output is for. `model` is the fallback.
  model: claude-sonnet-5
  scoring_model: claude-haiku-4-5      # ranks 50-200 jobs a run
  tailoring_model: claude-sonnet-5     # what a recruiter reads
  reasoning_model: claude-opus-5       # diagnose / gaps / prep / frame

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

A full search-and-apply cycle costs roughly $1 in API credit on these tiers:
about $0.63 to score 100 jobs on Haiku, about $0.29 to tailor five CVs and
cover letters on Sonnet.

---

## LLM Providers

| Provider | Status | Notes |
|----------|--------|-------|
| Claude (Anthropic) | Implemented | Default. Tiered per task; prompt caching on the CV prefix |
| Groq / OpenAI-compatible | Implemented | Any OpenAI-shaped endpoint via `provider: freellmapi` and a base URL |
| OpenAI | Implemented | Same provider class; set `OPENAI_API_KEY` and `provider: openai` |

Switching providers is a config change. See
[docs/adding-a-provider.md](docs/adding-a-provider.md) to add another.

---

## Architecture

```
nj/
  cli/          one file per command, no business logic
  models/       Pydantic models
  scrapers/     7 sources behind a BaseScraper ABC
  scoring/      scorer, visa filter, calibration, ghost filter, quality gate
  tailoring/    tailor, keyword_align, section_ranker, suppressor,
                renderer (LaTeX→PDF), anti_hallucination,
                cover_letter, prep_generator
  providers/    BaseLLMProvider, Claude (AsyncAnthropic), OpenAI-compatible
  prompts/      versioned prompt modules + untrusted-input fencing
  db/           SQLAlchemy + repository pattern (schema via create_all)
  diagnostics/  CV diagnosis engine + PDF renderer
  analytics/    skill_gaps, outcomes, outcomes_analysis
  intel/        H-1B petition ingest and job enrichment
  graph/        career knowledge graph
  ml/           sponsorship, salary and semantic models
  integrations/ gmail_watcher
```

Key decisions:

- **Repository pattern** — SQL stays behind repos so the storage engine can change
- **Provider abstraction** — switch LLM with one config line
- **Versioned prompts** — every score records the prompt version that produced it
- **Anti-hallucination as code** — a validator, not a prompt instruction
- **Untrusted input is fenced** — scraped postings go inside `<job_description>`
  tags with the candidate profile kept in the system prompt, so a posting cannot
  pose as an instruction

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

567 passing, 3 skipped (prompt regression, opt-in). No unit test touches the
network. CI runs the same three gates on Python 3.11, 3.12 and 3.13, plus
gitleaks over full history.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

- **Adding a scraper:** extend `BaseScraper`, add tests, register in `_get_enabled_scrapers()`. See [docs/adding-a-scraper.md](docs/adding-a-scraper.md).
- **Adding an LLM provider:** extend `BaseLLMProvider`, register in `registry.py`. See [docs/adding-a-provider.md](docs/adding-a-provider.md).
- **Improving prompts:** all prompts in `nj/prompts/` are versioned modules. See [docs/prompt-engineering.md](docs/prompt-engineering.md).

---

## Roadmap

- [x] Interactive msfconsole-style shell
- [x] 7 job scrapers
- [x] Explainable 6-sub-score AI scoring
- [x] Anti-hallucination CV tailoring
- [x] CV diagnosis engine and skill gap analysis
- [x] Interview prep PDF
- [x] Gmail callback detection
- [x] Outcome-calibrated threshold
- [x] Tiered Claude models with prompt caching
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

<div align="center">
<i>"never invents your experience."</i>
</div>

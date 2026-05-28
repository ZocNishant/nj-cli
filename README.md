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

[![Tests](https://img.shields.io/badge/tests-347%20passing-brightgreen)](https://github.com/ZocNishant/nj-cli)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-cyan)](https://github.com/ZocNishant/nj-cli/releases)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

---

## Why nj is different

**nj never invents your experience.**

Every tailored CV is validated against your original before it leaves your machine. If Claude tries to add a skill you don't have, a company you didn't work at, or a metric you didn't achieve — the validator rejects it and regenerates.

This is not a prompt instruction. It is a separate validation module (`nj/tailoring/anti_hallucination.py`) that diffs the output entity by entity against your source CV.

Most AI career tools hallucinate. nj does not.

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

Launch `nj` and you're in a full interactive shell — msfconsole style.  
Every command available from the prompt. No flags to memorize.

---

## Features

### Career Intelligence
| Command | What it does |
|---------|-------------|
| `nj diagnose` | Full CV health report — root causes of interview failure, recruiter first impression, ATS concerns, positioning mismatch |
| `nj gaps` | Skill gap analysis across all scored jobs — ranked by frequency and estimated score impact |
| `nj explain` | Exact breakdown of why a job scored the way it did — 6 sub-scores with rationale and evidence |
| `nj frame` | Reframe your best project for different audiences: production ML, research lab, healthtech startup, big tech |
| `nj diff` | Show exactly what changed between your base CV and the tailored version — bullet by bullet |

### Job Discovery (7 sources)
| Source | Auth | Coverage |
|--------|------|----------|
| RemoteOK | None — always works | 100+ ML/AI/CV jobs per run |
| WeWorkRemotely | None — RSS | Remote ML roles |
| Arbeitnow | None — free API | Remote + EU tech |
| JSearch | RapidAPI key (free tier) | 30+ boards: LinkedIn, Indeed, Glassdoor, ZipRecruiter... |
| Adzuna | Free API key | 15+ aggregated sources |
| LinkedIn | Session cookie | Highest ML job volume |
| USAJobs | Free API key (opt-in) | Government + research ML roles |

### AI Scoring
- **6 explainable sub-scores** — skills, experience, role alignment, sponsorship, location, resume strength
- **Weighted scoring** — configurable per your priorities
- **Confidence score** — how certain the model is
- **Visa compatibility** — OPT/H1B filtering built in
- **Outcome calibration** — `nj calibrate --from-outcomes` uses real interview data to set your threshold

### CV Tailoring
- Keyword alignment from job description
- Section reordering by relevance
- Security tools suppressed for ML roles automatically
- Anchor project always leads (your strongest project first)
- **Anti-hallucination validation** — entities diffed against source CV
- LaTeX → PDF via tectonic (your exact template preserved)
- Cover letter generation (3-paragraph, 250 words max)

### Application Pipeline
- Human review queue before any application (Phase 1 default)
- Quality gate blocks bad applications before submission
- Rate limiting (5-7 applications/day max)
- Email notification with tailored CV attached
- Application tracker with trajectory view
- Gmail callback detection (interview/rejection/offer signals)

### Interview Preparation
- `nj prep` generates a full PDF: company brief, 8-10 technical questions with confidence ratings, STAR behavioural questions, story bank, quick reference card
- `nj watch` monitors Gmail for callbacks and emails you `nj prep --job-id` to run immediately

---

## Quick start

### Requirements
- Python 3.11+
- [tectonic](https://tectonic-typesetting.github.io) — LaTeX compiler
- Anthropic API key — [get one here](https://console.anthropic.com)

```bash
# macOS
brew install tectonic

# Install nj
git clone https://github.com/ZocNishant/nj-cli
cd nj-cli
pip install -e .

# Launch
nj
```

### First run
```
nj (claude) > init        # setup wizard — API key, CV, email
nj (claude) > search      # find and score jobs (needs API key)
nj (claude) > diagnose    # get your CV diagnosis
nj (claude) > gaps        # see what to learn
nj (claude) > review      # approve jobs before applying
nj (claude) > calibrate   # tune your score threshold
```

### Zero-cost demo (no API key needed)
```bash
nj
nj (claude) > demo
```

---

## All commands

```
Intelligence:    diagnose  gaps  explain  diff  frame
Job hunting:     search    run   review   tailor  quality
Applications:    status    calibrate  label  watch  prep
CV management:   update-cv  update-intern
System:          init  logs  config  demo  help  exit
```

---

## Automation phases

nj uses phased automation — trust is earned before autonomy is granted.

| Phase | Mode | How to unlock |
|-------|------|---------------|
| 1 (default) | Score + tailor + human review | Default |
| 2 | Semi-auto — you approve each | `automation_phase: 2` in config |
| 3 | Full auto with quality gate | `automation_phase: 3` in config |

**What is NEVER automated regardless of phase:**
- Resume factual claims (validator enforces in code)
- Applications that fail the quality gate
- Interview communication

---

## Configuration

```bash
cp config.example.yaml config.yaml
# Edit config.yaml — your preferences stay local and gitignored
```

Key settings:
```yaml
scoring:
  threshold: 62          # raise to 68 after internship starts

apply:
  enabled: false         # set true when ready
  max_per_day: 5
  automation_phase: 1

visa:
  enabled: true
  status: "OPT"          # OPT | CPT | H1B | GC | citizen
  skip_no_sponsorship: true

llm:
  provider: claude       # or: freellmapi
```

---

## LLM Providers

| Provider | Status | Notes |
|----------|--------|-------|
| Claude (Anthropic) | ✅ Implemented | Default. Best quality. |
| FreeLLMAPI | ✅ Implemented | Free local proxy, 14 providers |
| OpenAI | 🔲 Interface ready | See `docs/adding-a-provider.md` |

Switch provider with one config change — zero code changes required.

---

## Architecture

```
nj/
  cli/          one file per command, no business logic
  models/       pure Pydantic models
  scrapers/     7 scrapers, BaseScraper ABC
  scoring/      scorer, visa filter, calibration, quality gate
  tailoring/    tailor, keyword_align, section_ranker, suppressor,
                renderer (LaTeX→PDF), anti_hallucination,
                cover_letter, prep_generator
  providers/    BaseLLMProvider, Claude, OpenAI-compatible
  prompts/      versioned prompt modules (scoring_v1, tailoring_v1...)
  db/           SQLAlchemy + repository pattern
  diagnostics/  CV diagnosis engine + PDF renderer
  analytics/    skill_gaps, outcome_feedback
  integrations/ gmail_watcher
```

Key decisions:
- **Repository pattern** — swap SQLite for Postgres with zero app changes
- **Provider abstraction** — switch LLM with one config line
- **Versioned prompts** — every score stores its prompt version for reproducibility
- **Anti-hallucination as code** — not a prompt instruction, a separate validator

See [ARCHITECTURE.md](ARCHITECTURE.md) for full decisions and [PRODUCT.md](PRODUCT.md) for product philosophy.

---

## International student support

Built by an F-1 OPT student, for F-1 OPT students.

- Visa keyword scanning — BLOCKED/CONFIRMED/LIKELY/UNKNOWN labels
- OPT/H1B context injected into every scoring prompt
- Auto-skip jobs with explicit no-sponsorship language
- Sponsorship compatibility is a weighted scoring category

```yaml
visa:
  enabled: true
  status: "OPT"          # OPT | CPT | H1B | GC | citizen
  h1b_future: true
  skip_no_sponsorship: true
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

**Adding a scraper:** Extend `BaseScraper`, add tests, register in `_get_enabled_scrapers()`. See [docs/adding-a-scraper.md](docs/adding-a-scraper.md).

**Adding an LLM provider:** Extend `BaseLLMProvider`, register in `registry.py`. See [docs/adding-a-provider.md](docs/adding-a-provider.md).

**Improving prompts:** All prompts in `nj/prompts/` are versioned Python modules. See [docs/prompt-engineering.md](docs/prompt-engineering.md).

---

## Testing

```bash
poetry run pytest                           # full suite
poetry run pytest tests/unit/              # unit only
NJ_RUN_REGRESSION_TESTS=true poetry run pytest tests/integration/test_prompt_regression.py
```

347 tests · 3 skipped (regression, require API key) · 0 warnings

---

## Roadmap

- [x] Interactive msfconsole-style shell
- [x] 7 job scrapers
- [x] Explainable 6-sub-score AI scoring  
- [x] Anti-hallucination CV tailoring
- [x] CV diagnosis engine
- [x] Skill gap analysis
- [x] Interview prep PDF
- [x] Gmail callback detection
- [x] Outcome-calibrated threshold
- [x] FreeLLMAPI support
- [ ] Auto-apply Phase 2 (August 2026)
- [ ] Web UI / self-hosted dashboard
- [ ] PyPI publish
- [ ] Glassdoor scraper

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

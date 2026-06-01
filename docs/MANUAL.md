# nj-cli Manual

**nj** — AI Career Operating System  
Anti-hallucination CV tailoring · Explainable scoring · H1B intelligence  
Career knowledge graph · ML models · Interactive shell

```
Usage:  nj <command> [flags]
Shell:  nj              → interactive shell with tab completion
Help:   nj manual <command>   → detailed help for any command
```

---

## Table of Contents

- [Intelligence](#intelligence)
  - [diagnose](#diagnose)
  - [gaps](#gaps)
  - [explain](#explain)
  - [diff](#diff)
  - [frame](#frame)
  - [postmortem](#postmortem)
- [Job Discovery](#job-discovery)
  - [search](#search)
  - [enrich](#enrich)
  - [tailor](#tailor)
  - [review](#review)
  - [quality](#quality)
- [Data & ML](#data--ml)
  - [intel](#intel)
  - [graph](#graph)
  - [ml](#ml)
- [Applications](#applications)
  - [run](#run)
  - [status](#status)
  - [calibrate](#calibrate)
  - [label](#label)
  - [watch](#watch)
  - [prep](#prep)
- [CV Management](#cv-management)
  - [update-cv](#update-cv)
  - [update-intern](#update-intern)
- [System](#system)
  - [init](#init)
  - [demo](#demo)
  - [logs](#logs)
  - [config](#config)
  - [manual](#manual)

---

## Intelligence

### diagnose

Full CV health report — root causes of interview failure, recruiter first impression, ATS concerns.

**Flags**

| Flag | Description |
|------|-------------|
| `--no-pdf` | Terminal output only, skip PDF generation |
| `--db PATH` | Database path (default: data/nj.db) |
| `--output DIR` | Output directory for PDF (default: output/) |

**Examples**

```bash
nj diagnose              # Full diagnosis with PDF report
nj diagnose --no-pdf     # Quick terminal-only diagnosis
```

> Uses career graph context if built. Requires API key. PDF saved to `output/`.

---

### gaps

Skill gap analysis across all scored jobs — ranked by frequency and estimated score impact.

**Flags**

| Flag | Description |
|------|-------------|
| `--top / -n N` | Number of gaps to show (default: 10) |
| `--min-freq N` | Minimum frequency % to include (default: 10) |
| `--db PATH` | Database path |

**Examples**

```bash
nj gaps          # Top 10 skill gaps
nj gaps --top 20 # Top 20 gaps
```

> No API calls. Pure aggregation of existing score data. Run `nj search` first.

---

### explain

Explain exactly why a job scored the way it did — 6 sub-scores, evidence, enrichment data.

**Flags**

| Flag | Description |
|------|-------------|
| `--job-id / -j ID` | Job ID to explain (first 8 chars work) |
| `--top / -n N` | Show top N jobs when no ID given (default: 10) |
| `--db PATH` | Database path |

**Examples**

```bash
nj explain                    # Show top 10 scored jobs
nj explain --job-id abc123    # Full explanation for specific job
```

> Shows sponsorship probability, USCIS history, salary estimate, and semantic match alongside AI scores.

---

### diff

Show exactly what changed between your base CV and the tailored version for a job.

**Flags**

| Flag | Description |
|------|-------------|
| `--job-id / -j ID` | Job ID to diff |
| `--section / -s NAME` | Section to diff: summary, skills, experience, projects |
| `--db PATH` | Database path |

**Examples**

```bash
nj diff                              # List jobs with tailored CVs
nj diff --job-id abc123              # Full diff for specific job
nj diff --job-id abc123 --section skills  # Skills diff only
```

> Requires `nj tailor` or `nj run` to have generated a tailored CV first.

---

### frame

Reframe your best project for a specific audience — production ML, research lab, healthtech, big tech.

**Flags**

| Flag | Description |
|------|-------------|
| `--project / -p ID` | Project ID to frame (see `nj frame --list`) |
| `--audience / -a TYPE` | Target: production_ml, research_lab, healthtech_startup, big_tech, early_stage_startup, custom |
| `--role TEXT` | Role description for custom audience |
| `--list / -l` | List available projects |

**Examples**

```bash
nj frame --list
nj frame --project gastrovision --audience healthtech_startup
nj frame --audience research_lab
```

> Anti-hallucination validated. Only reframes existing content — never invents.

---

### postmortem

Analyse application failure patterns — why interviews are not coming, what to fix.

**Flags**

| Flag | Description |
|------|-------------|
| `--min N` | Minimum applications for analysis (default: 3) |
| `--db PATH` | Database path |

**Examples**

```bash
nj postmortem    # Full failure analysis
```

> No API calls. Detects patterns: low scores, high no-response rate, visa issues, weak experience sub-scores.

---

## Job Discovery

### search

Scrape jobs from all enabled sources, enrich with intelligence, and score against your CV.

**Flags**

| Flag | Description |
|------|-------------|
| `--dry-run` | Scrape only — no scoring, no API credits used |
| `--verbose / -v` | Show per-scraper debug output |
| `--db PATH` | Database path (default: data/nj.db) |

**Examples**

```bash
nj search            # Full scrape + enrich + score
nj search --dry-run  # Scrape only, see what's out there
```

> Runs all 7 scrapers in parallel. Ghost jobs filtered automatically. Results saved to DB.

---

### enrich

Full intelligence report for any job URL — sponsorship probability, salary estimate, USCIS data, semantic match.

**Flags**

| Flag | Description |
|------|-------------|
| `URL` | Job URL (required) — works with LinkedIn, Greenhouse, Lever, Workday, any job board |
| `--no-score` | Skip AI scoring (faster, no API credits) |
| `--db PATH` | Database path |

**Examples**

```bash
nj enrich https://jobs.lever.co/company/job-id
nj enrich https://linkedin.com/jobs/view/123 --no-score
```

> Works without API key for sponsorship/salary/USCIS layers. Needs API key for AI scoring.

---

### tailor

Tailor CV and generate cover letter for a specific job URL.

**Flags**

| Flag | Description |
|------|-------------|
| `URL` | Job URL (required) |
| `--output DIR` | Output directory (default: output/) |
| `--db PATH` | Database path |

**Examples**

```bash
nj tailor https://jobs.lever.co/company/job
```

> Anti-hallucination validated. LaTeX → PDF via tectonic. Saves JSON for `nj diff`.

---

### review

Interactively review scored jobs before applying.

**Flags**

| Flag | Description |
|------|-------------|
| `--db PATH` | Database path |

**Examples**

```bash
nj review    # Start review queue
```

> Keys: `a`=approve, `s`=skip, `l`=label, `v`=view in browser, `q`=quit. Only approved jobs proceed to apply.

---

### quality

Run pre-submit quality gate on tailored applications.

**Flags**

| Flag | Description |
|------|-------------|
| `--job-id / -j ID` | Check specific job |
| `--db PATH` | Database path |

**Examples**

```bash
nj quality                   # Check all tailored jobs
nj quality --job-id abc123   # Check specific job
```

> Blocks: score below threshold, no-sponsorship language. Warns: banned phrases, senior signals, low confidence.

---

## Data & ML

### intel

H1B sponsorship intelligence powered by public USCIS petition data.

**Subcommands**

| Subcommand | Description |
|------------|-------------|
| `sync` | Download latest USCIS H1B data (~2-3 min first run) |
| `top` | Top ML/AI sponsors |
| `company NAME` | H1B profile for a specific company |
| `role TITLE` | Which companies sponsor this role |
| `stats` | Database statistics |

**Flags**

| Flag | Description |
|------|-------------|
| `--state / -s ST` | Filter by US state (CA, NY, TX, FL...) |
| `--year / -y YEAR` | Filter by year (2022, 2023, 2024) |
| `--limit / -n N` | Number of results (default: 20) |

**Examples**

```bash
nj intel sync                                    # Download USCIS data (run once)
nj intel top                                     # Top ML sponsors nationwide
nj intel top --state FL                          # Top ML sponsors in Florida
nj intel company Google                          # Google H1B history
nj intel company 'Moffitt Cancer Center'         # Moffitt H1B profile
nj intel role 'Machine Learning Engineer'        # Who sponsors ML Engineers
nj intel stats                                   # How much data is loaded
```

> Data source: USCIS H1B Employer Data Hub (public). Updated quarterly. Free.

---

### graph

Career knowledge graph — your skills, companies, projects, and applications as connected data.

**Subcommands**

| Subcommand | Description |
|------------|-------------|
| `build` | Build graph from CV + existing scores |
| `show` | Visualize your career tree |
| `stats` | Graph statistics |
| `skills` | Your skills vs gap skills |
| `companies` | Companies in your graph |
| `path FROM TO` | Shortest path between two nodes |

**Flags**

| Flag | Description |
|------|-------------|
| `--target / -t NODE` | Target node for path command |

**Examples**

```bash
nj graph build                              # Build from cv_base.json + DB
nj graph show                               # See your career as a tree
nj graph path PyTorch 'Senior ML Engineer'  # Skill path to target role
nj graph skills                             # Skills you have vs skills you need
```

> Auto-updates on every application. No API calls needed.

---

### ml

ML models — sponsorship probability classifier, salary predictor, semantic CV-JD similarity.

**Subcommands**

| Subcommand | Description |
|------------|-------------|
| `status` | Show which models are trained |
| `train` | Train models on USCIS data (requires `nj intel sync` first) |
| `predict` | Sponsorship probability for company + role |
| `salary` | Salary prediction for role + location |
| `semantic` | Semantic CV-JD similarity for a scored job |

**Flags**

| Flag | Description |
|------|-------------|
| `--company / -c NAME` | Company name for predict |
| `--role / -r TITLE` | Role title for predict/salary |
| `--state / -s ST` | State for salary (default: CA) |
| `--year / -y YEAR` | Year for salary (default: 2024) |
| `--job-id / -j ID` | Job ID for semantic |

**Examples**

```bash
nj ml status
nj ml train
nj ml predict --company Google --role 'ML Engineer'
nj ml salary --role 'Computer Vision Engineer' --state CA
nj ml semantic --job-id abc123
```

> Sponsorship + salary need `nj intel sync` + `nj ml train`. Semantic needs: `pip install sentence-transformers`.

---

## Applications

### run

Full pipeline — scrape, enrich, score, tailor, quality gate, apply, notify.

**Flags**

| Flag | Description |
|------|-------------|
| `--dry-run` | Scrape + score only, no applying |
| `--silent` | Suppress terminal output (for cron) |
| `--db PATH` | Database path |

**Examples**

```bash
nj run --dry-run   # Full pipeline without applying
nj run --silent    # Scheduled silent run
```

> Phase 1 (default): requires human review before applying. Set `automation_phase` in config to change.

---

### status

Application tracker — history, scores, trajectory view, ML intelligence summary.

**Flags**

| Flag | Description |
|------|-------------|
| `--update-id ID` | Job ID to update status for |
| `--update-status STATUS` | New status value |
| `--no-trajectory` | Hide weekly trajectory view |
| `--db PATH` | Database path |

**Examples**

```bash
nj status                                               # Full dashboard
nj status --no-trajectory                               # Just the table
nj status --update-id abc123 --update-status interview  # Mark as interview
```

> Shows weekly application trajectory and conversion rates when outcome data is available.

---

### calibrate

Tune score threshold from distribution data or real interview outcome data.

**Flags**

| Flag | Description |
|------|-------------|
| `--from-outcomes` | Calibrate from real interview callbacks (recommended) |
| `--db PATH` | Database path |

**Examples**

```bash
nj calibrate                 # Interactive threshold tuning
nj calibrate --from-outcomes # Data-driven threshold from interview data
```

> Run after `nj watch` detects interview callbacks. Threshold updates `config.yaml`.

---

### label

Label jobs yes/no/maybe to build calibration dataset.

**Flags**

| Flag | Description |
|------|-------------|
| `--db PATH` | Database path |

**Examples**

```bash
nj label    # Start labeling queue
```

> Builds dataset for `nj calibrate`. More labels = better threshold calibration.

---

### watch

Check Gmail for interview callbacks and offer signals. Auto-updates application outcomes.

**Flags**

| Flag | Description |
|------|-------------|
| `--setup` | Configure Gmail OAuth credentials |
| `--days N` | Days back to check (default: 30) |
| `--db PATH` | Database path |

**Examples**

```bash
nj watch --setup    # First-time Gmail setup
nj watch            # Check for callbacks
nj watch --days 7   # Check last 7 days only
```

> Detects interview/rejection/offer signals. Updates DB outcomes. Triggers `nj prep` suggestion.

---

### prep

Generate interview prep PDF — technical questions, STAR behavioural, story bank, quick reference.

**Flags**

| Flag | Description |
|------|-------------|
| `--job-id / -j ID` | Job ID from `nj status` |
| `--url / -u URL` | Job URL to prep for |
| `--last / -l` | Prep for most recently applied job |
| `--output DIR` | Output directory (default: output/) |

**Examples**

```bash
nj prep --last             # Prep for your last application
nj prep --job-id abc123    # Prep for specific job
nj prep --url https://...  # Prep for any job URL
```

> Generates PDF with 8-10 technical questions with confidence ratings. Requires API key.

---

## CV Management

### update-cv

Update CV sections interactively — no JSON editing needed.

**Flags**

| Flag | Description |
|------|-------------|
| `--section / -s NAME` | Section: summary, skills, research_interests, soft_skills, personal |
| `--show` | Display all sections and current values |

**Examples**

```bash
nj update-cv --show              # See all editable sections
nj update-cv --section summary   # Update summary
nj update-cv --section personal  # Update contact info
```

> Saves to `cv/cv_base.json`. Complex sections (skills dict) suggest editing JSON directly.

---

### update-intern

Generate CV bullets from plain English internship description.

**Flags**

| Flag | Description |
|------|-------------|
| `--db PATH` | Database path |

**Examples**

```bash
nj update-intern    # Interactive bullet generator
```

> Prompts for plain English description → Claude generates 3-4 bullets → preview + confirm → saves to `cv_base.json`.

---

## System

### init

First-time setup wizard — API keys, CV import, email, schedule.

**Examples**

```bash
nj init    # Run setup wizard
```

> 7-step wizard. Tests API key live. Can import CV from PDF. Creates `config.yaml` and `.env`.

---

### demo

Interactive demo using sample data — see what nj produces without an API key.

**Examples**

```bash
nj demo    # Run the demo
```

> No API key needed. Shows scored job, CV diagnosis, skill gaps using bundled sample data.

---

### logs

View recent logs or reliability statistics.

**Flags**

| Flag | Description |
|------|-------------|
| `--last / -n N` | Show last N log lines (default: 20) |
| `--stats` | Show parse failure rate and reliability metrics |
| `--file PATH` | Log file path (default: logs/nj.log) |

**Examples**

```bash
nj logs            # Last 20 log entries
nj logs --last 50  # Last 50 entries
nj logs --stats    # Reliability statistics
```

> Parse failure rate >5% triggers a warning — means scoring prompt needs attention.

---

### config

View, edit, or test configuration.

**Flags**

| Flag | Description |
|------|-------------|
| `--show` | Display config.yaml with syntax highlighting |
| `--check-provider` | Send test ping to configured LLM provider |
| `--path PATH` | Config file path (default: config.yaml) |

**Examples**

```bash
nj config --show              # View current config
nj config --check-provider    # Test Claude/FreeLLMAPI connection
```

> Opens `$EDITOR` by default. Use `--show` for read-only view.

---

### manual

Full command reference with every flag, example, and note.

**Arguments**

| Argument | Description |
|----------|-------------|
| `COMMAND` | Command to get detailed help for (optional) |

**Examples**

```bash
nj manual          # Show full command reference
nj manual intel    # Detailed help for intel command
nj manual ml       # Detailed help for ml command
```

> Also accessible inside the interactive shell: type `manual` or `manual <command>`.

---

## Quick Reference

```
First run:
  nj init                          # Setup wizard
  nj intel sync                    # Download H1B data
  nj ml train                      # Train sponsorship + salary models
  nj graph build                   # Build career knowledge graph

Daily workflow:
  nj search                        # Scrape + score new jobs
  nj explain                       # Review top scores
  nj enrich <url>                  # Quick intel on any job
  nj tailor <url>                  # Tailor CV for a job
  nj watch                         # Check Gmail for callbacks

Diagnostics:
  nj diagnose                      # CV health report
  nj gaps                          # Skill gap analysis
  nj postmortem                    # Application failure analysis
  nj calibrate --from-outcomes     # Tune threshold from real data
```

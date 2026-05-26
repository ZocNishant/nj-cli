# nj — AI-powered job hunting CLI

**nj** is an open-source AI recruiting agent that finds ML/AI/CV jobs,
scores them against your profile with explainable sub-scores, tailors
your CV for each application, and tracks everything locally.

Built by [Nishant Joshi](https://github.com/ZocNishant).
Apache 2.0 license.

---

## What it does

- Scrapes jobs from Indeed and LinkedIn
- Filters visa-incompatible roles (OPT/H1B support built-in)
- Scores each job with 6 explainable sub-scores via Claude AI
- Tailors your LaTeX CV to each job description
- Validates tailored CV — never invents experience or skills
- Generates targeted cover letters
- Emails you the tailored CV as attachment
- Tracks all applications in local SQLite
- Human-in-loop review queue before any auto-apply

---

## Requirements

- Python 3.11+
- [tectonic](https://tectonic-typesetting.github.io) (LaTeX compiler)
- Anthropic API key ([get one here](https://console.anthropic.com))
- Claude Pro or API credits

```bash
brew install tectonic        # macOS
brew install node            # if not installed
```

---

## Install

```bash
git clone https://github.com/ZocNishant/nj-cli
cd nj-cli
poetry install
playwright install chromium
```

---

## Quick start

```bash
nj init          # first-time setup wizard
nj search        # scrape and score jobs (no applying)
nj review        # review scored jobs interactively
nj calibrate     # tune your score threshold
```

When ready to apply:

```bash
# Set apply.enabled: true in config.yaml
nj run           # full pipeline
```

---

## All commands

| Command | Description |
|---|---|
| `nj init` | First-time setup wizard |
| `nj run` | Full pipeline: scrape, score, tailor, apply |
| `nj search` | Scrape and score only — no applying |
| `nj tailor [url]` | Tailor CV for any job URL |
| `nj review` | Interactive review queue |
| `nj status` | Application tracker dashboard |
| `nj calibrate` | Tune score threshold |
| `nj label` | Label jobs for calibration dataset |
| `nj update-intern` | Generate CV bullets from internship |
| `nj logs` | View recent logs |
| `nj config` | Edit configuration |
| `nj --schedule N` | Run every N days automatically |
| `nj --schedule 0` | Disable schedule |
| `nj --schedule show` | Show current schedule |

---

## Automation phases

nj uses a phased approach to automation — never auto-applies without
your consent first.

| Phase | Mode | How to enable |
|---|---|---|
| 1 (default) | Score + tailor + review queue | Default |
| 2 | Semi-auto: you approve each application | `automation_phase: 2` |
| 3 | Full auto with daily digest | `automation_phase: 3` |

Start at Phase 1. Run `nj review` to approve jobs manually.
Only upgrade phases after you trust the system's scoring.

---

## Configuration

Copy the example and edit:

```bash
cp config.example.yaml config.yaml
```

Key settings:

```yaml
scoring:
  threshold: 62        # minimum score to proceed (raise to 68 after internship)

apply:
  enabled: false       # set true when ready
  max_per_day: 5       # max applications per day
  automation_phase: 1  # 1=review, 2=semi-auto, 3=full-auto

visa:
  enabled: true
  status: "OPT"
  skip_no_sponsorship: true
```

See [config.example.yaml](config.example.yaml) for all options.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

The most useful contributions:
- New scrapers (Glassdoor, company sites)
- New LLM providers (OpenAI, Gemini)
- Prompt improvements

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

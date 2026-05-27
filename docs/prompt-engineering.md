# Prompt Engineering in nj-cli

## Overview

All prompts in nj-cli live in `nj/prompts/` as versioned Python
modules. Each file exports:
- `PROMPT_VERSION: str` — e.g. "scoring_v1"
- `SYSTEM_PROMPT: str` — the system instruction
- `build_user_prompt(**kwargs) -> str` — builds the user message

Prompt versions are stored alongside every ScoreResult and
DiagnosisResult for full reproducibility.

## How to improve a prompt

1. Copy the existing prompt file:
   `cp nj/prompts/scoring_v1.py nj/prompts/scoring_v2.py`

2. Update `PROMPT_VERSION = "scoring_v2"`

3. Make your changes

4. Test against regression fixtures:
```bash
NJ_RUN_REGRESSION_TESTS=true poetry run pytest \
  tests/integration/test_prompt_regression.py -v
```

5. Compare score distributions:
```bash
# Clear DB and run with new prompt
rm data/nj.db
poetry run nj search
poetry run nj calibrate
```

6. Update `nj/scoring/scorer.py` to import the new version:
```python
from nj.prompts import scoring_v2 as scoring_v1
```

7. Submit PR with:
   - The new prompt file
   - Updated regression fixture expectations if ranges changed
   - Before/after score comparison in PR description

## Scoring prompt design principles

- **Temperature 0.2** — deterministic scoring, not creative
- **Chain-of-thought** — "think step by step" improves accuracy
- **JSON schema in system prompt** — not user prompt
- **Candidate context dynamic** — built from cv_base at runtime
- **6 sub-scores required** — all categories must be present
- **Confidence score** — 0.0-1.0, calibrated against outcomes

## Tailoring prompt design principles

- **Temperature 0.4** — some creativity for rephrasing
- **Anti-hallucination rule verbatim** — never remove this
- **Anchor project rule** — uses anchor:true flag, not hardcoded
- **Incoming status rule** — generic, not name-specific

## Cover letter principles

- **Temperature 0.5** — more creative
- **250 word maximum** — enforced in system prompt
- **3-paragraph structure** — enforced
- **"passionate" banned** — explicitly in system prompt

## What not to do

- Do not hardcode candidate names, project names, or dates
- Do not increase temperature above 0.5 for structured output
- Do not remove the JSON schema from system prompt
- Do not skip the anti-hallucination rule in tailoring

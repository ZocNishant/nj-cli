---
description: Run scoring and anti-hallucination regression checks against tests/fixtures/
argument-hint: [--live]
allowed-tools: Bash(poetry run:*), Read, Grep, Glob
---

Evaluate whether the scoring and anti-hallucination behaviour still holds. Run
this after touching anything in `nj/prompts/`, `nj/scoring/`, or
`nj/tailoring/`, and before changing a model version.

Two tiers. The offline tier is free and always runs. The live tier costs money
and only runs when I passed `--live` in **$ARGUMENTS**.

## Tier 1 — offline (always)

These are the behavioural guarantees, pinned deterministically. No network.

```
poetry run pytest \
  tests/unit/test_anti_hallucination.py \
  tests/unit/test_drafter_reviewer.py \
  tests/unit/test_scoring.py \
  tests/unit/test_visa_filter.py \
  tests/unit/test_prompts.py \
  tests/unit/test_untrusted.py \
  -v --tb=short
```

What each one is actually protecting — say which guarantee broke, not just
which test failed:

- `test_anti_hallucination.py` — 19 cases over realistic CV shapes. Reorder,
  drop, and reword must pass; invented employer, title, institution, degree,
  project, certification, skill, and free-text claims must fail. A regression
  here means the pipeline can ship a fabricated claim.
- `test_drafter_reviewer.py` — the drafter-reviewer contract. The critical
  invariant is asymmetry: validator findings block, reviewer findings only
  advise, and a dead reviewer degrades to the validator rather than below it.
- `test_scoring.py` — score maths, the role-alignment cap, weighting.
- `test_visa_filter.py` — pins both historical failure directions (dropping
  employers who would sponsor, and keeping ones who say they will not).
- `test_prompts.py` / `test_untrusted.py` — prompt isolation. The CV lives in
  the system turn, the scraped posting in the user turn, and the fence defangs
  closing-tag escapes.

## Tier 2 — live fixtures (only with `--live`)

`tests/fixtures/scoring_regression/` holds 3 fixtures, each a real posting with
an expected score band. These make real Claude calls — roughly $0.05–0.10 a run.

```
NJ_RUN_REGRESSION_TESTS=true poetry run pytest \
  tests/integration/test_prompt_regression.py -v --tb=short
```

Needs `ANTHROPIC_API_KEY` in `.env`. If it is absent, say so and stop — do not
quietly report the offline tier as the whole result.

Scores are model output, so a single band miss is a signal, not a verdict. If
one fixture misses, report the delta and say whether it is directional (all
scores drifting the same way, which suggests a prompt or model change) or
isolated. Do not adjust a fixture's expected band to make it pass — that is
deleting the evidence.

## Coverage of the fixture set

Read `tests/fixtures/scoring_regression/*.json` and tell me what is *not*
covered. As of the last look the known gaps are: no fixture for a posting that
attempts prompt injection, and none for a role that should score low on
`role_alignment` and hit the score cap. If you spot others, name them.

## Report

- Tier 1: pass/fail per file, and for any failure the guarantee that broke.
- Tier 2: per fixture, expected band vs actual, and whether drift is
  directional. Say plainly if it did not run.
- One line: is the behaviour intact, and what needs attention.

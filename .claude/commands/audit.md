---
description: Run the full quality gate — lint, format, tests, schema drift, and a secrets scan
allowed-tools: Bash(poetry run:*), Bash(git status:*), Bash(git ls-files:*), Bash(git check-ignore:*), Bash(gitleaks:*), Read, Grep, Glob
---

Run every gate CI runs, plus the secret checks that only matter locally. Report
what failed; do not fix anything unless I ask.

Run these in order and keep going after a failure — I want the whole picture in
one pass, not the first thing that broke.

## 1. Lint and format

```
poetry run ruff check .
poetry run ruff format --check .
```

CI only checks `nj/ tests/`; check the whole tree, since `alembic/` is now part
of it.

## 2. Tests with the coverage ratchet

```
poetry run pytest tests/ --tb=short --cov=nj --cov-report=term-missing --cov-fail-under=55
```

`--cov-fail-under` is a ratchet set just under real coverage. If coverage has
risen meaningfully above it, say so and suggest the new floor — that is the
point of the ratchet.

## 3. Schema drift

```
poetry run alembic check
```

"No new upgrade operations detected" is the pass. Anything else means
`nj/db/models.py` moved without a migration; `alembic/README` has the fix.

## 4. Untracked secrets

The repo keeps real credentials in gitignored files. Verify none became tracked:

```
git ls-files --error-unmatch .env config.yaml cv/cv_base.json cv/profile.json .git-secret-replacements.txt 2>&1
```

Every one of those must report `did not match any file`. A path that *is*
tracked is the finding — report it loudly and stop, because the fix involves
history rewriting and is my call.

Then check nothing sensitive is staged or untracked-but-about-to-be-added:

```
git status --porcelain
```

Flag any new file matching `*.db`, `*.env*`, `*cookie*`, `*secret*`, `*.pem`,
`*token*`, or anything under `cv/` or `data/`.

## 5. Secrets in tracked content

If `gitleaks` is on PATH, run `gitleaks detect --no-banner --redact`. If it is
not installed, say so and skip it — CI runs it on every push, so this is an
early warning, not the authority.

Finally, use Grep over the tracked tree for credentials pasted inline rather
than read from the environment. Patterns: `sk-ant-`, `sk-proj-`, `AKIA`,
`li_at=`, and `api_key\s*=\s*["'][^"']{16,}`. Ignore matches in `.env.example`,
`config.example.yaml`, tests, and documentation — those are deliberately fake.

## Report

One short table: gate, pass/fail, and the specific first failure for each. Then
the single most important thing to fix. If everything passes, say so in one line
and give the test and coverage numbers — no summary of what you ran.

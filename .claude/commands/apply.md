---
description: Run the drafter-reviewer pipeline on one job — tailor, audit, compile, verify page budget, log
argument-hint: <job-url-or-job-id>
allowed-tools: Bash(poetry run:*), Read, Grep, Glob
---

Produce a tailored CV and cover letter for **$1** and tell me whether they are
fit to send.

This costs real API calls and writes to `data/nj.db`. If `$1` is empty, stop and
ask me for a job URL or an id from the database rather than guessing.

## What runs

`nj tailor` already wires the whole pipeline — drafter (Sonnet 5) → adversarial
reviewer (Haiku 4.5) → LaTeX render → page-budget check. Run it:

```
poetry run nj tailor "$1"
```

If `$1` looks like a job id rather than a URL (no `http`), look it up first.
`JobRepo` has no single-job getter, so filter the list:

```
poetry run python -c "
from nj.db.repos.job_repo import JobRepo
j = next((j for j in JobRepo('data/nj.db').get_jobs() if j.id == '$1'), None)
print(f'{j.title} @ {j.company}\n{j.url}' if j else 'NOT FOUND')
"
```

## What to check in the output

The pipeline is quiet when it works, so read the log lines rather than assuming.

1. **Did the reviewer run?** Look for `cv_review_complete` with
   `reviewer_ran=True`. If it is `False` the reviewer call failed and only the
   deterministic validator gated this CV — say so explicitly. That is a
   degraded run, not a clean one.

2. **Did it fall back?** `tailor_all_rounds_rejected_using_base` means every
   draft asserted something the base CV does not support, so what got rendered
   is the untailored base CV. The PDF is safe to send but is not tailored —
   tell me, because it looks fine and is not.

3. **Blocking vs advisory.** `blocking` findings come from
   `anti_hallucination.validate_tailored_cv` and are ground truth. `advisory`
   findings are the Haiku reviewer's judgement and can be wrong in either
   direction. Report the counts separately; never present an advisory finding
   as a proven hallucination.

4. **Page budget.** A `PageBudgetError` means the CV compiled past two pages.
   The PDF is still on disk at the path in the error. Open it, find what spilled,
   and tell me which bullet to cut — do not silently re-run with a larger budget.

5. **Did anything actually get written?** Check `output/` for the `.pdf`, the
   `.json`, and the `_cover.txt`. A missing PDF with no error usually means
   `templates/cv_template.tex` is empty or tectonic is not installed.

## Log the outcome

`nj tailor` does not record an application row — only `nj run` does. Record this
one so the daily cap and the outcome analytics stay honest:

```
poetry run python -c "
from nj.db.engine import init_db
from nj.db.repos.application_repo import ApplicationRepo
init_db('data/nj.db')
repo = ApplicationRepo('data/nj.db')
print(repo.count_today(), 'applications logged today')
"
```

Read `nj/db/repos/application_repo.py` for the exact method before writing a
row, and use the real CV and cover-letter paths from the run. Set the status to
pending, not applied — nothing was submitted. Submission is a human step; see
`nj/applying/linkedin_easy.py` for why.

## Report

- Score, and whether the CV was tailored or fell back to base.
- Blocking findings (count, and each one quoted) and advisory findings (count).
- Page count against the 2-page budget.
- Paths to the PDF and cover letter.
- One line: send it, or fix X first.

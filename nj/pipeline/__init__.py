"""Orchestration, extracted from the command modules.

`cmd_run.py` and `cmd_search.py` held 988 lines between them: scraping,
deduplication, ghost filtering, enrichment, scoring, tailoring, rendering,
gating, database writes and email. Because that logic lived inside a Typer
callback it was reachable in tests only through the CLI, which is why those two
files sat at 23% and 20% coverage while the services they called averaged above
90%.

It is also why the two drifted. Concurrent scoring was added to one, enrichment
to the other, skip-reason recording to the other again — so the choice of
command silently changed what a job got. Anything shared lives here now, and
the commands are argument parsing and Rich output.
"""

from nj.pipeline.ingest import IngestResult, IngestService
from nj.pipeline.scoring import ScoringService
from nj.pipeline.sources import build_scrapers

__all__ = ["IngestResult", "IngestService", "ScoringService", "build_scrapers"]

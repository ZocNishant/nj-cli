from __future__ import annotations

import asyncio
import random

from nj.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Caps applications per day and spaces them out.

    Pass `repo` (an ApplicationRepo) so the daily count is read from the
    database. Without it the counter lives only in this process, so the cap
    resets on every invocation and running `nj run` five times would allow
    five times the intended volume.
    """

    def __init__(
        self,
        delay_min: int = 30,
        delay_max: int = 90,
        max_per_day: int = 5,
        repo=None,
    ):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_per_day = max_per_day
        self.repo = repo
        self._applied_this_session = 0

    def applied_today(self) -> int:
        """Applications submitted today, across every process, when repo is set."""
        if self.repo is not None:
            try:
                return self.repo.count_today()
            except Exception as e:  # a counting failure must not unblock sending
                logger.warning("daily_count_failed", error=str(e))
                return self.max_per_day
        return self._applied_this_session

    def can_apply(self) -> bool:
        return self.applied_today() < self.max_per_day

    def record_application(self) -> None:
        self._applied_this_session += 1
        logger.info(
            "application_recorded",
            today=self.applied_today(),
            max=self.max_per_day,
        )

    async def wait(self) -> None:
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.info("rate_limit_wait", seconds=round(delay, 1))
        await asyncio.sleep(delay)

    def remaining_today(self) -> int:
        return max(0, self.max_per_day - self.applied_today())

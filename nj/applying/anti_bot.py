from __future__ import annotations

import asyncio
import random

from nj.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    def __init__(
        self,
        delay_min: int = 30,
        delay_max: int = 90,
        max_per_day: int = 5,
    ):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_per_day = max_per_day
        self._applied_today = 0

    def can_apply(self) -> bool:
        return self._applied_today < self.max_per_day

    def record_application(self) -> None:
        self._applied_today += 1
        logger.info(
            "application_recorded",
            today=self._applied_today,
            max=self.max_per_day,
        )

    async def wait(self) -> None:
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.info("rate_limit_wait", seconds=round(delay, 1))
        await asyncio.sleep(delay)

    def remaining_today(self) -> int:
        return max(0, self.max_per_day - self._applied_today)

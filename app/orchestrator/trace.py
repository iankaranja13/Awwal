"""In-memory workflow trace recorder (one per pipeline run)."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.core.clock import utc_now


@dataclass(frozen=True)
class StepRecord:
    """One recorded pipeline step."""

    name: str
    status: str
    started_at: str
    duration_ms: float
    rules_version: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceRecorder:
    """Collect timed pipeline steps for one run."""

    rules_version: str
    steps: list[StepRecord] = field(default_factory=list)

    @contextmanager
    def timed(self, name: str) -> Iterator[dict[str, Any]]:
        """Time one pipeline step, recording errors before re-raising.

        Args:
            name: Step name.

        Yields:
            Mutable detail mapping recorded at exit (never sensitive content).
        """
        detail: dict[str, Any] = {}
        started = utc_now().isoformat()
        begun = time.perf_counter()
        try:
            yield detail
        except Exception:
            duration_ms = round((time.perf_counter() - begun) * 1000.0, 3)
            self.steps.append(
                StepRecord(
                    name=name,
                    status="error",
                    started_at=started,
                    duration_ms=duration_ms,
                    rules_version=self.rules_version,
                    detail=detail,
                )
            )
            raise
        duration_ms = round((time.perf_counter() - begun) * 1000.0, 3)
        self.steps.append(
            StepRecord(
                name=name,
                status="ok",
                started_at=started,
                duration_ms=duration_ms,
                rules_version=self.rules_version,
                detail=detail,
            )
        )

    def skipped(self, name: str, detail: dict[str, Any] | None = None) -> None:
        """Record one skipped pipeline step.

        Args:
            name: Step name.
            detail: Step detail (never sensitive content).
        """
        self.steps.append(
            StepRecord(
                name=name,
                status="skipped",
                started_at=utc_now().isoformat(),
                duration_ms=0.0,
                rules_version=self.rules_version,
                detail=detail or {},
            )
        )

    def duration_ms(self) -> float:
        """Sum recorded step durations.

        Returns:
            Total milliseconds across steps.
        """
        return round(sum(step.duration_ms for step in self.steps), 3)

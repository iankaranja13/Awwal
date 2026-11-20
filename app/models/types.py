"""Custom SQLAlchemy column types."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator


class AwareDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every backend.

    PostgreSQL stores the zone; SQLite drops it, so values are normalised
    back to aware UTC on read. Naive values are assumed to be UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Attach UTC to naive values before storage.

        Args:
            value: Value being stored.
            dialect: Active dialect (unused).

        Returns:
            The value with UTC attached when naive.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Attach UTC to naive values after loading.

        Args:
            value: Value loaded from storage.
            dialect: Active dialect (unused).

        Returns:
            The value with UTC attached when naive.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

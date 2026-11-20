"""Database engine, sessions and request dependency."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_for(database_url: str) -> Engine:
    """Create a SQLAlchemy engine for the database URL.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        Configured engine (connects lazily on first use).
    """
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the engine.

    Args:
        engine: Bound engine.

    Returns:
        Session factory with commits managed per request.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """Yield one transactional session per request.

    The transaction commits when the endpoint returns and rolls back on
    any error, so services only flush and never commit.

    Args:
        request: Incoming request carrying the session factory.

    Yields:
        Request-scoped database session.
    """
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

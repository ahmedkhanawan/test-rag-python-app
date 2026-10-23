from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import init_db, make_engine


@pytest.fixture
def engine():
    engine = make_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """The login and chat limiters are process-wide state; keep tests independent."""
    from app.api.auth import login_limiter
    from app.api.chat import chat_limiter

    login_limiter.reset()
    chat_limiter.reset()
    yield
    login_limiter.reset()
    chat_limiter.reset()

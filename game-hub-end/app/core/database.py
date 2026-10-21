"""SQLAlchemy database setup and session helpers."""

from contextlib import contextmanager
from typing import Any, Generator, Optional, Tuple

from sqlalchemy import BigInteger, create_engine, event, inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings
from app.core.id_utils import generate_server_id
from app.core.time_utils import now_ms


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TimestampMixin:
    """Common millisecond timestamp columns for persisted entities."""

    __abstract__ = True

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """
    Provide a request-scoped SQLAlchemy session for FastAPI dependencies.
    :yield: SQLAlchemy ``Session``.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional SQLAlchemy session outside request handling.
    :yield: SQLAlchemy ``Session``.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def isolated_write(session: Session) -> Generator[None, None, None]:
    """在请求事务内隔离一次写入；保证 SQLite SAVEPOINT 不提前提交外层事务。"""
    connection = session.connection()
    if connection.dialect.name == "sqlite":
        driver_connection = connection.connection.driver_connection
        if not driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
    with session.begin_nested():
        yield


def _import_all_models() -> None:
    """
    Import all ORM model modules so ``Base.metadata`` contains every table.
    Keep imports local to avoid eager service initialization at module import time.
    """
    import app.modules.game_config.models as _game_models  # noqa: F401
    import app.modules.inventory.models as _inventory_models  # noqa: F401
    import app.modules.match.models as _match_models  # noqa: F401
    import app.modules.prop.models as _prop_models  # noqa: F401
    import app.modules.purchase.models as _purchase_models  # noqa: F401
    import app.modules.score.models as _score_models  # noqa: F401
    import app.modules.sync.models as _sync_models  # noqa: F401
    import app.modules.system.models as _system_models  # noqa: F401
    import app.modules.user.models as _user_models  # noqa: F401
    import app.modules.wallet.models as _wallet_models  # noqa: F401
    import app.modules.room.game_settlement_models as _game_settlement_models  # noqa: F401


def init_db() -> None:
    """Create every declared ORM table."""
    _import_all_models()
    Base.metadata.create_all(bind=engine)


def _updated_at_was_explicitly_set(obj: Any) -> bool:
    """
    Check whether ``updated_at`` was set explicitly before flush.
    ORM merges may intentionally carry a caller-provided ``updatedAt`` for LWW
    conflict resolution; in that case the automatic timestamp must not overwrite it.
    :param obj: ORM entity.
    :return: ``True`` when ``updated_at`` has pending changes.
    """
    state = sa_inspect(obj)
    return state.attrs.updated_at.history.has_changes()


@event.listens_for(Session, "before_flush")
def _stamp_timestamps(session: Session, flush_context: Any, instances: Any) -> None:
    """
    Stamp ``created_at`` and ``updated_at`` before ORM flush.
    New rows receive both timestamps when missing. Dirty rows receive a fresh
    ``updated_at`` unless the caller already set one explicitly for LWW semantics.
    """
    now = now_ms()
    for obj in list(session.new):
        if isinstance(obj, TimestampMixin):
            if hasattr(obj, "server_id") and not getattr(obj, "server_id", None):
                raise ValueError("Persisted entity must have server_id")
            if obj.created_at is None or obj.created_at == 0:
                obj.created_at = now
            if obj.updated_at is None or obj.updated_at == 0:
                obj.updated_at = now
    for obj in list(session.dirty):
        if isinstance(obj, TimestampMixin):
            if _updated_at_was_explicitly_set(obj):
                continue
            obj.updated_at = now


def new_entity_ids(prefix: str) -> Tuple[str, int, int]:
    """
    Generate a server id and paired create/update timestamps.
    :param prefix: Prefix passed to ``generate_server_id``.
    :return: ``(server_id, created_at, updated_at)``.
    """
    sid = generate_server_id(prefix)
    ts = now_ms()
    return sid, ts, ts

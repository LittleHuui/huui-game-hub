"""SQLAlchemy 引擎、会话与通用时间戳混入。"""

from contextlib import contextmanager
from typing import Any, Generator, Optional, Tuple

from sqlalchemy import BigInteger, create_engine, event, inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings
from app.core.id_utils import generate_server_id
from app.core.time_utils import now_ms


class Base(DeclarativeBase):
    """声明式映射基类。"""


class TimestampMixin:
    """通用时间戳字段混入（Unix 毫秒 + 软删除）。"""

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
    FastAPI 依赖：提供请求级数据库会话。

    :yield: SQLAlchemy ``Session``。
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
    非 Web 场景使用的会话上下文管理器。

    :yield: SQLAlchemy ``Session``。
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


def _import_all_models() -> None:
    """
    导入所有 ORM 模块以注册 ``metadata``。

    仅负责装载模型类映射，不做业务初始化、不调用 service、不执行 seed。
    """
    import app.modules.game.models as _game_models  # noqa: F401
    import app.modules.inventory.models as _inventory_models  # noqa: F401
    import app.modules.match.models as _match_models  # noqa: F401
    import app.modules.prop.models as _prop_models  # noqa: F401
    import app.modules.purchase.models as _purchase_models  # noqa: F401
    import app.modules.score.models as _score_models  # noqa: F401
    import app.modules.sync.models as _sync_models  # noqa: F401
    import app.modules.system.models as _system_models  # noqa: F401
    import app.modules.user.models as _user_models  # noqa: F401
    import app.modules.wallet.models as _wallet_models  # noqa: F401


def init_db() -> None:
    """创建所有已注册映射对应的数据库表。"""
    _import_all_models()
    Base.metadata.create_all(bind=engine)


def _updated_at_was_explicitly_set(obj: Any) -> bool:
    """
    判断 ``updated_at`` 是否已在本次会话中被业务代码显式赋值。

    状态类同步 merge 会写入事件的 ``updatedAt``；不得被 flush 时刻的服务端时间覆盖。

    :param obj: ORM 实例。
    :return: 若 ``updated_at`` 相对加载状态有变更则返回 ``True``。
    """
    state = sa_inspect(obj)
    return state.attrs.updated_at.history.has_changes()


@event.listens_for(Session, "before_flush")
def _stamp_timestamps(session: Session, flush_context: Any, instances: Any) -> None:
    """
    在 flush 前自动填充创建/更新时间戳（毫秒）。

    新建记录补 ``created_at`` / ``updated_at``；更新记录仅在未显式修改 ``updated_at`` 时写入 ``now_ms()``，
    以便状态类同步 LWW 保留事件时间而非 ORM flush 时间。
    """
    now = now_ms()
    for obj in list(session.new):
        if isinstance(obj, TimestampMixin):
            if hasattr(obj, "server_id") and not getattr(obj, "server_id", None):
                raise ValueError("持久化前必须设置 server_id")
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
    为新实体生成 server_id 与时间戳元组。

    :param prefix: 传给 ``generate_server_id`` 的前缀。
    :return: ``(server_id, created_at, updated_at)``。
    """
    sid = generate_server_id(prefix)
    ts = now_ms()
    return sid, ts, ts

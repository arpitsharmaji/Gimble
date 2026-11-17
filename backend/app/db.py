from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

_sqlite = settings.DATABASE_URL.startswith("sqlite")
_kwargs = {"pool_pre_ping": True}
if not _sqlite:  # managed Postgres: keep a small pool and recycle connections before the provider drops them
    _kwargs.update(pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW, pool_recycle=1800)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _sqlite else {},
    **_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

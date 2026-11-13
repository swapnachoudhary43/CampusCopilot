"""SQLAlchemy engine and sessions.

SQLite does not enforce foreign keys unless PRAGMA foreign_keys=ON.
The connect listener turns that on for every new connection.
"""

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None
_url = None


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    # The listener runs for every engine. Non-SQLite drivers do not use this pragma.
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        return


def get_engine():
    global _engine, _session_factory, _url
    url = get_settings().database_file_url
    if _engine is None or url != _url:
        if _engine is not None:
            _engine.dispose()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args)
        _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        _url = url
    return _engine


def get_session_factory():
    get_engine()
    return _session_factory


def reset_database_state():
    """Drop the cached engine so tests can point at a fresh database file."""
    global _engine, _session_factory, _url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _url = None


def _ensure_columns() -> None:
    """Add columns introduced after the first SQLite file was created.

    create_all does not alter an existing table. These fields record where a
    document came from and which operational rows are demonstration data.
    """
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        return
    additions = {
        "users": {"is_demo": "BOOLEAN NOT NULL DEFAULT 0"},
        "documents": {
            "source_url": "VARCHAR(500)",
            "source_page_url": "VARCHAR(500)",
            "publication_date": "VARCHAR(160)",
            "retrieved_at": "DATETIME",
            "provenance": "VARCHAR(40) NOT NULL DEFAULT 'uploaded'",
        },
        "complaints": {"is_demo": "BOOLEAN NOT NULL DEFAULT 0"},
        "events": {"is_demo": "BOOLEAN NOT NULL DEFAULT 0"},
        "notices": {
            "source_url": "VARCHAR(500)",
            "provenance": "VARCHAR(40) NOT NULL DEFAULT 'admin'",
        },
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table, columns in additions.items():
            if table not in existing_tables:
                continue
            present = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db():
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    # Importing entities registers every table on Base.metadata.
    import app.models.entities  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    _ensure_columns()


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

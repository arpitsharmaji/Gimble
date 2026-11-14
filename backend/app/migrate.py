"""Tiny additive migrator: adds columns that exist in the models but not yet in the database.

Lets a v2 database upgrade in place. It never drops or alters anything. For anything bigger
(renames, type changes) adopt Alembic.
"""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import MetaData

log = logging.getLogger("gimble.migrate")


def _default_sql(col, dialect: str) -> str:
    d = col.default.arg if col.default is not None and col.default.is_scalar else None
    if d is None:
        return ""
    if isinstance(d, bool):
        return " DEFAULT " + ("TRUE" if d else "FALSE")
    if isinstance(d, (int, float)):
        return f" DEFAULT {d}"
    return " DEFAULT '" + str(d).replace("'", "''") + "'"


def ensure_columns(engine: Engine, metadata: MetaData) -> list[str]:
    added = []
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all handles whole new tables
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}{_default_sql(col, engine.dialect.name)}'
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    if added:
        log.warning("Added missing columns: %s", ", ".join(added))
    return added

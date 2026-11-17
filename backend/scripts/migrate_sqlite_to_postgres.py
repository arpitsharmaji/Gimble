#!/usr/bin/env python3
"""One-time copy of an existing SQLite database into PostgreSQL, keeping every id (so bookings, messages and photos stay linked).

    python scripts/migrate_sqlite_to_postgres.py sqlite:///./gimble.db "postgres://user:pass@host:5432/dbname"

* Make a copy of your .db file first (the source is upgraded in place to the latest schema before copying).
* The target database must be empty of users. Run it once, then point DATABASE_URL at PostgreSQL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, select, text  # noqa: E402
from app.config import _normalise_db_url  # noqa: E402
from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401  (registers all tables)
from app.migrate import ensure_columns  # noqa: E402


def main(src_url: str, dst_url: str) -> None:
    src, dst = create_engine(src_url), create_engine(_normalise_db_url(dst_url))
    if dst.dialect.name != "postgresql":
        sys.exit("Target must be a PostgreSQL URL")
    print("Upgrading source schema (additive only)…")
    ensure_columns(src, Base.metadata)
    Base.metadata.create_all(dst)
    with dst.connect() as c:
        if c.execute(text("SELECT COUNT(*) FROM users")).scalar():
            sys.exit("Target database already has users - refusing to overwrite. Use an empty database.")
    have = set(inspect(src).get_table_names())
    total = 0
    with src.connect() as s, dst.begin() as d:
        for table in Base.metadata.sorted_tables:          # parents before children (foreign keys)
            if table.name not in have:
                continue
            src_cols = {c["name"] for c in inspect(src).get_columns(table.name)}
            cols = [c for c in table.columns if c.name in src_cols]
            rows = [dict(r) for r in s.execute(select(*cols)).mappings()]
            for i in range(0, len(rows), 500):
                d.execute(table.insert(), rows[i:i + 500])
            total += len(rows)
            print(f"  {table.name:<20} {len(rows):>6} rows")
        for table in Base.metadata.sorted_tables:          # make future inserts continue after the highest copied id
            if "id" in table.c and table.c.id.primary_key:
                d.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), COALESCE((SELECT MAX(id) FROM {table.name}), 1), "
                               f"(SELECT MAX(id) FROM {table.name}) IS NOT NULL)"))
    print(f"Done. Copied {total} rows. Now set DATABASE_URL to the PostgreSQL URL and restart.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

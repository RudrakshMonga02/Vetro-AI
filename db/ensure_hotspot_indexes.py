"""Idempotently add the indexes used by the hotspot intelligence endpoint.

Run once against an existing PostgreSQL database:
    venv\\Scripts\\python.exe -m db.ensure_hotspot_indexes

New databases receive equivalent indexes through db.models metadata. Existing
tables need this script because SQLAlchemy create_all() does not alter tables.
"""
from sqlalchemy import text

from db.connection import engine


INDEX_STATEMENTS = (
    '''CREATE INDEX IF NOT EXISTS idx_case_master_incident_date
       ON case_master ("IncidentFromDate")''',
    '''CREATE INDEX IF NOT EXISTS idx_case_master_coordinates
       ON case_master (latitude, longitude)
       WHERE latitude IS NOT NULL''',
)


def ensure_hotspot_indexes() -> None:
    with engine.begin() as connection:
        for statement in INDEX_STATEMENTS:
            connection.execute(text(statement))
    print("Hotspot indexes are present.")


if __name__ == "__main__":
    ensure_hotspot_indexes()

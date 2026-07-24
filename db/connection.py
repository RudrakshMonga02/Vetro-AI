"""
Central place for the DB engine/session. Reads DATABASE_URL from .env.
Swapping Postgres -> Catalyst Data Store later should only mean changing
this connection string (assuming Data Store speaks standard SQL over a
Postgres-compatible or generic SQL driver -- confirm this against
Catalyst's docs before the swap).
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:devpass@localhost:5432/ksp_datathon",
)

engine = create_engine(
    DATABASE_URL,
    future=True,
    # Verify a connection before reuse so a stale Supabase/Postgres socket is
    # discarded instead of surfacing as "server closed the connection" mid-call.
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    return SessionLocal()

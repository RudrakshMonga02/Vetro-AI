"""Creates all tables from models.py. Safe to re-run (checkfirst=True)."""
from db.connection import engine
from db.models import Base


def init_db():
    Base.metadata.create_all(engine, checkfirst=True)
    print("All tables created (or already existed).")


if __name__ == "__main__":
    init_db()

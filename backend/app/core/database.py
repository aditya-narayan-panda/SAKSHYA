from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import DATABASE_URL
from app.models.models import Base, install_append_only_guards

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    install_append_only_guards(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

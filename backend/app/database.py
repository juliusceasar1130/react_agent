from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker
from .models import Base

engine = create_engine(
    "sqlite:///./research_agent.db",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 首次调用创建表
# 之后调用不会重复创建
def create_tables():

    Base.metadata.create_all(bind=engine)

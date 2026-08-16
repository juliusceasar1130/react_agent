from sqlalchemy import create_engine, text

from sqlalchemy.orm import sessionmaker
from .models import Base
from .config import settings

engine = create_engine(
    settings.database_url,
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

    # 幂等迁移：create_all 不会为已存在的表补列，这里用 PG 的 IF NOT EXISTS 补全新列
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE chat_messages "
                "ADD COLUMN IF NOT EXISTS subagents TEXT"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE chat_messages "
                "ADD COLUMN IF NOT EXISTS tool_artifacts TEXT"
            )
        )

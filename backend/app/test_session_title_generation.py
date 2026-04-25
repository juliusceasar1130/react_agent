from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud
from backend.app.models import Base
from backend.app.schemas import MessageCreate, SessionCreate


def _build_test_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session_local()


def test_first_user_message_promotes_session_title() -> None:
    db = _build_test_db_session()
    try:
        session = crud.create_session(db, SessionCreate(title="新对话"))

        crud.create_message(
            db,
            MessageCreate(
                session_id=session.id,
                role="user",
                content="请帮我分析昨天喷涂缺陷趋势，并给出重点结论",
            ),
        )

        updated_session = crud.get_session(db, session.id)
        assert updated_session is not None
        assert updated_session.title == "请帮我分析昨天喷涂缺陷趋势，并给出重点结论"
    finally:
        db.close()


def test_second_user_message_does_not_override_existing_title() -> None:
    db = _build_test_db_session()
    try:
        session = crud.create_session(db, SessionCreate(title="新对话"))

        crud.create_message(
            db,
            MessageCreate(
                session_id=session.id,
                role="user",
                content="第一个问题",
            ),
        )
        crud.create_message(
            db,
            MessageCreate(
                session_id=session.id,
                role="user",
                content="第二个问题不应该覆盖标题",
            ),
        )

        updated_session = crud.get_session(db, session.id)
        assert updated_session is not None
        assert updated_session.title == "第一个问题"
    finally:
        db.close()


def test_legacy_placeholder_title_and_multiline_message_are_supported() -> None:
    db = _build_test_db_session()
    try:
        session = crud.create_session(db, SessionCreate(title="新会话"))

        crud.create_message(
            db,
            MessageCreate(
                session_id=session.id,
                role="user",
                content="  第一行问题 \n\n 第二行补充说明，内容比较长需要截断展示，并且继续追加更多描述用于验证省略号逻辑  ",
            ),
        )

        updated_session = crud.get_session(db, session.id)
        assert updated_session is not None
        assert updated_session.title.startswith("第一行问题 第二行补充说明")
        assert updated_session.title.endswith("...")
        assert len(updated_session.title) == crud.SESSION_TITLE_MAX_LENGTH
    finally:
        db.close()

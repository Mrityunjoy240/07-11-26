from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import settings
from src.storage.interfaces import ConversationMessage, ConversationStore

Base = declarative_base()


class ConversationModel(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    student_id = Column(String, nullable=True)
    title = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class PostgresConversationStore(ConversationStore):
    def __init__(self, dsn: str | None = None):
        self._engine = create_engine(
            dsn or settings.postgres_dsn,
            pool_size=settings.postgres_pool_size,
        )
        self._SessionLocal = sessionmaker(bind=self._engine)

    def init_db(self):
        Base.metadata.create_all(self._engine)

    async def save_message(self, conversation_id: str, message: ConversationMessage) -> None:
        with self._SessionLocal() as session:
            msg = MessageModel(
                conversation_id=conversation_id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            session.add(msg)
            session.commit()

    async def get_messages(self, conversation_id: str) -> list[ConversationMessage]:
        with self._SessionLocal() as session:
            rows = (
                session.query(MessageModel)
                .filter(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.created_at)
                .all()
            )
            return [
                ConversationMessage(role=r.role, content=r.content, created_at=r.created_at)
                for r in rows
            ]

    async def create_conversation(
        self, conversation_id: str, student_id: str | None = None
    ) -> None:
        with self._SessionLocal() as session:
            conv = ConversationModel(id=conversation_id, student_id=student_id)
            session.add(conv)
            session.commit()

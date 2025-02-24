import uuid
from database import Base
from sqlalchemy import UUID, CheckConstraint, Column, ForeignKey, Boolean, Integer, String, DateTime, func, inspect


class Flashcards(Base):
    __tablename__ = 'flashcards'

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    subject_id = Column(UUID(as_uuid=True), ForeignKey('subjects.id'))
    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id'))
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    difficulty = Column(Integer, nullable=False)
    last_response = Column(Boolean, default=None)
    opened = Column(Boolean, default=True)
    image_url = Column(String)
    origin = Column(String, nullable=False, default="user")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime)

    __table_args__ = (
        CheckConstraint("origin IN ('user', 'ai')", name='check_origin_valid_values'),
    )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
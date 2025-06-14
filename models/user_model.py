from datetime import timezone
import uuid
from database import Base
from sqlalchemy import Column, Enum, Integer, String, Boolean, DateTime, func, inspect
from sqlalchemy.dialects.postgresql import UUID 
from sqlalchemy.orm import relationship


class Users(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    google_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    account_type = Column(Integer, nullable=False, default=0)
    is_admin = Column(Boolean, default=False, nullable=False)
    refresh_token = Column(String, nullable=True)
    last_reset_date = Column(DateTime)
    credits = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now())
    deleted_at = Column(DateTime)

    subscriptions = relationship("SubscriptionModel", back_populates="user")

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
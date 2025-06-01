import uuid
from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, ForeignKey, Text, func, inspect
from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy.dialects.postgresql import UUID 


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    package_name = Column(String(255), nullable=False)
    purchase_token = Column(Text, nullable=False, unique=True)
    product_id = Column(String(255), nullable=False)
    
    start_date = Column(DateTime(timezone=True), nullable=False)
    expiration_date = Column(DateTime(timezone=True), nullable=False)
    
    subscription_state = Column(String(100), nullable=False)
    latest_order_id = Column(String(255), nullable=True)
    region_code = Column(String(10), nullable=True)
    auto_renewing = Column(Boolean, default=False)
    acknowledgement_state = Column(String(100), nullable=True)
    
    currency_code = Column(String(10), nullable=True)
    price_nanos = Column(BigInteger, nullable=True)
    
    base_plan_id = Column(String(255), nullable=True)
    linked_purchase_token = Column(Text, nullable=True)
    original_json = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    user = relationship("Users", back_populates="subscriptions")

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
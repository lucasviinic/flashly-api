import uuid
from database import Base
from sqlalchemy import UUID, Column, ForeignKey, String, DateTime, func, inspect, Integer, Text
from sqlalchemy.orm import relationship


class Survey(Base):
    __tablename__ = 'surveys'

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(20), default='active')
    winner_option_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now())
    deleted_at = Column(DateTime)

    options = relationship("SurveyOption", back_populates="survey", cascade="all, delete-orphan")
    votes = relationship("SurveyVote", back_populates="survey", cascade="all, delete-orphan")

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}

    def to_dict_with_options(self):
        data = self.to_dict()
        data['options'] = []
        
        for option in self.options:
            option_data = option.to_dict()
            option_data['vote_count'] = len(option.votes)
            data['options'].append(option_data)
        
        data['total_votes'] = sum(len(option.votes) for option in self.options)
        return data


class SurveyOption(Base):
    __tablename__ = 'survey_options'

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    emoji = Column(String(10))
    order_position = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now())
    deleted_at = Column(DateTime)

    survey = relationship("Survey", back_populates="options")
    votes = relationship("SurveyVote", back_populates="option", cascade="all, delete-orphan")

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


class SurveyVote(Base):
    __tablename__ = 'survey_votes'

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"), nullable=False)
    option_id = Column(UUID(as_uuid=True), ForeignKey("survey_options.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    voted_at = Column(DateTime, default=func.now())

    survey = relationship("Survey", back_populates="votes")
    option = relationship("SurveyOption", back_populates="votes")

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}



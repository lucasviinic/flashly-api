from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class SurveyOptionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    emoji: Optional[str] = None
    order_position: int = 0


class CreateSurveyRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    options: List[SurveyOptionRequest] = Field(..., min_items=2, max_items=10)


class VoteRequest(BaseModel):
    option_id: UUID


class SurveyOptionResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    emoji: Optional[str]
    order_position: int
    vote_count: int
    percentage: float


class SurveyResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    status: str
    total_votes: int
    user_has_voted: bool
    user_voted_option_id: Optional[UUID]
    winner_option_id: Optional[UUID]
    options: List[SurveyOptionResponse]
    created_at: datetime
    updated_at: datetime


class SurveyListResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    status: str
    total_votes: int
    user_has_voted: bool


class SurveyFeedbackRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class SurveyFeedbackResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    status: str
    votes_received: int
    created_at: datetime
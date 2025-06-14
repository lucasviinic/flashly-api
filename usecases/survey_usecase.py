from datetime import datetime
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from models.survey_model import Survey, SurveyOption, SurveyVote
from models.user_model import Users
from schemas.survey_schemas import (
    CreateSurveyRequest,
    VoteRequest,
    SurveyResponse, 
    SurveyOptionResponse
)


class SurveyUseCase:
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_current_survey(self, user_id: UUID) -> SurveyResponse:
        current_survey = self.db.query(Survey).filter(
            and_(
                Survey.status == 'active',
                Survey.start_date <= datetime.now(),
                Survey.end_date >= datetime.now(),
                Survey.deleted_at.is_(None)
            )
        ).first()
        
        if not current_survey:
            return None
        
        return self._build_survey_response(current_survey, user_id)
    
    def vote_survey(self, user_id: UUID, vote_data: VoteRequest) -> dict:
        option = self.db.query(SurveyOption).filter(
            and_(
                SurveyOption.id == vote_data.option_id,
                SurveyOption.deleted_at.is_(None)
            )
        ).first()
        
        if not option:
            raise ValueError("Invalid option")
        
        survey = self.db.query(Survey).filter(
            and_(
                Survey.id == option.survey_id,
                Survey.status == 'active',
                Survey.start_date <= datetime.now(),
                Survey.end_date >= datetime.now(),
                Survey.deleted_at.is_(None)
            )
        ).first()
        
        if not survey:
            raise ValueError("Survey is not active or not found")
        
        existing_vote = self.db.query(SurveyVote).filter(
            and_(
                SurveyVote.survey_id == survey.id,
                SurveyVote.user_id == user_id
            )
        ).first()
        
        if existing_vote:
            raise ValueError("User has already voted in this survey")
        
        new_vote = SurveyVote(
            survey_id=survey.id,
            option_id=vote_data.option_id,
            user_id=user_id,
            voted_at=datetime.now()
        )
        
        self.db.add(new_vote)
        
        survey.updated_at = datetime.now()
        
        self.db.commit()
        
        return {"message": "Vote recorded successfully"}
    
    def get_survey_by_id(self, survey_id: UUID, user_id: UUID) -> SurveyResponse:
        survey = self.db.query(Survey).filter(
            and_(
                Survey.id == survey_id,
                Survey.deleted_at.is_(None)
            )
        ).first()
        
        if not survey:
            return None
        
        return self._build_survey_response(survey, user_id)
    
    def create_survey(self, survey_data: CreateSurveyRequest, user_id: str) -> SurveyResponse:
        user = self.db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()

        if not user.is_admin:
            raise HTTPException(status_code=404, detail='Admin access required')

        active_survey = self.db.query(Survey).filter(
            and_(
                Survey.status == 'active',
                Survey.deleted_at.is_(None)
            )
        ).first()
        
        if active_survey:
            self._finish_survey_automatically(active_survey)
        
        new_survey = Survey(
            title=survey_data.title,
            description=survey_data.description,
            start_date=survey_data.start_date,
            end_date=survey_data.end_date,
            status='active',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.db.add(new_survey)
        self.db.flush()
        
        for i, option_data in enumerate(survey_data.options):
            new_option = SurveyOption(
                survey_id=new_survey.id,
                title=option_data.title,
                description=option_data.description,
                emoji=option_data.emoji,
                order_position=option_data.order_position or i,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.db.add(new_option)
        
        self.db.commit()
        
        return self.get_survey_by_id(new_survey.id, None)
    
    def _build_survey_response(self, survey: Survey, user_id: UUID) -> SurveyResponse:
        user_vote = None
        if user_id:
            user_vote = self.db.query(SurveyVote).filter(
                and_(
                    SurveyVote.survey_id == survey.id,
                    SurveyVote.user_id == user_id
                )
            ).first()
        
        options_data = []
        total_votes = 0
        
        for option in survey.options:
            vote_count = self.db.query(SurveyVote).filter(
                SurveyVote.option_id == option.id
            ).count()
            
            total_votes += vote_count
            
            options_data.append({
                'option': option,
                'vote_count': vote_count
            })
        
        survey_options = []
        for data in options_data:
            percentage = (data['vote_count'] / total_votes * 100) if total_votes > 0 else 0
            
            survey_options.append(SurveyOptionResponse(
                id=data['option'].id,
                title=data['option'].title,
                description=data['option'].description,
                emoji=data['option'].emoji,
                order_position=data['option'].order_position,
                vote_count=data['vote_count'],
                percentage=round(percentage, 1)
            ))
        
        survey_options.sort(key=lambda x: x.order_position)
        
        return SurveyResponse(
            id=survey.id,
            title=survey.title,
            description=survey.description,
            start_date=survey.start_date,
            end_date=survey.end_date,
            status=survey.status,
            total_votes=total_votes,
            user_has_voted=user_vote is not None,
            user_voted_option_id=user_vote.option_id if user_vote else None,
            winner_option_id=survey.winner_option_id,
            options=survey_options,
            created_at=survey.created_at,
            updated_at=survey.updated_at
        )
    
    def _finish_survey_automatically(self, survey: Survey):
        winner_option = self.db.query(SurveyOption)\
            .join(SurveyVote, SurveyOption.id == SurveyVote.option_id)\
            .filter(SurveyOption.survey_id == survey.id)\
            .group_by(SurveyOption.id)\
            .order_by(desc(func.count(SurveyVote.id)))\
            .first()
        
        survey.status = 'finished'
        survey.winner_option_id = winner_option.id if winner_option else None
        survey.updated_at = datetime.now()
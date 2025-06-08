from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from database import db_dependency
from models.flashcard_model import Flashcards
from models.requests_model import SubjectRequest
from models.session_model import Sessions
from models.subject_model import Subjects
from models.subscription_model import SubscriptionModel
from models.topic_model import Topics
from models.user_model import Users
from services.limit_service import LimitService
from services.subscription_service import SubscriptionService, GooglePlaySubscriptionError


class SubjectsUseCase:
    def __init__(self, db: db_dependency, user_id: str = None):
        self.db = db
        self.user_id = user_id
        self.subscription_service = SubscriptionService()

    def _get_user_subscription(self) -> Optional[SubscriptionModel]:
        return self.db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == self.user_id,
            SubscriptionModel.is_active == True,
            SubscriptionModel.deleted_at.is_(None)
        ).first()

    def _verify_and_update_subscription(self, subscription: SubscriptionModel) -> bool:
        try:
            subscription_data, status_info = self.subscription_service.get_complete_subscription_info(
                subscription.package_name,
                subscription.purchase_token
            )
            
            subscription.subscription_state = subscription_data.subscription_state.value
            subscription.expiration_date = subscription_data.expiration_date
            subscription.auto_renewing = subscription_data.auto_renewing
            subscription.is_active = status_info.is_active
            subscription.updated_at = datetime.now(timezone.utc)
            
            if subscription_data.price:
                subscription.currency_code = subscription_data.price.currency_code
                subscription.price_nanos = subscription_data.price.nanos
            
            self.db.commit()
            
            return status_info.is_active
            
        except GooglePlaySubscriptionError:
            subscription.is_active = False
            subscription.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return False

    def _determine_user_account_type(self, user: Users) -> int:
        subscription = self._get_user_subscription()
        
        if not subscription:
            return 0
            
        is_active = self._verify_and_update_subscription(subscription)
        
        return 1 if is_active else 0
    
    def _get_statistics(self) -> dict:        
        total_cards = self.db.query(func.count(Flashcards.id)).filter(
            Flashcards.user_id == self.user_id,
            Flashcards.deleted_at.is_(None)
        ).scalar() or 0
        
        sessions = self.db.query(Sessions.total_time_spent).filter(
            Sessions.user_id == self.user_id,
            Sessions.deleted_at.is_(None)
        ).all()
        
        total_seconds = 0
        for session in sessions:
            time_str = session.total_time_spent
            if time_str:
                try:
                    time_parts = time_str.split(':')
                    hours = int(time_parts[0])
                    minutes = int(time_parts[1])
                    seconds = int(time_parts[2])
                    total_seconds += hours * 3600 + minutes * 60 + seconds
                except (ValueError, IndexError):
                    continue
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        time_spend = f"{hours:02d}h {minutes:02d}m"
        
        sessions_stats = self.db.query(
            func.sum(Sessions.correct_answer_count).label('total_correct'),
            func.sum(Sessions.total_questions).label('total_questions')
        ).filter(
            Sessions.user_id == self.user_id,
            Sessions.deleted_at.is_(None)
        ).first()
        
        accuracy = 0.0
        if sessions_stats and sessions_stats.total_questions and sessions_stats.total_questions > 0:
            accuracy = round((sessions_stats.total_correct / sessions_stats.total_questions) * 100, 2)
        
        topics_count = self.db.query(func.count(Topics.id)).join(
            Subjects, Topics.subject_id == Subjects.id
        ).filter(
            Subjects.user_id == self.user_id,
            Subjects.deleted_at.is_(None),
            Topics.deleted_at.is_(None)
        ).scalar() or 0
        
        return {
            "total_cards": total_cards,
            "time_spend": time_spend,
            "accuracy": accuracy,
            "topics_count": topics_count
        }


    def retrieve_all_subjects_usecase(self, limit: int, offset: int, search: str) -> List[dict]:
        query = self.db.query(Subjects).filter(Subjects.user_id == self.user_id).filter(Subjects.deleted_at.is_(None))

        if search:
            query = query.filter(Subjects.subject_name.ilike(f"%{search}%"))

        subjects = query.offset(offset).limit(limit).all()

        result = []

        for subject in subjects:
            topics_with_count = self.db.query(
                Topics,
                func.count(Flashcards.id).label('count')
            ).outerjoin(
                Flashcards,
                (Flashcards.topic_id == Topics.id) & (Flashcards.deleted_at.is_(None))
            ).filter(
                Topics.subject_id == subject.id,
                Topics.deleted_at.is_(None)
            ).group_by(Topics.id).all()

            topics_list = []
            for topic, count in topics_with_count:
                topic_dict = topic.to_dict()
                topic_dict['count'] = count
                topics_list.append(topic_dict)

            result.append({
                "id": subject.id,
                "user_id": subject.user_id,
                "updated_at": subject.updated_at,
                "created_at": subject.created_at,
                "subject_name": subject.subject_name,
                "image_url": subject.image_url,
                "deleted_at": subject.deleted_at,
                "statistics": self._get_statistics(),
                "topics": topics_list
            })

        return result

    def create_subject_usecase(self, subject_request: SubjectRequest) -> dict:
        user = self.db.query(Users).filter(Users.id == self.user_id, Users.deleted_at.is_(None)).first()
        account_type = self._determine_user_account_type(user)
        
        original_account_type = user.account_type
        user.account_type = account_type

        try:
            limit_service = LimitService(self.db, user, Flashcards, Subjects)
            limit_service.check_subject_quota()

            subject_model = Subjects(**subject_request.model_dump(), user_id=self.user_id)
            self.db.add(subject_model)
            self.db.commit()
            self.db.refresh(subject_model)

            return subject_model.to_dict()
            
        finally:
            user.account_type = original_account_type

    def update_subject_usecase(self, subject_request: SubjectRequest, subject_id: str) -> dict:
        subject_model = self.db.query(Subjects).filter(Subjects.id == subject_id)\
            .filter(Subjects.user_id == self.user_id)\
            .filter(Subjects.deleted_at.is_(None)).first()

        if not subject_model:
            raise HTTPException(status_code=404, detail='Subject not found')

        subject_model.subject_name = subject_request.subject_name
        subject_model.image_url = subject_request.image_url
        subject_model.updated_at = datetime.now(timezone.utc)

        self.db.add(subject_model)
        self.db.commit()

        return subject_model.to_dict()

    def retrieve_subject_usecase(self, subject_id: str) -> dict:
        subject_model = self.db.query(Subjects).filter(Subjects.id == subject_id)\
            .filter(Subjects.user_id == self.user_id)\
            .filter(Subjects.deleted_at.is_(None)).first()

        if not subject_model:
            raise HTTPException(status_code=404, detail='Subject not found')

        return subject_model.to_dict()

    def delete_subject_usecase(self, subject_id: str) -> None:
        subject_model = self.db.query(Subjects).filter(Subjects.id == subject_id)\
            .filter(Subjects.user_id == self.user_id)\
            .filter(Subjects.deleted_at.is_(None)).first()

        if not subject_model:
            raise HTTPException(status_code=404, detail='Subject not found')

        now = datetime.now(timezone.utc)
        
        self.db.query(Sessions).filter(Sessions.subject_id == subject_id).update({
            "deleted_at": now
        })
        
        self.db.query(Flashcards).filter(Flashcards.subject_id == subject_id).update({
            "deleted_at": now
        })
        
        self.db.query(Topics).filter(Topics.subject_id == subject_id).update({
            "deleted_at": now
        })

        subject_model.deleted_at = now
        self.db.commit()

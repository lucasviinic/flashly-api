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
    def __init__(self):
        self.subscription_service = SubscriptionService()

    def _get_user_subscription(self, db: db_dependency, user_id: str) -> Optional[SubscriptionModel]:
        return db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == user_id,
            SubscriptionModel.is_active == True,
            SubscriptionModel.deleted_at.is_(None)
        ).first()

    def _verify_and_update_subscription(self, db: db_dependency, subscription: SubscriptionModel) -> bool:
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
            
            db.commit()
            
            return status_info.is_active
            
        except GooglePlaySubscriptionError:
            subscription.is_active = False
            subscription.updated_at = datetime.now(timezone.utc)
            db.commit()
            return False

    def _determine_user_account_type(self, db: db_dependency, user: Users) -> int:
        subscription = self._get_user_subscription(db, str(user.id))
        
        if not subscription:
            return 0
            
        is_active = self._verify_and_update_subscription(db, subscription)
        
        return 1 if is_active else 0
    
    def _get_statistics(self) -> dict:
        total_cards = ... # somatório da quantidade de flashcards em cada tópico
        time_spend = ... # somatório do tempo nas sessões de estudo
        return


    def retrieve_all_subjects_usecase(self, db: db_dependency, user_id: str, limit: int, offset: int, search: str) -> List[dict]:
        query = db.query(Subjects).filter(Subjects.user_id == user_id).filter(Subjects.deleted_at.is_(None))

        if search:
            query = query.filter(Subjects.subject_name.ilike(f"%{search}%"))

        subjects = query.offset(offset).limit(limit).all()

        result = []

        for subject in subjects:
            topics_with_count = db.query(
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

    def create_subject_usecase(self, db: db_dependency, subject_request: SubjectRequest, user_id: str) -> dict:
        user = db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()
        
        if not user:
            raise HTTPException(status_code=404, detail='User not found')

        account_type = self._determine_user_account_type(db, user)
        
        original_account_type = user.account_type
        user.account_type = account_type

        try:
            limit_service = LimitService(db, user, Flashcards, Subjects)
            limit_service.check_subject_quota()

            subject_model = Subjects(**subject_request.model_dump(), user_id=user_id)
            db.add(subject_model)
            db.commit()
            db.refresh(subject_model)

            return subject_model.to_dict()
            
        finally:
            user.account_type = original_account_type

    def update_subject_usecase(self, db: db_dependency, subject_request: SubjectRequest, subject_id: str, user_id: str) -> dict:
        subject_model = db.query(Subjects).filter(Subjects.id == subject_id)\
            .filter(Subjects.user_id == user_id)\
            .filter(Subjects.deleted_at.is_(None)).first()

        if not subject_model:
            raise HTTPException(status_code=404, detail='Subject not found')

        subject_model.subject_name = subject_request.subject_name
        subject_model.image_url = subject_request.image_url
        subject_model.updated_at = datetime.now(timezone.utc)

        db.add(subject_model)
        db.commit()

        return subject_model.to_dict()

    def retrieve_subject_usecase(self, db: db_dependency, subject_id: str, user_id: str) -> dict:
        subject_model = db.query(Subjects).filter(Subjects.id == subject_id)\
            .filter(Subjects.user_id == user_id)\
            .filter(Subjects.deleted_at.is_(None)).first()

        if not subject_model:
            raise HTTPException(status_code=404, detail='Subject not found')

        return subject_model.to_dict()

    def delete_subject_usecase(self, db: db_dependency, subject_id: str, user_id: str) -> None:
        subject_model = db.query(Subjects).filter(Subjects.id == subject_id)\
            .filter(Subjects.user_id == user_id)\
            .filter(Subjects.deleted_at.is_(None)).first()

        if not subject_model:
            raise HTTPException(status_code=404, detail='Subject not found')

        now = datetime.now(timezone.utc)
        
        db.query(Sessions).filter(Sessions.subject_id == subject_id).update({
            "deleted_at": now
        })
        
        db.query(Flashcards).filter(Flashcards.subject_id == subject_id).update({
            "deleted_at": now
        })
        
        db.query(Topics).filter(Topics.subject_id == subject_id).update({
            "deleted_at": now
        })

        subject_model.deleted_at = now
        db.commit()

from datetime import datetime, timezone
import os
from fastapi import HTTPException, UploadFile

from core.firebase.client import firebase_file_upload
from database import db_dependency
from models.flashcard_model import Flashcards
from models.session_model import Sessions
from models.subject_model import Subjects
from models.topic_model import Topics
from models.user_model import Users
from models.subscription_model import SubscriptionModel
from services.limit_service import LimitService
from services.subscription_service import SubscriptionService
from utils.utils import validate_file_size


class UserUseCase:
    def __init__(self, db: db_dependency):
        self.db = db
        self.subscription_service = SubscriptionService()
    
    def _get_user_by_id(self, user_id: str) -> Users:
        user_model = self.db.query(Users).filter(
            Users.id == user_id, 
            Users.deleted_at.is_(None)
        ).first()
        
        if not user_model:
            raise HTTPException(status_code=400, detail='user not found')
        
        return user_model
    
    def _get_user_subscription(self, user_id: str) -> SubscriptionModel:
        return self.db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == user_id,
            SubscriptionModel.deleted_at.is_(None)
        ).first()
    
    def _verify_subscription_with_google(self, subscription_model: SubscriptionModel) -> tuple[dict, dict]:
        if not subscription_model or not subscription_model.purchase_token or not subscription_model.package_name:
            return None, None
        
        try:
            is_active = self.subscription_service.check_subscription_active(
                subscription_model.package_name, 
                subscription_model.purchase_token
            )
            
            if not is_active:
                return None, None
            
            subscription_data_obj, subscription_status_obj = self.subscription_service.get_complete_subscription_info(
                subscription_model.package_name,
                subscription_model.purchase_token
            )
            
            subscription_data = {
                'package_name': subscription_data_obj.package_name,
                'product_id': subscription_data_obj.product_id,
                'start_date': subscription_data_obj.start_date.isoformat(),
                'expiration_date': subscription_data_obj.expiration_date.isoformat(),
                'subscription_state': subscription_data_obj.subscription_state.value,
                'auto_renewing': subscription_data_obj.auto_renewing,
                'is_active': subscription_data_obj.is_active,
                'price': {
                    'currency_code': subscription_data_obj.price.currency_code if subscription_data_obj.price else None,
                    'amount': subscription_data_obj.price.amount if subscription_data_obj.price else None
                } if subscription_data_obj.price else None
            }
            
            subscription_status = {
                'is_active': subscription_status_obj.is_active,
                'status_message': subscription_status_obj.status_message,
                'days_until_expiry': subscription_status_obj.days_until_expiry,
                'expiration_date': subscription_status_obj.expiration_date.isoformat()
            }
            
            return subscription_data, subscription_status
            
        except Exception as e:
            print(f"Erro ao verificar subscription: {str(e)}")
            return None, None
    
    def _update_user_account_type(self, user_model: Users, has_active_subscription: bool) -> None:
        should_be_premium = has_active_subscription
        current_is_premium = user_model.account_type == 1
        
        if should_be_premium and not current_is_premium:
            user_model.account_type = 1
            self.db.add(user_model)
            self.db.commit()
        elif not should_be_premium and current_is_premium:
            user_model.account_type = 0
            self.db.add(user_model)
            self.db.commit()
    
    def _get_user_usage_info(self, user_model: Users) -> dict:
        limit_service = LimitService(self.db, user_model, Flashcards, Subjects)
        usage = limit_service.get_usage()
        
        return {
            'flashcards_usage': f"{usage['flashcards'][0]}/{usage['flashcards'][1]}",
            'ai_gen_flashcards_usage': f"{usage['ai_flashcards'][0]}/{usage['ai_flashcards'][1]}",
            'subjects_usage': f"{usage['subjects'][0]}/{usage['subjects'][1]}"
        }
    
    def retrieve_user_usecase(self, user_id: str) -> dict:
        user_model = self._get_user_by_id(user_id)
        subscription_model = self._get_user_subscription(user_id)
        
        subscription_data, subscription_status = self._verify_subscription_with_google(subscription_model)
        
        has_active_subscription = (
            subscription_data is not None and 
            subscription_status is not None and 
            subscription_status.get('is_active', False)
        )
        
        self._update_user_account_type(user_model, has_active_subscription)
        
        usage_info = self._get_user_usage_info(user_model)
        
        user_data = user_model.to_dict()
        
        user_data['subscription'] = {
            'data': subscription_data,
            'status': subscription_status,
            'has_active_subscription': has_active_subscription
        }
        
        user_data.update(usage_info)
        
        return user_data
    
    def update_user_usecase(self, user_id: str, file_picture: UploadFile) -> dict:
        user_model = self._get_user_by_id(user_id)
        
        if not file_picture.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="the uploaded file is not an image")
        
        if validate_file_size(file_obj=file_picture.file, max_size_mb=5):
            raise HTTPException(status_code=400, detail=f"the file exceeds the maximum allowed size of 5MB")
        
        user_model.picture = firebase_file_upload(
            bucket_blob=os.getenv("FIREBASE_PROFILE_IMAGE_BLOB"),
            file_image=file_picture,
            image_id=user_id
        )
        
        self.db.add(user_model)
        self.db.commit()
        
        return self.retrieve_user(user_id)
    
    def delete_user_usecase(self, user_id: str) -> dict:
        user_model = self._get_user_by_id(user_id)
        deleted_counts = {
            'subscription': 0,
            'sessions': 0,
            'flashcards': 0,
            'topics': 0,
            'subjects': 0,
            'user': 0
        }
        deletion_time = datetime.now(timezone.utc)
        
        sessions_count = self.db.query(Sessions).filter(
            Sessions.user_id == user_id
        ).delete(synchronize_session=False)
        deleted_counts['sessions'] = sessions_count
        
        flashcards_count = self.db.query(Flashcards).filter(
            Flashcards.user_id == user_id
        ).delete(synchronize_session=False)
        deleted_counts['flashcards'] = flashcards_count
        
        user_subjects = self.db.query(Subjects).filter(
            Subjects.user_id == user_id
        ).all()
        
        topics_count = 0
        for subject in user_subjects:
            count = self.db.query(Topics).filter(
                Topics.subject_id == subject.id
            ).delete(synchronize_session=False)
            topics_count += count
        deleted_counts['topics'] = topics_count
        
        subjects_count = self.db.query(Subjects).filter(
            Subjects.user_id == user_id
        ).delete(synchronize_session=False)
        deleted_counts['subjects'] = subjects_count
        
        self.db.delete(user_model)
        deleted_counts['user'] = 1
        
        self.db.commit()
        
        return {
            'message': 'User account and all related data permanently deleted',
            'deleted_at': deletion_time.isoformat(),
            'user_id': user_id,
            'deleted_data_count': deleted_counts
        }

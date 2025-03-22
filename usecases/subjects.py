from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException
from database import db_dependency
from models.flashcard_model import Flashcards
from models.requests_model import SubjectRequest
from models.session_model import Sessions
from models.subject_model import Subjects
from models.topic_model import Topics
from models.user_model import Users
from utils.constants import USER_LIMITS


def retrieve_all_subjects_usecase(db: db_dependency, user_id: str, limit: int, offset: int, search: str) -> List[dict]:
    query = db.query(Subjects).filter(Subjects.user_id == user_id).filter(Subjects.deleted_at == None)
    
    if search:
        query = query.filter(Subjects.subject_name.ilike(f"%{search}%"))

    subjects = query.offset(offset).limit(limit).all()
    
    result = []
    
    for subject in subjects:
        topics = db.query(Topics).filter(Topics.subject_id == subject.id).all()
        topics_list = [topic.to_dict() for topic in topics]
        
        result.append({
            "id": subject.id,
            "user_id": subject.user_id,
            "updated_at": subject.updated_at,
            "created_at": subject.created_at,
            "subject_name": subject.subject_name,
            "image_url": subject.image_url,
            "deleted_at": subject.deleted_at,
            "topics": topics_list
        })
    
    return result

def create_subject_usecase(db: db_dependency, subject_request: SubjectRequest, user_id: str) -> dict:
    total_subjects = db.query(Subjects).filter(
        Subjects.user_id == user_id,
        Subjects.deleted_at.is_(None)
    ).count()

    user = db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()
    subjects_limit = USER_LIMITS[user.account_type]["subjects_limit"]

    if total_subjects >= subjects_limit:
        raise HTTPException(status_code=400, detail='Subject limit reached')

    subject_model = Subjects(**subject_request.model_dump(), user_id=user_id)

    db.add(subject_model)
    db.commit()
    db.refresh(subject_model)

    result = subject_model.to_dict()

    return result

def update_subject_usecase(db: db_dependency, subject_request: SubjectRequest, subject_id: str, user_id: str) -> dict:
    subject_model = db.query(Subjects).filter(Subjects.id == subject_id)\
        .filter(Subjects.user_id == user_id).first()
    
    if not subject_model:
        raise HTTPException(status_code=404, detail='subject not found')
    
    subject_model.subject_name = subject_request.subject_name
    subject_model.image_url = subject_request.image_url
    subject_model.updated_at = datetime.now(timezone.utc)

    db.add(subject_model)
    db.commit()

    result = subject_model.to_dict()

    return result

def retrieve_subject_usecase(db: db_dependency, subject_id: str, user_id: str) -> dict:
    subject_model = db.query(Subjects).filter(Subjects.id == subject_id)\
        .filter(Subjects.user_id == user_id).filter(Subjects.deleted_at == None).first()

    if not subject_model:
        raise HTTPException(status_code=404, detail='subject not found')
    
    result = subject_model.to_dict()

    return result

def delete_subject_usecase(db: db_dependency, subject_id: str, user_id: str) -> None:
    subject_model = db.query(Subjects).filter(Subjects.id == subject_id)\
        .filter(Subjects.user_id == user_id).first()
    
    if not subject_model:
        raise HTTPException(status_code=404, detail='subject not found')
        
    db.query(Flashcards).filter(Flashcards.subject_id == subject_id).delete()
    db.query(Topics).filter(Topics.subject_id == subject_id).delete()
    db.query(Sessions).filter(Sessions.subject_id == subject_id).delete()
    
    db.delete(subject_model)    
    db.commit()
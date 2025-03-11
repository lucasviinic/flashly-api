from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException
from models.flashcard_model import Flashcards
from models.requests_model import TopicRequest
from models.topic_model import Topics
from database import db_dependency


def create_topic_usecase(db: db_dependency, topic_request: TopicRequest) -> dict:
    topic_model = Topics(**topic_request.model_dump())

    topic_model.subject_id = topic_request.subject_id

    db.add(topic_model)
    db.commit()
    db.refresh(topic_model)

    result = topic_model.to_dict()

    return result

def retrieve_all_topics_usecase(db: db_dependency, subject_id: str) -> List[dict]:
    result = db.query(Topics).filter(Topics.subject_id == subject_id).filter(Topics.deleted_at == None).all()
    return result

def update_topic_usecase(db: db_dependency, topic_request: TopicRequest) -> dict:
    topic_model = db.query(Topics).filter(Topics.subject_id == topic_request.subject_id)\
                                  .filter(Topics.id == topic_request.id).first()

    if not topic_model:
        raise HTTPException(status_code=404, detail='topic not found')

    topic_model.topic_name = topic_request.topic_name
    topic_model.updated_at = datetime.now(timezone.utc)
    
    db.add(topic_model)
    db.commit()

    result = topic_model.to_dict()

    return result

def retrieve_topic_usecase(db: db_dependency, subject_id: str, topic_id: str) -> dict:
    topic_model = db.query(Topics).filter(Topics.subject_id == subject_id).filter(Topics.id == topic_id).filter(Topics.deleted_at == None).first()

    if not topic_model:
        raise HTTPException(status_code=404, detail='topic not found')
    
    result = topic_model.to_dict()
    
    return result

def delete_topic_usecase(db: db_dependency, topic_id: str) -> None:
    topic_model = db.query(Topics).filter(Topics.id == topic_id).first()

    if not topic_model:
        raise HTTPException(status_code=404, detail='topic not found')
    
    db.query(Flashcards).filter(Flashcards.topic_id == topic_id).delete()
    db.query(Topics).filter(Topics.id == topic_id).delete()
    db.commit()
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException
from sqlalchemy import func
from models.flashcard_model import Flashcards
from models.requests_model import TopicRequest
from models.session_model import Sessions
from models.topic_model import Topics
from database import db_dependency


class TopicUseCase:
    def __init__(self, db: db_dependency, subject_id: str = None, topic_id: str = None):
        self.db = db
        self.subject_id = subject_id
        self.topic_id = topic_id


    def create_topic(self, topic_request: TopicRequest) -> dict:
        topic_model = Topics(**topic_request.model_dump())

        topic_model.subject_id = topic_request.subject_id

        self.db.add(topic_model)
        self.db.commit()
        self.db.refresh(topic_model)

        result = topic_model.to_dict()

        return result

    def retrieve_all_topics(self) -> List[dict]:
        topics = self.db.query(Topics).filter(
            Topics.subject_id == self.subject_id,
            Topics.deleted_at.is_(None)
        ).all()
        
        result = []
        
        for topic in topics:
            flashcards_count = self.db.query(func.count(Flashcards.id)).filter(
                Flashcards.topic_id == topic.id,
                Flashcards.deleted_at.is_(None)
            ).scalar() or 0
            
            sessions_stats = self.db.query(
                func.sum(Sessions.correct_answer_count).label('total_correct'),
                func.sum(Sessions.total_questions).label('total_questions')
            ).filter(
                Sessions.topic_id == topic.id,
                Sessions.deleted_at.is_(None)
            ).first()
            
            accuracy = 0.0
            if sessions_stats and sessions_stats.total_questions and sessions_stats.total_questions > 0:
                accuracy = round((sessions_stats.total_correct / sessions_stats.total_questions) * 100, 2)
            
            sessions = self.db.query(Sessions.total_time_spent).filter(
                Sessions.topic_id == topic.id,
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
            seconds = total_seconds % 60
            time_spent = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            last_session = self.db.query(Sessions.created_at).filter(
                Sessions.topic_id == topic.id,
                Sessions.deleted_at.is_(None)
            ).order_by(Sessions.created_at.desc()).first()
            
            seconds_since_last_study = None
            if last_session and last_session.created_at:
                now = datetime.now(timezone.utc)
                last_study_time = last_session.created_at
                if last_study_time.tzinfo is None:
                    last_study_time = last_study_time.replace(tzinfo=timezone.utc)
                
                time_diff = now - last_study_time
                seconds_since_last_study = int(time_diff.total_seconds())
            
            topic_dict = topic.to_dict()
            topic_dict.update({
                'statistics': {
                    'flashcards_count': flashcards_count,
                    'accuracy': accuracy,
                    'time_spent': time_spent,
                    'seconds_since_last_study': seconds_since_last_study
                }
            })
            
            result.append(topic_dict)
        
        return result

    def update_topic(self, topic_request: TopicRequest) -> dict:
        topic_model = self.db.query(Topics).filter(Topics.subject_id == topic_request.subject_id)\
                                    .filter(Topics.id == topic_request.id).first()

        if not topic_model:
            raise HTTPException(status_code=404, detail='topic not found')

        topic_model.topic_name = topic_request.topic_name
        topic_model.updated_at = datetime.now(timezone.utc)
        
        self.db.add(topic_model)
        self.db.commit()

        result = topic_model.to_dict()

        return result

    def retrieve_topic(self) -> dict:
        topic_model = self.db.query(Topics).filter(Topics.subject_id == self.subject_id).filter(Topics.id == self.topic_id).filter(Topics.deleted_at == None).first()

        if not topic_model:
            raise HTTPException(status_code=404, detail='topic not found')
        
        result = topic_model.to_dict()
        
        return result

    def delete_topic(self) -> None:
        topic_model = self.db.query(Topics).filter(Topics.id == self.topic_id).first()

        if not topic_model:
            raise HTTPException(status_code=404, detail='topic not found')
        
        self.db.query(Flashcards).filter(Flashcards.topic_id == self.topic_id).delete()
        self.db.query(Topics).filter(Topics.id == self.topic_id).delete()
        self.db.commit()
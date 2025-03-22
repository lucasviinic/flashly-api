from datetime import datetime, timezone
import json
import os
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy import func

from core.firebase.client import firebase_file_upload
from models.flashcard_model import Flashcards
from models.requests_model import FlashcardRequest
from core.openai import client as openai_client
from database import db_dependency
from models.user_model import Users
from utils.constants import USER_LIMITS
from utils.utils import fragment_text


def generate_flashcards_usecase(db: db_dependency, content: str, quantity: int, user_id: str, subject_id: str,
        topic_id: str, difficulty: int = 1) -> List[dict]:
    
    total_flashcards = db.query(Flashcards).filter(
        Flashcards.user_id == user_id,
        Flashcards.deleted_at.is_(None)
    ).count()

    total_generated = db.query(Flashcards).filter(
        Flashcards.user_id == user_id,
        Flashcards.origin == "ai"
    ).count()

    user = db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()
    flashcards_limit = USER_LIMITS[user.account_type]["flashcards_limit"]
    generated_limit = USER_LIMITS[user.account_type]["ai_gen_flashcards_limit"]

    flashcards_remaining = flashcards_limit - total_flashcards
    generated_remaining = generated_limit - total_generated

    if flashcards_remaining <= 0:
        raise HTTPException(status_code=400, detail='Flashcard limit reached')
    if generated_remaining <= 0:
        raise HTTPException(status_code=400, detail='AI generated flashcards limit reached')
    
    quantity = quantity if quantity <= generated_remaining else generated_remaining
    
    generated_flashcards = []
    text_fragments = fragment_text(content)

    for fragment in text_fragments:
        flashcards_list = openai_client.flash_card_generator(prompt=fragment,\
            history=generated_flashcards, quantity=quantity, difficulty=difficulty)
        generated_flashcards.extend(flashcards_list)

    result = []

    for flashcard in generated_flashcards:
        flashcard_model = Flashcards()

        flashcard_model.question = flashcard.get('question')
        flashcard_model.answer = flashcard.get('answer')

        flashcard_model.user_id = user_id
        flashcard_model.subject_id = subject_id
        flashcard_model.topic_id = topic_id
        flashcard_model.difficulty = difficulty
        flashcard_model.opened = True
        flashcard_model.origin = 'ai'

        db.add(flashcard_model)
        db.commit()
        db.refresh(flashcard_model)

        result.append(flashcard_model.to_dict())
        
    return result
        
        
def create_flashcard_usecase(db: db_dependency, flashcard_request: FlashcardRequest, user_id: str, file: UploadFile) -> dict:
    total_flashcards = db.query(Flashcards).filter(
        Flashcards.user_id == user_id,
        Flashcards.deleted_at.is_(None)
    ).count()

    user = db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()

    if total_flashcards >= USER_LIMITS[user.account_type]["flashcards_limit"]:
        raise HTTPException(status_code=400, detail='Flashcard limit reached')

    try:
        flashcard_data = json.loads(flashcard_request)
        flashcard_model = Flashcards(**flashcard_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid flashcard data: {str(e)}")
    flashcard_model.user_id = user_id

    db.add(flashcard_model)
    db.flush()

    if file:
        try:
            image_url = firebase_file_upload(
                bucket_blob=os.getenv("FIREBASE_FLASHCARD_IMAGE_BLOB"),
                file_image=file,
                image_id=str(flashcard_model.id)
            )
            flashcard_model.image_url = image_url
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"error uploading image: {str(e)}")

    db.commit()
    db.refresh(flashcard_model)

    result = flashcard_model.to_dict()
    return result


def retrieve_all_flashcards_usecase(
        db: db_dependency,
        topic_id: str,
        user_id: str,
        limit: Optional[int] = 20,
        offset: Optional[int] = 0,
        difficulties: Optional[List[int]] = None,
        ai_generated: Optional[bool] = None
    ) -> Tuple[List[dict], int]:
    
    query = db.query(Flashcards).filter(
        Flashcards.topic_id == topic_id,
        Flashcards.user_id == user_id,
        Flashcards.deleted_at.is_(None)
    )

    if difficulties:
        query = query.filter(Flashcards.difficulty.in_(difficulties))
    
    if ai_generated is not None:
        query = query.filter(Flashcards.origin == "ai")

    total_count = query.count()

    if limit is None and offset is None:
        query = query.order_by(func.random())
    else:
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)
    
    flashcards = query.all()
    result = [flashcard.to_dict() for flashcard in flashcards]

    return result, total_count


def delete_flashcard_usecase(db: db_dependency, user_id: str, flashcard_id: int) -> None:
    flashcard_model = db.query(Flashcards).filter(
        Flashcards.id == flashcard_id,
        Flashcards.user_id == user_id
    ).first()

    if not flashcard_model:
        raise HTTPException(status_code=404, detail='Flashcard not found')

    flashcard_model.deleted_at = datetime.now(timezone.utc)

    db.delete(flashcard_model)
    db.commit()


def update_flashcard_usecase(
    db: db_dependency,
    user_id: str,
    flashcard_id: int,
    flashcard_request: FlashcardRequest,
    file: UploadFile = None
) -> dict:
    flashcard_model = db.query(Flashcards).filter(
        Flashcards.id == flashcard_id,
        Flashcards.user_id == user_id,
        Flashcards.deleted_at.is_(None)
    ).first()

    if not flashcard_model:
        raise HTTPException(status_code=404, detail='Flashcard not found')

    try:
        if isinstance(flashcard_request, str):
            flashcard_data = json.loads(flashcard_request)
        else:
            flashcard_data = flashcard_request.model_dump()

        for field, value in flashcard_data.items():
            if hasattr(flashcard_model, field) and value is not None:
                setattr(flashcard_model, field, value)

        flashcard_model.updated_at = datetime.now(timezone.utc)

        if file:
            try:
                image_url = firebase_file_upload(
                    bucket_blob=os.getenv("FIREBASE_FLASHCARD_IMAGE_BLOB"),
                    file_image=file,
                    image_id=str(flashcard_model.id)
                )
                flashcard_model.image_url = image_url
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

        db.commit()
        db.refresh(flashcard_model)

        return flashcard_model.to_dict()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating flashcard: {str(e)}")
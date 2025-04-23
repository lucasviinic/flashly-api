import os
from datetime import datetime, date
from fastapi import HTTPException, UploadFile

from core.firebase.client import firebase_file_upload
from database import db_dependency
from models.flashcard_model import Flashcards
from models.subject_model import Subjects
from models.user_model import Users
from utils.constants import USER_LIMITS
from sqlalchemy import cast, Date


from utils.utils import validate_file_size


def retrieve_user_usecase(db: db_dependency, user_id: str) -> dict:
    user_model = db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()

    if not user_model:
        raise HTTPException(status_code=400, detail='user not found')

    daily_flashcard_limit = USER_LIMITS[user_model.account_type]["flashcards_limit"]
    flashcards_count = db.query(Flashcards).filter(
        Flashcards.user_id == user_id,
        cast(Flashcards.created_at, Date) == date.today()
    ).count()
    flashcards_usage = f"{flashcards_count}/{daily_flashcard_limit}"

    ai_gen_flashcards_limit = USER_LIMITS[user_model.account_type]["ai_gen_flashcards_limit"]
    ai_gen_flashcards_count = db.query(Flashcards).filter(
        Flashcards.user_id == user_id,
        Flashcards.origin == 'ai',
        cast(Flashcards.created_at, Date) == date.today()
    ).count()
    ai_gen_flashcards_usage = f"{ai_gen_flashcards_count}/{ai_gen_flashcards_limit}"

    subjects_limit = USER_LIMITS[user_model.account_type]["subjects_limit"]
    subjects_count = db.query(Subjects).filter(
        Subjects.user_id == user_id,
        cast(Subjects.created_at, Date) == date.today()
    ).count()
    subjects_usage = f"{subjects_count}/{subjects_limit}"

    if user_model.account_type == 1:
        flashcards_usage = None
        ai_gen_flashcards_usage = None
        subjects_usage = None

    user_data = user_model.to_dict()

    user_data['flashcards_usage'] = flashcards_usage
    user_data['ai_gen_flashcards_usage'] = ai_gen_flashcards_usage
    user_data['subjects_usage'] = subjects_usage

    return user_data
    
def update_user_usecase(db: db_dependency, user_id: str, file_picture: UploadFile) -> dict:
    user_model = db.query(Users).filter(
        Users.id == user_id,
        Users.deleted_at.is_(None)
    ).first()

    if not user_model:
        raise HTTPException(status_code=404, detail='user not found')
    
    if not file_picture.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="the uploaded file is not an image")
    
    if validate_file_size(file_obj=file_picture.file, max_size_mb=5):
        raise HTTPException(status_code=400, detail=f"the file exceeds the maximum allowed size of 5MB")
    
    user_model.picture = firebase_file_upload(
        bucket_blob=os.getenv("FIREBASE_PROFILE_IMAGE_BLOB"),
        file_image=file_picture,
        image_id=user_id
    )

    db.add(user_model)
    db.commit()

    result = user_model.to_dict()
    return result
import os
from fastapi import HTTPException, UploadFile

from core.firebase.client import firebase_file_upload
from database import db_dependency
from models.flashcard_model import Flashcards
from models.subject_model import Subjects
from models.user_model import Users
from services.limit_service import LimitService
from utils.utils import validate_file_size


def retrieve_user_usecase(db: db_dependency, user_id: str) -> dict:
    user_model = db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()

    if not user_model:
        raise HTTPException(status_code=400, detail='user not found')

    limit_service = LimitService(db, user_model, Flashcards, Subjects)
    usage = limit_service.get_usage()
    
    user_data = user_model.to_dict()
    
    if user_model.account_type != 1:
        user_data['flashcards_usage'] = f"{usage['flashcards'][0]}/{usage['flashcards'][1]}"
        user_data['ai_gen_flashcards_usage'] = f"{usage['ai_flashcards'][0]}/{usage['ai_flashcards'][1]}"
        user_data['subjects_usage'] = f"{usage['subjects'][0]}/{usage['subjects'][1]}"
    else:
        user_data['flashcards_usage'] = None
        user_data['ai_gen_flashcards_usage'] = None
        user_data['subjects_usage'] = None

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
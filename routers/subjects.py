from datetime import datetime, timezone
import os
from typing import Annotated
from starlette import status

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from core.firebase.client import firebase_file_upload
from models.requests_model import SubjectRequest
from models.subject_model import Subjects
from usecases.auth import get_current_user_usecase
from database import db_dependency
from usecases.subjects import SubjectsUseCase

router = APIRouter(
    prefix='/subjects',
    tags=['subjects']
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_subject(db: db_dependency, user: user_dependency, subject_request: SubjectRequest):    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    subjects_usecase = SubjectsUseCase(db=db, user_id=user.get('id'))
    response = subjects_usecase.create_subject_usecase(subject_request)

    return response

@router.get("")
async def retrieve_all_subjects(
    user: user_dependency,
    db: db_dependency,
    limit: int = Query(default=15, ge=1),
    offset: int = Query(default=0, ge=0),
    search: str = Query(default=None)
):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    subjects_usecase = SubjectsUseCase(db=db, user_id=user.get('id'))
    response = subjects_usecase.retrieve_all_subjects_usecase(
        limit=limit, offset=offset, search=search
    )

    return response

@router.put("/{subject_id}")
async def update_subject(user: user_dependency, db: db_dependency, subject_request: SubjectRequest, subject_id: str):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    subjects_usecase = SubjectsUseCase(db=db, user_id=user.get('id'))
    response = subjects_usecase.update_subject_usecase(subject_request, subject_id)

    return response

@router.get("/{subject_id}", status_code=status.HTTP_200_OK)
async def retrieve_subject(user: user_dependency, db: db_dependency, subject_id: str):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    subjects_usecase = SubjectsUseCase(db=db, user_id=user.get('id'))
    response = subjects_usecase.retrieve_subject_usecase(subject_id)

    return response
    
@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(user: user_dependency, db: db_dependency, subject_id: str):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    subjects_usecase = SubjectsUseCase(db=db, user_id=user.get('id'))
    subjects_usecase.delete_subject_usecase(subject_id)

@router.put("/{subject_id}/upload-image", status_code=status.HTTP_200_OK)
async def update_subject_image(
    subject_id: str,
    user: user_dependency,
    db: db_dependency,
    file: UploadFile = File(...)
):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')

    subject_model = db.query(Subjects).filter(
        Subjects.id == subject_id,
        Subjects.user_id == user.get('id'),
        Subjects.deleted_at.is_(None)
    ).first()

    if not subject_model:
        raise HTTPException(status_code=404, detail='Subject not found')
    
    subject_model.image_url = firebase_file_upload(
        bucket_blob=os.getenv("FIREBASE_SUBJECT_IMAGE_BLOB"),
        file_image=file,
        image_id=subject_id
    )

    subject_model.updated_at = datetime.now(timezone.utc)

    db.add(subject_model)
    db.commit()
    db.refresh(subject_model)

    return subject_model.to_dict()

@router.get("/user/subscription-info")
async def get_user_subscription_info(user: user_dependency, db: db_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    subjects_usecase = SubjectsUseCase(db=db, user_id=user.get('id'))
    response = subjects_usecase.get_user_subscription_info(db, user_id=user.get('id'))

    return response
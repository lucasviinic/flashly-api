from typing import Annotated
from starlette import status
from models.requests_model import UserRequest
from usecases.auth import get_current_user_usecase
from usecases.user import UserUseCase
from database import db_dependency

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

router = APIRouter(
    prefix='/users',
    tags=['users']
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]

@router.get("")
async def retrieve_user(user: user_dependency, db: db_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')

    try:
        user_usecase = UserUseCase(db)
        user_data = user_usecase.retrieve_user_usecase(user_id=user.get('id'))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"error getting user: {str(e)}")

    return user_data

@router.put("/{user_id}")
async def update_user(
    user: user_dependency,
    db: db_dependency,
    user_id: str,
    file_picture: UploadFile = File(...)
):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')

    if user.get('id') != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='you can only update your own profile')

    try:
        user_usecase = UserUseCase(db)
        user_data = user_usecase.update_user_usecase(user_id=user_id, file_picture=file_picture)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"error updating user: {str(e)}")

    return user_data
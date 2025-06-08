from typing import Annotated
from starlette import status

from fastapi import APIRouter, Depends, HTTPException, Query

from models.requests_model import TopicRequest
from usecases.auth import get_current_user_usecase
from database import db_dependency
from usecases.topics import TopicUseCase


router = APIRouter(
    prefix="/topics",
    tags=["topics"]
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_topic(db: db_dependency, user: user_dependency, topic_request: TopicRequest):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')
    
    topic_usecase = TopicUseCase(db=db)
    response = topic_usecase.create_topic(topic_request=topic_request)

    return response

@router.get("/{subject_id}", status_code=status.HTTP_200_OK)
async def retrieve_all_topics(user: user_dependency, db: db_dependency, subject_id: str):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')
    
    topic_usecase = TopicUseCase(db=db, subject_id=subject_id)
    response = topic_usecase.retrieve_all_topics()

    return response

@router.put("")
async def update_topic(user: user_dependency, db: db_dependency, topic_request: TopicRequest):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')
    
    topic_usecase = TopicUseCase(db=db)
    response = topic_usecase.update_topic(topic_request=topic_request)
    
    return response

@router.get("/{subject_id}", status_code=status.HTTP_200_OK)
async def retrieve_topic(user: user_dependency, db: db_dependency, subject_id: str, topic_id: str = Query(...)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')
    
    topic_usecase = TopicUseCase(db=db, subject_id=subject_id, topic_id=topic_id)
    response = topic_usecase.retrieve_topic()

    return response

@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(user: user_dependency, db: db_dependency, topic_id: str):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication failed')
    
    topic_usecase = TopicUseCase(db=db, topic_id=topic_id)
    topic_usecase.delete_topic()

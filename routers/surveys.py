from typing import Annotated
from starlette import status
from uuid import UUID

from schemas.survey_schemas import (
    CreateSurveyRequest, VoteRequest, SurveyResponse, 
)
from usecases.auth import get_current_user_usecase
from database import db_dependency

from fastapi import APIRouter, Depends, HTTPException

from usecases.survey_usecase import SurveyUseCase


router = APIRouter(
    prefix='/surveys',
    tags=['surveys']
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]


@router.get("/current", response_model=SurveyResponse)
async def get_current_survey(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    try:
        survey_usecase = SurveyUseCase(db=db)
        survey = survey_usecase.get_current_survey(user_id=user['id'])
        if not survey:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No active survey found')
        return survey
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting survey: {str(e)}")


@router.post("/vote", status_code=status.HTTP_201_CREATED)
async def vote_on_survey(db: db_dependency, user: user_dependency, vote_data: VoteRequest):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    try:
        survey_usecase = SurveyUseCase(db=db)
        result = survey_usecase.vote_survey(user_id=user['id'], vote_data=vote_data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error voting: {str(e)}")


@router.get("/{survey_id}", response_model=SurveyResponse)
async def get_survey_by_id(survey_id: UUID, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication failed')
    
    try:
        survey_usecase = SurveyUseCase(db=db)
        survey = survey_usecase.get_survey_by_id(survey_id=survey_id, user_id=user['id'])
        if not survey:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Survey not found')
        return survey
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting survey: {str(e)}")


##################################### ⚠️ Admin routes ⚠️ #####################################
@router.post("", status_code=status.HTTP_201_CREATED, response_model=SurveyResponse)
async def create_survey(db: db_dependency, user: user_dependency, survey_data: CreateSurveyRequest):
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    
    try:
        survey_usecase = SurveyUseCase(db=db)
        survey = survey_usecase.create_survey(survey_data=survey_data, user_id=user.get('id'))
        return survey
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating survey: {str(e)}")


@router.put("/{survey_id}/finish", status_code=status.HTTP_200_OK)
async def finish_survey(survey_id: UUID, db: db_dependency, user: user_dependency):
    if not user or user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    
    try:
        # TODO: implement usecase to finish survey
        # finish_survey_usecase(db=db, survey_id=survey_id)
        return {"message": "Survey finished successfully"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error finishing survey: {str(e)}")
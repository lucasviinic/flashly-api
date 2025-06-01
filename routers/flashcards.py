from typing import Annotated, Optional
from starlette import status
from usecases.auth import get_current_user_usecase

from usecases.flashcards import FlashcardsUseCase
from utils import pdf_to_text
from database import db_dependency

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile


router = APIRouter(
    prefix='/flashcards',
    tags=['flashcards']
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]

@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_flashcards(
        db: db_dependency, 
        user: user_dependency, 
        file: UploadFile,
        quantity: int = Query(5, ge=1, le=30), 
        difficulty: int = Query(1, ge=0, le=2),
        subject_id: str = Query(..., description="ID da disciplina"), 
        topic_id: str = Query(..., description="ID do tópico")):
    
    text_content = pdf_to_text(pdf=file.file)

    flashcards_usecase = FlashcardsUseCase(db=db)

    flashcards_list = flashcards_usecase.generate_flashcards(
        content=text_content, 
        quantity=quantity, 
        difficulty=difficulty,
        subject_id=subject_id,
        topic_id=topic_id, 
        user_id=user.get('id')
    )

    return {"flashcards": flashcards_list}

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_flashcards(
    db: db_dependency,
    user: user_dependency,
    flashcard: str = Form(...),
    file: UploadFile = File(None)
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='authentication failed'
        )

    try:
        flashcards_usecase = FlashcardsUseCase(db=db)
        flashcard_created = flashcards_usecase.create_flashcard(
            flashcard_request=flashcard,
            user_id=user.get('id'),
            file=file
        )
        response = flashcard_created
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating flashcards: {str(e)}"
        )

    return response

@router.get("")
async def retrieve_all_flashcards(
    user: user_dependency,
    db: db_dependency,
    topic_id: str = Query(...),
    limit: Optional[int] = Query(default=15, ge=0),
    offset: int = Query(default=0, ge=0),
    difficulties: Optional[str] = Query(default=None),
    ai_generated: Optional[bool] = Query(default=None)
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='authentication failed'
        )
    
    difficulties_list = None
    if difficulties:
        try:
            difficulties_list = [int(d) for d in difficulties.split(",")]
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de 'difficulties' inválido"
            )
    
    flashcards_usecase = FlashcardsUseCase(db=db)

    try:
        if limit == 0:
            result, count = flashcards_usecase.retrieve_all_flashcards(
                topic_id=topic_id,
                user_id=user.get('id'),
                limit=None,
                offset=None,
                difficulties=difficulties_list,
                ai_generated=ai_generated
            )
        else:
            result, count = flashcards_usecase.retrieve_all_flashcards(
                topic_id=topic_id,
                user_id=user.get('id'),
                limit=limit,
                offset=offset,
                difficulties=difficulties_list,
                ai_generated=ai_generated
            )
        response = {"flashcards": result, "count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing flashcards: {str(e)}"
        )

    return response

@router.delete("/{flashcard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard(user: user_dependency, db: db_dependency, flashcard_id: str):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='authentication failed'
        )
    
    try:
        flashcards_usecase = FlashcardsUseCase(db=db)
        flashcards_usecase.delete_flashcard(user.get('id'), flashcard_id)
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting flashcard: {str(e.detail)}"
        )

    return None

@router.put("/{flashcard_id}", status_code=status.HTTP_200_OK)
async def update_flashcard(
    user: user_dependency,
    db: db_dependency,
    flashcard_id: str,
    flashcard: str = Form(...),
    file: UploadFile = File(None)
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='authentication failed'
        )

    try:
        flashcards_usecase = FlashcardsUseCase(db=db)
        updated_flashcard = flashcards_usecase.update_flashcard(
            user_id=user.get('id'),
            flashcard_id=flashcard_id,
            flashcard_request=flashcard,
            file=file
        )
        response = updated_flashcard
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating flashcard: {str(e.detail)}"
        )
    
    return response
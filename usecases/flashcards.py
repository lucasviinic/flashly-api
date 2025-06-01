from datetime import datetime, timezone
import json
import os
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy import func

from core.firebase.client import firebase_file_upload
from models.flashcard_model import Flashcards
from models.requests_model import FlashcardRequest
from models.subject_model import Subjects
from core.openai import client as openai_client
from database import db_dependency
from models.user_model import Users
from services.limit_service import LimitService
from utils.utils import fragment_text


class FlashcardsUseCase:
    def __init__(self, db: db_dependency):
        self.db = db

    def generate_flashcards(
        self,
        content: str,
        quantity: int,
        user_id: str,
        subject_id: str,
        topic_id: str,
        difficulty: int = 1
    ) -> List[dict]:
        user = self._get_user(user_id)
        limit_service = LimitService(self.db, user, Flashcards, Subjects)
        
        allowed_quantity = limit_service.check_flashcard_quota(origin='ai', quantity=quantity)
        
        generated_flashcards = []
        text_fragments = fragment_text(content)
        flashcards_created = 0

        for fragment in text_fragments:
            if flashcards_created >= allowed_quantity:
                break
                
            remaining_quantity = allowed_quantity - flashcards_created
            flashcards_list = openai_client.flash_card_generator(
                prompt=fragment,
                history=generated_flashcards,
                quantity=min(remaining_quantity, quantity),
                difficulty=difficulty
            )
            
            flashcards_to_add = flashcards_list[:remaining_quantity]
            generated_flashcards.extend(flashcards_to_add)
            flashcards_created += len(flashcards_to_add)

        result = []
        for flashcard in generated_flashcards:
            flashcard_model = self._create_flashcard_model(
                user_id=user_id,
                subject_id=subject_id,
                topic_id=topic_id,
                difficulty=difficulty,
                origin='ai',
                question=flashcard.get('question'),
                answer=flashcard.get('answer'),
                opened=True
            )
            result.append(flashcard_model.to_dict())

        return result

    def create_flashcard(
        self,
        flashcard_request: FlashcardRequest,
        user_id: str,
        file: UploadFile = None
    ) -> dict:
        user = self._get_user(user_id)
        limit_service = LimitService(self.db, user, Flashcards, Subjects)
        limit_service.check_flashcard_quota(origin='user', quantity=1)

        try:
            if isinstance(flashcard_request, str):
                flashcard_data = json.loads(flashcard_request)
            else:
                flashcard_data = flashcard_request.model_dump()

            flashcard_model = self._create_flashcard_model(
                user_id=user_id,
                origin='user',
                **flashcard_data
            )

            if file:
                self._handle_file_upload(flashcard_model, file)

            return flashcard_model.to_dict()

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error creating flashcard: {str(e)}"
            )

    def retrieve_all_flashcards(
        self,
        topic_id: str,
        user_id: str,
        limit: Optional[int] = 20,
        offset: Optional[int] = 0,
        difficulties: Optional[List[int]] = None,
        ai_generated: Optional[bool] = None
    ) -> Tuple[List[dict], int]:
        query = self.db.query(Flashcards).filter(
            Flashcards.topic_id == topic_id,
            Flashcards.user_id == user_id,
            Flashcards.deleted_at.is_(None)
        )

        if difficulties:
            query = query.filter(Flashcards.difficulty.in_(difficulties))

        if ai_generated is not None:
            origin = "ai" if ai_generated else "user"
            query = query.filter(Flashcards.origin == origin)

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

    def delete_flashcard(self, user_id: str, flashcard_id: int) -> None:
        flashcard_model = self._get_flashcard(user_id, flashcard_id)
        flashcard_model.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_flashcard(
        self,
        user_id: str,
        flashcard_id: int,
        flashcard_request: FlashcardRequest,
        file: UploadFile = None
    ) -> dict:
        flashcard_model = self._get_flashcard(user_id, flashcard_id)

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
                self._handle_file_upload(flashcard_model, file)

            self.db.commit()
            self.db.refresh(flashcard_model)

            return flashcard_model.to_dict()

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error updating flashcard: {str(e)}"
            )

    def _get_user(self, user_id: str) -> Users:
        user = self.db.query(Users).filter(
            Users.id == user_id,
            Users.deleted_at.is_(None)
        ).first()
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        return user

    def _get_flashcard(self, user_id: str, flashcard_id: int) -> Flashcards:
        flashcard = self.db.query(Flashcards).filter(
            Flashcards.id == flashcard_id,
            Flashcards.user_id == user_id,
            Flashcards.deleted_at.is_(None)
        ).first()
        if not flashcard:
            raise HTTPException(status_code=404, detail='Flashcard not found')
        return flashcard

    def _create_flashcard_model(self, **kwargs) -> Flashcards:
        flashcard_model = Flashcards(**kwargs)
        self.db.add(flashcard_model)
        self.db.commit()
        self.db.refresh(flashcard_model)
        return flashcard_model

    def _handle_file_upload(self, flashcard_model: Flashcards, file: UploadFile) -> None:
        try:
            image_url = firebase_file_upload(
                bucket_blob=os.getenv("FIREBASE_FLASHCARD_IMAGE_BLOB"),
                file_image=file,
                image_id=str(flashcard_model.id)
            )
            flashcard_model.image_url = image_url
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading image: {str(e)}"
            )
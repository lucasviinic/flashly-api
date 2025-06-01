from datetime import date
from sqlalchemy import cast, Date
from fastapi import HTTPException

from utils.constants import USER_LIMITS


class LimitService:
    def __init__(self, db, user, flashcard_model, subject_model):
        self.db = db
        self.user = user
        self.Flashcards = flashcard_model
        self.Subjects = subject_model
        self.limits = USER_LIMITS[user.account_type]

    def _count(self, model, **filters):
        return self.db.query(model).filter_by(**filters).filter(
            cast(model.created_at, Date) == date.today(),
            model.deleted_at.is_(None)
        ).count()

    def get_usage(self):
        usage = {}

        usage['flashcards'] = (self._count(self.Flashcards, user_id=self.user.id),
                               self.limits['daily_flashcards_limit'])
        usage['ai_flashcards'] = (self._count(self.Flashcards, user_id=self.user.id, origin='ai'),
                                  self.limits['daily_ai_gen_flashcards_limit'])
        usage['subjects'] = (self._count(self.Subjects, user_id=self.user.id),
                             self.limits['daily_subjects_limit'])
        return usage

    
    def check_flashcard_quota(self, origin='manual', quantity=1):
        used, limit = self.get_usage()['ai_flashcards' if origin == 'ai' else 'flashcards']
        available = limit - used
        
        if quantity > available:
            if available <= 0:
                detail = 'AI generated flashcards limit reached' if origin == 'ai' else 'Flashcard limit reached'
                raise HTTPException(status_code=400, detail=detail)
            return available
        
        return quantity

    def check_subject_quota(self):
        used, limit = self.get_usage()['subjects']
        if used + 1 > limit:
            raise HTTPException(status_code=400, detail='Subjects limit reached')

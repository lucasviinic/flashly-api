from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.user_model import Users


def process_payment_usecase(user_id: str, amount: float, description: str) -> bool:
    return True

def add_credits_usecase(db: Session, user_id: str, credits: int) -> Users:
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.credits += credits
    db.commit()
    db.refresh(user)
    return user
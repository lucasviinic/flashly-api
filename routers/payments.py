from typing import Annotated, List
from starlette import status
from fastapi import APIRouter, Depends, HTTPException, Path
from database import db_dependency
from models.user_model import Users
from usecases.auth import get_current_user_usecase
from usecases.payments import process_payment_usecase, add_credits_usecase
from utils.constants import CREDIT_PACKAGES


router = APIRouter(
    prefix="/payments",
    tags=["payments"]
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]

@router.get("/credit-packages", response_model=List[dict])
async def get_credit_packages():
    return CREDIT_PACKAGES

@router.post("/purchase-credits/{package_id}", status_code=status.HTTP_200_OK)
async def purchase_credits(
    db: db_dependency,
    user: user_dependency,
    package_id: int = Path(..., gt=0, description="ID do pacote de créditos")
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed'
        )

    try:
        package = next((p for p in CREDIT_PACKAGES if p["id"] == package_id), None)
        
        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found"
            )

        payment_success = process_payment_usecase(
            user_id=user.get('id'),
            amount=package["price"],
            description=f"Compra de {package['credits']} créditos"
        )

        if not payment_success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment processing failed"
            )

        updated_user = add_credits_usecase(
            db=db,
            user_id=user.get('id'),
            credits=package["credits"]
        )

        return {
            "message": "Credits added successfully",
            "new_balance": updated_user.credits,
            "package": {
                "id": package["id"],
                "credits": package["credits"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing credit purchase: {str(e)}"
        )
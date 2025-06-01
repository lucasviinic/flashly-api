from typing import Annotated
from starlette import status
from fastapi import APIRouter, Depends, HTTPException, Query
from database import db_dependency
from usecases.auth import get_current_user_usecase
from usecases.subscriptions import SubscriptionUseCase
from utils.constants import CREDIT_PACKAGES


router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"]
)

user_dependency = Annotated[dict, Depends(get_current_user_usecase)]

@router.get("/verify-subscription", status_code=status.HTTP_200_OK)
async def verify_subscription(
    db: db_dependency,
    user: user_dependency,
    package_name: str = Query(..., description="Nome do pacote da aplicação"),
    purchase_token: str = Query(..., description="Token de compra da assinatura"),
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail='Authentication failed'
        )

    try:
        subscription_usecase = SubscriptionUseCase()
        
        result = subscription_usecase.verify_and_process_subscription(
            db=db,
            user_id=user.get('id'),
            package_name=package_name,
            purchase_token=purchase_token
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return {
            "message": "Assinatura verificada com sucesso",
            "subscription": result["subscription_data"],
            "database": result["database_record"],
            "status": result["subscription_status"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao verificar assinatura: {str(e)}"
        )

@router.get("", status_code=status.HTTP_200_OK)
async def get_user_subscriptions(
    db: db_dependency,
    user: user_dependency
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail='Authentication failed'
        )
    
    try:
        subscription_usecase = SubscriptionUseCase()
        
        result = subscription_usecase.get_user_active_subscriptions(
            db=db, 
            user_id=user.get('id')
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return {
            "message": "Assinaturas recuperadas com sucesso",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar assinaturas: {str(e)}"
        )

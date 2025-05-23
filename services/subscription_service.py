from datetime import datetime
from fastapi import HTTPException
from googleapiclient.discovery import build
from google.oauth2 import service_account
from sqlalchemy.orm import Session
from typing import Dict, Any

from models.user_model import Users


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def verify_google_subscription(self, package_name: str, subscription_name: str, purchase_token: str) -> Dict[str, Any]:
        """
        Verifica o status da assinatura no Google Play
        """
        try:
            credentials = service_account.Credentials.from_service_account_file(
                'google-service-account.json',
                scopes=['https://www.googleapis.com/auth/androidpublisher']
            )

            service = build('androidpublisher', 'v3', credentials=credentials)

            result = service.purchases().subscriptions().get(
                packageName=package_name,
                subscriptionId=subscription_name,
                token=purchase_token
            ).execute()

            return {
                "status": result.get("paymentState"),
                "autoRenewing": result.get("autoRenewing"),
                "expiryTimeMillis": result.get("expiryTimeMillis"),
                "orderId": result.get("orderId"),
                "originalJson": result
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao verificar assinatura: {str(e)}"
            )

    def check_user_subscription(self, user_model: Users) -> bool:
        """
        Verifica se a assinatura do usuário está ativa
        
        Retorna True se a assinatura estiver ativa, False caso contrário
        """
            
        try:
            # Verifica a assinatura diretamente no Google Play
            subscription_info = self.verify_google_subscription(
                user_model.package_name,
                user_model.subscription_id,
                user_model.subscription_token
            )
            
            # Verifica se o paymentState é 1 (pago) e se está autoRenewing ou ainda dentro da validade
            payment_state = subscription_info.get("status")
            auto_renewing = subscription_info.get("autoRenewing", False)
            expiry_millis = subscription_info.get("expiryTimeMillis")
            
            if expiry_millis:
                expiry_date = datetime.fromtimestamp(int(expiry_millis) / 1000)
                user_model.subscription_expiry = expiry_date
            
            # Se o pagamento for válido e a assinatura estiver ativa ou dentro da validade
            if payment_state == 1 and (auto_renewing or (expiry_millis and datetime.now() < expiry_date)):
                user_model.account_type = 1
                self.db.commit()
                return True
            else:
                user_model.account_type = 0
                self.db.commit()
                return False
                
        except Exception as e:
            # Em caso de erro, verifica apenas a data de expiração salva no banco
            if user_model.subscription_expiry is None or user_model.subscription_expiry < datetime.now():
                user_model.account_type = 0
                self.db.commit()
                return False
            return user_model.account_type == 1

    def get_user_with_subscription_check(self, user_id: str) -> Users:
        """
        Obtém o usuário e verifica a situação da assinatura
        """
        user_model = self.db.query(Users).filter(Users.id == user_id, Users.deleted_at.is_(None)).first()

        if not user_model:
            raise HTTPException(status_code=400, detail='user not found')

        # Verifica se a assinatura ainda é válida (consultando o Google Play)
        self.check_user_subscription(user_model)
            
        return user_model
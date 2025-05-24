import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class SubscriptionService:    
    def __init__(self, credentials_path: str = 'play-console-validator.json'):
        self.credentials_path = credentials_path
        self._service = None
    
    def _get_google_play_service(self):
        """Inicializa o serviço do Google Play API"""
        if not self._service:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/androidpublisher']
            )
            self._service = build('androidpublisher', 'v3', credentials=credentials)
        return self._service
    
    def verify_subscription_with_google(self, package_name: str, purchase_token: str) -> Dict[str, Any]:
        """
        Verifica a assinatura diretamente com o Google Play
        
        Args:
            package_name: Nome do pacote da aplicação
            purchase_token: Token de compra da assinatura
            
        Returns:
            Dict com os dados da resposta do Google Play
            
        Raises:
            Exception: Se houver erro na verificação
        """
        try:
            service = self._get_google_play_service()
            
            result = service.purchases().subscriptionsv2().get(
                packageName=package_name,
                token=purchase_token
            ).execute()
            
            return result
            
        except HttpError as e:
            raise Exception(f"Erro na API do Google Play: {e}")
        except Exception as e:
            raise Exception(f"Erro ao verificar assinatura: {str(e)}")
    
    def parse_google_datetime(self, datetime_str: str) -> datetime:
        """
        Converte string de data do Google Play para datetime
        
        Args:
            datetime_str: String de data no formato ISO do Google
            
        Returns:
            datetime object
        """
        try:
            if not datetime_str:
                return datetime.now(timezone.utc)
            
            # Remove o 'Z' no final e parseia
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1] + '+00:00'
            
            return datetime.fromisoformat(datetime_str)
        except Exception:
            return datetime.now(timezone.utc)
    
    def extract_subscription_data(self, google_response: Dict[str, Any], package_name: str, purchase_token: str) -> Dict[str, Any]:
        """
        Extrai e estrutura os dados da resposta do Google Play
        
        Args:
            google_response: Resposta completa do Google Play API
            package_name: Nome do pacote
            purchase_token: Token de compra
            
        Returns:
            Dict com dados estruturados da assinatura
        """
        line_items = google_response.get("lineItems", [])
        line_item = line_items[0] if line_items else {}
        
        start_time = google_response.get("startTime")
        expiry_time = line_item.get("expiryTime")
        subscription_state = google_response.get("subscriptionState")
        
        recurring_price = line_item.get("autoRenewingPlan", {}).get("recurringPrice", {})
        
        offer_details = line_item.get("offerDetails", {})
        
        return {
            "package_name": package_name,
            "purchase_token": purchase_token,
            "product_id": line_item.get("productId", ""),
            "start_date": self.parse_google_datetime(start_time),
            "expiration_date": self.parse_google_datetime(expiry_time),
            "subscription_state": subscription_state,
            "latest_order_id": google_response.get("latestOrderId"),
            "region_code": google_response.get("regionCode"),
            "auto_renewing": line_item.get("autoRenewingPlan", {}).get("autoRenewEnabled", False),
            "acknowledgement_state": google_response.get("acknowledgementState"),
            "linked_purchase_token": google_response.get("linkedPurchaseToken"),
            "currency_code": recurring_price.get("currencyCode"),
            "price_nanos": recurring_price.get("nanos"),
            "base_plan_id": offer_details.get("basePlanId"),
            "original_json": json.dumps(google_response),
            "is_active": True,
            "updated_at": datetime.now(timezone.utc)
        }
    
    def is_subscription_active(self, subscription_state: str, expiration_date: datetime) -> bool:
        """
        Verifica se uma assinatura está ativa baseada no estado e data de expiração
        
        Args:
            subscription_state: Estado da assinatura retornado pelo Google
            expiration_date: Data de expiração da assinatura
            
        Returns:
            bool: True se a assinatura estiver ativa
        """
        active_states = [
            "SUBSCRIPTION_STATE_ACTIVE",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",  # Período de carência
            "SUBSCRIPTION_STATE_ON_HOLD"  # Em espera (ainda válida)
        ]
        
        # Verifica se o estado é ativo E se não expirou
        is_state_active = subscription_state in active_states
        is_not_expired = expiration_date > datetime.now(timezone.utc)
        
        return is_state_active and is_not_expired
    
    def get_subscription_status_info(self, google_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa o status da assinatura e retorna informações detalhadas
        
        Args:
            google_response: Resposta do Google Play API
            
        Returns:
            Dict com informações do status da assinatura
        """
        subscription_state = google_response.get("subscriptionState")
        line_items = google_response.get("lineItems", [])
        
        expiry_time = None
        auto_renewing = False
        
        if line_items:
            expiry_time = line_items[0].get("expiryTime")
            auto_renewing = line_items[0].get("autoRenewingPlan", {}).get("autoRenewEnabled", False)
        
        expiration_date = self.parse_google_datetime(expiry_time) if expiry_time else datetime.now(timezone.utc)
        is_active = self.is_subscription_active(subscription_state, expiration_date)
        
        status_messages = {
            "SUBSCRIPTION_STATE_ACTIVE": "Assinatura ativa",
            "SUBSCRIPTION_STATE_EXPIRED": "Assinatura expirada",
            "SUBSCRIPTION_STATE_CANCELED": "Assinatura cancelada",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD": "Assinatura em período de carência",
            "SUBSCRIPTION_STATE_ON_HOLD": "Assinatura em espera",
            "SUBSCRIPTION_STATE_PAUSED": "Assinatura pausada"
        }
        
        return {
            "is_active": is_active,
            "subscription_state": subscription_state,
            "status_message": status_messages.get(subscription_state, "Status desconhecido"),
            "auto_renewing": auto_renewing,
            "expiration_date": expiration_date,
            "expiry_time_millis": expiry_time,
            "days_until_expiry": (expiration_date - datetime.now(timezone.utc)).days if expiration_date > datetime.now(timezone.utc) else 0,
            "should_save_to_database": is_active
        }
    
    def validate_subscription_data(self, package_name: str, purchase_token: str) -> Dict[str, Any]:
        """
        Valida os dados da assinatura antes de processar
        
        Args:
            package_name: Nome do pacote
            purchase_token: Token de compra
            
        Returns:
            Dict com resultado da validação
        """
        errors = []
        
        if not package_name or not package_name.strip():
            errors.append("Package name é obrigatório")
        
        if not purchase_token or not purchase_token.strip():
            errors.append("Purchase token é obrigatório")
        
        if len(purchase_token) < 10:  # Tokens do Google são bem longos
            errors.append("Purchase token parece inválido")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }
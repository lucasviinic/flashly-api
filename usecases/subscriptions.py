from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from models.subscription_model import Subscription
from services.subscription_service import SubscriptionService


class SubscriptionUseCase:    
    def __init__(self):
        self.subscription_service = SubscriptionService()
    
    def verify_and_process_subscription(
        self, 
        db: Session, 
        user_id: str, 
        package_name: str, 
        purchase_token: str
    ) -> Dict[str, Any]:
        """
        Verifies the subscription with Google Play and processes it in the database

        Args:
            db: Database session
            user_id: User ID
            package_name: Application package name
            purchase_token: Subscription purchase token

        Returns:
            Dict with the verification and processing result
        """
        try:            
            google_response = self.subscription_service.verify_subscription_with_google(
                package_name, purchase_token
            )
            
            status_info = self.subscription_service.get_subscription_status_info(google_response)
            
            subscription_data = self.subscription_service.extract_subscription_data(
                google_response, package_name, purchase_token
            )
            
            subscription_record = None
            if status_info["should_save_to_database"]:
                subscription_record = self._create_or_update_subscription(
                    db, user_id, subscription_data
                )
            
            return {
                "success": True,
                "subscription_status": status_info,
                "subscription_data": {
                    "subscriptionState": status_info["subscription_state"],
                    "autoRenewing": status_info["auto_renewing"],
                    "expiryTimeMillis": status_info["expiry_time_millis"],
                    "isActive": status_info["is_active"],
                    "statusMessage": status_info["status_message"],
                    "daysUntilExpiry": status_info["days_until_expiry"],
                    "originalJson": google_response
                },
                "database_record": {
                    "saved": subscription_record is not None,
                    "subscription_id": subscription_record.id if subscription_record else None,
                    "user_id": user_id
                },
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "subscription_data": None,
                "database_record": {"saved": False}
            }
    
    def _create_or_update_subscription(
        self, 
        db: Session, 
        user_id: str, 
        subscription_data: Dict[str, Any]
    ) -> Optional[Subscription]:
        """
        Creates or updates a subscription in the database

        Args:
            db: Database session
            user_id: User ID
            subscription_data: Subscription data

        Returns:
            Subscription: Created/updated subscription record
        """
        try:
            existing_subscription = db.query(Subscription).filter(
                Subscription.purchase_token == subscription_data["purchase_token"]
            ).first()
            
            if existing_subscription:
                for key, value in subscription_data.items():
                    if key != "user_id" and hasattr(existing_subscription, key):
                        setattr(existing_subscription, key, value)
                
                existing_subscription.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing_subscription)
                return existing_subscription
            else:
                subscription_data["user_id"] = user_id
                new_subscription = Subscription(**subscription_data)
                db.add(new_subscription)
                db.commit()
                db.refresh(new_subscription)
                return new_subscription
                
        except Exception as e:
            db.rollback()
            raise Exception(f"Erro ao salvar assinatura no banco: {str(e)}")
    
    def get_user_active_subscriptions(self, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Fetches all active subscriptions of the user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with the user's active subscriptions
        """
        try:
            active_subscriptions = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.expiration_date > datetime.utcnow()
            ).all()
            
            truly_active = []
            for sub in active_subscriptions:
                if self.subscription_service.is_subscription_active(
                    sub.subscription_state, sub.expiration_date
                ):
                    truly_active.append(sub)
            
            return {
                "success": True,
                "user_id": user_id,
                "total_subscriptions": len(truly_active),
                "has_active_subscription": len(truly_active) > 0,
                "subscriptions": [
                    {
                        "id": sub.id,
                        "product_id": sub.product_id,
                        "subscription_state": sub.subscription_state,
                        "start_date": sub.start_date.isoformat(),
                        "expiration_date": sub.expiration_date.isoformat(),
                        "auto_renewing": sub.auto_renewing,
                        "currency_code": sub.currency_code,
                        "price_nanos": sub.price_nanos,
                        "region_code": sub.region_code,
                        "latest_order_id": sub.latest_order_id,
                        "days_until_expiry": (sub.expiration_date - datetime.utcnow()).days
                    } for sub in truly_active
                ]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id,
                "subscriptions": []
            }
    
    def check_user_premium_status(self, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Checks if the user has premium status based on subscriptions

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with the user's premium status
        """
        try:
            user_subscriptions = self.get_user_active_subscriptions(db, user_id)
            
            if not user_subscriptions["success"]:
                return {
                    "success": False,
                    "is_premium": False,
                    "error": user_subscriptions.get("error")
                }
            
            has_active = user_subscriptions["has_active_subscription"]
            next_expiry = None
            
            if has_active and user_subscriptions["subscriptions"]:
                expiry_dates = [
                    datetime.fromisoformat(sub["expiration_date"]) 
                    for sub in user_subscriptions["subscriptions"]
                ]
                next_expiry = max(expiry_dates)
            
            return {
                "success": True,
                "user_id": user_id,
                "is_premium": has_active,
                "active_subscriptions_count": user_subscriptions["total_subscriptions"],
                "premium_expires_at": next_expiry.isoformat() if next_expiry else None,
                "days_until_expiry": (next_expiry - datetime.utcnow()).days if next_expiry else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "is_premium": False,
                "error": str(e)
            }
    
    def deactivate_subscription(self, db: Session, subscription_id: int, user_id: str) -> Dict[str, Any]:
        """
        Deactivates a specific subscription (soft delete)

        Args:
            db: Database session
            subscription_id: Subscription ID
            user_id: User ID (for validation)

        Returns:
            Dict with the result of the operation
        """
        try:
            subscription = db.query(Subscription).filter(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "error": "Assinatura não encontrada"
                }
            
            subscription.is_active = False
            subscription.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "success": True,
                "message": "Assinatura desativada com sucesso",
                "subscription_id": subscription_id
            }
            
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": f"Erro ao desativar assinatura: {str(e)}"
            }
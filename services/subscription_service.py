import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from enum import Enum

from sqlalchemy import UUID


class SubscriptionState(Enum):
    ACTIVE = "SUBSCRIPTION_STATE_ACTIVE"
    EXPIRED = "SUBSCRIPTION_STATE_EXPIRED"
    CANCELED = "SUBSCRIPTION_STATE_CANCELED"
    IN_GRACE_PERIOD = "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"
    ON_HOLD = "SUBSCRIPTION_STATE_ON_HOLD"
    PAUSED = "SUBSCRIPTION_STATE_PAUSED"


class AcknowledgementState(Enum):
    ACKNOWLEDGED = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
    PENDING = "ACKNOWLEDGEMENT_STATE_PENDING"


@dataclass
class SubscriptionPrice:
    currency_code: str
    nanos: int
    
    @property
    def amount(self) -> float:
        return self.nanos / 1_000_000_000 if self.nanos else 0.0


@dataclass
class SubscriptionValidation:
    is_valid: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class SubscriptionStatusInfo:
    is_active: bool
    subscription_state: SubscriptionState
    status_message: str
    auto_renewing: bool
    expiration_date: datetime
    expiry_time_millis: Optional[str]
    days_until_expiry: int
    should_save_to_database: bool


@dataclass
class SubscriptionData:
    package_name: str
    purchase_token: str
    product_id: str
    start_date: datetime
    expiration_date: datetime
    subscription_state: SubscriptionState
    latest_order_id: Optional[str]
    region_code: Optional[str]
    auto_renewing: bool
    acknowledgement_state: Optional[AcknowledgementState]
    linked_purchase_token: Optional[str]
    price: Optional[SubscriptionPrice]
    base_plan_id: Optional[str]
    original_json: str
    is_active: bool
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self, user_id: UUID) -> dict:
        return {
            "user_id": user_id,
            "package_name": self.package_name,
            "purchase_token": self.purchase_token,
            "product_id": self.product_id,
            "start_date": self.start_date,
            "expiration_date": self.expiration_date,
            "subscription_state": self.subscription_state.value,
            "latest_order_id": self.latest_order_id,
            "region_code": self.region_code,
            "auto_renewing": self.auto_renewing,
            "acknowledgement_state": self.acknowledgement_state.value if self.acknowledgement_state else None,
            "currency_code": self.price.currency_code if self.price else None,
            "price_nanos": self.price.nanos if self.price else None,
            "base_plan_id": self.base_plan_id,
            "linked_purchase_token": self.linked_purchase_token,
            "original_json": self.original_json,
            "is_active": self.is_active,
            "updated_at": self.updated_at
        }


class GooglePlaySubscriptionError(Exception):
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class SubscriptionService:
    ACTIVE_STATES = {
        SubscriptionState.ACTIVE,
        SubscriptionState.IN_GRACE_PERIOD,
        SubscriptionState.ON_HOLD
    }
    
    STATUS_MESSAGES = {
        SubscriptionState.ACTIVE: "Active subscription",
        SubscriptionState.EXPIRED: "Expired subscription",
        SubscriptionState.CANCELED: "Canceled subscription",
        SubscriptionState.IN_GRACE_PERIOD: "Subscription in grace period",
        SubscriptionState.ON_HOLD: "Subscription on hold",
        SubscriptionState.PAUSED: "Paused subscription"
    }

    def __init__(self, credentials_path: str = 'play-console-validator.json'):
        self.credentials_path = credentials_path
        self._service = None
    
    def _get_google_play_service(self):
        if not self._service:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/androidpublisher']
            )
            self._service = build('androidpublisher', 'v3', credentials=credentials)
        return self._service
    
    def verify_subscription_with_google(self, package_name: str, purchase_token: str) -> Dict[str, Any]:
        try:
            service = self._get_google_play_service()
            
            result = service.purchases().subscriptionsv2().get(
                packageName=package_name,
                token=purchase_token
            ).execute()
            
            return result
            
        except HttpError as e:
            raise GooglePlaySubscriptionError(f"Google Play API error: {e}", e)
        except Exception as e:
            raise GooglePlaySubscriptionError(f"Subscription verification error: {str(e)}", e)
    
    def _parse_google_datetime(self, datetime_str: Optional[str]) -> datetime:
        try:
            if not datetime_str:
                return datetime.now(timezone.utc)
            
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1] + '+00:00'
            
            return datetime.fromisoformat(datetime_str)
        except Exception:
            return datetime.now(timezone.utc)
    
    def _extract_price(self, line_item: Dict[str, Any]) -> Optional[SubscriptionPrice]:
        recurring_price = line_item.get("autoRenewingPlan", {}).get("recurringPrice", {})
        
        if not recurring_price:
            return None
            
        return SubscriptionPrice(
            currency_code=recurring_price.get("currencyCode", ""),
            nanos=recurring_price.get("nanos", 0)
        )
    
    def extract_subscription_data(self, google_response: Dict[str, Any], 
                                package_name: str, purchase_token: str) -> SubscriptionData:
        line_items = google_response.get("lineItems", [])
        line_item = line_items[0] if line_items else {}
        
        start_time = google_response.get("startTime")
        expiry_time = line_item.get("expiryTime")
        subscription_state_str = google_response.get("subscriptionState")
        acknowledgement_state_str = google_response.get("acknowledgementState")
        
        subscription_state = SubscriptionState(subscription_state_str) if subscription_state_str else SubscriptionState.ACTIVE
        acknowledgement_state = AcknowledgementState(acknowledgement_state_str) if acknowledgement_state_str else None
        
        expiration_date = self._parse_google_datetime(expiry_time)
        is_active = self.is_subscription_active(subscription_state, expiration_date)
        
        return SubscriptionData(
            package_name=package_name,
            purchase_token=purchase_token,
            product_id=line_item.get("productId", ""),
            start_date=self._parse_google_datetime(start_time),
            expiration_date=expiration_date,
            subscription_state=subscription_state,
            latest_order_id=google_response.get("latestOrderId"),
            region_code=google_response.get("regionCode"),
            auto_renewing=line_item.get("autoRenewingPlan", {}).get("autoRenewEnabled", False),
            acknowledgement_state=acknowledgement_state,
            linked_purchase_token=google_response.get("linkedPurchaseToken"),
            price=self._extract_price(line_item),
            base_plan_id=line_item.get("offerDetails", {}).get("basePlanId"),
            original_json=json.dumps(google_response),
            is_active=is_active
        )
    
    def is_subscription_active(
            self, subscription_state: SubscriptionState, 
            expiration_date: datetime
        ) -> bool:

        is_state_active = subscription_state.value == SubscriptionState.ACTIVE.value
        is_not_expired = expiration_date > datetime.now(timezone.utc)
        
        return is_state_active and is_not_expired
    
    def get_subscription_status_info(self, google_response: Dict[str, Any]) -> SubscriptionStatusInfo:
        subscription_state_str = google_response.get("subscriptionState")
        subscription_state = SubscriptionState(subscription_state_str) if subscription_state_str else SubscriptionState.ACTIVE
        
        line_items = google_response.get("lineItems", [])
        
        expiry_time = None
        auto_renewing = False
        
        if line_items:
            expiry_time = line_items[0].get("expiryTime")
            auto_renewing = line_items[0].get("autoRenewingPlan", {}).get("autoRenewEnabled", False)
        
        expiration_date = self._parse_google_datetime(expiry_time) if expiry_time else datetime.now(timezone.utc)
        is_active = self.is_subscription_active(subscription_state, expiration_date)
        
        days_until_expiry = 0
        if expiration_date > datetime.now(timezone.utc):
            days_until_expiry = (expiration_date - datetime.now(timezone.utc)).days
        
        return SubscriptionStatusInfo(
            is_active=is_active,
            subscription_state=subscription_state,
            status_message=self.STATUS_MESSAGES.get(subscription_state, "Unknown status"),
            auto_renewing=auto_renewing,
            expiration_date=expiration_date,
            expiry_time_millis=expiry_time,
            days_until_expiry=days_until_expiry,
            should_save_to_database=is_active
        )
    
    def validate_subscription_data(self, package_name: str, purchase_token: str) -> SubscriptionValidation:
        errors = []
        
        if not package_name or not package_name.strip():
            errors.append("Package name is required")
        
        if not purchase_token or not purchase_token.strip():
            errors.append("Purchase token is required")
        
        if len(purchase_token) < 10:
            errors.append("Purchase token appears to be invalid")
        
        return SubscriptionValidation(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def get_complete_subscription_info(self, package_name: str, 
                                     purchase_token: str) -> tuple[SubscriptionData, SubscriptionStatusInfo]:
        validation = self.validate_subscription_data(package_name, purchase_token)
        if not validation.is_valid:
            raise GooglePlaySubscriptionError(f"Invalid data: {', '.join(validation.errors)}")
        
        google_response = self.verify_subscription_with_google(package_name, purchase_token)
        subscription_data = self.extract_subscription_data(google_response, package_name, purchase_token)
        status_info = self.get_subscription_status_info(google_response)
        
        return subscription_data, status_info
    
    def check_subscription_active(self, package_name: str, purchase_token: str) -> bool:
        try:
            _, status_info = self.get_complete_subscription_info(package_name, purchase_token)
            return status_info.is_active
        except GooglePlaySubscriptionError:
            return False
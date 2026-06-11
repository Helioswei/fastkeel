# fastkeel/modules/payment.py
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Session

from fastkeel.core.auth import get_current_user
from fastkeel.core.config import Config
from fastkeel.core.db import Base, get_db, init_db


class SubscriptionPlan(Base):
    __tablename__ = "fastkeel_subscription_plans"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    currency = Column(String, default="cny", nullable=False)
    duration_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class Subscription(Base):
    __tablename__ = "fastkeel_subscriptions"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("fastkeel_users.id"), index=True, nullable=False)
    plan_id = Column(String, ForeignKey("fastkeel_subscription_plans.id"), nullable=False)
    status = Column(String, default="active", nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    auto_renew = Column(Boolean, default=True, nullable=False)
    provider = Column(String, default="", nullable=False)
    provider_order_id = Column(String, default="", nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class PaymentRecord(Base):
    __tablename__ = "fastkeel_payment_records"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("fastkeel_users.id"), index=True, nullable=False)
    subscription_id = Column(String, ForeignKey("fastkeel_subscriptions.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="cny", nullable=False)
    provider = Column(String, nullable=False)
    provider_order_id = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class VerifyRequest(BaseModel):
    provider: str
    receipt: dict
    plan_id: str


class SubscriptionInfo(BaseModel):
    id: str
    status: str
    start_date: datetime
    end_date: datetime
    plan_id: str
    auto_renew: bool

    model_config = {"from_attributes": True}


class VerifyResponse(BaseModel):
    valid: bool
    subscription: SubscriptionInfo | None = None


class PlanResponse(BaseModel):
    id: str
    name: str
    price: int
    currency: str
    duration_days: int

    model_config = {"from_attributes": True}


class SubscriptionStatusResponse(BaseModel):
    has_active: bool
    subscription: SubscriptionInfo | None = None


receipt_verifiers: dict[str, Callable] = {}
webhook_parsers: dict[str, Callable] = {}


def register_verifier(provider: str, func: Callable) -> None:
    """Register a receipt verifier for the given provider.

    The function should accept a single argument (receipt dict) and return a dict
    with at least a 'valid' key.
    """
    receipt_verifiers[provider] = func


def register_webhook_parser(provider: str, func: Callable) -> None:
    """Register a webhook parser for the given provider.

    The function should accept two arguments (body dict, headers dict) and return a dict
    with at least a 'type' key.
    """
    webhook_parsers[provider] = func


def _dev_verify(receipt: dict) -> dict:
    return {
        "valid": True,
        "user_id": receipt.get("user_id", ""),
        "plan_id": receipt.get("plan_id", ""),
        "provider_order_id": receipt.get("order_id", uuid.uuid4().hex),
    }


def _dev_parse_webhook(body: dict, headers: dict) -> dict:
    event_type = body.get("event_type", "renewal")
    return {
        "type": event_type,
        "subscription_id": body.get("subscription_id", ""),
        "new_end_date": body.get("new_end_date"),
        "user_id": body.get("user_id", ""),
    }


register_verifier("dev", lambda receipt: _dev_verify(receipt))
register_webhook_parser("dev", lambda body, headers: _dev_parse_webhook(body, headers))


_payment_config: Config | None = None


def _get_config() -> Config:
    if _payment_config is None:
        raise RuntimeError("Payment module not initialized")
    return _payment_config


payment_router = APIRouter()


@payment_router.post("/verify", response_model=VerifyResponse)
def verify_receipt(
    body: VerifyRequest,
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> VerifyResponse:
    verifier = receipt_verifiers.get(body.provider)
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider: {body.provider}",
        )

    result = verifier(body.receipt)
    if not result.get("valid"):
        return VerifyResponse(valid=False)

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == body.plan_id,
        SubscriptionPlan.is_active.is_(True),
    ).first()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {body.plan_id}",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    existing = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status.in_(["active", "cancelled"]),
    ).first()

    if existing:
        new_end = max(existing.end_date, now) + timedelta(days=plan.duration_days)
        existing.end_date = new_end
        existing.status = "active"
        existing.updated_at = now
        subscription = existing
    else:
        subscription = Subscription(
            id=uuid.uuid4().hex,
            user_id=current_user.id,
            plan_id=plan.id,
            start_date=now,
            end_date=now + timedelta(days=plan.duration_days),
            provider=body.provider,
            provider_order_id=result.get("provider_order_id", ""),
        )
        db.add(subscription)
        db.flush()

    record = PaymentRecord(
        id=uuid.uuid4().hex,
        user_id=current_user.id,
        subscription_id=subscription.id,
        amount=plan.price,
        currency=plan.currency,
        provider=body.provider,
        provider_order_id=result.get("provider_order_id", ""),
        status="completed",
    )
    db.add(record)
    db.commit()
    db.refresh(subscription)

    return VerifyResponse(
        valid=True,
        subscription=SubscriptionInfo.model_validate(subscription),
    )


@payment_router.get("/subscription", response_model=SubscriptionStatusResponse)
def get_subscription(
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionStatusResponse:
    sub = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status.in_(["active", "cancelled"]),
    ).order_by(Subscription.end_date.desc()).first()

    if sub is None:
        return SubscriptionStatusResponse(has_active=False)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_active = sub.status == "active" and sub.end_date > now

    if not is_active and sub.status == "active":
        sub.status = "expired"
        db.commit()

    if not is_active:
        return SubscriptionStatusResponse(has_active=False)

    return SubscriptionStatusResponse(
        has_active=True,
        subscription=SubscriptionInfo.model_validate(sub),
    )


@payment_router.post("/webhook")
async def payment_webhook(
    request: Request,
    config: Config = Depends(_get_config),
) -> dict:
    body = await request.json()
    provider = request.headers.get("X-Provider", request.headers.get("x-provider", "unknown"))

    parser = webhook_parsers.get(provider)
    if parser is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider: {provider}",
        )

    event = parser(body, dict(request.headers))
    db = next(get_db())

    try:
        if event["type"] == "renewal":
            sub = db.query(Subscription).filter(
                Subscription.id == event.get("subscription_id"),
            ).first()
            if sub and event.get("new_end_date"):
                sub.end_date = datetime.fromisoformat(event["new_end_date"].replace("Z", "+00:00"))
                sub.status = "active"
                db.commit()
        elif event["type"] == "cancellation":
            sub = db.query(Subscription).filter(
                Subscription.id == event.get("subscription_id"),
            ).first()
            if sub:
                sub.auto_renew = False
                db.commit()
        elif event["type"] == "refund":
            sub = db.query(Subscription).filter(
                Subscription.id == event.get("subscription_id"),
            ).first()
            if sub:
                sub.status = "refunded"
                db.commit()

        return {"ok": True}
    finally:
        db.close()


@payment_router.get("/plans", response_model=list[PlanResponse])
def list_plans(
    db: Session = Depends(get_db),
) -> list[PlanResponse]:
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active.is_(True),
    ).all()
    return [PlanResponse.model_validate(p) for p in plans]


def _seed_plans(config: Config, db: Session) -> None:
    if not config.payment_plans:
        return
    for plan_data in config.payment_plans:
        existing = db.get(SubscriptionPlan, plan_data["id"])
        if existing:
            continue
        plan = SubscriptionPlan(
            id=plan_data["id"],
            name=plan_data["name"],
            price=plan_data["price"],
            currency=plan_data.get("currency", "cny"),
            duration_days=plan_data["duration_days"],
            is_active=plan_data.get("is_active", True),
        )
        db.add(plan)
    db.commit()


def include_payment(app: FastAPI, config: Config) -> None:
    global _payment_config
    _payment_config = config

    init_db(config)

    db = next(get_db())
    try:
        _seed_plans(config, db)
    finally:
        db.close()

    app.include_router(payment_router, prefix="/api/v1/payment")

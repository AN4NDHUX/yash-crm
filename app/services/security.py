from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import secrets
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any
from urllib.request import Request as URLRequest, urlopen

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access_policy import request_entitlement_feature, request_resource_action
from app.database import SessionLocal, TENANT_ACTOR_ID, TENANT_ORGANIZATION_ID, get_db
from app.models import *
from app.services.core import *

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"
MIN_PASSWORD_LENGTH = 8

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default

def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}

def _is_platform_owner(actor: User | None) -> bool:
    if not isinstance(actor, User) or str(actor.role or "").lower() != "administrator":
        return False
    configured_username = os.getenv("APP_USERNAME", "").strip().lower()
    actor_username = str(actor.username or "").strip().lower()
    return bool(configured_username and secrets.compare_digest(actor_username, configured_username))

def _app_credentials() -> tuple[str, str]:
    # Hosting secret stores often add a trailing newline when a value is pasted; that
    # silently made a correct password fail with 401.
    return os.getenv("APP_USERNAME", "").strip(), os.getenv("APP_PASSWORD", "").strip("\r\n")


def _basic_auth_valid(header: str) -> bool:
    scheme, _, token = header.strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "basic" or not token:  # the scheme name is case-insensitive (RFC 7235)
        return False
    token += "=" * (-len(token) % 4)  # tolerate clients that omit base64 padding
    try:
        decoded = base64.b64decode(token).decode("utf-8")
        supplied_user, supplied_password = decoded.split(":", 1)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return False
    expected_user, expected_password = _app_credentials()
    user_ok = secrets.compare_digest(supplied_user.encode(), expected_user.encode())
    password_ok = secrets.compare_digest(supplied_password.encode(), expected_password.encode())
    return user_ok and password_ok


def _basic_username(header: str) -> str:
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "basic" or not token:
        return ""
    try:
        token += "=" * (-len(token) % 4)
        decoded = base64.b64decode(token).decode("utf-8")
        return decoded.split(":", 1)[0].strip()
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return ""


AUTH_COOKIE = "yash_session"
AUTH_SESSION_DAYS = max(1, min(_env_int("YASHCRM_SESSION_DAYS", 14), 90))
PASSWORD_ITERATIONS = 260_000


def _password_hash(password: str) -> str:
    password = str(password or "")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must contain at least {MIN_PASSWORD_LENGTH} characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _password_valid(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, int(iterations))
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


def _session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(AUTH_COOKIE, "")
    if not token:
        return None
    now = datetime.utcnow()
    session = db.scalar(select(AuthSession).where(
        AuthSession.token_hash == _session_token_hash(token),
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > now,
    ))
    if session is None:
        return None
    user = db.get(User, session.user_id)
    if user is None or user.status != "Active":
        return None
    if session.last_seen_at < now - timedelta(minutes=5):
        session.last_seen_at = now
        user.last_active = now
        db.commit()
    return user


def _create_session(request: Request, db: Session, user: User, auth_method: str = "password") -> str:
    raw = secrets.token_urlsafe(48)
    now = datetime.utcnow()
    db.add(AuthSession(
        user_id=user.id,
        token_hash=_session_token_hash(raw),
        created_at=now,
        expires_at=now + timedelta(days=AUTH_SESSION_DAYS),
        last_seen_at=now,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
    ))
    user.last_login_at = now
    user.last_active = now
    db.add(LoginHistory(
        user_id=user.id,
        event="login",
        success=True,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
        metadata_json={"path": request.url.path, "method": str(auth_method or "password")[:40]},
    ))
    db.commit()
    return raw


def _revoke_session(request: Request, db: Session) -> None:
    token = request.cookies.get(AUTH_COOKIE, "")
    if not token:
        return
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _session_token_hash(token), AuthSession.revoked_at.is_(None)))
    if session is not None:
        session.revoked_at = datetime.utcnow()
        db.commit()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=AUTH_SESSION_DAYS * 86400,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE, path="/", secure=IS_PRODUCTION, httponly=True, samesite="lax")


def _normalize_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    prefix = "+" if raw.startswith("+") else ""
    digits = re.sub(r"\D", "", raw)
    if not 8 <= len(digits) <= 15:
        raise HTTPException(422, "Enter a valid phone number with 8 to 15 digits")
    return prefix + digits


def _clean_username(value: Any) -> str:
    username = re.sub(r"[^a-z0-9._-]+", "", str(value or "").strip().lower())
    if not 3 <= len(username) <= 40:
        raise HTTPException(422, "Username must contain 3 to 40 letters, numbers, dots, dashes, or underscores")
    return username


def _account_by_identifier(db: Session, identifier: str) -> User | None:
    value = str(identifier or "").strip()
    if not value:
        return None
    lowered = value.lower()
    normalized_phone = re.sub(r"\D", "", value)
    clauses = [func.lower(User.email) == lowered, func.lower(User.username) == lowered]
    if normalized_phone:
        clauses.append(func.replace(func.replace(func.replace(User.phone, "+", ""), " ", ""), "-", "") == normalized_phone)
    return db.scalar(select(User).where(or_(*clauses)))


def _environment_admin_credentials_valid(identifier: str, password: str) -> bool:
    configured_username = os.getenv("APP_USERNAME", "").strip()
    configured_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    configured_password = os.getenv("APP_PASSWORD", "").strip("\r\n")
    if not configured_password or len(configured_password) < MIN_PASSWORD_LENGTH:
        return False
    supplied_identifier = str(identifier or "").strip().lower()
    username_ok = bool(configured_username) and secrets.compare_digest(
        supplied_identifier.encode(), configured_username.lower().encode()
    )
    email_ok = bool(configured_email) and secrets.compare_digest(
        supplied_identifier.encode(), configured_email.encode()
    )
    password_ok = secrets.compare_digest(
        str(password or "").encode(), configured_password.encode()
    )
    return (username_ok or email_ok) and password_ok


def _send_email_message(to_email: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender or not to_email:
        return False
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = env_bool("SMTP_STARTTLS", True)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=12) as client:
            if use_tls:
                client.starttls()
            if username:
                client.login(username, password)
            client.send_message(message)
        return True
    except Exception:
        return False


def _send_sms_message(phone: str, body: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    sender = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    if not sid or not token or not sender or not phone:
        return False
    payload = urlencode({"From": sender, "To": phone, "Body": body}).encode()
    req = URLRequest(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=payload, method="POST")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode())
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req, timeout=12) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def _dispatch_account_message(user: User, subject: str, body: str) -> None:
    email = str(user.email or "")
    phone = str(user.phone or "")
    threading.Thread(target=lambda: _send_email_message(email, subject, body), daemon=True).start()
    if phone:
        threading.Thread(target=lambda: _send_sms_message(phone, body[:1400]), daemon=True).start()


def _notify_account(db: Session, user: User, kind: str, title: str, body: str) -> None:
    db.add(Notification(user_id=user.id, kind=kind, title=title[:220], body=body, resource="account", record_id=user.id))
    db.commit()
    _dispatch_account_message(user, title, body)


def _notify_account_once(db: Session, user: User, kind: str, title: str, body: str, *, within_minutes: int = 10) -> None:
    """Avoid flooding email/SMS providers when a user signs in repeatedly in a short window."""
    cutoff = datetime.utcnow() - timedelta(minutes=max(1, within_minutes))
    recent = db.scalar(select(Notification.id).where(
        Notification.user_id == user.id,
        Notification.kind == kind,
        Notification.created_at >= cutoff,
    ).order_by(Notification.created_at.desc()).limit(1))
    if recent is None:
        _notify_account(db, user, kind, title, body)


def _ensure_plan_catalog(db: Session) -> None:
    """Keep the subscription catalog aligned with the CRM pricing presented in-product."""
    catalog = [
        {
            "code": "free", "name": "Free", "price_monthly": 0, "currency": "INR",
            "max_records": 1000, "max_storage_mb": 250, "max_custom_modules": 2, "ai_limit_monthly": 0,
            "features": {
                "reports": True, "custom_modules": True, "apex": False, "max_users": 3, "inventory_management": False, "cpq": False, "customer_portals": False, "approval_process": False, "developer_sandbox": False,
                "tagline": "Forever free, for 3 users",
                "included_features": [
                    "Contact management", "Follow-up reminders", "Workflow automation",
                    "Custom email templates", "Tasks, meetings & calls", "Data import and export",
                    "Standard reports", "APIs", "Mobile apps"
                ]
            }
        },
        {
            "code": "bigin_express", "name": "Bigin Express", "price_monthly": 400, "currency": "INR",
            "max_records": 5000, "max_storage_mb": 1024, "max_custom_modules": 0, "ai_limit_monthly": 0,
            "features": {
                "reports": True, "custom_modules": False, "apex": False, "max_users": 5, "inventory_management": False, "cpq": False, "customer_portals": False, "approval_process": False, "developer_sandbox": False,
                "tagline": "First-timer, moving from spreadsheets",
                "included_features": [
                    "Sales pipeline", "Built-in calling", "Appointment scheduling", "Payment collection",
                    "Tags", "Email integration", "Calendar integration", "Social Ads integration",
                    "Custom fields", "QuickBooks integration"
                ]
            }
        },
        {
            "code": "standard", "name": "Standard", "price_monthly": 800, "currency": "INR",
            "max_records": 10000, "max_storage_mb": 2048, "max_custom_modules": 10, "ai_limit_monthly": 1500,
            "features": {
                "reports": True, "custom_modules": True, "apex": True, "max_users": 25, "inventory_management": False, "cpq": False, "customer_portals": False, "approval_process": False, "developer_sandbox": False,
                "tagline": "Small team, getting started",
                "included_features": [
                    "Email integration & mass emails", "Built-in calling", "Multiple sales pipelines",
                    "Calendar integration", "Data capture via forms", "Sales forecasting", "Data enrichment",
                    "Custom modules", "HIPAA compliance", "Gmail and Outlook integration",
                    "Slack, Zoom, Teams integration"
                ]
            }
        },
        {
            "code": "professional", "name": "Professional", "price_monthly": 1400, "currency": "INR",
            "max_records": 100000, "max_storage_mb": 10240, "max_custom_modules": 50, "ai_limit_monthly": 10000,
            "features": {
                "reports": True, "custom_modules": True, "apex": True, "advanced_analytics": True, "max_users": 100,
                "inventory_management": True, "cpq": True, "customer_portals": True, "approval_process": False, "developer_sandbox": False,
                "tagline": "Growing team, needs automation", "popular": True,
                "included_features": [
                    "AI agents", "Process management", "Inventory management", "Predictive intelligence",
                    "Unlimited reports", "Configure, Price, Quote (CPQ)", "Custom portals",
                    "Customer journeys", "Web-to-case forms", "Google Ads integration"
                ]
            }
        },
        {
            "code": "enterprise", "name": "Enterprise", "price_monthly": 2400, "currency": "INR",
            "max_records": None, "max_storage_mb": None, "max_custom_modules": None, "ai_limit_monthly": None,
            "features": {
                "reports": True, "custom_modules": True, "apex": True, "advanced_analytics": True, "max_users": None,
                "priority_support": True, "inventory_management": True, "cpq": True, "customer_portals": True, "approval_process": True, "developer_sandbox": True,
                "tagline": "Running a mature sales org",
                "included_features": [
                    "Multi-team management", "Reporting hierarchy", "Custom buttons and functions",
                    "Extended field types", "Sequential data collection", "Approval process",
                    "Account Based Marketing", "Developer sandbox", "Field-level encryption",
                    "Extended AI capabilities", "QuickBooks integration"
                ]
            }
        },
        {
            "code": "crm_plus", "name": "CRM Plus", "price_monthly": 20, "currency": "USD",
            "max_records": None, "max_storage_mb": None, "max_custom_modules": None, "ai_limit_monthly": None,
            "features": {
                "reports": True, "custom_modules": True, "apex": True, "advanced_analytics": True, "max_users": None,
                "priority_support": True, "inventory_management": True, "cpq": True, "customer_portals": True, "approval_process": True, "developer_sandbox": True, "suite_bundle": True,
                "tagline": "Sales, marketing, service in one unified package.",
                "included_features": ["Unified sales workspace", "Marketing workspace", "Customer service workspace"]
            }
        },
    ]

    for spec in catalog:
        plan = db.scalar(select(Plan).where(Plan.code == spec["code"]))
        if plan is None:
            plan = Plan(code=spec["code"])
            db.add(plan)
        plan.name = spec["name"]
        plan.price_monthly = spec["price_monthly"]
        plan.currency = spec["currency"]
        plan.max_records = spec["max_records"]
        plan.max_storage_mb = spec["max_storage_mb"]
        plan.max_custom_modules = spec["max_custom_modules"]
        plan.ai_limit_monthly = spec["ai_limit_monthly"]
        plan.active = True
        plan.features = spec["features"]
    db.flush()


def _default_plan(db: Session) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.code == "free"))
    if plan is None:
        plan = Plan(
            code="free",
            name="Free",
            price_monthly=0,
            currency="INR",
            max_records=1000,
            max_storage_mb=250,
            max_custom_modules=2,
            ai_limit_monthly=0,
            active=True,
            features={"reports": True, "custom_modules": True, "apex": False},
        )
        db.add(plan)
        db.flush()
    return plan


def _organization_slug_for_user(user: User) -> str:
    base = re.sub(r"[^a-z0-9-]+", "-", str(user.username or user.name or f"user-{user.id}").lower()).strip("-")
    return (base or f"user-{user.id}")[:90] + f"-{user.id}"


def _organization_for_user(db: Session, user_id: int) -> Organization | None:
    membership = db.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user_id, OrganizationMember.status == "Active")
        .order_by(OrganizationMember.id)
    )
    return db.get(Organization, membership.organization_id) if membership else None

def _organization_id_for_user(db: Session, user_id: int) -> int | None:
    membership = db.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user_id, OrganizationMember.status == "Active")
        .order_by(OrganizationMember.id)
    )
    return membership.organization_id if membership else None


def _organization_user_ids(db: Session, actor: User) -> set[int]:
    """Return active CRM users in the actor's organization.

    User accounts are global authentication identities, so membership—not the users
    table itself—is the tenant boundary for user administration.
    """
    organization_id = _organization_id_for_user(db, actor.id)
    if organization_id is None:
        return {actor.id}
    return {
        int(user_id)
        for user_id in db.scalars(
            select(OrganizationMember.user_id).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == "Active",
            )
        ).all()
    }


def _user_in_actor_organization(db: Session, actor: User, user_id: int) -> bool:
    return int(user_id) in _organization_user_ids(db, actor)



def _ensure_user_organization(db: Session, user: User) -> Organization:
    organization = _organization_for_user(db, user.id)
    if organization is not None:
        return organization

    organization = Organization(
        name=(user.name or user.username or "Yash CRM")[:160],
        slug=_organization_slug_for_user(user),
        status="Active",
        owner_user_id=user.id,
    )
    db.add(organization)
    db.flush()
    db.add(OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        membership_role="Owner",
        status="Active",
    ))
    db.flush()
    return organization


def _ensure_organization_subscription(db: Session, user: User) -> OrganizationSubscription:
    organization = _ensure_user_organization(db, user)
    subscription = db.scalar(
        select(OrganizationSubscription).where(OrganizationSubscription.organization_id == organization.id)
    )
    if subscription is not None:
        return subscription

    legacy = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    plan = db.get(Plan, legacy.plan_id) if legacy else None
    plan = plan or _default_plan(db)
    now = datetime.utcnow()
    subscription = OrganizationSubscription(
        organization_id=organization.id,
        plan_id=plan.id,
        status=(legacy.status if legacy else "Active"),
        started_at=(legacy.started_at if legacy else now),
        trial_ends_at=(legacy.trial_ends_at if legacy else None),
        current_period_start=(legacy.current_period_start if legacy else now),
        current_period_end=(legacy.current_period_end if legacy else None),
        cancel_at_period_end=(legacy.cancel_at_period_end if legacy else False),
        provider=(legacy.provider if legacy else None),
        provider_customer_id=(legacy.provider_customer_id if legacy else None),
        provider_subscription_id=(legacy.provider_subscription_id if legacy else None),
    )
    db.add(subscription)
    db.flush()
    return subscription


def _ensure_user_subscription(db: Session, user: User) -> OrganizationSubscription:
    """Compatibility wrapper: subscriptions are organization-owned from Tier 0 onward."""
    return _ensure_organization_subscription(db, user)


def _subscription_payload(db: Session, user_id: int) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        return {"plan_code": "free", "plan_name": "Free", "status": "Unknown"}
    subscription = _ensure_organization_subscription(db, user)
    organization = db.get(Organization, subscription.organization_id)
    plan = db.get(Plan, subscription.plan_id)
    pending = db.scalar(
        select(SubscriptionChangeRequest).where(
            SubscriptionChangeRequest.organization_id == subscription.organization_id,
            SubscriptionChangeRequest.status == "Pending Payment",
        ).order_by(SubscriptionChangeRequest.id.desc())
    )
    pending_plan = db.get(Plan, pending.to_plan_id) if pending else None
    return {
        "id": subscription.id,
        "organization_id": subscription.organization_id,
        "organization_name": organization.name if organization else None,
        "status": subscription.status,
        "plan_id": subscription.plan_id,
        "plan_code": plan.code if plan else None,
        "plan_name": plan.name if plan else "Unknown",
        "price_monthly": float(plan.price_monthly or 0) if plan else 0,
        "currency": plan.currency if plan else "INR",
        "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
        "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
        "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "cancel_at_period_end": bool(subscription.cancel_at_period_end),
        "provider": subscription.provider,
        "pending_upgrade": ({
            "request_id": pending.id,
            "plan_id": pending_plan.id if pending_plan else pending.to_plan_id,
            "plan_code": pending_plan.code if pending_plan else None,
            "plan_name": pending_plan.name if pending_plan else "Pending plan",
            "status": pending.status,
            "requested_at": pending.created_at.isoformat() if pending.created_at else None,
        } if pending else None),
    }


def _active_plan(db: Session, actor: User) -> Plan | None:
    # Only the deployment-provisioned platform owner bypasses customer plan limits.
    if _is_platform_owner(actor):
        return None
    subscription = _ensure_organization_subscription(db, actor)
    if str(subscription.status or "").lower() not in {"active", "trialing", "trial"}:
        raise HTTPException(403, detail={"code": "SUBSCRIPTION_INACTIVE", "message": "Your organization subscription is not active."})
    plan = db.get(Plan, subscription.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(403, detail={"code": "PLAN_UNAVAILABLE", "message": "Your organization subscription plan is unavailable."})
    return plan


def _enforce_plan_feature(db: Session, actor: User, feature: str) -> None:
    plan = _active_plan(db, actor)
    if plan is None:
        return
    if not bool((plan.features or {}).get(feature, False)):
        raise HTTPException(403, detail={"code": "PLAN_UPGRADE_REQUIRED", "message": f"Your {plan.name} plan does not include this feature."})


def _organization_id_required(db: Session, actor: User) -> int:
    organization_id = _organization_id_for_user(db, actor.id)
    if not organization_id:
        organization = _ensure_user_organization(db, actor)
        organization_id = organization.id
    return int(organization_id)


def _organization_record_count(db: Session, actor: User) -> int:
    organization_id = _organization_id_required(db, actor)
    total = 0
    for model in (Lead, Contact, Account, Deal, Activity):
        total += int(
            db.scalar(
                select(func.count()).select_from(model).where(model.organization_id == organization_id)
            ) or 0
        )
    total += int(
        db.scalar(
            select(func.count()).select_from(PlatformRecord).where(
                PlatformRecord.organization_id == organization_id,
                PlatformRecord.archived == False,
            )
        ) or 0
    )
    return total


def _enforce_record_limit(db: Session, actor: User) -> None:
    plan = _active_plan(db, actor)
    if plan is None or plan.max_records is None:
        return
    if _organization_record_count(db, actor) >= int(plan.max_records):
        raise HTTPException(403, detail={
            "code": "PLAN_RECORD_LIMIT",
            "message": f"Your organization has reached the {plan.name} plan record limit.",
        })


def _enforce_custom_module_limit(db: Session, actor: User) -> None:
    _enforce_plan_feature(db, actor, "custom_modules")
    plan = _active_plan(db, actor)
    if plan is None or plan.max_custom_modules is None:
        return
    organization_id = _organization_id_required(db, actor)
    current = int(
        db.scalar(
            select(func.count()).select_from(MetadataModule).where(
                MetadataModule.organization_id == organization_id
            )
        ) or 0
    )
    if current >= int(plan.max_custom_modules):
        raise HTTPException(403, detail={
            "code": "PLAN_CUSTOM_MODULE_LIMIT",
            "message": f"Your organization has reached the {plan.name} custom-module limit.",
        })


def _enforce_storage_limit(db: Session, actor: User, incoming_bytes: int) -> None:
    plan = _active_plan(db, actor)
    if plan is None or plan.max_storage_mb is None:
        return
    organization_id = _organization_id_required(db, actor)
    rows = db.scalars(
        select(PlatformRecord).where(
            PlatformRecord.resource == "documents",
            PlatformRecord.organization_id == organization_id,
            PlatformRecord.archived == False,
        )
    ).all()
    used = sum(int((row.data or {}).get("file_size") or 0) for row in rows)
    maximum = int(plan.max_storage_mb) * 1024 * 1024
    if used + max(0, int(incoming_bytes)) > maximum:
        raise HTTPException(403, detail={
            "code": "PLAN_STORAGE_LIMIT",
            "message": f"Your organization has reached the {plan.name} storage limit.",
        })


def _enforce_ai_limit(db: Session, actor: User) -> None:
    _enforce_plan_feature(db, actor, "apex")
    plan = _active_plan(db, actor)
    if plan is None or plan.ai_limit_monthly is None:
        return
    organization_id = _organization_id_required(db, actor)
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    used = int(
        db.scalar(
            select(func.count()).select_from(ApexAssistantRun).where(
                ApexAssistantRun.organization_id == organization_id,
                ApexAssistantRun.created_at >= month_start,
            )
        ) or 0
    )
    if used >= int(plan.ai_limit_monthly):
        raise HTTPException(403, detail={
            "code": "PLAN_AI_LIMIT",
            "message": f"Your organization has reached the {plan.name} monthly AI limit.",
        })


def _claim_legacy_custom_modules(db: Session, actor: User) -> None:
    unowned = db.scalars(select(MetadataModule).where(MetadataModule.owner_id.is_(None))).all()
    changed = False
    for module in unowned:
        owned_record = db.scalar(select(PlatformRecord.id).where(
            PlatformRecord.resource == module.api_name,
            PlatformRecord.owner_id == actor.id,
        ).limit(1))
        if owned_record:
            module.owner_id = actor.id
            changed = True
    if changed:
        db.commit()


def record_login_event(request: Request, username: str, event: str, success: bool) -> None:
    """Persist authentication events without exposing credential material."""
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(func.lower(User.email) == username.lower())) if username else None
            if user is None and username:
                user = db.scalar(select(User).where(func.lower(User.name) == username.lower()))
            if user is not None and success and event == "login":
                user.last_login_at = datetime.utcnow()
                user.last_active = datetime.utcnow()
            db.add(LoginHistory(user_id=user.id if user else None, event=event, success=success, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent", "")[:500], metadata_json={"path": request.url.path}))
            db.commit()
    except Exception:
        # Authentication must not fail because audit persistence is temporarily unavailable.
        return


def current_actor(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Resolve the named CRM user authenticated by a database session.

    HTTP Basic remains an emergency compatibility path for existing automated tests and
    deployment recovery, but normal browser access uses the HttpOnly session cookie.
    """
    if not env_bool("ENABLE_AUTH", IS_PRODUCTION):
        raw_id = request.headers.get("X-Yash-Actor-Id")
        if raw_id and raw_id.isdigit():
            actor = db.get(User, int(raw_id))
            if actor and actor.status == "Active":
                return actor
        return db.scalar(select(User).where(User.status == "Active", func.lower(User.role) == "administrator").order_by(User.id)) or db.scalar(select(User).where(User.status == "Active").order_by(User.id))
    actor_id = getattr(request.state, "actor_id", None)
    if actor_id:
        actor = db.get(User, int(actor_id))
        if actor and actor.status == "Active":
            return actor
    actor = _session_user(request, db)
    if actor is not None:
        return actor
    username = _basic_username(request.headers.get("Authorization", "")) if not IS_PRODUCTION else ""
    if username:
        actor = db.scalar(select(User).where(func.lower(User.email) == username.lower(), User.status == "Active"))
        if actor is None:
            actor = db.scalar(select(User).where(func.lower(User.name) == username.lower(), User.status == "Active"))
        if actor is None and username.lower() in {"admin", "administrator"}:
            actor = db.scalar(select(User).where(func.lower(User.role) == "administrator", User.status == "Active").order_by(User.id))
        if actor is not None:
            return actor
    raise HTTPException(401, "Sign in to continue")


def _role_record(db: Session, role: str | None) -> PlatformRecord | None:
    if not role:
        return None
    normalized = role.lower().replace("representative", "rep").replace("sales ", "").strip()
    rows = db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "roles", PlatformRecord.archived == False)).all()
    return next((row for row in rows if str((row.data or {}).get("name") or row.title).lower().replace("representative", "rep").replace("sales ", "").strip() == normalized), None)


def _role_names_visible_to_actor(db: Session, actor: User) -> set[str]:
    role = _role_record(db, actor.role)
    if role is None:
        return {str(actor.role or "").lower()}
    scope = str((role.data or {}).get("data_scope") or "Own").lower()
    if scope == "all" or _is_platform_owner(actor):
        return {"*"}
    visible = {str((role.data or {}).get("name") or role.title).lower().replace("representative", "rep")}
    if "subordinate" not in scope:
        return visible
    changed = True
    while changed:
        changed = False
        for candidate in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "roles", PlatformRecord.archived == False)).all():
            parent = str((candidate.data or {}).get("parent_role") or "").lower().replace("representative", "rep")
            name = str((candidate.data or {}).get("name") or candidate.title).lower().replace("representative", "rep")
            if parent in visible and name not in visible:
                visible.add(name)
                changed = True
    return visible


def _sharing_allows(db: Session, resource: str, actor: User, record_owner_id: int | None, access: str = "read") -> bool:
    if record_owner_id == actor.id or "*" in _role_names_visible_to_actor(db, actor):
        return True
    requested = "write" if str(access).lower() in {"write", "update", "delete"} else "read"
    actor_roles = _role_names_visible_to_actor(db, actor)
    policies = db.scalars(select(SharingPolicy).where(
        SharingPolicy.enabled == True,
        or_(SharingPolicy.module == resource, SharingPolicy.module == "*"),
    )).all()
    for policy in policies:
        policy_access = str(policy.access or "Read Only").lower().replace("_", " ")
        allows_write = policy_access in {"read/write", "read write", "write", "read and write"}
        allows_read = allows_write or policy_access in {"read", "read only"}
        if requested == "write" and not allows_write:
            continue
        if requested == "read" and not allows_read:
            continue

        scope = str(policy.scope or "").lower().replace("_", " ")
        if scope in {"public", "public read only", "public read/write", "public read write"}:
            if requested == "read" or allows_write:
                return True

        if scope in {"role hierarchy", "own and subordinates"} and actor_roles:
            owner = db.get(User, record_owner_id) if record_owner_id else None
            owner_role = str(owner.role or "").lower().replace("representative", "rep") if owner else ""
            if owner_role and owner_role in actor_roles:
                return True

        criteria = policy.criteria or {}
        allowed_roles = criteria.get("roles") if isinstance(criteria, dict) else None
        if isinstance(allowed_roles, list):
            normalized = {str(role).lower().replace("representative", "rep") for role in allowed_roles}
            if actor_roles.intersection(normalized):
                return True
    return False

def can_access_record(db: Session, resource: str, record: Any, actor: User | None, access: str = "read") -> bool:
    if not isinstance(actor, User):
        return True
    actor_org = _organization_id_for_user(db, actor.id)
    if _is_platform_owner(actor):
        return True
    if isinstance(record, User):
        return _user_in_actor_organization(db, actor, record.id)
    if hasattr(record, "organization_id"):
        record_org = getattr(record, "organization_id", None)
        if record_org is None or actor_org != record_org:
            return False
    if not hasattr(record, "owner_id"):
        return True
    return _sharing_allows(db, resource, actor, getattr(record, "owner_id", None), access)


def _metadata_fields(db: Session, resource: str) -> list[MetadataField]:
    names = {resource.lower(), resource.rstrip("s").lower(), resource.replace("_", "").lower()}
    modules = db.scalars(select(MetadataModule)).all()
    module_ids = [item.id for item in modules if item.api_name.lower() in names or item.label.lower().replace(" ", "_") in names]
    if not module_ids:
        return []
    return db.scalars(select(MetadataField).where(MetadataField.module_id.in_(module_ids))).all()


def field_allowed(db: Session, resource: str, field_name: str, actor: User | None, action: str = "read") -> bool:
    if not isinstance(actor, User):
        return True
    if _is_platform_owner(actor):
        return True

    # Field security is primarily Profile-based (Zoho-style). Role remains a
    # compatibility fallback for existing field-security definitions.
    principals = []
    if actor.profile_name:
        principals.append(str(actor.profile_name).lower().replace("representative", "rep"))
    if actor.role:
        principals.append(str(actor.role).lower().replace("representative", "rep"))

    def matching_value(mapping: dict[str, Any]) -> Any:
        normalized = {
            str(key).lower().replace("representative", "rep"): value
            for key, value in (mapping or {}).items()
        }
        for principal in principals:
            if principal in normalized:
                return normalized[principal]
        return normalized.get("*")

    for field in _metadata_fields(db, resource):
        if field.api_name.lower() != field_name.lower():
            continue
        visibility = field.visibility or {}
        permissions = field.permissions or {}
        selected_visibility = matching_value(visibility)
        if action == "read" and str(selected_visibility or "").lower() == "hidden":
            return False
        grants = matching_value(permissions)
        if isinstance(grants, dict):
            requested = "write" if action in {"write", "create", "update"} else action
            if grants.get(requested) is False:
                return False
        if action in {"write", "create", "update"} and field.read_only:
            return False
    return True


def authorize_field_values(db: Session, resource: str, values: dict[str, Any], actor: User | None, action: str = "write") -> None:
    if not isinstance(actor, User):
        return
    for key in values:
        if not field_allowed(db, resource, key, actor, action):
            raise HTTPException(403, detail={"code": "FIELD_PERMISSION_DENIED", "message": f"You do not have {action} access to field '{key}'."})


def redact_record_fields(db: Session, resource: str, data: dict[str, Any], actor: User | None) -> dict[str, Any]:
    if not isinstance(actor, User):
        return data
    return {key: value for key, value in data.items() if field_allowed(db, resource, key, actor, "read")}


def _profile_permission_record(db: Session, actor: User) -> dict[str, Any] | None:
    profile_name = str(actor.profile_name or "").strip()
    if not profile_name:
        return None
    rows = db.scalars(select(PlatformRecord).where(
        PlatformRecord.resource == "profiles",
        PlatformRecord.archived == False,
    )).all()
    for row in rows:
        name = str((row.data or {}).get("name") or row.title or "").strip()
        if name.lower() == profile_name.lower():
            data = dict(row.data or {})
            permissions = data.get("permissions")
            return permissions if isinstance(permissions, dict) else {}
    direct = db.scalar(select(PermissionProfile).where(func.lower(PermissionProfile.name) == profile_name.lower()))
    return dict(direct.grants or {}) if direct else None


def _profile_action_allowed(db: Session, actor: User, resource: str, action: str) -> bool:
    if _is_platform_owner(actor):
        return True
    matrix = _profile_permission_record(db, actor)
    if matrix is None:
        # Compatibility default for accounts that have not yet been assigned a configured profile.
        return True
    candidates = [
        matrix.get(resource),
        (matrix.get("modules") or {}).get(resource) if isinstance(matrix.get("modules"), dict) else None,
        matrix.get("*"),
        matrix.get("default"),
    ]
    rule = next((item for item in candidates if item is not None), None)
    if rule is None:
        return True
    if isinstance(rule, bool):
        return rule
    if isinstance(rule, list):
        return action in {str(v).lower() for v in rule}
    if isinstance(rule, dict):
        aliases = {
            "read": ["read", "view"],
            "create": ["create"],
            "update": ["update", "edit"],
            "delete": ["delete"],
            "export": ["export"],
            "import": ["import"],
            "admin": ["admin", "manage"],
        }
        for key in aliases.get(action, [action]):
            if key in rule:
                return bool(rule[key])
        return True
    return True


def _enforce_request_access(db: Session, actor: User, path: str, method: str) -> None:
    if _is_platform_owner(actor):
        return
    feature = request_entitlement_feature(path)
    if feature:
        _enforce_plan_feature(db, actor, feature)
    resource, action = request_resource_action(path, method)
    if resource and not _profile_action_allowed(db, actor, resource, action):
        raise HTTPException(403, detail={
            "code": "PROFILE_PERMISSION_DENIED",
            "message": f"Your profile does not allow {action} access to {resource.replace('_', ' ')}.",
        })


def _enforce_organization_user_limit(db: Session, actor: User) -> None:
    plan = _active_plan(db, actor)
    if plan is None:
        return
    raw_limit = (plan.features or {}).get("max_users")
    if raw_limit in {None, "", 0}:
        return
    organization_id = _organization_id_required(db, actor)
    active_members = int(db.scalar(select(func.count()).select_from(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.status == "Active",
    )) or 0)
    pending = int(db.scalar(select(func.count()).select_from(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == organization_id,
        OrganizationInvitation.status == "Pending",
        OrganizationInvitation.expires_at > datetime.utcnow(),
    )) or 0)
    if active_members + pending >= int(raw_limit):
        raise HTTPException(403, detail={
            "code": "PLAN_USER_LIMIT",
            "message": f"Your {plan.name} plan allows up to {int(raw_limit)} organization users.",
        })


configure_security_hooks(redact_record_fields, can_access_record, _organization_id_for_user)

__all__ = [
    "APP_ENV",
    "AUTH_COOKIE",
    "AUTH_SESSION_DAYS",
    "IS_PRODUCTION",
    "MIN_PASSWORD_LENGTH",
    "PASSWORD_ITERATIONS",
    "_account_by_identifier",
    "_active_plan",
    "_app_credentials",
    "_basic_auth_valid",
    "_basic_username",
    "_claim_legacy_custom_modules",
    "_clean_username",
    "_clear_session_cookie",
    "_create_session",
    "_default_plan",
    "_dispatch_account_message",
    "_enforce_ai_limit",
    "_enforce_custom_module_limit",
    "_enforce_organization_user_limit",
    "_enforce_plan_feature",
    "_enforce_record_limit",
    "_enforce_request_access",
    "_enforce_storage_limit",
    "_ensure_organization_subscription",
    "_ensure_plan_catalog",
    "_ensure_user_organization",
    "_ensure_user_subscription",
    "_env_int",
    "_environment_admin_credentials_valid",
    "_is_platform_owner",
    "_metadata_fields",
    "_normalize_phone",
    "_notify_account",
    "_notify_account_once",
    "_organization_for_user",
    "_organization_id_for_user",
    "_organization_user_ids",
    "_user_in_actor_organization",
    "_organization_id_required",
    "_organization_record_count",
    "_organization_slug_for_user",
    "_password_hash",
    "_password_valid",
    "_profile_action_allowed",
    "_profile_permission_record",
    "_revoke_session",
    "_role_names_visible_to_actor",
    "_role_record",
    "_send_email_message",
    "_send_sms_message",
    "_session_token_hash",
    "_session_user",
    "_set_session_cookie",
    "_sharing_allows",
    "_subscription_payload",
    "authorize_field_values",
    "can_access_record",
    "current_actor",
    "env_bool",
    "field_allowed",
    "record_login_event",
    "redact_record_fields"
]

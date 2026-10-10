from __future__ import annotations

from typing import Final


ENTITLEMENT_RESOURCE_FEATURES: Final[dict[str, str]] = {
    "reports": "reports",
    "dashboards": "reports",
    "analytics": "advanced_analytics",
    "ai": "apex",
    "cpq": "cpq",
    "price_books": "inventory_management",
    "vendors": "inventory_management",
    "quotes": "inventory_management",
    "sales_orders": "inventory_management",
    "purchase_orders": "inventory_management",
    "invoices": "inventory_management",
    "payments": "inventory_management",
    "portals": "customer_portals",
    "approval_processes": "approval_process",
    "approvals": "approval_process",
    "sandbox": "developer_sandbox",
    "sandboxes": "developer_sandbox",
}


def request_resource_action(path: str, method: str) -> tuple[str | None, str]:
    method = method.upper()
    action = (
        "read" if method in {"GET", "HEAD"}
        else "create" if method == "POST"
        else "update" if method in {"PATCH", "PUT"}
        else "delete" if method == "DELETE"
        else "read"
    )
    parts = path.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "api":
        return None, action
    if parts[1] in {"import-wizard", "import"} and len(parts) >= 3:
        return parts[2], "create"
    if parts[1] == "export" and len(parts) >= 3:
        return parts[2].removesuffix(".csv"), "read"
    if parts[1] == "platform" and len(parts) >= 3:
        return parts[2], action
    if parts[1] in {"auth", "organization", "owner", "plans", "subscription", "billing", "settings", "security"}:
        return None, action
    if parts[1] == "admin" and len(parts) >= 3 and parts[2] == "metadata":
        return "custom_modules", action
    return parts[1], action


def request_entitlement_feature(path: str) -> str | None:
    parts = path.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "api":
        return None
    if parts[1] == "ai":
        return "apex"
    if parts[1] == "cpq":
        return "cpq"
    if parts[1] in {"reports", "dashboards"}:
        return "reports"
    if parts[1] == "analytics":
        return "advanced_analytics"
    if parts[1] == "admin" and len(parts) >= 3 and parts[2] == "metadata":
        return "custom_modules"
    if parts[1] == "platform" and len(parts) >= 3:
        return ENTITLEMENT_RESOURCE_FEATURES.get(parts[2])
    return ENTITLEMENT_RESOURCE_FEATURES.get(parts[1])

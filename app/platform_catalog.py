"""Declarative catalog for Yash CRM's extensible modules and setup surfaces.

The catalog is intentionally product-neutral.  It supplies field metadata to the
API and browser client while records are stored by the platform record engine.
"""

from __future__ import annotations

from typing import Any


def field(key: str, label: str, kind: str = "text", *, required: bool = False,
          options: list[str] | None = None, full: bool = False) -> dict[str, Any]:
    value: dict[str, Any] = {"key": key, "label": label, "type": kind}
    if required:
        value["required"] = True
    if options:
        value["options"] = options
    if full:
        value["full"] = True
    return value


COMMON_STATUS = ["Active", "Inactive"]
SALES_STATUS = ["Draft", "Pending Approval", "Approved", "Sent", "Accepted", "Closed", "Cancelled"]


PLATFORM_RESOURCES: dict[str, dict[str, Any]] = {
    "price_books": {
        "label": "Price Books", "singular": "Price Book", "group": "Sales & Inventory",
        "description": "Maintain reusable product pricing and effective periods.",
        "fields": [field("name", "Name", required=True), field("currency", "Currency", "select", options=["INR", "USD", "EUR"]), field("discount_percent", "Discount %", "number"), field("valid_from", "Valid from", "date"), field("valid_to", "Valid to", "date"), field("status", "Status", "select", options=COMMON_STATUS), field("description", "Description", "textarea", full=True)],
    },
    "vendors": {
        "label": "Vendors", "singular": "Vendor", "group": "Sales & Inventory",
        "description": "Track suppliers, purchasing contacts and commercial terms.",
        "fields": [field("name", "Vendor name", required=True), field("email", "Email", "email"), field("phone", "Phone"), field("website", "Website"), field("category", "Category"), field("tax_id", "Tax ID"), field("status", "Status", "select", options=COMMON_STATUS), field("address", "Address", "textarea", full=True)],
    },
    "quotes": {
        "label": "Quotes", "singular": "Quote", "group": "Sales & Inventory",
        "description": "Prepare commercial offers linked to customers and opportunities.",
        "fields": [field("name", "Quote subject", required=True), field("quote_number", "Quote number (automatic)"), field("account_id", "Account", "account"), field("contact_id", "Contact", "contact"), field("deal_id", "Opportunity", "deal"), field("amount", "Total", "number"), field("valid_until", "Valid until", "date"), field("status", "Status", "select", options=SALES_STATUS), field("terms", "Terms", "textarea", full=True)],
    },
    "sales_orders": {
        "label": "Sales Orders", "singular": "Sales Order", "group": "Sales & Inventory",
        "description": "Track accepted customer orders through fulfilment.",
        "fields": [field("name", "Order subject", required=True), field("order_number", "Order number (automatic)"), field("account_id", "Account", "account"), field("quote_id", "Source quote", "platform:quotes"), field("deal_id", "Opportunity", "deal"), field("amount", "Total", "number"), field("due_date", "Delivery date", "date"), field("status", "Status", "select", options=["Draft", "Confirmed", "In Fulfilment", "Fulfilled", "Cancelled"]), field("notes", "Notes", "textarea", full=True)],
    },
    "purchase_orders": {
        "label": "Purchase Orders", "singular": "Purchase Order", "group": "Sales & Inventory",
        "description": "Control purchasing commitments with vendors.",
        "fields": [field("name", "PO subject", required=True), field("po_number", "PO number (automatic)"), field("vendor_id", "Vendor", "platform:vendors"), field("amount", "Total", "number"), field("due_date", "Expected date", "date"), field("status", "Status", "select", options=["Draft", "Issued", "Partially Received", "Received", "Cancelled"]), field("notes", "Notes", "textarea", full=True)],
    },
    "invoices": {
        "label": "Invoices", "singular": "Invoice", "group": "Sales & Inventory",
        "description": "Track invoices, due dates and payment state.",
        "fields": [field("name", "Invoice subject", required=True), field("invoice_number", "Invoice number (automatic)"), field("account_id", "Account", "account"), field("sales_order_id", "Sales order", "platform:sales_orders"), field("deal_id", "Opportunity", "deal"), field("amount", "Total", "number"), field("due_date", "Due date", "date"), field("status", "Status", "select", options=["Draft", "Issued", "Partially Paid", "Paid", "Overdue", "Void"]), field("notes", "Notes", "textarea", full=True)],
    },
    "payments": {
        "label": "Payments", "singular": "Payment", "group": "Sales & Inventory",
        "description": "Record customer collections against invoices and sales ownership.",
        "fields": [field("name", "Payment reference", required=True), field("invoice_id", "Invoice", "platform:invoices", required=True), field("account_id", "Account", "account"), field("deal_id", "Opportunity", "deal"), field("amount", "Amount received", "number", required=True), field("payment_date", "Payment date", "date", required=True), field("method", "Method", "select", options=["Bank Transfer", "UPI", "Card", "Cheque", "Cash", "Other"]), field("status", "Status", "select", options=["Pending", "Received", "Cleared", "Failed", "Refunded"]), field("notes", "Notes", "textarea", full=True)],
    },
    "site_visits": {
        "label": "Site Visits", "singular": "Site Visit", "group": "Customer & Marketing",
        "description": "Schedule, complete and review visits without losing lead or opportunity context.",
        "fields": [field("name", "Visit subject", required=True), field("lead_id", "Lead", "lead"), field("account_id", "Account", "account"), field("contact_id", "Contact", "contact"), field("deal_id", "Opportunity", "deal"), field("visit_date", "Visit date", "date", required=True), field("status", "Status", "select", options=["Scheduled", "Completed", "Cancelled", "Rescheduled"]), field("location", "Location"), field("outcome", "Outcome", "textarea", full=True), field("next_action", "Next action", "textarea", full=True)],
    },
    "sales_targets": {
        "label": "Sales Targets", "singular": "Sales Target", "group": "Analytics",
        "description": "Set salesperson targets and calculate achievement and earned incentives from cleared payments.",
        "fields": [field("name", "Target name", required=True), field("owner_id", "Salesperson", "user", required=True), field("period_start", "Period start", "date", required=True), field("period_end", "Period end", "date", required=True), field("target_amount", "Target amount", "number", required=True), field("incentive_rate", "Incentive rate %", "number"), field("threshold_percent", "Minimum achievement %", "number"), field("status", "Status", "select", options=["Active", "Closed", "Draft"]), field("notes", "Notes", "textarea", full=True)],
    },
    "campaigns": {
        "label": "Campaigns", "singular": "Campaign", "group": "Customer & Marketing",
        "description": "Plan campaigns and measure their response and revenue influence.",
        "fields": [field("name", "Campaign name", required=True), field("campaign_type", "Type", "select", options=["Email", "Event", "Webinar", "Advertising", "Partner", "Other"]), field("start_date", "Start date", "date"), field("end_date", "End date", "date"), field("budget", "Budget", "number"), field("expected_revenue", "Expected revenue", "number"), field("status", "Status", "select", options=["Planned", "Active", "Completed", "Cancelled"]), field("description", "Description", "textarea", full=True)],
    },
    "cases": {
        "label": "Cases", "singular": "Case", "group": "Customer & Marketing",
        "description": "Manage customer issues with priority, ownership and resolution.",
        "fields": [field("name", "Case subject", required=True), field("case_number", "Case number"), field("account_id", "Account", "account"), field("contact_id", "Contact", "contact"), field("priority", "Priority", "select", options=["Low", "Normal", "High", "Critical"]), field("channel", "Channel", "select", options=["Email", "Phone", "Web", "Chat", "Other"]), field("status", "Status", "select", options=["New", "In Progress", "Waiting on Customer", "Resolved", "Closed"]), field("description", "Description", "textarea", full=True)],
    },
    "solutions": {
        "label": "Solutions", "singular": "Solution", "group": "Customer & Marketing",
        "description": "Build a searchable internal knowledge base for case resolution.",
        "fields": [field("name", "Solution title", required=True), field("category", "Category"), field("status", "Status", "select", options=["Draft", "Reviewed", "Published", "Retired"]), field("content", "Solution", "textarea", required=True, full=True)],
    },
    "documents": {
        "label": "Documents", "singular": "Document", "group": "Collaboration",
        "description": "Upload governed documents and connect them to the relevant CRM record.",
        "fields": [field("name", "Document name", required=True), field("file", "Upload document", "file"), field("document_type", "Type"), field("url", "Secure URL"), field("version", "Version"), field("related_type", "Related module", "select", options=["leads", "contacts", "accounts", "deals", "quotes", "sales_orders", "purchase_orders", "invoices", "payments", "site_visits"]), field("related_id", "Related record ID", "number"), field("status", "Status", "select", options=["Draft", "Active", "Archived"]), field("description", "Description", "textarea", full=True)],
    },
    "forecasts": {
        "label": "Forecasts", "singular": "Forecast", "group": "Analytics",
        "description": "Capture period targets, committed revenue and forecast outcomes.",
        "fields": [field("name", "Forecast name", required=True), field("period", "Period", required=True), field("target", "Target", "number"), field("committed", "Committed", "number"), field("best_case", "Best case", "number"), field("status", "Status", "select", options=["Open", "Submitted", "Final"]), field("notes", "Notes", "textarea", full=True)],
    },
    "reports": {
        "label": "Reports", "singular": "Report", "group": "Analytics",
        "description": "Save reusable report definitions and sharing settings.",
        "fields": [field("name", "Report name", required=True), field("module", "Primary module", required=True), field("report_type", "Type", "select", options=["Tabular", "Summary", "Matrix"]), field("filters", "Filters (JSON)", "json", full=True), field("columns", "Columns (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)],
    },
    "dashboards": {
        "label": "Dashboards", "singular": "Dashboard", "group": "Analytics",
        "description": "Compose KPI dashboards from saved report definitions.",
        "fields": [field("name", "Dashboard name", required=True), field("audience", "Audience"), field("components", "Components (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)],
    },

    # General and security
    "company_details": {"label": "Company Details", "singular": "Company Profile", "group": "General", "singleton": True, "description": "Legal and operating identity used by templates and exports.", "fields": [field("name", "Company name", required=True), field("legal_name", "Legal name"), field("email", "Business email", "email"), field("phone", "Phone"), field("website", "Website"), field("tax_id", "Tax ID"), field("address", "Address", "textarea", full=True)]},
    "fiscal_years": {"label": "Fiscal Year", "singular": "Fiscal Year", "group": "General", "description": "Define financial reporting periods.", "fields": [field("name", "Fiscal year name", required=True), field("start_date", "Start date", "date", required=True), field("end_date", "End date", "date", required=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "roles": {"label": "Roles", "singular": "Role", "group": "Security", "description": "Define record-visibility hierarchy independently from permissions.", "fields": [field("name", "Role name", required=True), field("parent_role", "Reports to role"), field("data_scope", "Data scope", "select", options=["Own", "Own and Subordinates", "All"]), field("status", "Status", "select", options=COMMON_STATUS), field("description", "Description", "textarea", full=True)]},
    "profiles": {"label": "Profiles", "singular": "Profile", "group": "Security", "description": "Bundle module and setup permissions for assignment to users.", "fields": [field("name", "Profile name", required=True), field("permissions", "Permission matrix (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS), field("description", "Description", "textarea", full=True)]},
    "permissions": {"label": "Permissions", "singular": "Permission Set", "group": "Security", "description": "Configure create, read, update, delete, export and administration grants.", "fields": [field("name", "Permission set", required=True), field("module", "Module", required=True), field("grants", "Grants (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "sharing_rules": {"label": "Sharing Rules", "singular": "Sharing Rule", "group": "Security", "description": "Extend record visibility between roles or groups.", "fields": [field("name", "Rule name", required=True), field("module", "Module", required=True), field("from_role", "From role"), field("to_role", "To role"), field("access", "Access", "select", options=["Read Only", "Read/Write"]), field("status", "Status", "select", options=COMMON_STATUS)]},

    # Customization
    "custom_modules": {"label": "Modules", "singular": "Module", "group": "Customization", "description": "Register custom business modules and labels.", "fields": [field("name", "Module name", required=True), field("api_name", "API name", required=True), field("plural_label", "Plural label"), field("status", "Status", "select", options=COMMON_STATUS)]},
    "custom_fields": {"label": "Fields", "singular": "Field", "group": "Customization", "description": "Define additional fields and validation metadata.", "fields": [field("name", "Field label", required=True), field("module", "Module", required=True), field("api_name", "API name", required=True), field("field_type", "Type", "select", options=["Text", "Number", "Date", "DateTime", "Boolean", "Picklist", "Lookup", "Currency"]), field("required", "Required", "select", options=["No", "Yes"]), field("options", "Options (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "layouts": {"label": "Layouts", "singular": "Layout", "group": "Customization", "description": "Arrange fields into reusable module layouts.", "fields": [field("name", "Layout name", required=True), field("module", "Module", required=True), field("sections", "Sections (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "pipelines": {"label": "Pipelines", "singular": "Pipeline", "group": "Customization", "description": "Configure ordered stages, probabilities and closing states.", "fields": [field("name", "Pipeline name", required=True), field("module", "Module", required=True), field("stages", "Stages (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "validation_rules": {"label": "Validation Rules", "singular": "Validation Rule", "group": "Customization", "description": "Reject records that fail configured criteria.", "fields": [field("name", "Rule name", required=True), field("module", "Module", required=True), field("expression", "Expression", required=True), field("error_message", "Error message", required=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "custom_views": {"label": "Custom Views", "singular": "Custom View", "group": "Customization", "description": "Save filters, sort order and visible columns.", "fields": [field("name", "View name", required=True), field("module", "Module", required=True), field("filters", "Filters (JSON)", "json", full=True), field("sort", "Sort"), field("columns", "Columns (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},

    # Automation
    "workflow_rules": {"label": "Workflow Rules", "singular": "Workflow Rule", "group": "Automation", "description": "Evaluate create/update criteria and queue supported actions.", "fields": [field("name", "Rule name", required=True), field("module", "Module", required=True), field("event", "Event", "select", options=["create", "update"]), field("criteria_field", "Criteria field"), field("criteria_value", "Equals value"), field("action_type", "Action", "select", options=["audit", "create_task", "field_update", "webhook_queue"]), field("action_value", "Action value"), field("status", "Status", "select", options=COMMON_STATUS)]},
    "assignment_rules": {"label": "Assignment Rules", "singular": "Assignment Rule", "group": "Automation", "description": "Assign incoming records to an owner when criteria match.", "fields": [field("name", "Rule name", required=True), field("module", "Module", required=True), field("criteria_field", "Criteria field"), field("criteria_value", "Equals value"), field("owner_id", "Assign owner", "user"), field("status", "Status", "select", options=COMMON_STATUS)]},
    "scoring_rules": {"label": "Scoring Rules", "singular": "Scoring Rule", "group": "Automation", "description": "Add or subtract score when record values match.", "fields": [field("name", "Rule name", required=True), field("module", "Module", required=True), field("criteria_field", "Criteria field", required=True), field("criteria_value", "Equals value", required=True), field("score_delta", "Score change", "number", required=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "schedules": {"label": "Schedules", "singular": "Schedule", "group": "Automation", "description": "Persist recurring job definitions for an external worker.", "fields": [field("name", "Schedule name", required=True), field("cron", "Cron expression", required=True), field("job_type", "Job type"), field("payload", "Payload (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "webhooks": {"label": "Webhooks", "singular": "Webhook", "group": "Automation", "description": "Configure signed outbound event destinations. Delivery requires a worker.", "fields": [field("name", "Webhook name", required=True), field("event", "Event", required=True), field("url", "HTTPS URL", required=True), field("secret_reference", "Secret reference"), field("status", "Status", "select", options=COMMON_STATUS)]},

    # Templates and developer settings
    "email_templates": {"label": "Email Templates", "singular": "Email Template", "group": "Templates", "description": "Store reusable email subjects and bodies.", "fields": [field("name", "Template name", required=True), field("subject", "Subject", required=True), field("module", "Module"), field("content", "Body", "textarea", required=True, full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "quote_templates": {"label": "Quote Templates", "singular": "Quote Template", "group": "Templates", "description": "Define quote layouts and default terms.", "fields": [field("name", "Template name", required=True), field("content", "Template content", "textarea", required=True, full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "invoice_templates": {"label": "Invoice Templates", "singular": "Invoice Template", "group": "Templates", "description": "Define invoice layouts and payment terms.", "fields": [field("name", "Template name", required=True), field("content", "Template content", "textarea", required=True, full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "api_settings": {"label": "API", "singular": "API Client", "group": "Developer", "description": "Register API clients. Secret values are never returned by this UI foundation.", "fields": [field("name", "Client name", required=True), field("scopes", "Scopes (JSON)", "json", full=True), field("token_hint", "Token hint"), field("status", "Status", "select", options=COMMON_STATUS)]},
    "integration_settings": {"label": "Integration Settings", "singular": "Integration", "group": "Developer", "description": "Configure external connection metadata without storing raw secrets.", "fields": [field("name", "Integration name", required=True), field("provider", "Provider", required=True), field("base_url", "Base URL"), field("credential_reference", "Credential reference"), field("settings", "Settings (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
}


SETUP_NAVIGATION: dict[str, list[tuple[str, str]]] = {
    "General": [("company_details", "Company Details"), ("fiscal_years", "Fiscal Year")],
    "Security": [("users", "Users"), ("roles", "Roles"), ("profiles", "Profiles"), ("permissions", "Permissions"), ("sharing_rules", "Sharing Rules"), ("audit_log", "Audit Log")],
    "Customization": [("custom_modules", "Modules"), ("custom_fields", "Fields"), ("layouts", "Layouts"), ("pipelines", "Pipelines"), ("validation_rules", "Validation Rules"), ("custom_views", "Custom Views")],
    "Automation": [("workflow_rules", "Workflow Rules"), ("assignment_rules", "Assignment Rules"), ("approval_processes", "Approval Processes"), ("blueprints", "Blueprint"), ("scoring_rules", "Scoring Rules"), ("schedules", "Schedules"), ("webhooks", "Webhooks")],
    "Templates": [("email_templates", "Email Templates"), ("quote_templates", "Quote Templates"), ("invoice_templates", "Invoice Templates")],
    "Data Administration": [("import", "Import"), ("export", "Export"), ("duplicates", "Duplicate Management"), ("recycle_bin", "Recycle Bin"), ("audit_log", "Audit History")],
    "Developer": [("api_settings", "API"), ("webhooks", "Webhooks"), ("integration_settings", "Integration Settings")],
}


def public_catalog() -> dict[str, Any]:
    return {key: value for key, value in PLATFORM_RESOURCES.items()}

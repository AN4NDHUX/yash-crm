"""Declarative catalog for CONVOSIS CRM's extensible modules and setup surfaces.

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
        "fields": [field("name", "Report name", required=True), field("module", "Primary module", required=True), field("report_type", "Type", "select", options=["Tabular", "Summary", "Matrix"]), field("filters", "Filters (JSON)", "json", full=True), field("columns", "Columns (JSON)", "json", full=True), field("group_by", "Group by field"), field("aggregate", "Aggregate (JSON)", "json", full=True), field("sort", "Sort (JSON)", "json", full=True), field("limit", "Row limit", "number"), field("status", "Status", "select", options=COMMON_STATUS)],
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
    "workflow_rules": {"label": "Workflow Rules", "singular": "Workflow Rule", "group": "Automation", "description": "Evaluate nested AND/OR criteria and run immediate or queued actions.", "fields": [field("name", "Rule name", required=True), field("module", "Module", required=True), field("event", "Event", "select", options=["create", "update"]), field("criteria_field", "Legacy criteria field"), field("criteria_value", "Legacy equals value"), field("criteria", "Nested criteria (JSON)", "json", full=True), field("action_type", "Legacy action", "select", options=["audit", "create_task", "field_update", "webhook_queue"]), field("action_value", "Legacy action value"), field("actions", "Actions (JSON)", "json", full=True), field("scheduled_for", "Run at (ISO datetime)"), field("status", "Status", "select", options=COMMON_STATUS)]},
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
    "mcp_servers": {"label": "MCP Servers", "singular": "MCP Server", "group": "Developer", "description": "Register MCP servers for approved AI agents. Credentials remain in server-side secret references.", "fields": [field("name", "Server name", required=True), field("endpoint", "Endpoint", required=True), field("transport", "Transport", "select", options=["HTTP", "SSE", "stdio"]), field("auth_reference", "Auth secret reference"), field("scopes", "Scopes (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "mcp_tools": {"label": "MCP Tools", "singular": "MCP Tool", "group": "Developer", "description": "Declare tools exposed to agents with explicit scopes and input schemas.", "fields": [field("name", "Tool name", required=True), field("server_id", "Server record ID", "number", required=True), field("description", "Description", "textarea", full=True), field("input_schema", "Input schema (JSON)", "json", full=True), field("scopes", "Required scopes (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "api_versions": {"label": "API Versions", "singular": "API Version", "group": "Developer", "description": "Publish versioned REST contracts with lifecycle and deprecation metadata.", "fields": [field("name", "Version name", required=True), field("version", "Version", required=True), field("base_path", "Base path", required=True), field("status", "Status", "select", options=["Draft", "Active", "Deprecated"]), field("sunset_date", "Sunset date", "date"), field("notes", "Notes", "textarea", full=True)]},
    "connections": {"label": "Connections", "singular": "Connection", "group": "Developer", "description": "Configure OAuth2, API key, and service connection metadata without storing raw credentials.", "fields": [field("name", "Connection name", required=True), field("provider", "Provider", required=True), field("auth_type", "Authentication", "select", options=["OAuth2", "API Key", "Basic", "Custom"]), field("secret_reference", "Secret reference", required=True), field("scopes", "Scopes (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "variables": {"label": "Variables", "singular": "Variable", "group": "Developer", "description": "Store environment-aware configuration references. Secret values never appear in responses.", "fields": [field("name", "Variable name", required=True), field("api_name", "API name", required=True), field("value_reference", "Value or secret reference"), field("value_type", "Type", "select", options=["String", "Number", "Boolean", "JSON", "Secret"]), field("environment", "Environment", "select", options=["Development", "Staging", "Production"]), field("status", "Status", "select", options=COMMON_STATUS)]},
    "functions": {"label": "Functions", "singular": "Function", "group": "Developer", "description": "Define server-side functions with safe execution metadata and associations.", "fields": [field("name", "Function name", required=True), field("runtime", "Runtime", "select", options=["Python", "JavaScript", "HTTP"]), field("entrypoint", "Entrypoint", required=True), field("input_schema", "Input schema (JSON)", "json", full=True), field("associations", "Associations (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "widgets": {"label": "Widgets", "singular": "Widget", "group": "Developer", "description": "Register embeddable CRM widgets and allowed scopes.", "fields": [field("name", "Widget name", required=True), field("mount_path", "Mount path", required=True), field("source_reference", "Source reference", required=True), field("scopes", "Scopes (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "data_models": {"label": "Data Model", "singular": "Data Model", "group": "Developer", "description": "Inspect and document modules, fields, relationships, and API names.", "fields": [field("name", "Model name", required=True), field("module", "Module", required=True), field("relationships", "Relationships (JSON)", "json", full=True), field("api_names", "API names (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "queries": {"label": "Queries", "singular": "Query", "group": "Developer", "description": "Store allowlisted query definitions; unrestricted SQL is not supported.", "fields": [field("name", "Query name", required=True), field("resource", "Resource", required=True), field("filters", "Filters (JSON)", "json", full=True), field("columns", "Columns (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "client_scripts": {"label": "Client Scripts", "singular": "Client Script", "group": "Developer", "description": "Declare supported client lifecycle events with reviewed source references.", "fields": [field("name", "Script name", required=True), field("module", "Module", required=True), field("event", "Event", "select", options=["Create", "Edit", "Clone", "List", "Detail", "Wizard"]), field("source_reference", "Source reference", required=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "developer_solutions": {"label": "Developer Solutions", "singular": "Developer Solution", "group": "Developer", "description": "Package reusable developer assets and their supported versions.", "fields": [field("name", "Solution name", required=True), field("version", "Version", required=True), field("components", "Components (JSON)", "json", full=True), field("documentation_url", "Documentation URL"), field("status", "Status", "select", options=COMMON_STATUS)]},
    "product_configurators": {"label": "Product Configurator", "singular": "Configurator", "group": "CPQ", "description": "Define guided product selections, dependencies, exclusions, and required options.", "fields": [field("name", "Configurator name", required=True), field("product_id", "Base product ID", "number", required=True), field("configuration_schema", "Configuration schema (JSON)", "json", required=True, full=True), field("guided_questions", "Guided questions (JSON)", "json", full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
    "price_rules": {"label": "Price Rules", "singular": "Price Rule", "group": "CPQ", "description": "Apply transparent discounts, markups, and fixed adjustments to configured product lines.", "fields": [field("name", "Rule name", required=True), field("priority", "Priority", "number"), field("scope", "Scope", "select", options=["All", "Product", "Category", "Quantity", "Customer"]), field("scope_value", "Scope value"), field("condition", "Condition (JSON)", "json", full=True), field("action_type", "Action", "select", options=["Discount %", "Markup %", "Fixed adjustment"]), field("action_value", "Action value", "number", required=True), field("stackable", "Stackable", "select", options=["Yes", "No"]), field("status", "Status", "select", options=COMMON_STATUS)]},
    "guided_selling": {"label": "Guided Selling", "singular": "Guided Selling Flow", "group": "CPQ", "description": "Guide sellers to a recommended configuration using questions and recommendation rules.", "fields": [field("name", "Flow name", required=True), field("questions", "Questions (JSON)", "json", required=True, full=True), field("recommendations", "Recommendations (JSON)", "json", required=True, full=True), field("status", "Status", "select", options=COMMON_STATUS)]},
}


# Extended enterprise Setup catalog.  These resources use the same audited,
# validated PlatformRecord engine as the original setup surfaces.  Provider-
# specific delivery remains disabled until an administrator configures a real
# connection; storing configuration never implies that an external action ran.
def setup_resource(label: str, singular: str, group: str, description: str, fields_: list[dict[str, Any]], *, singleton: bool = False) -> dict[str, Any]:
    out = {"label": label, "singular": singular, "group": group, "description": description, "fields": fields_}
    if singleton:
        out["singleton"] = True
    return out


def std_status(*, options: list[str] | None = None) -> dict[str, Any]:
    return field("status", "Status", "select", options=options or COMMON_STATUS)


PLATFORM_RESOURCES.update({
    # General
    "personal_settings": setup_resource("Personal Settings", "Personal Setting", "General", "Personal profile, locale, signature, notifications and interface preferences.", [field("name","Name",required=True), field("photo_url","Photo URL"), field("email","Email","email"), field("phone","Phone"), field("language","Language"), field("locale","Locale"), field("timezone","Timezone"), field("date_format","Date Format"), field("time_format","Time Format"), field("number_format","Number Format"), field("signature","Signature","textarea",full=True), field("notifications","Notifications (JSON)","json",full=True), field("ui_preferences","UI Preferences (JSON)","json",full=True)], singleton=True),
    "calendar_booking": setup_resource("Calendar Booking", "Booking Configuration", "General", "Configure personal/team booking, availability, duration, URLs, round robin, rescheduling and cancellation.", [field("name","Booking name",required=True), field("booking_type","Type","select",options=["Personal","Team"]), field("availability","Availability (JSON)","json",full=True), field("working_hours","Working Hours (JSON)","json",full=True), field("meeting_duration","Meeting Duration (minutes)","number"), field("booking_url","Booking URL"), field("round_robin","Round Robin","select",options=["Enabled","Disabled"]), field("reschedule_policy","Reschedule Policy","textarea",full=True), field("cancellation_policy","Cancellation Policy","textarea",full=True), std_status()]),
    "motivator": setup_resource("Motivator", "Motivator Plan", "General", "Targets, KPIs, goals, leaderboards and sales-performance configuration.", [field("name","Plan name",required=True), field("target_type","Target Type","select",options=["Revenue","Deals","Activities","Custom KPI"]), field("target_value","Target","number"), field("period","Period"), field("kpis","KPIs (JSON)","json",full=True), field("leaderboard","Leaderboard (JSON)","json",full=True), std_status()]),
    "agents": setup_resource("Agents", "Agent", "General", "Human and Apex-assisted agent configuration.", [field("name","Agent name",required=True), field("agent_type","Type","select",options=["Human","Apex AI"]), field("purpose","Purpose","textarea",full=True), field("permissions","Permissions (JSON)","json",full=True), std_status()]),
    "business_hours": setup_resource("Business Hours", "Business Hours Rule", "General", "Organization working days, hours and timezone.", [field("name","Name",required=True), field("timezone","Timezone",required=True), field("schedule","Schedule (JSON)","json",required=True,full=True), std_status()]),
    "shifts": setup_resource("Shifts", "Shift", "General", "Define workforce shifts and assignment rules.", [field("name","Shift name",required=True), field("start_time","Start time"), field("end_time","End time"), field("timezone","Timezone"), field("days","Days (JSON)","json",full=True), field("assignment","Assignment (JSON)","json",full=True), std_status()]),
    "holidays": setup_resource("Holidays", "Holiday", "General", "Maintain company and regional holidays used by scheduling.", [field("name","Holiday",required=True), field("date","Date","date",required=True), field("region","Region"), field("description","Description","textarea",full=True), std_status()]),
    "currencies": setup_resource("Currencies", "Currency", "General", "Manage base and additional currencies and exchange-rate metadata.", [field("name","Currency name",required=True), field("code","ISO Code",required=True), field("symbol","Symbol"), field("exchange_rate","Exchange Rate","number"), field("base_currency","Base Currency","select",options=["Yes","No"]), std_status()]),
    "calendar_settings": setup_resource("Calendar Settings", "Calendar Setting", "General", "Calendar defaults, week rules, reminders and synchronization preferences.", [field("name","Configuration name",required=True), field("week_starts","Week Starts","select",options=["Monday","Sunday"]), field("default_duration","Default Duration","number"), field("reminders","Reminders (JSON)","json",full=True), field("sync_preferences","Sync Preferences (JSON)","json",full=True), std_status()], singleton=True),

    # Security
    "mail_users": setup_resource("Email / Mail Users", "Mail User", "Security Control", "Mail identity and mailbox access assignments.", [field("name","User name",required=True), field("email","Email","email",required=True), field("mailbox_role","Mailbox Role"), field("permissions","Permissions (JSON)","json",full=True), std_status()]),
    "compliance_settings": setup_resource("Compliance Settings", "Compliance Policy", "Security Control", "Consent, personal/sensitive data, retention, subject export, deletion and anonymization controls.", [field("name","Policy name",required=True), field("consent","Consent Rules (JSON)","json",full=True), field("personal_data","Personal Data Rules (JSON)","json",full=True), field("sensitive_data","Sensitive Data Rules (JSON)","json",full=True), field("retention","Retention (JSON)","json",full=True), field("subject_rights","Subject Rights (JSON)","json",full=True), std_status()]),
    "territory_management": setup_resource("Territory Management", "Territory Rule", "Security Control", "Territory hierarchy, users, assignment, visibility, forecasts and reporting.", [field("name","Territory",required=True), field("parent","Parent Territory"), field("users","Users (JSON)","json",full=True), field("assignment_rules","Assignment Rules (JSON)","json",full=True), field("visibility","Visibility (JSON)","json",full=True), field("forecasting","Forecasting","select",options=["Enabled","Disabled"]), std_status()]),
    "trusted_domains": setup_resource("Trusted Domain", "Trusted Domain", "Security Control", "Manage domains trusted for CRM access and integrations.", [field("name","Domain label",required=True), field("domain","Domain",required=True), field("purpose","Purpose"), std_status()]),
    "support_access": setup_resource("Support Access", "Support Access Grant", "Security Control", "Temporary audited support access with explicit expiry.", [field("name","Grant name",required=True), field("support_identity","Support Identity"), field("expires_at","Expires At","datetime"), field("scope","Scope (JSON)","json",full=True), field("audit_note","Audit Note","textarea",full=True), std_status(options=["Enabled","Disabled","Expired"])]),
    "sso_saml": setup_resource("Single Sign-On (SAML)", "SAML Configuration", "Security Control", "Identity provider, entity ID, login/logout URLs, certificate, domains and user mapping.", [field("name","Configuration name",required=True), field("identity_provider","Identity Provider",required=True), field("entity_id","Entity ID",required=True), field("login_url","Login URL"), field("logout_url","Logout URL"), field("certificate","Certificate / Fingerprint","textarea",full=True), field("domains","Domains (JSON)","json",full=True), field("user_mapping","User Mapping (JSON)","json",full=True), std_status()], singleton=True),
    "security_policies": setup_resource("Security Policies", "Security Policy", "Security Control", "Password, session, IP, login and MFA policy metadata.", [field("name","Policy name",required=True), field("password_policy","Password Policy (JSON)","json",full=True), field("session_policy","Session Policy (JSON)","json",full=True), field("ip_restrictions","IP Restrictions (JSON)","json",full=True), field("login_restrictions","Login Restrictions (JSON)","json",full=True), field("mfa","MFA Configuration (JSON)","json",full=True), std_status()]),
    "active_directory_sync": setup_resource("Active Directory Sync", "Directory Sync", "Security Control", "Directory synchronization architecture and mapping metadata.", [field("name","Sync name",required=True), field("directory_type","Directory Type","select",options=["Active Directory","LDAP","Microsoft Entra ID"]), field("endpoint","Endpoint"), field("mapping","User/Group Mapping (JSON)","json",full=True), field("schedule","Schedule"), field("last_sync","Last Sync","datetime"), std_status()]),
    "login_history": setup_resource("Login History", "Login Event", "Security Control", "User login time, IP, device/browser and result.", [field("name","Event",required=True), field("user_email","User","email"), field("login_time","Time","datetime"), field("ip_address","IP Address"), field("device","Device / Browser"), field("result","Result","select",options=["Success","Failure","Blocked"]), field("source","Source")]),

    # Channels
    "email_channels": setup_resource("Email", "Email Channel", "Channels", "SMTP/IMAP, organization addresses, provider sync, relay, tracking and unsubscribe configuration.", [field("name","Channel name",required=True), field("provider","Provider","select",options=["SMTP/IMAP","Gmail","Microsoft","Other"]), field("organization_addresses","Organization Addresses (JSON)","json",full=True), field("sync","Email Sync","select",options=["Enabled","Disabled"]), field("relay","Relay","select",options=["Enabled","Disabled"]), field("tracking","Tracking","select",options=["Enabled","Disabled"]), field("unsubscribe","Unsubscribe Handling","select",options=["Enabled","Disabled"]), field("connection_reference","Secret/Connection Reference"), std_status()]),
    "telephony": setup_resource("Telephony", "Telephony Provider", "Channels", "Provider integration, click-to-call, popups, logging, recording metadata and dispositions.", [field("name","Provider name",required=True), field("provider","Provider"), field("click_to_call","Click-to-Call","select",options=["Enabled","Disabled"]), field("incoming_popup","Incoming Popup","select",options=["Enabled","Disabled"]), field("recording_metadata","Recording Metadata","select",options=["Enabled","Disabled"]), field("dispositions","Dispositions (JSON)","json",full=True), field("connection_reference","Connection Reference"), std_status()]),
    "business_messaging": setup_resource("Business Messaging", "Messaging Provider", "Channels", "WhatsApp Business, SMS and future messaging provider configuration.", [field("name","Provider name",required=True), field("provider","Provider","select",options=["WhatsApp Business","SMS","Other"]), field("sender_id","Sender ID"), field("templates","Templates (JSON)","json",full=True), field("connection_reference","Connection Reference"), std_status()]),
    "notification_sms": setup_resource("Notification SMS", "SMS Configuration", "Channels", "SMS provider and notification template configuration.", [field("name","Configuration name",required=True), field("provider","Provider"), field("sender_id","Sender ID"), field("templates","Templates (JSON)","json",full=True), field("connection_reference","Connection Reference"), std_status()]),
    "webforms": setup_resource("Webforms", "Webform", "Channels", "Build governed forms that map submitted fields to CRM records.", [field("name","Form name",required=True), field("target_module","Target Module","select",options=["Leads","Contacts","Cases","Custom Module"]), field("fields","Fields (JSON)","json",required=True,full=True), field("hidden_fields","Hidden Fields (JSON)","json",full=True), field("defaults","Defaults (JSON)","json",full=True), field("assignment","Assignment (JSON)","json",full=True), field("autoresponse","Autoresponse (JSON)","json",full=True), field("spam_protection","Spam Protection","select",options=["Enabled","Disabled"]), field("redirect_url","Redirect URL"), field("embed_code","Embed Code","textarea",full=True), std_status()]),
    "social_channels": setup_resource("Social", "Social Channel", "Channels", "Social-provider connection and CRM interaction metadata.", [field("name","Channel name",required=True), field("provider","Provider"), field("account_reference","Account Reference"), field("permissions","Permissions (JSON)","json",full=True), std_status()]),
    "chat_channels": setup_resource("Chat", "Chat Channel", "Channels", "Customer chat channel and routing configuration.", [field("name","Channel name",required=True), field("provider","Provider"), field("routing","Routing (JSON)","json",full=True), field("business_hours","Business Hours Reference"), std_status()]),
    "portals": setup_resource("Portals", "Portal", "Channels", "Customer, partner, vendor and custom portal permissions.", [field("name","Portal name",required=True), field("portal_type","Type","select",options=["Customer","Partner","Vendor","Custom"]), field("modules","Modules (JSON)","json",full=True), field("record_permissions","Record Permissions (JSON)","json",full=True), field("field_permissions","Field Permissions (JSON)","json",full=True), std_status()]),

    # Customization
    "wizards": setup_resource("Wizards", "Wizard", "Customization", "Multi-step record form definitions.", [field("name","Wizard name",required=True), field("module","Module",required=True), field("steps","Steps (JSON)","json",required=True,full=True), field("rules","Rules (JSON)","json",full=True), std_status()]),
    "kiosk_builder": setup_resource("Kiosk Process Builder", "Kiosk Flow", "Customization", "Yash-native guided no-code process screen definitions.", [field("name","Flow name",required=True), field("screens","Screens (JSON)","json",required=True,full=True), field("transitions","Transitions (JSON)","json",full=True), field("permissions","Permissions (JSON)","json",full=True), std_status()]),
    "page_designer": setup_resource("Page Designer", "Page Design", "Customization", "Yash-native designer metadata for detail, create/edit, home, cards and module views.", [field("name","Design name",required=True), field("surface","Surface","select",options=["Record Detail","Create/Edit","Home","Cards","Module View"]), field("module","Module"), field("layout","Layout (JSON)","json",required=True,full=True), field("responsive_rules","Responsive Rules (JSON)","json",full=True), std_status()]),
    "home_customization": setup_resource("Customize Home Page", "Home Layout", "Customization", "Configurable home widgets, ordering and layout.", [field("name","Layout name",required=True), field("widgets","Widgets (JSON)","json",required=True,full=True), field("audience","Audience (JSON)","json",full=True), std_status()]),
    "translations": setup_resource("Translations", "Translation Set", "Customization", "Module, field, picklist and custom UI translations.", [field("name","Translation set",required=True), field("language","Language",required=True), field("module_labels","Module Labels (JSON)","json",full=True), field("field_labels","Field Labels (JSON)","json",full=True), field("picklists","Picklists (JSON)","json",full=True), field("ui_text","Custom UI Text (JSON)","json",full=True), std_status()]),
    "template_library": setup_resource("Templates", "Template", "Customization", "Email, inventory, mail merge, messaging and other reusable templates.", [field("name","Template name",required=True), field("template_type","Type","select",options=["Email","Inventory","Mail Merge","Messaging","Other"]), field("module","Module"), field("subject","Subject"), field("content","Content","textarea",required=True,full=True), std_status()]),
    "teamspace_settings": setup_resource("Teamspace", "Teamspace Configuration", "Customization", "Teamspace module ordering, visibility and member-role configuration.", [field("name","Configuration name",required=True), field("modules","Modules (JSON)","json",full=True), field("module_order","Module Order (JSON)","json",full=True), field("visibility","Visibility (JSON)","json",full=True), field("member_roles","Member Roles (JSON)","json",full=True), std_status()]),

    # Automation / process
    "automation_actions": setup_resource("Actions", "Automation Action", "Automation", "Reusable field update, email, task, call, meeting, webhook, function, record, owner, tag, notification and approval actions.", [field("name","Action name",required=True), field("action_type","Type","select",options=["Field Update","Email","Task","Call","Meeting","Webhook","Function","Create Record","Owner Change","Tags","Notification","Approval"]), field("configuration","Configuration (JSON)","json",required=True,full=True), std_status()]),
    "cadences": setup_resource("Cadences", "Cadence", "Automation", "Multi-step governed outreach sequences.", [field("name","Cadence name",required=True), field("module","Module",required=True), field("steps","Steps (JSON)","json",required=True,full=True), field("exit_rules","Exit Rules (JSON)","json",full=True), std_status()]),
    "review_processes": setup_resource("Review Processes", "Review Process", "Process Management", "Require record verification before completion or downstream actions.", [field("name","Process name",required=True), field("module","Module",required=True), field("entry_criteria","Entry Criteria (JSON)","json",full=True), field("reviewers","Reviewers (JSON)","json",full=True), field("actions","Actions (JSON)","json",full=True), std_status()]),
    "connected_workflows": setup_resource("Connected Workflow", "Connected Workflow", "Process Management", "Cross-module and cross-process automation definitions.", [field("name","Workflow name",required=True), field("source_module","Source Module",required=True), field("trigger","Trigger",required=True), field("steps","Cross-module Steps (JSON)","json",required=True,full=True), field("error_policy","Error Policy (JSON)","json",full=True), std_status()]),

    # Experience
    "signals": setup_resource("Signals", "Signal Rule", "Experience Center", "Central CRM events from communication, web, integrations and Apex.", [field("name","Signal name",required=True), field("signal_type","Type","select",options=["Email","Call","Meeting","Website","Messaging","Integration","Apex"]), field("source","Source"), field("criteria","Criteria (JSON)","json",full=True), field("actions","Actions (JSON)","json",full=True), std_status()]),
    "command_center": setup_resource("CommandCenter", "Journey", "Experience Center", "Customer/business journey orchestration.", [field("name","Journey name",required=True), field("audience","Audience (JSON)","json",full=True), field("stages","Stages (JSON)","json",required=True,full=True), field("transitions","Transitions (JSON)","json",full=True), field("goals","Goals (JSON)","json",full=True), std_status()]),
    "segmentation": setup_resource("Segmentation", "Segment", "Experience Center", "Dynamic customer segments based on CRM, activity, sales, engagement and scores.", [field("name","Segment name",required=True), field("target_module","Target Module",required=True), field("criteria","Criteria (JSON)","json",required=True,full=True), field("refresh_policy","Refresh Policy"), std_status()]),

    # Data Administration
    "data_backup": setup_resource("Data Backup", "Backup Plan", "Data Administration", "Manual/scheduled backup configuration and restore metadata.", [field("name","Backup plan",required=True), field("schedule","Schedule"), field("scope","Scope (JSON)","json",full=True), field("retention_days","Retention Days","number"), field("last_backup","Last Backup","datetime"), field("restore_point","Restore Point"), std_status()]),
    "storage": setup_resource("Storage", "Storage Snapshot", "Data Administration", "Track database, files, documents and attachment usage metadata.", [field("name","Snapshot",required=True), field("database_bytes","Database Bytes","number"), field("file_bytes","File Bytes","number"), field("document_bytes","Document Bytes","number"), field("attachment_bytes","Attachment Bytes","number"), field("captured_at","Captured At","datetime")]),
    "sandboxes": setup_resource("Sandbox", "Sandbox", "Data Administration", "Isolated configuration test environment metadata for modules, fields, layouts, automation, permissions and templates.", [field("name","Sandbox name",required=True), field("environment","Environment","select",options=["Development","Testing","Staging"]), field("components","Components (JSON)","json",full=True), field("source_version","Source Version"), field("deployment_status","Deployment Status","select",options=["Draft","Ready","Deployed","Failed"]), std_status()]),
    "copy_customization": setup_resource("Copy Customization", "Customization Copy", "Data Administration", "Copy supported configuration sets between environments or organizations.", [field("name","Copy job",required=True), field("source","Source",required=True), field("destination","Destination",required=True), field("components","Components (JSON)","json",full=True), field("conflict_policy","Conflict Policy","select",options=["Skip","Overwrite","Review"]), std_status(options=["Draft","Queued","Completed","Failed"])]),
    "data_quality": setup_resource("Data Quality", "Quality Rule", "Data Administration", "Rules for completeness, validity, normalization and duplicate prevention.", [field("name","Rule name",required=True), field("module","Module",required=True), field("rule_type","Rule Type","select",options=["Completeness","Validity","Normalization","Duplicate","Freshness"]), field("criteria","Criteria (JSON)","json",full=True), field("severity","Severity","select",options=["Low","Medium","High","Critical"]), std_status()]),
    "migration": setup_resource("Migration", "Migration Job", "Data Administration", "Source migration, mapping, validation and reconciliation metadata.", [field("name","Migration name",required=True), field("source_system","Source System",required=True), field("mapping","Mapping (JSON)","json",full=True), field("duplicate_policy","Duplicate Policy"), field("validation","Validation (JSON)","json",full=True), field("history","History (JSON)","json",full=True), std_status(options=["Draft","Validated","Running","Completed","Failed"])]),

    # Marketplace
    "marketplace_integrations": setup_resource("Marketplace", "Integration", "Marketplace", "Installable integration registry with category, permissions and connection state.", [field("name","Integration name",required=True), field("category","Category","select",options=["Yash Native","Google","Microsoft","Meta/Facebook","LinkedIn","Other Providers"]), field("provider","Provider"), field("permissions","Permissions (JSON)","json",full=True), field("configuration","Configuration (JSON)","json",full=True), field("connection_status","Connection Status","select",options=["Not Connected","Connected","Error"]), std_status(options=["Available","Installed","Enabled","Disabled"])]),

    # Developer Hub extensions
    "oauth_clients": setup_resource("OAuth Clients", "OAuth Client", "Developer", "OAuth client metadata and approved scopes. Secrets are referenced, never rendered.", [field("name","Client name",required=True), field("client_id","Client ID"), field("redirect_uris","Redirect URIs (JSON)","json",full=True), field("scopes","Scopes (JSON)","json",full=True), field("secret_reference","Secret Reference"), std_status()]),
    "api_usage": setup_resource("API Usage", "API Usage Record", "Developer", "API usage counters and rate-limit observations.", [field("name","Usage record",required=True), field("client_id","Client ID"), field("period","Period"), field("request_count","Request Count","number"), field("error_count","Error Count","number"), field("rate_limit","Rate Limit","number")]),
    "circuits": setup_resource("Circuits", "Circuit", "Developer", "Yash-native orchestration of functions, conditions, API calls, waits, retries and error handling.", [field("name","Circuit name",required=True), field("steps","Steps (JSON)","json",required=True,full=True), field("retry_policy","Retry Policy (JSON)","json",full=True), field("error_handling","Error Handling (JSON)","json",full=True), std_status()]),
    "style_ui": setup_resource("StyleUI", "StyleUI Extension", "Developer", "Yash-native UI extension and design metadata.", [field("name","Extension name",required=True), field("surface","Surface"), field("tokens","Design Tokens (JSON)","json",full=True), field("components","Components (JSON)","json",full=True), field("permissions","Permissions (JSON)","json",full=True), std_status()]),

    # Apex
    "apex_agents": setup_resource("Apex Agents", "Apex Agent", "Apex", "AI agents with purpose, instructions, tools, scopes, model and test/log metadata.", [field("name","Agent name",required=True), field("purpose","Purpose","textarea",full=True), field("instructions","Instructions","textarea",full=True), field("tools","Tools (JSON)","json",full=True), field("permissions","Permissions (JSON)","json",full=True), field("scopes","Scopes (JSON)","json",full=True), field("model","Model"), field("logs","Logs (JSON)","json",full=True), std_status()]),
    "apex_data_enrichment": setup_resource("Data Enrichment", "Enrichment Rule", "Apex", "CRM record enrichment rules and provider mappings.", [field("name","Rule name",required=True), field("module","Module",required=True), field("provider","Provider"), field("fields","Fields (JSON)","json",full=True), field("confidence_threshold","Confidence Threshold","number"), std_status()]),
    "apex_prediction": setup_resource("Prediction", "Prediction Model", "Apex", "Predictive configurations for leads, deals, customers and cases with uncertainty metadata.", [field("name","Prediction name",required=True), field("target","Target","select",options=["Leads","Deals","Customers","Cases"]), field("model","Model"), field("features","Features (JSON)","json",full=True), field("thresholds","Thresholds (JSON)","json",full=True), std_status()]),
    "apex_recommendation": setup_resource("Recommendation", "Recommendation Rule", "Apex", "Next-best-action, cross-sell, upsell, follow-up and deal recommendation rules.", [field("name","Rule name",required=True), field("recommendation_type","Type","select",options=["Next Best Action","Cross-Sell","Upsell","Follow-Up","Deal Recommendation"]), field("criteria","Criteria (JSON)","json",full=True), field("actions","Actions (JSON)","json",full=True), std_status()]),
    "apex_communication": setup_resource("Communication", "Communication AI Rule", "Apex", "AI assistance for email, calls, meetings, messages, sentiment, intent and summaries.", [field("name","Rule name",required=True), field("channels","Channels (JSON)","json",full=True), field("features","Features (JSON)","json",full=True), field("confirmation_required","External Send Confirmation","select",options=["Required","Approved Automation Only"]), std_status()]),
    "apex_vision": setup_resource("Vision", "Vision Configuration", "Apex", "Image/document intelligence configuration where supported by connected providers.", [field("name","Configuration name",required=True), field("provider","Provider"), field("capabilities","Capabilities (JSON)","json",full=True), field("limits","Limits (JSON)","json",full=True), std_status()]),
    "apex_notifications": setup_resource("Notifications", "AI Notification Rule", "Apex", "Configure AI-generated alerts and insights.", [field("name","Rule name",required=True), field("signal","Signal"), field("criteria","Criteria (JSON)","json",full=True), field("recipients","Recipients (JSON)","json",full=True), std_status()]),
    "apex_voc": setup_resource("Voice of the Customer", "VOC Configuration", "Apex", "Analyze feedback, interactions, sentiment, themes and trends.", [field("name","Configuration name",required=True), field("sources","Sources (JSON)","json",full=True), field("themes","Themes (JSON)","json",full=True), field("sentiment","Sentiment","select",options=["Enabled","Disabled"]), std_status()]),
    "apex_models": setup_resource("Models", "AI Model", "Apex", "AI providers, models, credential references, roles, fallbacks and limits.", [field("name","Model configuration",required=True), field("provider","Provider",required=True), field("model","Model",required=True), field("credential_reference","Credential Reference"), field("role","Model Role"), field("fallback_model","Fallback Model"), field("limits","Limits (JSON)","json",full=True), std_status()]),
    "apex_presentation": setup_resource("Presentation", "Presentation Configuration", "Apex", "AI-assisted CRM summary/presentation generation configuration.", [field("name","Configuration name",required=True), field("templates","Templates (JSON)","json",full=True), field("data_scopes","Data Scopes (JSON)","json",full=True), std_status()]),
    "apex_studio": setup_resource("Custom AI Studio", "AI Studio Asset", "Apex", "Prompts, tools, agents, model connections, workflows, testing and versioning.", [field("name","Asset name",required=True), field("asset_type","Type","select",options=["Prompt","Tool","Agent","Model Connection","AI Workflow"]), field("configuration","Configuration (JSON)","json",required=True,full=True), field("version","Version"), field("test_results","Test Results (JSON)","json",full=True), std_status()]),
    "apex_competitors": setup_resource("Competitors", "Competitor", "Apex", "Competitor intelligence connected to deals, accounts and products.", [field("name","Competitor name",required=True), field("website","Website"), field("strengths","Strengths","textarea",full=True), field("weaknesses","Weaknesses","textarea",full=True), field("positioning","Positioning","textarea",full=True), field("related_context","Related Context (JSON)","json",full=True), std_status()]),

    # Setup UI preferences
    "setup_preferences": setup_resource("Customize Setup", "Setup Preference", "General", "Visibility and ordering preferences for Setup groups without deleting configuration.", [field("name","Preference name",required=True), field("hidden_groups","Hidden Groups (JSON)","json",full=True), field("hidden_items","Hidden Items (JSON)","json",full=True), field("group_order","Group Order (JSON)","json",full=True)], singleton=True),
})


SETUP_NAVIGATION: dict[str, list[tuple[str, str]]] = {
    "General": [
        ("personal_settings","Personal Settings"),("users","Users"),("company_details","Company Settings"),
        ("calendar_booking","Calendar Booking"),("motivator","Motivator"),("agents","Agents"),
        ("fiscal_years","Fiscal Year"),("business_hours","Business Hours"),("shifts","Shifts"),
        ("holidays","Holidays"),("currencies","Currencies"),("calendar_settings","Calendar Settings")
    ],
    "Security Control": [
        ("profiles","Profiles"),("roles","Roles and Sharing"),("mail_users","Mail Add-on Users"),
        ("compliance_settings","Compliance Settings"),("territory_management","Territory Management"),
        ("trusted_domains","Trusted Domain"),("support_access","Support Access"),("sso_saml","Single Sign-On (SAML)"),
        ("security_policies","Security Policies"),("active_directory_sync","Active Directory Sync"),
        ("login_history","Login History"),("audit_log","Audit Log")
    ],
    "Channels": [
        ("email_channels","Email"),("telephony","Telephony"),("business_messaging","Business Messaging"),
        ("notification_sms","Notification SMS"),("webforms","Webforms"),("social_channels","Social"),
        ("chat_channels","Chat"),("portals","Portals")
    ],
    "Customization": [
        ("custom_modules","Modules and Fields"),("pipelines","Pipelines"),("wizards","Wizards"),
        ("kiosk_builder","Kiosk Studio"),("page_designer","Canvas"),("home_customization","Customize Home page"),
        ("translations","Translations"),("template_library","Templates"),("teamspace_settings","Teamspace")
    ],
    "Automation": [
        ("workflow_rules","Workflow Rules"),("automation_actions","Actions"),("schedules","Schedules"),
        ("assignment_rules","Assignment"),("scoring_rules","Scoring Rules"),("cadences","Cadences")
    ],
    "Process Management": [
        ("blueprints","Blueprint"),("approval_processes","Approval Processes"),
        ("review_processes","Review Processes"),("connected_workflows","Connected Workflow")
    ],
    "Experience Center": [("signals","Signals"),("command_center","CommandCenter"),("segmentation","Segmentation")],
    "Data Administration": [
        ("import","Import"),("export","Export"),("data_backup","Data Backup"),("storage","Storage"),("recycle_bin","Recycle Bin"),("sandboxes","Sandbox"),("copy_customization","Copy Customization"),
        ("duplicates","Duplicate Management"),("data_quality","Data Quality"),("migration","Migration")
    ],
    "Marketplace": [("marketplace_integrations","All Integrations")],
    "Developer Hub": [
        ("mcp_servers","MCP for AI Agents"),("api_settings","APIs and SDKs"),("connections","Connections"),
        ("variables","Variables"),("circuits","Circuits"),("functions","Functions"),("widgets","Widgets"),
        ("data_models","Data Model"),("style_ui","StyleUI"),("queries","Queries"),
        ("client_scripts","Client Script"),("developer_solutions","Catalyst Solutions")
    ],
    "Apex": [
        ("apex_agents","Agents"),("apex_data_enrichment","Data Enrichment"),("apex_prediction","Prediction"),
        ("apex_recommendation","Recommendation"),("apex_communication","Communication"),("apex_vision","Vision"),
        ("apex_notifications","Notifications"),("apex_voc","Voice of the Customer"),("apex_models","Models"),
        ("apex_presentation","Presentation"),("apex_studio","Custom AI Studio"),
        ("apex_competitors","Competitors")
    ],
    "CPQ": [("product_configurators","Product Configurator"),("price_rules","Price Rules"),("guided_selling","Guided Selling")],
}


def public_catalog() -> dict[str, Any]:
    return {key: value for key, value in PLATFORM_RESOURCES.items()}

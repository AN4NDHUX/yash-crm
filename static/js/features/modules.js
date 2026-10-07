import { esc, titleCase, badge, lookupName, formatDate, formatDateTime, formatMoney } from "../core/runtime.js";

export const MODULES = {
  leads: {
    label: "Leads", singular: "Lead", icon: "✦", description: "Capture and qualify every new relationship.", search: "Search by name, company or email...", status: ["New", "Contacted", "Qualified", "Unqualified", "Converted"],
    columns: [
      { label: "Lead", cell: (r) => `<button class="record-link" data-open-record="leads" data-id="${r.id}">${esc(r.name)}<span class="sub-cell">${esc(r.company || "No company")}</span></button>` },
      { label: "Status", cell: (r) => badge(r.status) },
      { label: "Source", key: "source" },
      { label: "Score", cell: (r) => `<strong>${r.lead_score ?? 0}</strong><span class="sub-cell">out of 100</span>` },
      { label: "Owner", cell: (r) => r.owner_name || "Unassigned" },
      { label: "Next follow-up", cell: (r) => formatDate(r.next_follow_up) },
    ],
    fields: [
      { key: "name", label: "Full name", required: true }, { key: "company", label: "Company" }, { key: "email", label: "Email", type: "email" }, { key: "phone", label: "Phone" },
      { key: "source", label: "Lead source", type: "select", options: ["Website", "Referral", "LinkedIn", "Event", "Outbound", "Other"] },
      { key: "status", label: "Status", type: "select", options: ["New", "Contacted", "Qualified", "Unqualified", "Converted"] },
      { key: "owner_id", label: "Owner", type: "user" }, { key: "lead_score", label: "Lead score", type: "number" }, { key: "next_follow_up", label: "Next follow-up", type: "date" },
      { key: "tags", label: "Tags", hint: "Separate tags with commas" }, { key: "notes", label: "Notes", type: "textarea", full: true },
    ],
  },
  contacts: {
    label: "Contacts", singular: "Contact", icon: "◎", description: "Build a complete view of every person you work with.", search: "Search contacts by name or email...", status: [],
    columns: [
      { label: "Contact", cell: (r) => `<button class="record-link" data-open-record="contacts" data-id="${r.id}">${esc(r.full_name || `${r.first_name} ${r.last_name}`)}<span class="sub-cell">${esc(r.job_title || r.email || "No title")}</span></button>` },
      { label: "Email", key: "email" }, { label: "Phone", key: "phone" }, { label: "Account", cell: (r) => esc(lookupName("accounts", r.account_id)) }, { label: "Owner", cell: (r) => r.owner_name || "Unassigned" },
    ],
    fields: [
      { key: "first_name", label: "First name", required: true }, { key: "last_name", label: "Last name", required: true }, { key: "email", label: "Email", type: "email" }, { key: "phone", label: "Phone" },
      { key: "job_title", label: "Job title" }, { key: "department", label: "Department" }, { key: "account_id", label: "Account", type: "account" }, { key: "owner_id", label: "Owner", type: "user" },
      { key: "tags", label: "Tags", hint: "Separate tags with commas" }, { key: "notes", label: "Notes", type: "textarea", full: true },
    ],
  },
  accounts: {
    label: "Accounts", singular: "Account", icon: "▣", description: "Keep company relationships, context, and history together.", search: "Search companies, industries or locations...", status: ["Active", "Inactive"],
    columns: [
      { label: "Account", cell: (r) => `<button class="record-link" data-open-record="accounts" data-id="${r.id}">${esc(r.name)}<span class="sub-cell">${esc(r.industry || "Industry not set")}</span></button>` },
      { label: "Type", key: "type" }, { label: "Location", cell: (r) => [r.billing_city, r.billing_country].filter(Boolean).join(", ") || "—" }, { label: "Employees", key: "employees" }, { label: "Owner", cell: (r) => r.owner_name || "Unassigned" },
    ],
    fields: [
      { key: "name", label: "Account name", required: true }, { key: "type", label: "Account type", type: "select", options: ["Customer", "Prospect", "Partner", "Inactive"] }, { key: "website", label: "Website" }, { key: "phone", label: "Phone" },
      { key: "industry", label: "Industry", type: "select", options: ["Technology", "Retail", "Logistics", "Healthcare", "Finance", "Education", "Other"] }, { key: "employees", label: "Employees", type: "number" }, { key: "annual_revenue", label: "Annual revenue", type: "number" }, { key: "owner_id", label: "Owner", type: "user" },
      { key: "billing_city", label: "City" }, { key: "billing_country", label: "Country" }, { key: "tags", label: "Tags", hint: "Separate tags with commas" }, { key: "notes", label: "Notes", type: "textarea", full: true },
    ],
  },
  deals: {
    label: "Deals", singular: "Deal", icon: "◇", description: "Move the right opportunities forward with confidence.", search: "Search deals, stages or sources...", status: ["Qualification", "Needs Analysis", "Proposal", "Negotiation", "Closed Won", "Closed Lost"],
    columns: [
      { label: "Deal", cell: (r) => `<button class="record-link" data-open-record="deals" data-id="${r.id}">${esc(r.name)}<span class="sub-cell">${esc(lookupName("accounts", r.account_id))}</span></button>` },
      { label: "Stage", cell: (r) => badge(r.stage) }, { label: "Amount", cell: (r) => `<strong>${formatMoney(r.amount)}</strong>` }, { label: "Probability", cell: (r) => `${r.probability || 0}%` }, { label: "Close date", cell: (r) => formatDate(r.expected_close_date) }, { label: "Owner", cell: (r) => r.owner_name || "Unassigned" },
    ],
    fields: [
      { key: "name", label: "Deal name", required: true }, { key: "account_id", label: "Account", type: "account" }, { key: "contact_id", label: "Primary contact", type: "contact" }, { key: "amount", label: "Amount", type: "number" },
      { key: "stage", label: "Stage", type: "select", options: ["Qualification", "Needs Analysis", "Proposal", "Negotiation", "Closed Won", "Closed Lost"] }, { key: "probability", label: "Probability (%)", type: "number" }, { key: "expected_close_date", label: "Expected close date", type: "date" }, { key: "owner_id", label: "Owner", type: "user" },
      { key: "type", label: "Deal type", type: "select", options: ["New business", "Expansion", "Renewal", "Partnership"] }, { key: "source", label: "Source" }, { key: "status", label: "Status", type: "select", options: ["Open", "Won", "Lost"] }, { key: "notes", label: "Notes", type: "textarea", full: true },
    ],
  },
  products: {
    label: "Products", singular: "Product", icon: "□", description: "Organize the products and services behind every customer conversation.", search: "Search products, SKUs or categories...", status: ["Active", "Inactive"],
    columns: [
      { label: "Product", cell: (r) => `<button class="record-link" data-open-record="products" data-id="${r.id}">${esc(r.name)}<span class="sub-cell">${esc(r.sku || r.category || "No SKU")}</span></button>` },
      { label: "Category", key: "category" }, { label: "Unit price", cell: (r) => formatMoney(r.unit_price) }, { label: "Stock", key: "stock_quantity" }, { label: "Status", cell: (r) => badge(r.status) },
    ],
    fields: [
      { key: "name", label: "Product name", required: true }, { key: "sku", label: "SKU" }, { key: "category", label: "Category" }, { key: "unit_price", label: "Unit price", type: "number" }, { key: "stock_quantity", label: "Stock quantity", type: "number" },
      { key: "status", label: "Status", type: "select", options: ["Active", "Inactive"] }, { key: "owner_id", label: "Owner", type: "user" }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" },
      { key: "description", label: "Description", type: "textarea", full: true },
    ],
  },
  activities: {
    label: "Activities", singular: "Activity", icon: "✓", description: "Stay on top of the work that keeps relationships moving.", search: "Search activities by subject or type...", status: ["Open", "Completed"],
    columns: [
      { label: "Activity", cell: (r) => `<button class="record-link" data-edit-record="activities" data-id="${r.id}">${esc(r.subject)}<span class="sub-cell">${esc(titleCase(r.activity_type))} · ${esc(r.related_label || "Unlinked")}</span></button>` },
      { label: "Due", cell: (r) => formatDateTime(r.due_at) }, { label: "Priority", cell: (r) => badge(r.priority) }, { label: "Status", cell: (r) => badge(r.status) }, { label: "Owner", cell: (r) => r.owner_name || "Unassigned" },
    ],
    fields: [
      { key: "activity_type", label: "Type", type: "select", options: ["Task", "Call", "Meeting"] }, { key: "subject", label: "Subject", required: true }, { key: "start_at", label: "Start date and time", type: "datetime-local" }, { key: "due_at", label: "Due date and time", type: "datetime-local" }, { key: "owner_id", label: "Owner", type: "user" },
      { key: "status", label: "Status", type: "select", options: ["Open", "Completed"] }, { key: "priority", label: "Priority", type: "select", options: ["Low", "Normal", "High"] }, { key: "related_type", label: "Related to", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" },
      { key: "description", label: "Description", type: "textarea", full: true },
    ],
  },
};

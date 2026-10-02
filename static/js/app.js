const state = {
  meta: null,
  route: window.location.pathname,
  moduleState: {},
  modal: null,
  confirmResolve: null,
  settingsCache: {},
  lookups: { accounts: [], contacts: [], leads: [], deals: [], loaded: false },
  platformLookups: {},
  profile: null,
  platformCatalog: { resources: {}, setup_navigation: {} },
  aiMessages: [],
  aiStatus: null,
  aiExceptionView: "needs_review",
  aiExceptionOrder: "deterministic",
  aiRankedItems: null,
  aiSelectedException: null,
  aiConversationStarted: false,
};

const PLATFORM_MODULE_ROUTES = [
  "price_books", "vendors", "quotes", "sales_orders", "purchase_orders", "invoices", "payments",
  "campaigns", "cases", "solutions", "documents", "site_visits", "forecasts", "reports", "dashboards", "sales_targets",
];
const BRAND_ORBS_LOADER_URL = "/static/threeui/brand-orbs-loader.html?v=20261001-logo-orbs";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const titleCase = (value) => String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const initials = (value) => String(value || "Y").split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
const formatDate = (value) => {
  if (!value) return "—";
  const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric" }).formatToParts(parsed).reduce((acc, part) => ({ ...acc, [part.type]: part.value }), {});
  if (state.settingsCache.date_format === "MM/DD/YYYY") return `${parts.month}/${parts.day}/${parts.year}`;
  if (state.settingsCache.date_format === "YYYY-MM-DD") return `${parts.year}-${parts.month}-${parts.day}`;
  return `${parts.day} ${parts.month} ${parts.year}`;
};
const formatDateTime = (value) => value ? new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "—";
const formatMoney = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: state.settingsCache.currency || "INR", maximumFractionDigits: 0 }).format(Number(value || 0));
const slug = (value) => String(value || "").toLowerCase().replace(/\s+/g, "-");
const pathFor = (resource, id) => `/${resource}${id ? `/${id}` : ""}`;

const MODULES = {
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

function badge(value) {
  const label = value || "Not set";
  const cls = { "Closed Won": "won", "Closed Lost": "lost", Completed: "green", Active: "active", Qualified: "qualified", Proposal: "progress", Negotiation: "progress", High: "amber", Open: "blue", New: "indigo" }[label] || slug(label);
  return `<span class="status-badge ${esc(cls)}">${esc(label)}</span>`;
}

function lookupName(resource, id) {
  if (!id) return "—";
  const item = state.lookups[resource]?.find((entry) => Number(entry.id) === Number(id));
  if (!item) return `#${id}`;
  return item.full_name || item.name || `${item.first_name} ${item.last_name}`;
}

async function api(path, options = {}, retried = false) {
  let response;
  const { headers: extraHeaders, ...fetchOptions } = options;
  const csrf = state.aiStatus?.csrf_token;
  try {
    // headers are merged AFTER the options spread; previously a caller-supplied `headers`
    // replaced Content-Type and the CSRF header wholesale.
    response = await fetch(path, { credentials: "same-origin", ...fetchOptions, headers: { "Content-Type": "application/json", ...(csrf ? { "X-Yash-CSRF": csrf } : {}), ...(extraHeaders || {}) } });
  }
  catch { throw new Error("Yash CRM could not reach the server. Check the connection and try again."); }
  const raw = await response.text();
  let body = {};
  try { body = raw ? JSON.parse(raw) : {}; } catch { body = {}; }
  if (!response.ok) {
    const detail = body.detail && typeof body.detail === "object" ? body.detail : null;
    // A restart/redeploy while this tab was open invalidates nothing now that the token is stable,
    // but a rotated YASHCRM_CSRF_SECRET or APP_PASSWORD still does: refresh once, then retry.
    // The server rejects before acting, so replaying the request cannot double-apply it.
    if (response.status === 403 && detail?.code === "CSRF_REJECTED" && !retried && path !== "/api/ai/status") {
      let refreshed = null;
      try { refreshed = await api("/api/ai/status", {}, true); } catch { /* keep the original error */ }
      if (refreshed?.csrf_token) { state.aiStatus = refreshed; return api(path, options, true); }
    }
    const message = response.status === 401
      ? "You are not signed in, or your sign-in expired. Reload the page and enter your credentials again."
      : (detail?.message || body.detail || body.message || raw.slice(0, 180) || `Request failed with HTTP ${response.status}`);
    const error = new Error(message);
    error.status = response.status;
    error.code = detail?.code || body.code || null;
    throw error;
  }
  return body;
}

function toast(title, message = "", type = "success") {
  const region = $("#toast-region");
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.innerHTML = `<span class="result-icon">${type === "error" ? "!" : "✓"}</span><div><strong>${esc(title)}</strong><small>${esc(message)}</small></div>`;
  region.appendChild(item);
  setTimeout(() => item.remove(), 3600);
}

function setBreadcrumb(label, parent = "Workspace") {
  $("#breadcrumbs").innerHTML = `<span>${esc(parent)}</span><b>/</b><strong>${esc(label)}</strong>`;
}

function activeNav(route) {
  const root = route.split("/").filter(Boolean)[0] || "dashboard";
  $$('[data-route]').forEach((link) => link.classList.toggle("active", link.dataset.route === root));
}

function enhanceNavigation() {
  const setupLink = $('[data-route="setup"]');
  if (setupLink) setupLink.remove();
  const settingsLink = $('[data-route="settings"]');
  if (settingsLink) settingsLink.textContent = "Settings & General Setup";
  const addAfter = (route, nextRoute, label) => {
    const anchor = $(`[data-route="${route}"]`);
    if (anchor && !$(`[data-route="${nextRoute}"]`)) anchor.insertAdjacentHTML("afterend", `<a href="/${nextRoute}" data-route="${nextRoute}">${label}</a>`);
  };
  addAfter("invoices", "payments", "Payments");
  addAfter("documents", "site_visits", "Site Visits");
  addAfter("reports", "sales_targets", "Sales Targets & Incentives");
  addAfter("sales_targets", "ai", "AI Copilot");
}

function pageHeader(eyebrow, title, copy, actions = "") {
  return `<div class="page-heading"><div><span class="eyebrow">${esc(eyebrow)}</span><h1>${esc(title)}</h1><p class="subheading">${esc(copy)}</p></div><div class="heading-actions">${actions}</div></div>`;
}

function loading() { return `<div class="loading" role="status" aria-live="polite"><div class="brand-orbs-shell"><iframe class="brand-orbs-loader" src="${BRAND_ORBS_LOADER_URL}" title="Loading animation" aria-hidden="true" tabindex="-1" loading="eager"></iframe><span class="yash-loading-logo" aria-hidden="true"><img src="/static/yash-crm-logo.png" alt="" /></span></div><span class="loading-label">Connecting your customer journey</span><span class="loading-steps" aria-hidden="true"><i>Lead</i><b></b><i>Visit</i><b></b><i>Quote</i><b></b><i>Payment</i></span><span class="loading-progress" aria-hidden="true"><i></i></span></div>`; }
function emptyState(icon, title, copy, button = "") { return `<div class="empty-state"><span class="empty-icon">${icon}</span><h3>${esc(title)}</h3><p>${esc(copy)}</p>${button ? `<div style="margin-top:16px">${button}</div>` : ""}</div>`; }

async function ensureLookups() {
  if (state.lookups.loaded) return;
  const [accounts, contacts, leads, deals] = await Promise.all([api("/api/accounts?limit=100"), api("/api/contacts?limit=100"), api("/api/leads?limit=100"), api("/api/deals?limit=100")]);
  state.lookups.accounts = accounts.items;
  state.lookups.contacts = contacts.items;
  state.lookups.leads = leads.items;
  state.lookups.deals = deals.items;
  state.lookups.loaded = true;
}

async function ensurePlatformLookup(resource) {
  if (state.platformLookups[resource]) return;
  state.platformLookups[resource] = (await api(`/api/platform/${resource}?limit=100&sort=name_asc`)).items;
}

function invalidateLookups() { state.lookups.loaded = false; state.platformLookups = {}; }

async function refreshMeta() {
  try { state.meta = await api("/api/meta"); } catch (error) { /* keep the previous list */ }
}

async function ensurePlatformCatalog() {
  if (Object.keys(state.platformCatalog.resources || {}).length) return true;
  try {
    state.platformCatalog = await api("/api/platform/catalog");
    return Object.keys(state.platformCatalog.resources || {}).length > 0;
  } catch (error) {
    return false;
  }
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function applyProfile() {
  const profile = state.profile;
  if (!profile) return;
  const role = profile.role || "";
  $$(".user-mini .avatar, .top-profile .avatar").forEach((node) => { node.textContent = initials(profile.name); });
  $$(".user-mini strong, .top-profile-copy strong").forEach((node) => { node.textContent = profile.name; });
  $$(".user-mini small, .top-profile-copy small").forEach((node) => { node.textContent = role; });
}

async function refreshNavCount() {
  try {
    const data = await api("/api/leads?limit=1");
    const badgeNode = $("#nav-leads-count");
    if (badgeNode) { badgeNode.textContent = data.total; badgeNode.hidden = !data.total; }
  } catch (error) { /* counts are best effort */ }
}

async function navigate(path, replace = false) {
  if (replace) history.replaceState({}, "", path); else history.pushState({}, "", path);
  state.route = path;
  await renderRoute();
  $("#sidebar").classList.remove("open");
}

async function renderRoute() {
  const route = window.location.pathname;
  state.route = route;
  activeNav(route);
  const content = $("#app-content");
  content.innerHTML = loading();
  refreshNavCount();
  try {
    await ensureLookups();
    const parts = route.split("/").filter(Boolean);
    if (!parts.length || route === "/dashboard") {
      setBreadcrumb("Dashboard");
      content.innerHTML = await dashboardView();
      bindDashboard();
      return;
    }
    if (parts[0] === "ai") {
      setBreadcrumb("AI Copilot", "Intelligence");
      content.innerHTML = await aiView();
      bindAI();
      return;
    }
    if (parts[0] === "setup") {
      const resource = parts[1] || "company_details";
      setBreadcrumb(titleCase(resource), "Setup");
      content.innerHTML = await setupView(resource);
      bindPlatform(resource);
      return;
    }
    if (parts[0] === "settings") {
      const validTabs = ["general", "profile-users", "approval-process", "blueprint"];
      if (parts[1] && !validTabs.includes(parts[1])) return navigate("/settings/general", true);
      const tab = parts[1] || "general";
      setBreadcrumb("Settings", "Manage");
      content.innerHTML = await settingsView(tab);
      bindSettings();
      return;
    }
    if (PLATFORM_MODULE_ROUTES.includes(parts[0])) {
      const catalogReady = await ensurePlatformCatalog();
      const resource = parts[0];
      if (!catalogReady || !state.platformCatalog.resources[resource]) {
        content.innerHTML = `<div class="card empty-state"><span class="empty-icon">!</span><h3>${esc(titleCase(resource))} is temporarily unavailable</h3><p>Yash CRM could not load the module catalog. Please retry without leaving this module.</p><div style="margin-top:16px"><button class="button button-primary" data-retry>Retry module</button></div></div>`;
        return;
      }
      setBreadcrumb(state.platformCatalog.resources[resource].label);
      content.innerHTML = await platformModuleView(resource);
      bindPlatform(resource);
      return;
    }
    if (parts[0] === "activities" && ["tasks", "meetings", "calls"].includes(parts[1])) {
      const type = parts[1].slice(0, -1).replace(/^./, (value) => value.toUpperCase());
      setBreadcrumb(`${type}s`, "Activities");
      content.innerHTML = await activityTypeView(type);
      bindModule("activities");
      return;
    }
    if (MODULES[parts[0]]) {
      const resource = parts[0];
      setBreadcrumb(parts[1] ? `${MODULES[resource].singular} detail` : MODULES[resource].label);
      if (parts[1] && !Number.isInteger(Number(parts[1]))) return navigate(`/${resource}`, true);
      if (parts[1]) {
        content.innerHTML = await detailView(resource, Number(parts[1]));
        bindDetail(resource, Number(parts[1]));
      } else {
        content.innerHTML = await moduleView(resource);
        bindModule(resource);
      }
      return;
    }
    if (state.platformCatalog.resources[parts[0]]) {
      const resource = parts[0];
      setBreadcrumb(state.platformCatalog.resources[resource].label);
      content.innerHTML = await platformModuleView(resource);
      bindPlatform(resource);
      return;
    }
    await navigate("/dashboard", true);
  } catch (error) {
    content.innerHTML = `<div class="card empty-state"><span class="empty-icon">!</span><h3>Could not load this view</h3><p>${esc(error.message)}</p><div style="margin-top:16px"><button class="button button-primary" data-retry>Try again</button></div></div>`;
  }
}

async function dashboardView() {
  const data = await api("/api/dashboard");
  const metrics = data.metrics;
  const journey = data.journey || {};
  const maxPipeline = Math.max(...data.pipeline.map((row) => row.amount), 1);
  const maxLeads = Math.max(...data.lead_funnel.map((row) => row.count), 1);
  const performancePanel = `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>Sales performance</h2><small>Target, collections, conversion and earned incentive</small></div><button class="card-head-link" data-go="/sales_targets">Manage targets →</button></div><div class="card-body">${performanceTable(data.sales_performance || [])}</div></section>`;
  const attentionPanel = `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>AI action queue</h2><small>Prioritized from live CRM dates and statuses</small></div></div><div class="card-body">${attentionQueue(data.attention || {})}</div></section>`;
  return `${pageHeader("Overview", `${greeting()}, ${String(state.profile?.name || "there").split(" ")[0]}`, "Here is what is happening across your customer workspace.", `<button class="button button-ghost" data-go="/ai"><span class="button-icon">✦</span>Ask AI</button><button class="button button-ghost" data-create="activities"><span class="button-icon">＋</span>Log activity</button><button class="button button-primary" data-create="leads"><span class="button-icon">＋</span>Add lead</button>`)}
    <div class="stats-grid">
      <article class="card stat-card"><div class="stat-top"><span class="stat-label">Total leads</span><span class="stat-icon">✦</span></div><div class="stat-value">${metrics.total_leads}</div><div class="stat-foot"><span class="trend-up">Live</span><span>from CRM records</span></div></article>
      <article class="card stat-card"><div class="stat-top"><span class="stat-label">Open deals</span><span class="stat-icon">◇</span></div><div class="stat-value">${metrics.open_deals}</div><div class="stat-foot"><span class="trend-up">Live</span><span>from CRM records</span></div></article>
      <article class="card stat-card"><div class="stat-top"><span class="stat-label">Pipeline value</span><span class="stat-icon">₹</span></div><div class="stat-value">${formatMoney(metrics.pipeline_value)}</div><div class="stat-foot"><span class="trend-up">Live</span><span>open opportunities</span></div></article>
      <article class="card stat-card"><div class="stat-top"><span class="stat-label">Activities due</span><span class="stat-icon">✓</span></div><div class="stat-value">${metrics.activities_due}</div><div class="stat-foot"><span class="trend-warm">Needs attention</span><span>next 7 days</span></div></article>
    </div>
    <section class="dashboard-journey card"><div class="dashboard-journey-head"><div><span class="eyebrow">Revenue operations</span><h2>Complete customer journey</h2><small>One source of truth from lead received to incentive earned.</small></div><button class="card-head-link" data-go="/ai">Open Apex helpdesk →</button></div><div class="dashboard-journey-track">${[["Leads", journey.leads || metrics.total_leads, "/leads"], ["Visits", journey.visits || 0, "/site_visits"], ["Quotations", journey.quotes || 0, "/quotes"], ["Invoices", journey.invoices || 0, "/invoices"], ["Payments", journey.payments || 0, "/payments"]].map(([label, count, href], index, items) => `<a href="${href}" class="dashboard-journey-step"><span class="journey-step-number">0${index + 1}</span><strong>${count}</strong><small>${label}</small>${index < items.length - 1 ? `<i>→</i>` : ""}</a>`).join("")}</div></section>
    <div class="dashboard-grid management-grid">${performancePanel}${attentionPanel}</div>
    <div class="dashboard-grid">
      <div class="dashboard-column">
        <section class="card"><div class="card-head"><div class="card-head-copy"><h2>Pipeline overview</h2><small>Open opportunities by stage</small></div><button class="card-head-link" data-go="/deals">View deals ↗</button></div><div class="card-body"><div class="pipeline-chart">${data.pipeline.length ? data.pipeline.map((row) => `<div class="pipeline-row"><span class="pipeline-label">${esc(row.stage)}</span><div class="progress-track"><div class="progress-bar" style="width:${Math.max(4, row.amount / maxPipeline * 100)}%"></div></div><span class="pipeline-meta"><strong>${formatMoney(row.amount)}</strong>${row.count} deal${row.count === 1 ? "" : "s"}</span></div>`).join("") : `<p class="loading">No pipeline records yet.</p>`}</div></div></section>
        <section class="card"><div class="card-head"><div class="card-head-copy"><h2>Recent activity</h2><small>Latest updates from the team</small></div><button class="card-head-link" data-go="/activities">View all ↗</button></div><div class="card-body"><div class="activity-list">${data.recent_activity.length ? data.recent_activity.map(activityItem).join("") : emptyState("✓", "No activity yet", "Log a call, task, or meeting to start your timeline.")}</div></div></section>
      </div>
      <div class="dashboard-column">
        <section class="card"><div class="card-head"><div class="card-head-copy"><h2>Lead funnel</h2><small>Current lead distribution</small></div><button class="card-head-link" data-go="/leads">View leads ↗</button></div><div class="card-body"><div class="funnel">${data.lead_funnel.length ? data.lead_funnel.map((row) => `<div class="funnel-row"><span>${esc(row.status)}</span><div class="funnel-bar"><i style="width:${Math.max(8, row.count / maxLeads * 100)}%"></i></div><b>${row.count}</b></div>`).join("") : `<p class="loading">No lead records yet.</p>`}</div></div></section>
        <section class="card"><div class="card-head"><div class="card-head-copy"><h2>Quick actions</h2><small>Keep your workspace up to date</small></div></div><div class="card-body"><div class="quick-actions"><button class="quick-action" data-create="leads"><span>✦</span>Add lead</button><button class="quick-action" data-create="contacts"><span>◎</span>Add contact</button><button class="quick-action" data-create="accounts"><span>▣</span>Add account</button><button class="quick-action" data-create="deals"><span>◇</span>Add deal</button><button class="quick-action" data-create="activities"><span>✓</span>Log activity</button><button class="quick-action" data-go="/settings/general"><span>⚙</span>Open settings</button></div></div></section>
      </div>
    </div>`;
}

function performanceTable(rows) {
  if (!rows.length) return emptyState("◎", "No active salespeople", "Add active users and targets to calculate performance.");
  return `<div class="table-wrap"><table class="data-table performance-table"><thead><tr><th>Salesperson</th><th>Target</th><th>Achieved</th><th>Achievement</th><th>Conversions</th><th>Incentive</th></tr></thead><tbody>${rows.map((row) => `<tr><td><strong>${esc(row.name)}</strong><span class="sub-cell">${esc(row.role)}${row.target_configured ? "" : " · target missing"}</span></td><td>${formatMoney(row.target)}</td><td>${formatMoney(row.achieved)}</td><td><span class="achievement-meter"><i style="width:${Math.min(Number(row.achievement_percent || 0), 100)}%"></i></span><strong>${Number(row.achievement_percent || 0).toFixed(1)}%</strong></td><td>${row.conversions}</td><td>${formatMoney(row.incentive)}</td></tr>`).join("")}</tbody></table></div>`;
}

function attentionQueue(attention) {
  const leads = attention.stuck_leads || [];
  const quotes = attention.quotes_needing_follow_up || [];
  const items = [
    ...leads.map((item) => `<button class="related-item" data-go="/leads/${item.id}"><span class="related-dot">!</span><span class="related-main"><strong>${esc(item.name)}</strong><small>Lead stuck at ${esc(item.status)}${item.next_follow_up ? ` · follow-up ${formatDate(item.next_follow_up)}` : ""}</small></span><span>›</span></button>`),
    ...quotes.map((item) => `<button class="related-item" data-go="/quotes"><span class="related-dot">₹</span><span class="related-main"><strong>${esc(item.name)}</strong><small>${esc(item.status)}${item.valid_until ? ` · valid until ${formatDate(item.valid_until)}` : " · no expiry date"}</small></span><span>›</span></button>`),
  ];
  return items.length ? items.join("") : emptyState("✓", "Nothing urgent", "No stale leads or quotations need immediate follow-up.");
}

function activityItem(item) {
  const rawKind = String(item.activity_type || "task").toLowerCase();
  const kind = ["call", "meeting"].includes(rawKind) ? rawKind : "task";
  const icon = kind === "call" ? "⌕" : kind === "meeting" ? "◷" : "✓";
  return `<div class="activity-item"><span class="activity-icon ${kind}">${icon}</span><div class="activity-copy"><strong>${esc(item.subject)}</strong><small>${esc(item.related_label || "Unlinked record")} · ${esc(titleCase(item.status))}</small></div><span class="activity-time">${formatDateTime(item.due_at)}</span></div>`;
}

function bindDashboard() {
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create)));
  $$('[data-go]').forEach((button) => button.addEventListener("click", () => navigate(button.dataset.go)));
}

async function moduleView(resource) {
  const config = MODULES[resource];
  const current = state.moduleState[resource] || { search: "", status: "", owner_id: "", sort: "created_desc", min_amount: "", max_amount: "", close_from: "", close_to: "", offset: 0, view: resource === "deals" ? "list" : "list", selectedIds: [] };
  state.moduleState[resource] = current;
  const kanban = resource === "deals" && current.view === "kanban";
  const params = new URLSearchParams({ limit: kanban ? "100" : "25", offset: kanban ? "0" : String(current.offset) });
  if (current.search) params.set("search", current.search);
  if (current.status) params.set("status", current.status);
  if (current.owner_id) params.set("owner_id", current.owner_id);
  if (current.sort) params.set("sort", current.sort);
  if (current.min_amount) params.set("min_amount", current.min_amount);
  if (current.max_amount) params.set("max_amount", current.max_amount);
  if (current.close_from) params.set("close_from", current.close_from);
  if (current.close_to) params.set("close_to", current.close_to);
  const data = await api(`/api/${resource}?${params}`);
  const actions = `<button class="button button-primary" data-create="${resource}"><span class="button-icon">＋</span>Add ${config.singular.toLowerCase()}</button>`;
  const viewToggle = resource === "deals" ? `<div class="view-toggle"><button class="${current.view === "list" ? "active" : ""}" data-toggle-view="list">List</button><button class="${current.view === "kanban" ? "active" : ""}" data-toggle-view="kanban">Pipeline</button></div>` : "";
  return `${pageHeader("Workspace / " + config.label, config.label, config.description, `${viewToggle}${actions}`)}
    <div class="module-toolbar"><label class="toolbar-search"><span>⌕</span><input data-module-search="${resource}" value="${esc(current.search)}" placeholder="${esc(config.search)}" /></label>${config.status.length ? `<select class="filter-select" data-module-status="${resource}"><option value="">All statuses</option>${config.status.map((option) => `<option ${current.status === option ? "selected" : ""}>${esc(option)}</option>`).join("")}</select>` : ""}<select class="filter-select" data-module-owner="${resource}"><option value="">All owners</option>${(state.meta?.users || []).map((user) => `<option value="${user.id}" ${String(current.owner_id) === String(user.id) ? "selected" : ""}>${esc(user.name)}</option>`).join("")}</select><select class="filter-select" data-module-sort="${resource}"><option value="created_desc" ${current.sort === "created_desc" ? "selected" : ""}>Recently added</option><option value="name_asc" ${current.sort === "name_asc" ? "selected" : ""}>Name A–Z</option>${resource === "deals" ? `<option value="amount_desc" ${current.sort === "amount_desc" ? "selected" : ""}>Amount high–low</option><option value="close_asc" ${current.sort === "close_asc" ? "selected" : ""}>Close date soonest</option>` : ""}${resource === "leads" ? `<option value="score_desc" ${current.sort === "score_desc" ? "selected" : ""}>Lead score high–low</option>` : ""}</select>${resource === "deals" ? `<input class="field-input" style="width:105px" data-deal-filter="min_amount" type="number" placeholder="Min amount" value="${esc(current.min_amount)}" /><input class="field-input" style="width:105px" data-deal-filter="max_amount" type="number" placeholder="Max amount" value="${esc(current.max_amount)}" /><input class="field-input" style="width:140px" data-deal-filter="close_from" type="date" value="${esc(current.close_from)}" /><input class="field-input" style="width:140px" data-deal-filter="close_to" type="date" value="${esc(current.close_to)}" />` : ""}<button class="button button-ghost button-small" data-clear-filters="${resource}">Clear filters</button>${resource === "leads" ? `<button class="button button-ghost button-small" data-bulk-archive="leads" ${current.selectedIds.length ? "" : "disabled"}>Archive selected${current.selectedIds.length ? ` (${current.selectedIds.length})` : ""}</button>` : ""}<span style="margin-left:auto;color:var(--text-faint);font-size:11px">${data.total} record${data.total === 1 ? "" : "s"}</span></div>
    ${resource === "deals" && current.view === "kanban" ? kanbanView(data.items) : tableView(resource, data)}
    ${resource === "deals" && current.view === "kanban" ? "" : pagination(resource, data)}`;
}

async function activityTypeView(type) {
  const resource = "activities";
  const current = state.moduleState[resource] || { search: "", status: "", owner_id: "", sort: "created_desc", offset: 0, selectedIds: [] };
  state.moduleState[resource] = current;
  const params = new URLSearchParams({ limit: "25", offset: String(current.offset), activity_type: type });
  if (current.search) params.set("search", current.search);
  if (current.status) params.set("status", current.status);
  if (current.owner_id) params.set("owner_id", current.owner_id);
  if (current.sort) params.set("sort", current.sort);
  const data = await api(`/api/activities?${params}`);
  return `${pageHeader("Activities", `${type}s`, `Manage ${type.toLowerCase()} records, ownership, due dates and related CRM context.`, `<button class="button button-primary" data-create="activities" data-activity-type="${type}">+ Add ${type.toLowerCase()}</button>`)}
    <div class="module-toolbar"><label class="toolbar-search"><span>?</span><input data-module-search="activities" value="${esc(current.search)}" placeholder="Search ${type.toLowerCase()}s..." /></label><select class="filter-select" data-module-status="activities"><option value="">All statuses</option><option ${current.status === "Open" ? "selected" : ""}>Open</option><option ${current.status === "Completed" ? "selected" : ""}>Completed</option></select><select class="filter-select" data-module-owner="activities"><option value="">All owners</option>${(state.meta?.users || []).map((user) => `<option value="${user.id}" ${String(current.owner_id) === String(user.id) ? "selected" : ""}>${esc(user.name)}</option>`).join("")}</select><select class="filter-select" data-module-sort="activities"><option value="created_desc">Recently added</option><option value="name_asc">Subject A-Z</option></select><span style="margin-left:auto;color:var(--text-faint);font-size:11px">${data.total} record${data.total === 1 ? "" : "s"}</span></div>
    ${tableView(resource, data)}${pagination(resource, data)}`;
}

function platformState(resource) {
  if (!state.moduleState[`platform:${resource}`]) state.moduleState[`platform:${resource}`] = { search: "", status: "", owner_id: "", sort: "updated_desc", offset: 0 };
  return state.moduleState[`platform:${resource}`];
}

function platformTable(resource, data) {
  const config = state.platformCatalog.resources[resource];
  if (!data.items.length) return `<section class="card">${emptyState("+", `No ${config.label.toLowerCase()} found`, "Create a record or adjust the current filters.", `<button class="button button-primary" data-platform-create="${resource}">Add ${config.singular.toLowerCase()}</button>`)}</section>`;
  const visible = (config.fields || []).filter((item) => !["textarea", "json", "file"].includes(item.type)).slice(0, 4);
  return `<section class="card table-card"><div class="table-wrap"><table class="data-table"><thead><tr>${visible.map((field) => `<th>${esc(field.label)}</th>`).join("")}<th>Owner</th><th>Updated</th><th></th></tr></thead><tbody>${data.items.map((row) => `<tr>${visible.map((field, index) => `<td class="${index === 0 ? "platform-cell" : ""}">${index === 0 ? `<strong>${esc(row[field.key] ?? row.name ?? "-")}</strong><span class="sub-cell">#${row.id}</span>` : field.type === "number" && ["amount", "budget", "target", "target_amount", "committed", "best_case", "expected_revenue"].includes(field.key) ? formatMoney(row[field.key]) : field.type === "date" ? formatDate(row[field.key]) : field.key === "status" ? badge(row[field.key]) : platformDisplay(field, row[field.key])}</td>`).join("")}<td>${esc(row.owner_name || "Unassigned")}</td><td>${formatDateTime(row.updated_at)}</td><td><div class="table-actions"><button class="table-action" title="Edit" data-platform-edit="${resource}" data-id="${row.id}">Edit</button><button class="table-action" title="Archive" data-platform-delete="${resource}" data-id="${row.id}">Archive</button></div></td></tr>`).join("")}</tbody></table></div></section>`;
}

function platformDisplay(field, value) {
  const type = String(field.type || "");
  if (type === "account" || type === "contact" || type === "lead" || type === "deal") return esc(lookupName(`${type}s`, value));
  if (type === "user") return esc((state.meta?.users || []).find((item) => Number(item.id) === Number(value))?.name || (value ? `#${value}` : "-"));
  if (type.startsWith("platform:")) {
    const resource = type.split(":")[1];
    return esc((state.platformLookups[resource] || []).find((item) => Number(item.id) === Number(value))?.name || (value ? `#${value}` : "-"));
  }
  return esc(value ?? "-");
}

async function platformPanel(resource, compact = false) {
  const config = state.platformCatalog.resources[resource];
  if (!config) return `<section class="card">${emptyState("!", "Configuration view unavailable", "This setup surface is not registered in the platform catalog.")}</section>`;
  const current = platformState(resource);
  const params = new URLSearchParams({ limit: compact ? "100" : "25", offset: compact ? "0" : String(current.offset), sort: current.sort });
  if (current.search) params.set("search", current.search);
  if (current.status) params.set("status", current.status);
  if (current.owner_id) params.set("owner_id", current.owner_id);
  const data = await api(`/api/platform/${resource}?${params}`);
  const toolbar = `<div class="module-toolbar"><label class="toolbar-search"><span>?</span><input data-platform-search="${resource}" value="${esc(current.search)}" placeholder="Search ${esc(config.label.toLowerCase())}..." /></label><select class="filter-select" data-platform-status="${resource}"><option value="">All statuses</option><option ${current.status === "Active" ? "selected" : ""}>Active</option><option ${current.status === "Inactive" ? "selected" : ""}>Inactive</option></select><select class="filter-select" data-platform-owner="${resource}"><option value="">All owners</option>${(state.meta?.users || []).map((user) => `<option value="${user.id}" ${String(current.owner_id) === String(user.id) ? "selected" : ""}>${esc(user.name)}</option>`).join("")}</select><select class="filter-select" data-platform-sort="${resource}"><option value="updated_desc">Recently updated</option><option value="name_asc" ${current.sort === "name_asc" ? "selected" : ""}>Name A-Z</option><option value="created_desc" ${current.sort === "created_desc" ? "selected" : ""}>Recently created</option></select><a class="button button-ghost button-small" href="/api/export/${resource}.csv" download>Export CSV</a><span style="margin-left:auto;color:var(--text-faint);font-size:11px">${data.total} record${data.total === 1 ? "" : "s"}</span></div>`;
  return `${toolbar}${platformTable(resource, data)}${compact ? "" : pagination(`platform:${resource}`, data)}`;
}

async function platformModuleView(resource) {
  const config = state.platformCatalog.resources[resource];
  await Promise.all((config.fields || []).filter((field) => String(field.type || "").startsWith("platform:")).map((field) => ensurePlatformLookup(field.type.split(":")[1])));
  return `${pageHeader(config.group || "Workspace", config.label, config.description, `<button class="button button-primary" data-platform-create="${resource}">+ Add ${config.singular.toLowerCase()}</button>`)}${await platformPanel(resource)}`;
}

function setupDirectory(active) {
  return `<section class="card settings-nav">${Object.entries(state.platformCatalog.setup_navigation || {}).map(([group, links]) => `<div><span class="eyebrow" style="display:block;padding:12px 12px 5px">${esc(group)}</span>${links.map(([resource, label]) => `<a href="/setup/${resource}" class="${active === resource ? "active" : ""}">${esc(label)}</a>`).join("")}</div>`).join("")}</section>`;
}

async function auditView() {
  const data = await api("/api/audit?limit=100");
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Audit history</h2><p>Immutable application events for record, configuration and automation changes.</p></div>${data.items.length ? data.items.map((item) => `<div class="audit-row"><small>${formatDateTime(item.occurred_at)}</small>${badge(titleCase(item.action))}<div><strong>${esc(item.summary)}</strong><small>${esc(titleCase(item.resource))}${item.record_id ? ` · #${item.record_id}` : ""}</small></div></div>`).join("") : emptyState("A", "No audit events yet", "Changes made after this upgrade will appear here.")}</section>`;
}

async function recycleBinView() {
  const data = await api("/api/administration/recycle-bin");
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Recycle Bin</h2><p>Restore archived CRM and setup records.</p></div>${data.items.length ? data.items.map((item) => `<div class="rule-row"><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(titleCase(item.resource))} · #${item.id}</small></div><button class="button button-small button-ghost" data-restore-resource="${item.resource}" data-id="${item.id}">Restore</button></div>`).join("") : emptyState("R", "Recycle bin is empty", "Archived records will appear here.")}</section>`;
}

function importView() {
  const choices = Object.entries(state.platformCatalog.resources).filter(([, config]) => !["Security", "Customization", "Automation", "Templates", "Developer", "General"].includes(config.group));
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Import</h2><p>Import UTF-8 CSV files into expanded CRM modules. Required column names match the field API names.</p></div><form data-import-form><div class="form-grid"><div class="field"><label>Module</label><select class="field-select" name="resource">${choices.map(([key, config]) => `<option value="${key}">${esc(config.label)}</option>`).join("")}</select></div><div class="field"><label>CSV file</label><input class="field-input" name="file" type="file" accept=".csv,text/csv" required /></div></div><div class="form-actions"><button class="button button-primary" type="submit">Import records</button></div></form></section>`;
}

function exportView() {
  const resources = [...Object.keys(MODULES), ...Object.keys(state.platformCatalog.resources)];
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Export</h2><p>Download active records as UTF-8 CSV for analysis or backup.</p></div><div class="setup-directory">${resources.map((resource) => `<a class="button button-ghost" href="/api/export/${resource}.csv" download>${esc(MODULES[resource]?.label || state.platformCatalog.resources[resource]?.label || titleCase(resource))}</a>`).join("")}</div></section>`;
}

function duplicateView() {
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Duplicate Management</h2><p>Scan platform modules by normalized name, or leads, contacts and users by email.</p></div><form data-duplicate-form><div class="form-grid"><div class="field"><label>Module</label><select class="field-select" name="resource"><option>leads</option><option>contacts</option><option>users</option>${Object.keys(state.platformCatalog.resources).map((key) => `<option>${key}</option>`).join("")}</select></div></div><div class="form-actions"><button class="button button-primary" type="submit">Scan for duplicates</button></div></form><div data-duplicate-results></div></section>`;
}

async function setupView(resource) {
  let content;
  if (resource === "personal_settings" || resource === "users") content = await profileUsersView();
  else if (resource === "approval_processes") content = await approvalSettingsView();
  else if (resource === "blueprints") content = await blueprintSettingsView();
  else if (resource === "audit_log") content = await auditView();
  else if (resource === "recycle_bin") content = await recycleBinView();
  else if (resource === "import") content = importView();
  else if (resource === "export") content = exportView();
  else if (resource === "duplicates") content = duplicateView();
  else if (state.platformCatalog.resources[resource]) content = `<section class="foundation-note">This is a working foundation: records persist, validate, filter, sort, export, audit and recycle. External delivery, identity-provider enforcement and background scheduling require deployment-specific workers or integrations.</section>${await platformPanel(resource, true)}`;
  else content = `<section class="card">${emptyState("!", "Unknown setup page", "Choose a setup item from the directory.")}</section>`;
  return `${pageHeader("Setup", titleCase(resource), "Configure Yash CRM without changing its source code.")}<div class="settings-layout">${setupDirectory(resource)}<div class="settings-content">${content}</div></div>`;
}

function tableView(resource, data) {
  const config = MODULES[resource];
  if (!data.items.length) return `<section class="card">${emptyState(config.icon, `No ${config.label.toLowerCase()} found`, "Try changing your filters or create a new record.", `<button class="button button-primary" data-create="${resource}">Add ${config.singular.toLowerCase()}</button>`)}</section>`;
  const selectionHeader = resource === "leads" ? `<th><input type="checkbox" data-select-all="leads" /></th>` : "";
  return `<section class="card table-card"><div class="table-wrap"><table class="data-table"><thead><tr>${selectionHeader}${config.columns.map((column) => `<th>${column.label}</th>`).join("")}<th></th></tr></thead><tbody>${data.items.map((row) => `<tr>${resource === "leads" ? `<td><input type="checkbox" data-select-record="leads" data-id="${row.id}" ${state.moduleState[resource].selectedIds.includes(row.id) ? "checked" : ""} /></td>` : ""}${config.columns.map((column) => `<td class="${column.key === "name" ? "primary-cell" : ""}">${column.cell ? column.cell(row) : esc(row[column.key] ?? "—")}</td>`).join("")}<td><div class="table-actions">${resource === "activities" && row.status !== "Completed" ? `<button class="table-action" title="Mark complete" data-complete-activity="${row.id}">✓</button>` : ""}<button class="table-action" title="Edit" data-edit-record="${resource}" data-id="${row.id}">✎</button><button class="table-action" title="Archive" data-delete-record="${resource}" data-id="${row.id}">⌫</button></div></td></tr>`).join("")}</tbody></table></div></section>`;
}

function kanbanView(items) {
  const stages = MODULES.deals.status;
  return `<div class="kanban-grid">${stages.map((stage) => { const deals = items.filter((item) => item.stage === stage); return `<section class="kanban-column"><div class="kanban-head"><strong>${esc(stage)}</strong><span>${deals.length}</span></div>${deals.map((deal) => `<article class="deal-card" data-open-record="deals" data-id="${deal.id}"><h3>${esc(deal.name)}</h3><p>${esc(lookupName("accounts", deal.account_id))}</p><div class="deal-card-foot"><strong>${formatMoney(deal.amount)}</strong><span>${deal.probability || 0}%</span></div></article>`).join("") || `<p style="font-size:10px;color:var(--text-faint);padding:10px 2px">No deals here</p>`}</section>`; }).join("")}</div>`;
}

function pagination(resource, data) {
  const start = data.total ? data.offset + 1 : 0;
  const end = Math.min(data.offset + data.items.length, data.total);
  return `<div class="pagination"><span>Showing ${start}–${end} of ${data.total}</span><div class="pagination-actions"><button data-page="prev" data-resource="${resource}" ${data.offset === 0 ? "disabled" : ""}>←</button><button data-page="next" data-resource="${resource}" ${end >= data.total ? "disabled" : ""}>→</button></div></div>`;
}

function dataIds(resource) {
  return $$(`[data-select-record="${resource}"]`).map((input) => Number(input.dataset.id));
}

async function bulkArchiveLeads(current) {
  if (!current.selectedIds.length) return;
  const confirmed = await confirmAction("Archive selected leads?", `This will remove ${current.selectedIds.length} selected lead${current.selectedIds.length === 1 ? "" : "s"} from the active list.`, "Archive leads");
  if (!confirmed) return;
  try {
    await api("/api/leads/bulk-archive", { method: "POST", body: JSON.stringify({ related_id: current.selectedIds }) });
    current.selectedIds = [];
    toast("Leads archived", "The selected leads are no longer in the active list.");
    await renderRoute();
  } catch (error) { toast("Could not archive leads", error.message, "error"); }
}

function bindModule(resource) {
  const current = state.moduleState[resource];
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create, null, button.dataset.activityType ? { activity_type: button.dataset.activityType } : {})));
  $$('[data-open-record]').forEach((button) => button.addEventListener("click", () => navigate(pathFor(button.dataset.openRecord, button.dataset.id))));
  $$('[data-edit-record]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.editRecord, Number(button.dataset.id))));
  $$('[data-delete-record]').forEach((button) => button.addEventListener("click", () => deleteRecord(button.dataset.deleteRecord, Number(button.dataset.id))));
  const search = $("[data-module-search]");
  let searchTimer;
  search?.addEventListener("input", (event) => { clearTimeout(searchTimer); current.search = event.target.value; current.offset = 0; searchTimer = setTimeout(renderRoute, 260); });
  $("[data-module-status]")?.addEventListener("change", (event) => { current.status = event.target.value; current.offset = 0; renderRoute(); });
  $("[data-module-owner]")?.addEventListener("change", (event) => { current.owner_id = event.target.value; current.offset = 0; renderRoute(); });
  $("[data-module-sort]")?.addEventListener("change", (event) => { current.sort = event.target.value; current.offset = 0; renderRoute(); });
  $$('[data-deal-filter]').forEach((input) => input.addEventListener("change", (event) => { current[event.target.dataset.dealFilter] = event.target.value; current.offset = 0; renderRoute(); }));
  $("[data-clear-filters]")?.addEventListener("click", () => { Object.assign(current, { search: "", status: "", owner_id: "", sort: "created_desc", min_amount: "", max_amount: "", close_from: "", close_to: "", offset: 0 }); renderRoute(); });
  $$('[data-select-record]').forEach((input) => input.addEventListener("change", (event) => { const id = Number(event.target.dataset.id); current.selectedIds = event.target.checked ? [...new Set([...current.selectedIds, id])] : current.selectedIds.filter((selected) => selected !== id); renderRoute(); }));
  $("[data-select-all]")?.addEventListener("change", (event) => { current.selectedIds = event.target.checked ? [...new Set([...current.selectedIds, ...dataIds(resource)])] : current.selectedIds.filter((id) => !dataIds(resource).includes(id)); renderRoute(); });
  $("[data-bulk-archive]")?.addEventListener("click", () => bulkArchiveLeads(current));
  $$('[data-toggle-view]').forEach((button) => button.addEventListener("click", () => { current.view = button.dataset.toggleView; renderRoute(); }));
  $$('[data-complete-activity]').forEach((button) => button.addEventListener("click", async () => { try { await api(`/api/activities/${button.dataset.completeActivity}`, { method: "PATCH", body: JSON.stringify({ status: "Completed" }) }); toast("Activity completed", "Nice work — it has been marked as done."); await renderRoute(); } catch (error) { toast("Could not update activity", error.message, "error"); } }));
  $$('[data-page]').forEach((button) => button.addEventListener("click", () => { current.offset += button.dataset.page === "next" ? 25 : -25; renderRoute(); }));
}

async function detailView(resource, id) {
  const [record, related] = await Promise.all([api(`/api/${resource}/${id}`), api(`/api/${resource}/${id}/related`)]);
  if (resource === "leads") related.journey = await api(`/api/journey/leads/${id}`);
  const config = MODULES[resource];
  const title = resource === "contacts" ? record.full_name : record.name || record.subject;
  const secondary = resource === "leads" ? record.company || record.email : resource === "contacts" ? record.email || record.job_title : resource === "accounts" ? record.website || record.industry : resource === "deals" ? `${record.stage} · ${formatMoney(record.amount)}` : resource === "products" ? `${record.category || "Product"} · ${formatMoney(record.unit_price)}` : `${titleCase(record.activity_type)} · ${formatDateTime(record.due_at)}`;
  const details = detailFields(resource, record);
  return `${pageHeader(config.label, title, secondary || "Record detail", `${resource === "leads" ? `<button class="button button-ghost" data-go="/ai?lead=${id}">✦ Analyze with AI</button>` : ""}<button class="button button-ghost" data-go="/${resource}">← Back to ${config.label.toLowerCase()}</button><button class="button button-primary" data-edit-record="${resource}" data-id="${id}">Edit ${config.singular.toLowerCase()}</button>`)}
    <div class="detail-layout"><div class="dashboard-column"><section class="card detail-summary"><div class="detail-title-row"><span class="detail-avatar">${initials(title)}</span><div class="detail-title-copy"><span class="eyebrow">${esc(config.singular)}</span><h2>${esc(title)}</h2><p>${esc(secondary || "No summary available")}</p></div><div class="detail-actions">${resource === "leads" && record.status !== "Converted" && !record.converted_contact_id ? `<button class="button button-small button-ghost" data-convert-lead="${id}">Convert</button>` : ""}<button class="button button-small button-ghost" data-delete-record="${resource}" data-id="${id}">Archive</button></div></div><div class="detail-meta-grid">${details.map((item) => `<div><span class="meta-label">${esc(item.label)}</span><span class="meta-value">${item.html || esc(item.value || "—")}</span></div>`).join("")}</div>${record.notes ? `<div class="notes-box"><h3>Notes</h3><p>${esc(record.notes)}</p></div>` : ""}</section>${resource === "deals" ? `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>Stage progress</h2><small>Move the deal forward as the conversation evolves.</small></div></div><div class="card-body">${dealProgress(record)}</div></section>` : ""}</div><div class="detail-side"><section class="card"><div class="card-head"><div class="card-head-copy"><h2>Related records</h2><small>Connected context around this ${config.singular.toLowerCase()}.</small></div><button class="card-head-link" data-create="activities">＋ Activity</button></div><div class="card-body">${relatedContent(resource, related)}</div></section><section class="card"><div class="card-head"><div class="card-head-copy"><h2>Timeline</h2><small>Latest activity updates</small></div></div><div class="card-body"><div class="activity-list">${related.activities?.length ? related.activities.map(activityItem).join("") : `<p style="color:var(--text-faint);font-size:11px">No linked activity yet.</p>`}</div></div></section></div></div>`;
}

function detailFields(resource, record) {
  const owner = record.owner_name || "Unassigned";
  if (resource === "leads") return [{ label: "Status", html: badge(record.status) }, { label: "Owner", value: owner }, { label: "Lead score", value: `${record.lead_score || 0}/100` }, { label: "Email", value: record.email }, { label: "Phone", value: record.phone }, { label: "Follow-up", value: formatDate(record.next_follow_up) }];
  if (resource === "contacts") return [{ label: "Email", value: record.email }, { label: "Phone", value: record.phone }, { label: "Job title", value: record.job_title }, { label: "Department", value: record.department }, { label: "Account", value: lookupName("accounts", record.account_id) }, { label: "Owner", value: owner }];
  if (resource === "accounts") return [{ label: "Type", value: record.type }, { label: "Industry", value: record.industry }, { label: "Employees", value: record.employees }, { label: "Website", value: record.website }, { label: "Location", value: [record.billing_city, record.billing_country].filter(Boolean).join(", ") }, { label: "Owner", value: owner }];
  if (resource === "deals") return [{ label: "Stage", html: badge(record.stage) }, { label: "Amount", value: formatMoney(record.amount) }, { label: "Probability", value: `${record.probability || 0}%` }, { label: "Account", value: lookupName("accounts", record.account_id) }, { label: "Close date", value: formatDate(record.expected_close_date) }, { label: "Owner", value: owner }];
  if (resource === "products") return [{ label: "SKU", value: record.sku }, { label: "Category", value: record.category }, { label: "Unit price", value: formatMoney(record.unit_price) }, { label: "Stock", value: record.stock_quantity }, { label: "Status", html: badge(record.status) }, { label: "Owner", value: owner }];
  return [{ label: "Type", value: titleCase(record.activity_type) }, { label: "Status", html: badge(record.status) }, { label: "Priority", html: badge(record.priority) }, { label: "Starts", value: formatDateTime(record.start_at) }, { label: "Due", value: formatDateTime(record.due_at) }, { label: "Owner", value: owner }, { label: "Related to", value: record.related_label }];
}

function relatedContent(resource, related) {
  const sections = [];
  const addSection = (key, label, icon, rows, createResource) => {
    sections.push(`<div class="related-group"><div class="related-group-head"><strong>${label}</strong><button class="card-head-link" data-create="${createResource}">＋ Add</button></div>${rows.length ? rows.join("") : `<p class="related-empty">No ${label.toLowerCase()} yet.</p>`}</div>`);
  };
  if (related.journey) {
    const stages = related.journey.stages || [];
    sections.push(`<div class="related-group journey-group"><div class="related-group-head"><strong>Customer journey</strong><span class="eyebrow">Lead to cash</span></div><div class="journey-track">${stages.map((stage) => `<span class="journey-stage ${stage.complete ? "complete" : ""}"><i>${stage.complete ? "✓" : stage.count}</i><b>${esc(stage.label)}</b></span>`).join("")}</div><div class="journey-actions"><button class="button button-small button-ghost" data-platform-create="site_visits" data-lead-id="${related.journey.lead.id}">+ Site visit</button>${related.journey.lead.converted_deal_id ? `<button class="button button-small button-ghost" data-platform-create="quotes" data-deal-id="${related.journey.lead.converted_deal_id}">+ Quotation</button>` : ""}</div></div>`);
  }
  addSection("activities", "Open activities", "✓", (related.activities || []).filter((item) => item.status !== "Completed").map((item) => relatedRow("✓", item.subject, `${titleCase(item.activity_type)} · ${formatDateTime(item.due_at)}`, "activities", item.id)), "activities");
  addSection("notes", "Notes", "▤", (related.notes || []).map((item) => relatedRow("▤", item.title, item.content || "Open note", "notes", item.id, false)), "notes");
  addSection("products", "Products", "□", (related.products || []).map((item) => relatedRow("□", item.name, `${formatMoney(item.unit_price)} · ${item.sku || "No SKU"}`, "products", item.id)), "products");
  addSection("attachments", "Attachments", "↗", (related.attachments || []).map((item) => relatedRow("↗", item.name, `${item.file_type || "File"} · ${item.file_size || "Size not set"}`, "attachments", item.id, false)), "attachments");
  addSection("emails", "Email", "@", (related.emails || []).map((item) => relatedRow("@", item.subject, `${item.status} · ${item.to_email || "No recipient"}`, "emails", item.id, false)), "emails");
  if (["accounts", "contacts", "leads", "deals"].includes(resource)) {
    if (related.accounts?.length) addSection("accounts", "Accounts", "▣", related.accounts.map((item) => relatedRow("▣", item.name, item.industry || item.type, "accounts", item.id)), "accounts");
    if (related.contacts?.length) addSection("contacts", "Contacts", "◎", related.contacts.map((item) => relatedRow("◎", item.full_name || `${item.first_name} ${item.last_name}`, item.job_title || item.email, "contacts", item.id)), "contacts");
    if (related.deals?.length) addSection("deals", "Deals", "◇", related.deals.map((item) => relatedRow("◇", item.name, `${formatMoney(item.amount)} · ${item.stage}`, "deals", item.id)), "deals");
  }
  return sections.join("");
}

function relatedRow(icon, title, meta, resource, id, navigable = true) { const action = navigable && MODULES[resource] ? `data-open-record="${resource}"` : `data-edit-record="${resource}"`; return `<button class="related-item" ${action} data-id="${id}"><span class="related-dot">${icon}</span><span class="related-main"><strong>${esc(title)}</strong><small>${esc(meta || "")}</small></span><span style="color:var(--text-faint)">${navigable && MODULES[resource] ? "›" : "✎"}</span></button>`; }

function dealProgress(record) {
  const stages = MODULES.deals.status;
  return `<div class="blueprint-flow">${stages.map((stage, index) => `<div class="blueprint-stage" style="${stage === record.stage ? "border-color:#aaa6ff;background:var(--surface-indigo)" : ""}"><strong>${esc(stage)}</strong><small>${stage === record.stage ? "Current stage" : index < stages.indexOf(record.stage) ? "Completed" : "Upcoming"}</small></div>${index < stages.length - 1 ? `<span class="blueprint-arrow">→</span>` : ""}`).join("")}</div><div style="display:flex;gap:8px;flex-wrap:wrap">${stages.filter((stage) => stage !== record.stage).map((stage) => `<button class="button button-small button-ghost" data-stage-update="${record.id}" data-stage="${esc(stage)}">Move to ${esc(stage)}</button>`).join("")}</div>`;
}

function bindDetail(resource, id) {
  $$('[data-go]').forEach((button) => button.addEventListener("click", () => navigate(button.dataset.go)));
  $$('[data-edit-record]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.editRecord, Number(button.dataset.id))));
  $$('[data-delete-record]').forEach((button) => button.addEventListener("click", () => deleteRecord(button.dataset.deleteRecord, Number(button.dataset.id))));
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create, null, { related_type: resource, related_id: id })));
  $$('[data-platform-create]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate, null, { lead_id: button.dataset.leadId ? Number(button.dataset.leadId) : null, deal_id: button.dataset.dealId ? Number(button.dataset.dealId) : null })));
  $$('[data-open-record]').forEach((button) => button.addEventListener("click", () => navigate(pathFor(button.dataset.openRecord, button.dataset.id))));
  $("[data-convert-lead]")?.addEventListener("click", () => openConvertModal(Number(id)));
  $$('[data-stage-update]').forEach((button) => button.addEventListener("click", async () => { try { await api(`/api/deals/${button.dataset.stageUpdate}`, { method: "PATCH", body: JSON.stringify({ stage: button.dataset.stage }) }); toast("Deal updated", `Moved to ${button.dataset.stage}`); await renderRoute(); } catch (error) { toast("Could not update deal", error.message, "error"); } }));
}

function fieldHtml(field, value = "") {
  const type = field.type || "text";
  const id = `field-${field.key}`;
  const required = field.required ? "required" : "";
  const hint = field.hint ? `<small style="font-size:10px;color:var(--text-faint)">${esc(field.hint)}</small>` : "";
  let input = "";
  if (type === "file") {
    input = `<input class="field-input" id="${id}" name="${field.key}" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg" ${required} />`;
  }
  else if (type === "textarea" || type === "json") {
    let rendered = value || "";
    if (type === "json" && typeof rendered !== "string") rendered = JSON.stringify(rendered ?? [], null, 2);
    if (["conditions", "steps", "stages", "transitions", "transition_requirements"].includes(field.key) && typeof rendered !== "string") rendered = JSON.stringify(rendered || [], null, 2);
    input = `<textarea class="field-textarea" id="${id}" name="${field.key}" ${type === "json" ? 'data-json="true"' : ""} ${required}>${esc(rendered)}</textarea>`;
  }
  else if (["select", "user", "account", "contact", "lead", "deal"].includes(type) || type.startsWith("platform:")) {
    let options = field.options || [];
    if (type === "user") options = (state.meta?.users || []).map((user) => ({ value: user.id, label: user.name }));
    if (type === "account") options = state.lookups.accounts.map((item) => ({ value: item.id, label: item.name }));
    if (type === "contact") options = state.lookups.contacts.map((item) => ({ value: item.id, label: item.full_name || `${item.first_name} ${item.last_name}` }));
    if (type === "lead") options = state.lookups.leads.map((item) => ({ value: item.id, label: `${item.name}${item.company ? ` · ${item.company}` : ""}` }));
    if (type === "deal") options = state.lookups.deals.map((item) => ({ value: item.id, label: `${item.name} · ${formatMoney(item.amount)}` }));
    if (type.startsWith("platform:")) options = (state.platformLookups[type.split(":")[1]] || []).map((item) => ({ value: item.id, label: item.name }));
    const normalized = options.map((option) => typeof option === "string" ? { value: option, label: option } : option);
    const numeric = type !== "select" ? 'data-numeric="true"' : "";
    input = `<select class="field-select" id="${id}" name="${field.key}" ${numeric} ${required}><option value="">Select ${esc(field.label.toLowerCase())}</option>${normalized.map((option) => `<option value="${esc(option.value)}" ${String(option.value) === String(value ?? "") ? "selected" : ""}>${esc(option.label)}</option>`).join("")}</select>`;
  } else {
    let rendered = value ?? "";
    if (type === "datetime-local" && rendered) rendered = String(rendered).slice(0, 16);
    if (type === "date" && rendered) rendered = String(rendered).slice(0, 10);
    if (field.key === "tags" && Array.isArray(rendered)) rendered = rendered.join(", ");
    if (["conditions", "steps", "stages", "transitions", "transition_requirements"].includes(field.key) && typeof rendered !== "string") rendered = JSON.stringify(rendered || [], null, 2);
    input = `<input class="field-input" id="${id}" name="${field.key}" type="${type}" value="${esc(rendered)}" ${type === "number" ? 'step="any" data-numeric="true"' : ""} ${required} />`;
  }
  return `<div class="field ${field.full ? "full" : ""}"><label for="${id}">${esc(field.label)}${field.required ? ' <span class="required">*</span>' : ""}</label>${input}${hint}</div>`;
}

async function openRecordModal(resource, id = null, preset = {}) {
  const config = MODULES[resource] || settingsResourceConfig(resource);
  if (!config) return;
  if (["contacts", "deals"].some((resourceName) => resource === resourceName) || config.fields.some((field) => ["account", "contact"].includes(field.type))) await ensureLookups();
  let record = { ...preset };
  if (id) record = await api(`/api/${resource}/${id}`);
  state.modal = { resource, id, preset };
  $("#modal-eyebrow").textContent = id ? `Edit ${config.singular}` : `New ${config.singular}`;
  $("#modal-title").textContent = id ? `Update ${config.singular.toLowerCase()}` : `Create ${config.singular.toLowerCase()}`;
  $("#modal-submit").textContent = id ? "Save changes" : `Create ${config.singular.toLowerCase()}`;
  $("#modal-body").innerHTML = `<div class="form-grid">${config.fields.map((field) => fieldHtml(field, record[field.key])).join("")}</div>`;
  $("#modal-backdrop").hidden = false;
  $("#modal-body input, #modal-body select, #modal-body textarea")?.focus();
}

async function openPlatformModal(resource, id = null, preset = {}) {
  const config = state.platformCatalog.resources[resource];
  if (!config) return;
  if ((config.fields || []).some((field) => ["account", "contact", "lead", "deal"].includes(field.type))) await ensureLookups();
  await Promise.all((config.fields || []).filter((field) => String(field.type || "").startsWith("platform:")).map((field) => ensurePlatformLookup(field.type.split(":")[1])));
  let record = { ...preset };
  if (id) record = await api(`/api/platform/${resource}/${id}`);
  state.modal = { resource, id, platform: true };
  $("#modal-eyebrow").textContent = id ? `Edit ${config.singular}` : `New ${config.singular}`;
  $("#modal-title").textContent = id ? `Update ${config.singular.toLowerCase()}` : `Create ${config.singular.toLowerCase()}`;
  $("#modal-submit").textContent = id ? "Save changes" : `Create ${config.singular.toLowerCase()}`;
  $("#modal-body").innerHTML = `<div class="form-grid">${config.fields.map((field) => fieldHtml(field, record[field.key])).join("")}${config.fields.some((field) => field.key === "owner_id") ? "" : fieldHtml({ key: "owner_id", label: "Owner", type: "user" }, record.owner_id)}</div>`;
  $("#modal-backdrop").hidden = false;
  $("#modal-body input, #modal-body select, #modal-body textarea")?.focus();
}

function settingsResourceConfig(resource) {
  if (resource === "users") return { label: "Users", singular: "User", fields: [{ key: "name", label: "Name", required: true }, { key: "email", label: "Email", type: "email", required: true }, { key: "role", label: "Role", type: "select", options: ["Administrator", "Sales manager", "Sales rep"] }, { key: "status", label: "Status", type: "select", options: ["Active", "Inactive"] }] };
  if (resource === "notes") return { label: "Notes", singular: "Note", fields: [{ key: "title", label: "Title", required: true }, { key: "content", label: "Note", type: "textarea", full: true }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" }] };
  if (resource === "attachments") return { label: "Attachments", singular: "Attachment", fields: [{ key: "name", label: "File name", required: true }, { key: "file_type", label: "File type" }, { key: "file_size", label: "File size" }, { key: "url", label: "File URL" }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" }] };
  if (resource === "emails") return { label: "Emails", singular: "Email", fields: [{ key: "subject", label: "Subject", required: true }, { key: "from_email", label: "From", type: "email" }, { key: "to_email", label: "To", type: "email" }, { key: "status", label: "Status", type: "select", options: ["Draft", "Sent", "Scheduled"] }, { key: "sent_at", label: "Sent at", type: "datetime-local" }, { key: "body", label: "Message", type: "textarea", full: true }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" }] };
  if (resource === "approval_processes") return { label: "Approval process", singular: "Approval rule", fields: [{ key: "name", label: "Rule name", required: true }, { key: "module", label: "Module", type: "select", options: ["Deals", "Leads", "Accounts"] }, { key: "trigger", label: "Trigger", required: true }, { key: "approver", label: "Approver", required: true }, { key: "status", label: "Status", type: "select", options: ["Active", "Inactive"] }, { key: "conditions", label: "Conditions (JSON)", type: "textarea", hint: "Example: [{\"field\":\"amount\",\"operator\":\">\",\"value\":\"100000\"}]", full: true }, { key: "steps", label: "Approval steps (JSON)", type: "textarea", hint: "Example: [{\"order\":1,\"approver\":\"Sales manager\"}]", full: true }] };
  if (resource === "blueprints") return { label: "Blueprint", singular: "Blueprint", fields: [{ key: "name", label: "Blueprint name", required: true }, { key: "module", label: "Module", type: "select", options: ["Deals", "Leads", "Accounts"] }, { key: "entry_criteria", label: "Entry criteria", type: "textarea", full: true }, { key: "stages", label: "Stages (JSON)", type: "textarea", hint: "Example: [{\"id\":\"qualification\",\"label\":\"Qualification\"}]", full: true }, { key: "transitions", label: "Transitions (JSON)", type: "textarea", hint: "Example: [{\"from\":\"Qualification\",\"to\":\"Proposal\",\"label\":\"Create proposal\"}]", full: true }, { key: "transition_requirements", label: "Transition requirements (JSON)", type: "textarea", hint: "Example: [{\"transition\":\"Create proposal\",\"required\":[\"amount\",\"close date\"]}]", full: true }, { key: "active", label: "Active", type: "select", options: ["true", "false"] }] };
  return null;
}

function readForm(form) {
  const data = {};
  $$('[name]', form).forEach((input) => {
    if (input.type === "file") return;
    let value = input.value;
    if (input.dataset.numeric === "true" || ["owner_id", "account_id", "contact_id", "deal_id", "related_id", "lead_score", "probability", "amount", "employees", "annual_revenue", "unit_price", "stock_quantity"].includes(input.name)) value = value ? Number(value) : null;
    else if (["tags"].includes(input.name)) value = value ? value.split(",").map((tag) => tag.trim()).filter(Boolean) : [];
    else if (input.dataset.json === "true" || ["conditions", "steps", "stages", "transitions", "transition_requirements"].includes(input.name)) {
      try { value = value ? JSON.parse(value) : []; } catch { throw new Error(`${titleCase(input.name)} must be valid JSON. Check the brackets and quotes.`); }
      if (input.dataset.json !== "true" && !Array.isArray(value)) throw new Error(`${titleCase(input.name)} must be a JSON list, like [ ... ].`);
    }
    else if (input.dataset.boolean === "true") value = input.classList.contains("on");
    else if (value === "") value = null;
    data[input.name] = value;
  });
  return data;
}

async function submitRecord(event) {
  event.preventDefault();
  if (!state.modal) return;
  if (state.modal.convert) return submitConvert(event.currentTarget);
  if (state.modal.platform) return submitPlatformRecord(event.currentTarget);
  const { resource, id } = state.modal;
  const singular = MODULES[resource]?.singular || settingsResourceConfig(resource)?.singular || "record";
  const submit = $("#modal-submit");
  try {
    const data = readForm(event.currentTarget);
    submit.disabled = true;
    await api(`/api/${resource}${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", body: JSON.stringify(data) });
    if (["accounts", "contacts"].includes(resource)) invalidateLookups();
    if (resource === "users") { await refreshMeta(); if (id && id === state.profile?.id) { state.profile = await api("/api/settings/profile"); applyProfile(); } }
    closeModal();
    toast(`${id ? "Updated" : "Created"} ${singular}`);
    await renderRoute();
  } catch (error) { toast("Could not save record", error.message, "error"); }
  finally { submit.disabled = false; }
}

async function submitPlatformRecord(form) {
  const { resource, id } = state.modal;
  const config = state.platformCatalog.resources[resource];
  const submit = $("#modal-submit");
  try {
    const data = readForm(form);
    submit.disabled = true;
    const upload = resource === "documents" ? form.querySelector('input[type="file"]')?.files?.[0] : null;
    if (upload) {
      if (id) throw new Error("Upload a new document as a separate record; existing file history remains unchanged.");
      const body = new FormData();
      body.append("file", upload);
      Object.entries(data).forEach(([key, value]) => { if (value !== null && value !== "") body.append(key, String(value)); });
      const response = await fetch("/api/documents/upload", { method: "POST", body });
      const raw = await response.text();
      let result = {}; try { result = raw ? JSON.parse(raw) : {}; } catch { result = {}; }
      if (!response.ok) throw new Error(result.detail || raw.slice(0, 180) || `Upload failed with HTTP ${response.status}`);
    } else {
      await api(`/api/platform/${resource}${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", body: JSON.stringify(data) });
    }
    invalidateLookups();
    closeModal();
    toast(`${id ? "Updated" : "Created"} ${config.singular}`);
    await renderRoute();
  } catch (error) { toast("Could not save record", error.message, "error"); }
  finally { submit.disabled = false; }
}

async function submitConvert(form) {
  const submit = $("#modal-submit");
  try {
    const data = readForm(form);
    data.create_deal = data.create_deal === "true";
    data.deal_amount = Number(data.deal_amount || 0);
    submit.disabled = true;
    await api(`/api/leads/${state.modal.id}/convert`, { method: "POST", body: JSON.stringify(data) });
    invalidateLookups();
    closeModal();
    toast("Lead converted", "The account, contact and deal are ready in your workspace.");
    await navigate("/leads");
  } catch (error) { toast("Could not convert lead", error.message, "error"); }
  finally { submit.disabled = false; }
}

function closeModal() { $("#modal-backdrop").hidden = true; state.modal = null; }

function closeConfirm(result) {
  if ($("#confirm-backdrop").hidden) return;
  $("#confirm-backdrop").hidden = true;
  const resolve = state.confirmResolve;
  state.confirmResolve = null;
  resolve?.(result);
}

function confirmAction(title, copy, actionLabel = "Continue") {
  $("#confirm-title").textContent = title;
  $("#confirm-copy").textContent = copy;
  $("#confirm-action").textContent = actionLabel;
  $("#confirm-backdrop").hidden = false;
  return new Promise((resolve) => { state.confirmResolve = resolve; });
}

async function deleteRecord(resource, id) {
  const permanent = ["approval_processes", "blueprints"].includes(resource);
  const confirmed = permanent
    ? await confirmAction("Delete this rule?", "This permanently removes it from your workspace and cannot be undone.", "Delete")
    : resource === "users"
      ? await confirmAction("Deactivate this user?", "They will no longer appear as an owner option. You can reactivate them from the same list.", "Deactivate")
      : await confirmAction("Archive this record?", "This removes the record from your active workspace lists.", "Archive");
  if (!confirmed) return;
  try {
    await api(`/api/${resource}/${id}`, { method: "DELETE" });
    if (["accounts", "contacts"].includes(resource)) invalidateLookups();
    if (resource === "users") await refreshMeta();
    toast(permanent ? "Deleted" : resource === "users" ? "User deactivated" : "Record archived", permanent ? "The rule has been removed." : "The record has been removed from the active view.");
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (MODULES[resource] && parts[0] === resource && parts[1]) await navigate(`/${resource}`);
    else await renderRoute();
  } catch (error) { toast("Could not complete that action", error.message, "error"); }
}

async function deletePlatformRecord(resource, id) {
  const config = state.platformCatalog.resources[resource];
  const confirmed = await confirmAction(`Archive this ${config.singular.toLowerCase()}?`, "The record will move to the recycle bin and can be restored.", "Archive");
  if (!confirmed) return;
  try {
    await api(`/api/platform/${resource}/${id}`, { method: "DELETE" });
    toast("Record archived", "It can be restored from Setup > Recycle Bin.");
    await renderRoute();
  } catch (error) { toast("Could not archive record", error.message, "error"); }
}

function bindPlatform(resource) {
  if (["personal_settings", "users", "approval_processes", "blueprints"].includes(resource)) bindSettings();
  $$('[data-platform-create]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
  $$('[data-platform-edit]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformEdit, Number(button.dataset.id))));
  $$('[data-platform-delete]').forEach((button) => button.addEventListener("click", () => deletePlatformRecord(button.dataset.platformDelete, Number(button.dataset.id))));
  const current = state.platformCatalog.resources[resource] ? platformState(resource) : null;
  let timer;
  $('[data-platform-search]')?.addEventListener("input", (event) => { clearTimeout(timer); current.search = event.target.value; current.offset = 0; timer = setTimeout(renderRoute, 250); });
  $('[data-platform-status]')?.addEventListener("change", (event) => { current.status = event.target.value; current.offset = 0; renderRoute(); });
  $('[data-platform-owner]')?.addEventListener("change", (event) => { current.owner_id = event.target.value; current.offset = 0; renderRoute(); });
  $('[data-platform-sort]')?.addEventListener("change", (event) => { current.sort = event.target.value; current.offset = 0; renderRoute(); });
  $$('[data-page]').forEach((button) => button.addEventListener("click", () => { if (!current) return; current.offset += button.dataset.page === "next" ? 25 : -25; renderRoute(); }));
  $$('[data-restore-resource]').forEach((button) => button.addEventListener("click", async () => { try { await api("/api/administration/restore", { method: "POST", body: JSON.stringify({ resource: button.dataset.restoreResource, record_id: Number(button.dataset.id) }) }); toast("Record restored"); await renderRoute(); } catch (error) { toast("Could not restore record", error.message, "error"); } }));
  $('[data-import-form]')?.addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; const file = form.querySelector('[name="file"]').files[0]; if (!file) return; const body = new FormData(); body.append("file", file); try { const response = await fetch(`/api/import/${form.elements.resource.value}`, { method: "POST", body }); const result = await response.json(); if (!response.ok) throw new Error(result.detail || "Import failed"); toast("Import complete", `${result.imported} rows imported; ${result.errors.length} errors.`); form.reset(); } catch (error) { toast("Could not import CSV", error.message, "error"); } });
  $('[data-duplicate-form]')?.addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; const target = $('[data-duplicate-results]'); try { const result = await api(`/api/administration/duplicates?resource=${encodeURIComponent(form.elements.resource.value)}`); target.innerHTML = result.groups.length ? result.groups.map((group) => `<div class="rule-row"><div class="rule-info"><strong>${esc(group.value)}</strong><small>${group.count} records match on ${esc(group.match_on)}</small></div>${badge("Review")}</div>`).join("") : emptyState("✓", "No duplicates found", "No exact normalized matches were detected."); } catch (error) { toast("Duplicate scan failed", error.message, "error"); } });
}

function bindGlobal() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (link && !link.hasAttribute("download") && !link.getAttribute("href").startsWith("/api/") && !event.metaKey && !event.ctrlKey && !event.shiftKey && link.origin === window.location.origin && link.getAttribute("href").startsWith("/")) { event.preventDefault(); navigate(link.getAttribute("href")); return; }
    const retry = event.target.closest("[data-retry]"); if (retry) renderRoute();
  });
  window.addEventListener("popstate", renderRoute);
  $("#menu-toggle").addEventListener("click", () => $("#sidebar").classList.add("open"));
  $("#sidebar-close").addEventListener("click", () => $("#sidebar").classList.remove("open"));
  $("#modal-close").addEventListener("click", closeModal); $("#modal-cancel").addEventListener("click", closeModal); $("#modal-backdrop").addEventListener("click", (event) => { if (event.target.id === "modal-backdrop") closeModal(); });
  $("#confirm-close").addEventListener("click", () => closeConfirm(false)); $("#confirm-cancel").addEventListener("click", () => closeConfirm(false)); $("#confirm-action").addEventListener("click", () => closeConfirm(true));
  $("#confirm-backdrop").addEventListener("click", (event) => { if (event.target.id === "confirm-backdrop") closeConfirm(false); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { if (!$("#confirm-backdrop").hidden) closeConfirm(false); else if (!$("#modal-backdrop").hidden) closeModal(); else $("#search-results").classList.remove("open"); }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("#global-search").focus(); }
  });
  $("#record-form").addEventListener("submit", submitRecord);
  $("#top-profile").addEventListener("click", () => navigate("/settings/profile-users")); $("#profile-shortcut").addEventListener("click", () => navigate("/settings/profile-users"));
  const searchInput = $("#global-search"); let searchTimer;
  searchInput.addEventListener("input", () => { clearTimeout(searchTimer); if (!searchInput.value.trim()) { $("#search-results").classList.remove("open"); return; } searchTimer = setTimeout(async () => { try { const data = await api(`/api/search?q=${encodeURIComponent(searchInput.value)}`); const result = $("#search-results"); result.innerHTML = data.results.length ? data.results.map((item) => `<button class="search-result" data-search-route="/${item.resource}/${item.id}"><span class="result-icon">${MODULES[item.resource]?.icon || "◈"}</span><span><strong>${esc(item.label)}</strong><small>${esc(titleCase(item.resource))} · ${esc(item.meta || "")}</small></span></button>`).join("") : `<p style="padding:10px;color:var(--text-faint);font-size:11px">No matching records.</p>`; result.classList.add("open"); } catch (error) { /* search is best effort */ } }, 240); });
  document.addEventListener("click", (event) => { const result = event.target.closest("[data-search-route]"); if (result) { $("#search-results").classList.remove("open"); searchInput.value = ""; navigate(result.dataset.searchRoute); } else if (!event.target.closest("#global-search-wrap")) $("#search-results").classList.remove("open"); });
}

async function aiView() {
  const [status, dashboard, performanceReport] = await Promise.all([
    api("/api/ai/status").catch((error) => ({ configured: false, available: false, model: "offline", detail: error.message, csrf_token: state.aiStatus?.csrf_token })),
    api("/api/dashboard").catch(() => ({ journey: {}, sales_performance: [], attention: {} })),
    api("/api/ai/performance").catch(() => ({ people: [], totals: {}, calculation_basis: {} })),
  ]);
  state.aiStatus = status;
  if (!state.aiMessages.length) {
    state.aiMessages = [{ role: "assistant", result: { answer: "I’m Apex, your CRM helpdesk copilot. I can help you triage a customer request, find the next best action, or surface where a revenue journey is getting stuck.", actions: ["Summarize today’s pipeline and stuck leads", "What should I follow up on next?", "Show me who is close to target"], risks: ["I never change invoices, payments, assignments, or incentives without an explicit human approval."], confidence: "high", model: "Apex guardrails", sources: ["Live CRM workspace"], disclaimer: "Apex uses CRM data as context. Verify important decisions before acting." } }];
  }
  const journey = dashboard.journey || {};
  const journeyStages = [
    ["Leads", journey.leads || 0, "/leads", "✦"], ["Visits", journey.visits || 0, "/site_visits", "◷"], ["Quotes", journey.quotes || 0, "/quotes", "▤"], ["Invoices", journey.invoices || 0, "/invoices", "▣"], ["Payments", journey.payments || 0, "/payments", "₹"],
  ];
  const prompts = ["Summarize today’s pipeline and stuck leads", "What should I follow up on next?", "Show me who is close to target", "Draft a safe customer reply for a delayed quotation"];
  const analytics = (() => { try { return JSON.parse(localStorage.getItem("apex-helpdesk-analytics") || "{}"); } catch { return {}; } })();
  const intentChips = prompts.map((prompt) => `<button class="apex-prompt" data-apex-prompt="${esc(prompt)}">${esc(prompt)}</button>`).join("");
  return `${pageHeader("Apex intelligence", "Helpdesk command center", "Triage conversations quickly, keep permissions explicit, and move every customer journey forward.", `<span class="ai-status ${status.available ? "ready" : "offline"}"><i></i>${status.available ? "AI online" : "Safe fallback mode"}</span>`)}
    <section class="apex-journey card"><div class="apex-journey-head"><div><span class="eyebrow">One source of truth</span><h2>Lead → payment journey</h2></div><small>${journey.collected ? `${formatMoney(journey.collected)} collected from cleared payments` : "Live CRM stage counts"}</small></div><div class="apex-journey-track">${journeyStages.map(([label, count, href, icon], index) => `<a class="apex-stage" href="${href}"><span class="apex-stage-icon">${icon}</span><span><strong>${count}</strong><small>${label}</small></span>${index < journeyStages.length - 1 ? `<b class="apex-stage-line"></b>` : ""}</a>`).join("")}</div></section>
    ${apexPerformanceMarkup(performanceReport)}
    <div class="apex-layout"><section class="card apex-chat"><div class="apex-chat-head"><div class="apex-avatar">A</div><div><h2>Ask Apex</h2><small>${status.available ? `Connected to ${esc(status.provider || "your AI provider")}` : "Local helpdesk answers stay available while cloud AI is offline"}</small></div><span class="apex-live-dot"></span></div><div class="apex-conversation" id="apex-conversation">${state.aiMessages.map(aiMessageHtml).join("")}</div><div class="apex-suggestions"><span>Try asking</span>${intentChips}</div><form class="apex-composer" id="apex-composer"><textarea id="apex-question" rows="2" placeholder="Ask about a lead, follow-up, quote, payment, or salesperson…" aria-label="Ask Apex"></textarea><button class="button button-primary" type="submit"><span>Send</span><b>↗</b></button></form><div class="apex-composer-foot"><span>⌘ Enter to send</span><span>Usage today: ${Number(analytics.messages || 0)} messages</span><span class="apex-permission">Human approval required for write actions</span></div></section>
      <aside class="apex-side"><section class="card apex-side-card"><span class="eyebrow">Triage playbook</span><h3>What Apex can do</h3><div class="apex-capability"><b>01</b><span><strong>Understand intent</strong><small>Classify support, follow-up, payment, and performance questions.</small></span></div><div class="apex-capability"><b>02</b><span><strong>Use live context</strong><small>Connect conversations back to owners, visits, quotations, invoices, and payments.</small></span></div><div class="apex-capability"><b>03</b><span><strong>Escalate safely</strong><small>Suggest a human handoff when evidence is missing, sensitive, or ambiguous.</small></span></div></section><section class="card apex-side-card apex-attention"><div class="apex-side-title"><div><span class="eyebrow">Needs attention</span><h3>Keep revenue moving</h3></div><a href="/dashboard">View all →</a></div>${attentionQueue(dashboard.attention || {})}</section></aside></div>`;
}

function apexPerformanceMarkup(report) {
  const people = report.people || [];
  const totals = report.totals || {};
  const basis = report.calculation_basis || {};
  const rows = people.length ? people.map((row) => `<tr><td><strong>${esc(row.name)}</strong><span class="sub-cell">${esc(row.role || "Salesperson")} · ${row.target_configured ? esc(row.period_start) + " to " + esc(row.period_end) : "target not configured"}</span></td><td><strong>${formatMoney(row.target)}</strong><span class="sub-cell">${row.target_name ? esc(row.target_name) : "No active target"}</span></td><td><strong>${formatMoney(row.achieved)}</strong><span class="sub-cell">${formatMoney(row.remaining_to_target)} remaining</span></td><td><div class="apex-achievement"><span class="achievement-meter"><i style="width:${Math.min(Number(row.achievement_percent || 0), 100)}%"></i></span><strong>${Number(row.achievement_percent || 0).toFixed(1)}%</strong></div><span class="sub-cell">${row.eligible_for_incentive ? "Eligible" : `Needs ${Number(row.threshold_percent || 0).toFixed(0)}%`}</span></td><td>${row.conversions}</td><td><strong>${formatMoney(row.incentive)}</strong><span class="sub-cell">${Number(row.incentive_rate || 0).toFixed(2)}% rate</span></td></tr>`).join("") : `<tr><td colspan="6"><div class="empty-state"><span class="empty-icon">◎</span><h3>No active salesperson targets</h3><p>Add targets in Sales Targets & Incentives to generate this report.</p></div></td></tr>`;
  return `<section class="card apex-performance"><div class="apex-performance-head"><div><span class="eyebrow">Management intelligence</span><h2>Sales performance & incentive report</h2><p>Generated from live CRM payments, converted leads, and active target rules.</p></div><button class="button button-ghost button-small" data-apex-performance-refresh>↻ Recalculate</button></div><div class="apex-performance-summary"><div><span>Team target</span><strong>${formatMoney(totals.target)}</strong></div><div><span>Achieved</span><strong>${formatMoney(totals.achieved)}</strong></div><div><span>Achievement</span><strong>${Number(totals.achievement_percent || 0).toFixed(1)}%</strong></div><div><span>Incentive earned</span><strong>${formatMoney(totals.incentive)}</strong></div><div><span>Conversions</span><strong>${totals.conversions || 0}</strong></div></div><div class="table-wrap"><table class="data-table apex-performance-table"><thead><tr><th>Salesperson</th><th>Target</th><th>Achieved</th><th>Achievement</th><th>Conversions</th><th>Incentive</th></tr></thead><tbody>${rows}</tbody></table></div><details class="apex-formula"><summary>How Apex calculates incentive</summary><div><p><strong>Achieved:</strong> ${esc(basis.achieved || "Received or Cleared payments in the active target period")}</p><p><strong>Achievement:</strong> ${esc(basis.achievement || "achieved / target × 100")}</p><p><strong>Incentive:</strong> ${esc(basis.incentive || "achieved × rate / 100 when threshold is met")}</p><p><strong>Conversions:</strong> ${esc(basis.conversions || "Converted leads in the active target period")}</p></div></details></section>`;
}

function apexFallback(question, dashboard) {
  const q = question.toLowerCase();
  const performance = dashboard.sales_performance || [];
  if (q.includes("target") || q.includes("achievement") || q.includes("incentive") || q.includes("perform") || q.includes("salesperson")) {
    const ranked = [...performance].sort((a, b) => Number(b.achievement_percent || 0) - Number(a.achievement_percent || 0));
    const breakdown = ranked.length ? ranked.map((row) => `${row.name}: ${Number(row.achievement_percent || 0).toFixed(1)}% achieved (${formatMoney(row.achieved)} / ${formatMoney(row.target)}), ${row.conversions} conversions, incentive ${formatMoney(row.incentive)}${row.remaining_to_target ? `, ${formatMoney(row.remaining_to_target)} remaining` : ""}.`).join(" ") : "No active salesperson targets are configured.";
    return { answer: `Here is the current salesperson breakdown. ${breakdown}`, actions: ["Open Sales Targets & Incentives", "Review the full calculation formula"], risks: ["Incentives are calculated from cleared payments and the active target period only. A salesperson becomes eligible only after reaching the configured threshold."], confidence: ranked.length ? "high" : "medium", model: "Apex fallback", sources: ["Sales performance", "Cleared payments", "Converted leads"], disclaimer: "This answer uses the CRM snapshot available in the browser. Recalculate the report after recording new payments or conversions." };
  }
  if (q.includes("follow") || q.includes("stuck") || q.includes("next")) return { answer: "I found the highest-value next step in the AI action queue: review stale leads and quotations nearing validity. Open an item to see its owner, date, and the exact activity Apex recommends. Any task creation stays approval-controlled.", actions: ["Review AI action queue", "Open quotation exceptions"], risks: ["A missing follow-up date is treated as a risk signal, not proof that a customer was ignored."], confidence: "high", model: "Apex fallback", sources: ["Live CRM action queue"], disclaimer: "Verify the record before contacting a customer." };
  if (q.includes("reply") || q.includes("customer") || q.includes("support") || q.includes("help")) return { answer: "Here is a safe starting point: ‘Thanks for reaching out. I’m checking the latest status with our team and will confirm the next step shortly.’ I can help locate the related lead or quotation, but a human should review any customer-facing message before sending.", actions: ["Find the related lead", "Create a review task"], risks: ["Do not share payment, pricing, or delivery commitments until the CRM record is verified."], confidence: "medium", model: "Apex fallback", sources: ["Helpdesk playbook"], disclaimer: "Draft only — human review required before sending." };
  return { answer: "I can help with leads, customer conversations, site visits, quotations, invoices, payments, salesperson targets, achievement, and incentives. Try one of the prompts below or ask me to find where a journey is stuck.", actions: ["Summarize today’s pipeline", "Show close-to-target salespeople", "Review quotation follow-ups"], risks: ["If a request involves a financial commitment or permission change, Apex will stop and ask for a human review."], confidence: "medium", model: "Apex fallback", sources: ["Apex helpdesk playbook"], disclaimer: "Apex is decision support, not an autonomous operator." };
}

function aiMessageHtml(message, messageIndex) {
  if (message.role === "user") return `<article class="ai-message user"><span>You</span><p>${esc(message.text)}</p></article>`;
  const result = message.result;
  const actions = (result.actions || []).length ? `<div class="ai-result-list"><strong>Recommended actions</strong><ol>${result.actions.map((item) => `<li>${esc(item)}</li>`).join("")}</ol></div>` : "";
  const risks = (result.risks || []).length ? `<div class="ai-result-list risks"><strong>Risks and gaps</strong><ul>${result.risks.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>` : "";
  const proposals = (result.proposed_activities || []).length ? `<div class="ai-proposals"><div class="ai-proposals-head"><div><strong>Proposed CRM activities</strong><small>Review each item. Approval writes selected activities to the CRM and audit history.</small></div></div>${result.proposed_activities.map((item, index) => `<label class="ai-proposal"><input type="checkbox" data-ai-proposal-index="${index}" checked ${result.approval_result ? "disabled" : ""}/><span><b>${esc(item.activity_type)} · ${esc(item.subject)}</b><small>${esc(titleCase(item.priority))} · due ${formatDateTime(item.due_at)} · ${esc(titleCase(item.related_type))} #${item.related_id}${item.owner_id ? ` · owner #${item.owner_id}` : ""}</small><em>${esc(item.reason)}</em></span></label>`).join("")}<div class="ai-approval-row">${result.approval_result ? `<span class="ai-approved">✓ ${result.approval_result.created.length} created · ${result.approval_result.skipped.length} duplicate${result.approval_result.skipped.length === 1 ? "" : "s"} skipped</span>` : `<button class="button button-primary button-small" data-ai-approve="${messageIndex}">Review and approve selected</button>`}</div></div>` : "";
  const sources = (result.sources || []).map((item) => `<span>${esc(item)}</span>`).join("");
  return `<article class="ai-message assistant" data-ai-message="${messageIndex}"><div class="ai-message-head"><span>Apex</span><small>${esc(result.model)} · ${esc(result.confidence)} confidence</small></div><p>${esc(result.answer).replace(/\n/g, "<br>")}</p>${actions}${risks}${proposals}<div class="ai-sources"><strong>CRM context used</strong>${sources}</div><small class="ai-disclaimer">${esc(result.disclaimer)}</small></article>`;
}

function renderAIConversation() {
  const conversation = $("#ai-conversation");
  if (!conversation) return;
  conversation.innerHTML = state.aiMessages.map(aiMessageHtml).join("");
  bindAIProposalActions();
  conversation.scrollTop = conversation.scrollHeight;
}

function bindAIProposalActions() {
  $$('[data-ai-approve]').forEach((button) => button.addEventListener("click", async () => {
    const messageIndex = Number(button.dataset.aiApprove);
    const message = state.aiMessages[messageIndex];
    if (!message?.result) return;
    const card = button.closest("[data-ai-message]");
    const indexes = $$('[data-ai-proposal-index]:checked', card).map((input) => Number(input.dataset.aiProposalIndex));
    const activities = indexes.map((index) => message.result.proposed_activities[index]).filter(Boolean);
    if (!activities.length) { toast("Nothing selected", "Select at least one proposed activity.", "error"); return; }
    const confirmed = await confirmAction("Create selected AI activities?", `This will create ${activities.length} open CRM activit${activities.length === 1 ? "y" : "ies"}. Every item will be recorded in audit history.`, "Create activities");
    if (!confirmed) return;
    button.disabled = true;
    try {
      const approval = await api("/api/ai/activities/approve", { method: "POST", body: JSON.stringify({ request_id: message.result.request_id, activities }) });
      message.result.approval_result = approval;
      toast("AI activities processed", `${approval.created.length} created; ${approval.skipped.length} duplicate${approval.skipped.length === 1 ? "" : "s"} skipped.`);
      renderAIConversation();
    } catch (error) { button.disabled = false; toast("Could not create AI activities", error.message, "error"); }
  }));
}

function bindAI() {
  const conversation = $("#apex-conversation");
  const form = $("#apex-composer");
  const question = $("#apex-question");
  if (!form || !conversation) return;
  const submit = async (text) => {
    const value = String(text || "").trim();
    if (value.length < 3) return;
    state.aiMessages.push({ role: "user", text: value });
    conversation.innerHTML = state.aiMessages.map(aiMessageHtml).join("") + `<div class="apex-thinking"><i></i><span>Apex is checking CRM context…</span></div>`;
    conversation.scrollTop = conversation.scrollHeight;
    question.value = "";
    const dashboard = await api("/api/dashboard").catch(() => ({ sales_performance: [], attention: {} }));
    let result;
    try {
      const response = await api("/api/ai/chat", { method: "POST", body: JSON.stringify({ question: value }) });
      result = { ...response, model: response.model || "Apex", sources: response.sources || ["Live CRM workspace"] };
    } catch (error) {
      result = apexFallback(value, dashboard);
      result.disclaimer = `${result.disclaimer} Cloud response unavailable: ${error.message}`;
    }
    state.aiMessages.push({ role: "assistant", result });
    try { const stats = JSON.parse(localStorage.getItem("apex-helpdesk-analytics") || "{}"); stats.messages = Number(stats.messages || 0) + 1; stats.last_intent = value.slice(0, 80); localStorage.setItem("apex-helpdesk-analytics", JSON.stringify(stats)); } catch {}
    conversation.innerHTML = state.aiMessages.map(aiMessageHtml).join("");
    bindAIProposalActions();
    conversation.scrollTop = conversation.scrollHeight;
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); submit(question.value); });
  question.addEventListener("keydown", (event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); submit(question.value); } });
  $$('[data-apex-prompt]').forEach((button) => button.addEventListener("click", () => submit(button.dataset.apexPrompt)));
  $("[data-apex-performance-refresh]")?.addEventListener("click", () => navigate("/ai"));
}

async function settingsView(tab) {
  const tabs = [{ id: "general", label: "General settings", icon: "⚙" }, { id: "profile-users", label: "Profile & users", icon: "◎" }, { id: "approval-process", label: "Approval process", icon: "✓" }, { id: "blueprint", label: "Blueprint", icon: "◇" }];
  const nav = `<section class="card settings-nav">${tabs.map((item) => `<a href="/settings/${item.id}" class="${tab === item.id ? "active" : ""}"><span>${item.icon}</span>${item.label}</a>`).join("")}</section>`;
  let content = "";
  if (tab === "general") content = `${await generalSettingsView()}${await settingsPlatformSummary("company_details", "Company details")}${await settingsPlatformSummary("fiscal_years", "Fiscal years")}`;
  if (tab === "profile-users") content = await profileUsersView();
  if (tab === "approval-process") content = await approvalSettingsView();
  if (tab === "blueprint") content = await blueprintSettingsView();
  return `${pageHeader("Manage", "Settings", "Shape how Apex CRM works for your team.")}<div class="settings-layout">${nav}<div class="settings-content">${content}</div></div>`;
}

async function settingsPlatformSummary(resource, title) {
  const config = state.platformCatalog.resources[resource];
  if (!config) return "";
  const data = await api(`/api/platform/${resource}?limit=100&sort=name_asc`);
  const add = config.singleton && data.total ? "" : `<button class="button button-primary button-small" data-platform-create="${resource}">+ Add ${esc(config.singular.toLowerCase())}</button>`;
  return `<section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>${esc(title)}</h2><p>${esc(config.description)}</p></div>${add}</div>${platformTable(resource, data)}</section>`;
}

async function generalSettingsView() {
  const setting = await api("/api/settings/general"); state.settingsCache = { ...state.settingsCache, ...setting };
  const notifications = setting.notifications || {};
  return `<section class="card settings-section"><div class="settings-section-head"><h2>General settings</h2><p>Set the defaults your workspace uses across records and reports.</p></div><form class="settings-form" data-settings-form="general"><div class="form-grid"><div class="field"><label for="org_name">Organization name</label><input class="field-input" id="org_name" name="org_name" value="${esc(setting.org_name)}" /></div><div class="field"><label for="timezone">Timezone</label><select class="field-select" id="timezone" name="timezone"><option ${setting.timezone === "Asia/Kolkata" ? "selected" : ""}>Asia/Kolkata</option><option ${setting.timezone === "Asia/Singapore" ? "selected" : ""}>Asia/Singapore</option><option ${setting.timezone === "UTC" ? "selected" : ""}>UTC</option></select></div><div class="field"><label for="currency">Currency</label><select class="field-select" id="currency" name="currency"><option ${setting.currency === "INR" ? "selected" : ""}>INR</option><option ${setting.currency === "USD" ? "selected" : ""}>USD</option><option ${setting.currency === "EUR" ? "selected" : ""}>EUR</option></select></div><div class="field"><label for="date_format">Date format</label><select class="field-select" id="date_format" name="date_format"><option ${setting.date_format === "DD MMM YYYY" ? "selected" : ""}>DD MMM YYYY</option><option ${setting.date_format === "MM/DD/YYYY" ? "selected" : ""}>MM/DD/YYYY</option><option ${setting.date_format === "YYYY-MM-DD" ? "selected" : ""}>YYYY-MM-DD</option></select></div><div class="field"><label for="fiscal_year_start">Fiscal year starts in</label><select class="field-select" id="fiscal_year_start" name="fiscal_year_start"><option ${setting.fiscal_year_start === "April" ? "selected" : ""}>April</option><option ${setting.fiscal_year_start === "January" ? "selected" : ""}>January</option><option ${setting.fiscal_year_start === "July" ? "selected" : ""}>July</option></select></div><div class="field"><label for="default_pipeline">Default pipeline</label><input class="field-input" id="default_pipeline" name="default_pipeline" value="${esc(setting.default_pipeline)}" /></div></div><div style="margin-top:24px"><h3 style="margin-bottom:5px">Notifications</h3><p style="color:var(--text-faint);font-size:11px;margin-bottom:10px">Choose which updates your team should see in their workspace.</p><div class="switch-row"><div class="switch-copy"><strong>Daily digest</strong><small>Receive a concise summary of records that need attention.</small></div><button type="button" class="switch ${notifications.daily_digest ? "on" : ""}" data-setting-toggle="daily_digest" data-boolean="true" aria-label="Toggle daily digest"></button></div><div class="switch-row"><div class="switch-copy"><strong>Mentions</strong><small>Be notified when someone mentions you in a note or activity.</small></div><button type="button" class="switch ${notifications.mentions ? "on" : ""}" data-setting-toggle="mentions" data-boolean="true" aria-label="Toggle mentions"></button></div><div class="switch-row"><div class="switch-copy"><strong>Deal updates</strong><small>Stay informed when deals you own change stage.</small></div><button type="button" class="switch ${notifications.deal_updates ? "on" : ""}" data-setting-toggle="deal_updates" data-boolean="true" aria-label="Toggle deal updates"></button></div></div><div class="form-actions"><button type="submit" class="button button-primary">Save general settings</button></div></form></section>`;
}

async function profileUsersView() {
  const [profile, users] = await Promise.all([api("/api/settings/profile"), api("/api/users?limit=100")]);
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Your profile</h2><p>Keep your personal details current for the rest of the team.</p></div><form class="settings-form" data-settings-form="profile"><div class="form-grid"><div class="field"><label for="profile-name">Full name</label><input class="field-input" id="profile-name" name="name" value="${esc(profile.name)}" /></div><div class="field"><label for="profile-email">Email</label><input class="field-input" id="profile-email" name="email" type="email" required value="${esc(profile.email)}" /></div><div class="field"><label>Role</label><input class="field-input" value="${esc(profile.role)}" disabled /></div></div><div class="form-actions"><button type="submit" class="button button-primary">Save profile</button></div></form></section><section class="card settings-section"><div class="settings-section-head" style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start"><div><h2>Users</h2><p>Manage who has access to this workspace and what they can do.</p></div><button class="button button-primary button-small" data-create="users">＋ Add user</button></div><div>${users.items.map((user) => `<div class="rule-row"><span class="avatar ${user.status === "Active" ? "avatar-green" : "avatar-amber"}">${initials(user.name)}</span><div class="rule-info"><strong>${esc(user.name)}</strong><small>${esc(user.email)} · ${esc(user.role)} · Last active ${formatDateTime(user.last_active)}</small></div>${badge(user.status)}<div class="rule-actions"><button class="table-action" data-edit-record="users" data-id="${user.id}">✎</button><button class="table-action" data-toggle-user="${user.id}" data-status="${user.status}">${user.status === "Active" ? "⏸" : "▶"}</button></div></div>`).join("")}</div></section>`;
}

async function approvalSettingsView() {
  const data = await api("/api/approval_processes?limit=100");
  return `<section class="card settings-section"><div class="settings-section-head" style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start"><div><h2>Approval process</h2><p>Automate the moments where a second pair of eyes keeps work moving safely.</p></div><button class="button button-primary button-small" data-create="approval_processes">＋ New rule</button></div><div>${data.items.length ? data.items.map((rule) => `<div class="rule-row"><span class="related-dot">✓</span><div class="rule-info"><strong>${esc(rule.name)}</strong><small>${esc(rule.module)} · ${esc(rule.trigger)} · Approver: ${esc(rule.approver)}</small></div>${badge(rule.status)}<div class="rule-actions"><button class="table-action" data-edit-record="approval_processes" data-id="${rule.id}">✎</button><button class="table-action" data-delete-record="approval_processes" data-id="${rule.id}">⌫</button></div></div>`).join("") : emptyState("✓", "No approval rules", "Create an approval rule for deals, leads, or accounts.", `<button class="button button-primary" data-create="approval_processes">New rule</button>`)}</div></section>`;
}

async function blueprintSettingsView() {
  const data = await api("/api/blueprints?limit=100");
  const head = `<div class="settings-section-head" style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start"><div><h2>Blueprint</h2><p>Guide records through the right stages with clear transitions and requirements.</p></div><button class="button button-primary button-small" data-create="blueprints">＋ New blueprint</button></div>`;
  const blocks = data.items.map((bp, position) => {
    const stages = bp.stages || [];
    const transitions = bp.transitions || [];
    const flow = stages.length
      ? `<div style="margin-top:19px"><span class="eyebrow">Current flow</span><div class="blueprint-flow">${stages.map((stage, index) => `<div class="blueprint-stage"><strong>${esc(stage.label || stage.name)}</strong><small>Stage ${index + 1}</small></div>${index < stages.length - 1 ? `<span class="blueprint-arrow">→</span>` : ""}`).join("")}</div></div>`
      : `<p class="related-empty" style="margin-top:14px">No stages defined yet. Edit this blueprint to add some.</p>`;
    const moves = transitions.length
      ? `<div style="margin:6px 0 16px"><span class="eyebrow">Transitions</span>${transitions.map((item) => `<p class="related-empty" style="padding:4px 0">${esc(item.from)} → ${esc(item.to)}${item.label ? ` · ${esc(item.label)}` : ""}</p>`).join("")}</div>`
      : "";
    return `<div style="${position ? "margin-top:26px;padding-top:22px;border-top:1px solid var(--border)" : ""}"><div class="rule-row" style="padding-top:0"><span class="related-dot">◇</span><div class="rule-info"><strong>${esc(bp.name)}</strong><small>${esc(bp.module)} · Entry: ${esc(bp.entry_criteria || "No entry criteria")}</small></div>${badge(bp.active ? "Active" : "Inactive")}<div class="rule-actions"><button class="table-action" data-edit-record="blueprints" data-id="${bp.id}">✎</button><button class="table-action" data-delete-record="blueprints" data-id="${bp.id}">⌫</button></div></div>${flow}${moves}<div class="card" style="background:var(--surface-soft);box-shadow:none"><div class="card-body"><div class="switch-row" style="padding-top:0"><div class="switch-copy"><strong>Blueprint active</strong><small>Apply this flow to new ${esc(String(bp.module || "").toLowerCase())} records.</small></div><button type="button" class="switch ${bp.active ? "on" : ""}" data-toggle-blueprint="${bp.id}" data-active="${bp.active}" aria-label="Toggle blueprint"></button></div></div></div></div>`;
  });
  return `<section class="card settings-section">${head}${blocks.length ? blocks.join("") : emptyState("◇", "No blueprints yet", "Create a guided stage flow for one of your modules.", `<button class="button button-primary" data-create="blueprints">New blueprint</button>`)}</section>`;
}

function bindSettings() {
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create)));
  $$('[data-edit-record]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.editRecord, Number(button.dataset.id))));
  $$('[data-delete-record]').forEach((button) => button.addEventListener("click", () => deleteRecord(button.dataset.deleteRecord, Number(button.dataset.id))));
  $$('[data-platform-create]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
  $$('[data-platform-edit]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformEdit, Number(button.dataset.id))));
  $$('[data-platform-delete]').forEach((button) => button.addEventListener("click", () => deletePlatformRecord(button.dataset.platformDelete, Number(button.dataset.id))));
  $$('[data-setting-toggle]').forEach((button) => button.addEventListener("click", () => button.classList.toggle("on")));
  $$('[data-toggle-user]').forEach((button) => button.addEventListener("click", async () => { try { const status = button.dataset.status === "Active" ? "Inactive" : "Active"; await api(`/api/users/${button.dataset.toggleUser}`, { method: "PATCH", body: JSON.stringify({ status }) }); await refreshMeta(); toast("User status updated", `${status} user`); await renderRoute(); } catch (error) { toast("Could not update user", error.message, "error"); } }));
  $$('[data-toggle-blueprint]').forEach((button) => button.addEventListener("click", async () => { try { const active = button.dataset.active !== "true"; await api(`/api/blueprints/${button.dataset.toggleBlueprint}`, { method: "PATCH", body: JSON.stringify({ active }) }); toast("Blueprint updated", active ? "Blueprint is active" : "Blueprint is inactive"); await renderRoute(); } catch (error) { toast("Could not update blueprint", error.message, "error"); } }));
  $$('[data-settings-form]').forEach((form) => form.addEventListener("submit", async (event) => { event.preventDefault(); const kind = form.dataset.settingsForm; try { if (kind === "general") { const data = readForm(form); data.notifications = {}; $$('[data-setting-toggle]', form).forEach((toggle) => { data.notifications[toggle.dataset.settingToggle] = toggle.classList.contains("on"); }); await api("/api/settings/general", { method: "PUT", body: JSON.stringify(data) }); state.settingsCache = { ...state.settingsCache, ...data }; toast("Settings saved", "Your workspace defaults are up to date."); } else { state.profile = await api("/api/settings/profile", { method: "PUT", body: JSON.stringify(readForm(form)) }); applyProfile(); await refreshMeta(); toast("Profile saved", "Your profile details have been updated."); } } catch (error) { toast("Could not save settings", error.message, "error"); } }));
}

async function openConvertModal(id) {
  state.modal = { resource: "leads", id, convert: true };
  $("#modal-eyebrow").textContent = "Lead conversion"; $("#modal-title").textContent = "Convert lead"; $("#modal-submit").textContent = "Convert lead";
  $("#modal-body").innerHTML = `<div class="form-grid"><div class="field full"><label for="convert-account">Account name</label><input class="field-input" id="convert-account" name="account_name" placeholder="Company account" /></div><div class="field"><label for="convert-deal">Create a deal</label><select class="field-select" id="convert-deal" name="create_deal"><option value="true" selected>Create deal</option></select></div><div class="field"><label for="convert-amount">Deal amount</label><input class="field-input" id="convert-amount" name="deal_amount" type="number" step="any" value="0" /></div><div class="field"><label for="convert-name">Deal name</label><input class="field-input" id="convert-name" name="deal_name" placeholder="Optional opportunity name" /></div><div class="field"><label for="convert-date">Expected close date</label><input class="field-input" id="convert-date" name="expected_close_date" type="date" /></div></div>`;
  $("#modal-backdrop").hidden = false;
}

async function init() {
  bindGlobal();
  try { await ensurePlatformCatalog(); } catch (error) { toast("Module catalog unavailable", error.message, "error"); }
  enhanceNavigation();
  try { state.meta = await api("/api/meta"); } catch (error) { toast("Workspace data unavailable", error.message, "error"); }
  try { state.settingsCache = await api("/api/settings/general"); } catch (error) { /* use defaults until settings load */ }
  try { state.profile = await api("/api/settings/profile"); applyProfile(); } catch (error) { /* keep the shell usable */ }
  try { await ensureLookups(); } catch (error) { /* lookups retry when a related form opens */ }
  await renderRoute();
}

init();

if ("serviceWorker" in navigator && (location.protocol === "https:" || ["localhost", "127.0.0.1"].includes(location.hostname))) {
  navigator.serviceWorker.register("/sw.js").catch(() => { /* installability is optional */ });
}

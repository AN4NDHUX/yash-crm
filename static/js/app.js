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
};

const PLATFORM_MODULE_ROUTES = [
  "price_books", "vendors", "quotes", "sales_orders", "purchase_orders", "invoices", "payments",
  "campaigns", "cases", "solutions", "documents", "site_visits", "forecasts", "reports", "dashboards", "sales_targets",
];
const BRAND_ORBS_LOADER_URL = "/static/threeui/brand-orbs-loader.html?v=20261006-particles-v2";

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
    if (parts[0] === "teamspaces") {
      setBreadcrumb("Teamspaces", "Workspace");
      content.innerHTML = await teamspacesView();
      bindTeamspaces();
      return;
    }
    if (parts[0] === "activities" && !parts[1]) {
      return navigate("/activities/tasks", true);
    }
    if (parts[0] === "ai") {
      if (parts[1] === "exceptions") {
        setBreadcrumb("Quotation Exceptions", "Apex AI Copilot");
        content.innerHTML = await aiView();
        bindAI();
      } else {
        setBreadcrumb("AI Copilot", "Intelligence");
        content.innerHTML = await aiDashboardView();
        bindDashboard();
        bindApexAssistant();
      }
      return;
    }
    if (parts[0] === "developer") {
      setBreadcrumb("Developer Hub", "Administration");
      content.innerHTML = await developerHubView();
      bindDeveloperHub();
      return;
    }
    if (parts[0] === "security") {
      setBreadcrumb("Security Administration", "Administration");
      content.innerHTML = await securityAdminView();
      bindSecurityAdmin();
      return;
    }
    if (parts[0] === "cpq") {
      setBreadcrumb("CPQ Workspace", "Sales & Inventory");
      content.innerHTML = await cpqView();
      bindCPQ();
      return;
    }
    if (parts[0] === "setup-console") {
      setBreadcrumb("Setup Console", "Administration");
      content.innerHTML = await setupConsoleView(parts[1] || "modules");
      bindSetupConsole();
      return;
    }
    if (parts[0] === "setup") {
      const resource = parts[1] || "index";
      setBreadcrumb(resource === "index" ? "Setup" : titleCase(resource), "Setup");
      content.innerHTML = await setupView(resource);
      bindSettings();
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
    if (parts[0] === "reports") {
      setBreadcrumb("Reports", "Analytics");
      content.innerHTML = await reportEngineView();
      bindReportDashboard();
      return;
    }
    if (parts[0] === "dashboards") {
      setBreadcrumb("Dashboards", "Analytics");
      content.innerHTML = await dashboardBuilderView(parts[1] ? Number(parts[1]) : null);
      bindReportDashboard();
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

async function teamspacesView() {
  const data = await api("/api/teamspaces");
  const items = data.items || [];
  return `${pageHeader("Workspace", "Teamspaces", "Organize modules, people, and work around the teams that use Yash CRM.")}
    <div class="teamspaces-layout">
      <section class="card settings-section"><div class="settings-section-head"><h2>Create a teamspace</h2><p>Give a group a focused workspace without changing the underlying CRM records.</p></div>
        <form data-teamspace-form class="settings-form"><div class="form-grid"><div class="field"><label>Name</label><input class="field-input" name="name" required placeholder="Revenue team" /></div><div class="field"><label>Icon</label><input class="field-input" name="icon" value="◈" maxlength="4" /></div><div class="field field-full"><label>Description</label><textarea class="field-input" name="description" rows="3" placeholder="What this teamspace is for"></textarea></div></div><div class="form-actions"><button class="button button-primary" type="submit">Create teamspace</button></div></form>
      </section>
      <section class="card settings-section"><div class="settings-section-head"><h2>Your teamspaces</h2><p>${items.length} active workspace${items.length === 1 ? "" : "s"} with shared module context.</p></div><div class="teamspace-list">${items.length ? items.map((item) => `<article class="teamspace-card"><div class="teamspace-icon">${esc(item.icon || "◈")}</div><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(item.description || "No description yet")}</small><small>${item.members?.length || 0} member${item.members?.length === 1 ? "" : "s"} · ${(item.modules || []).length} module${(item.modules || []).length === 1 ? "" : "s"}</small></div><button class="button button-small button-ghost" data-teamspace-open="${item.id}">Open</button></article>`).join("") : emptyState("◈", "No teamspaces yet", "Create a workspace for a sales, support, or operations group.")}</div></section>
    </div>`;
}

function bindTeamspaces() {
  $("[data-teamspace-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await api("/api/teamspaces", { method: "POST", body: JSON.stringify(readForm(event.currentTarget)) }); toast("Teamspace created", "The new workspace is ready for your team."); await navigate("/teamspaces", true); }
    catch (error) { toast("Could not create teamspace", error.message, "error"); }
  });
  $$('[data-teamspace-open]').forEach((button) => button.addEventListener("click", async () => {
    const item = await api(`/api/teamspaces/${button.dataset.teamspaceOpen}`);
    toast(item.name, `${item.members.length} members · ${(item.modules || []).length} modules`, "success");
  }));
}

async function dashboardView() {
  const data = await api("/api/dashboard");
  const metrics = data.metrics;
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

function reportResultHtml(result) {
  if (!result) return "";
  if (result.error) return `<div class="empty-state"><span class="empty-icon">!</span><h3>Widget unavailable</h3><p>${esc(result.error)}</p></div>`;
  const rows = result.rows || [];
  const columns = result.group_by ? [...new Set([result.group_by, "count", result.aggregate?.operation].filter(Boolean))] : (result.columns || []);
  return `<div class="report-result-meta"><span>${result.total} row${result.total === 1 ? "" : "s"}${result.truncated ? " · limited to 500" : ""}</span><span>${esc(result.module || "")}${result.group_by ? ` · grouped by ${esc(result.group_by)}` : ""}</span></div>${rows.length ? `<div class="table-wrap"><table class="data-table"><thead><tr>${columns.map((column) => `<th>${esc(column)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${typeof row[column] === "number" && ["amount", "sum", "avg", "min", "max"].includes(column) ? formatMoney(row[column]) : esc(row[column] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : emptyState("◎", "No matching records", "Adjust the report filters or add CRM records.")}`;
}

async function reportEngineView() {
  const data = await api("/api/platform/reports?limit=100&sort=name_asc");
  const reportRows = data.items.length ? data.items.map((report) => `<div class="rule-row"><span class="related-dot">▤</span><div class="rule-info"><strong>${esc(report.name)}</strong><small>${esc(report.module || report.data?.module || "deals")} · ${esc(report.report_type || report.data?.report_type || "Tabular")} · ${report.data?.columns?.length || 0} columns</small></div>${badge(report.status)}<button class="button button-small button-ghost" data-run-report="${report.id}">Run</button><button class="table-action" data-report-edit="${report.id}">✎</button></div>`).join("") : emptyState("▤", "No saved reports", "Create a report definition to query CRM records.");
  return `${pageHeader("Analytics", "Report Engine", "Build secure, reusable reports over CRM modules with filters, grouping, and aggregates.", `<button class="button button-primary" data-new-report>＋ New report</button>`)}<div class="analytics-layout"><section class="card settings-section"><div class="settings-section-head"><h2>Saved reports</h2><p>Definitions are stored as metadata and executed through the server-side Report Engine.</p></div>${reportRows}</section><section class="card settings-section" data-report-editor hidden><div class="settings-section-head"><h2>Report definition</h2><p>Use API names for fields. Filters accept equals, contains, comparisons, and empty checks.</p></div><form data-report-form class="settings-form"><input type="hidden" name="id" /><div class="form-grid"><div class="field"><label>Name</label><input class="field-input" name="name" required placeholder="Open pipeline by stage" /></div><div class="field"><label>Module</label><select class="field-select" name="module"><option value="deals">Deals</option><option value="leads">Leads</option><option value="accounts">Accounts</option><option value="contacts">Contacts</option><option value="quotes">Quotes</option><option value="invoices">Invoices</option></select></div><div class="field"><label>Type</label><select class="field-select" name="report_type"><option>Tabular</option><option>Summary</option><option>Matrix</option></select></div><div class="field"><label>Group by</label><input class="field-input" name="group_by" placeholder="stage" /></div><div class="field field-full"><label>Columns (JSON)</label><textarea class="field-input" name="columns" rows="2">["name","status","amount","owner_name"]</textarea></div><div class="field field-full"><label>Filters (JSON)</label><textarea class="field-input" name="filters" rows="3">[]</textarea></div><div class="field"><label>Aggregate (JSON)</label><input class="field-input" name="aggregate" placeholder='{"field":"amount","operation":"sum"}' /></div></div><div class="form-actions"><button class="button button-primary" type="submit">Save report</button><button class="button button-ghost" type="button" data-close-report>Cancel</button></div></form></section></div><section class="card settings-section" data-report-output hidden><div class="settings-section-head"><h2>Report output</h2><p data-report-run-meta></p></div><div data-report-result></div></section>`;
}

async function dashboardBuilderView(dashboardId) {
  const [dashboards, reports] = await Promise.all([api("/api/platform/dashboards?limit=100&sort=name_asc"), api("/api/platform/reports?limit=100&sort=name_asc")]);
  const selected = dashboardId ? dashboards.items.find((item) => Number(item.id) === dashboardId) : null;
  const definition = selected?.data || {};
  const components = definition.components || definition.widgets || [];
  const list = dashboards.items.length ? dashboards.items.map((item) => `<div class="rule-row"><span class="related-dot">▦</span><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(item.audience || item.data?.audience || "Shared dashboard")} · ${(item.data?.components || item.data?.widgets || []).length} widgets</small></div><button class="button button-small button-ghost" data-open-dashboard="${item.id}">Open</button></div>`).join("") : emptyState("▦", "No dashboards", "Create a dashboard from saved reports.");
  return `${pageHeader("Analytics", "Dashboard Builder", "Compose a custom dashboard from saved reports and configure each widget's layout.", `<button class="button button-primary" data-new-dashboard>＋ New dashboard</button>`)}<div class="analytics-layout"><section class="card settings-section"><div class="settings-section-head"><h2>Dashboards</h2><p>${dashboards.total} saved dashboard${dashboards.total === 1 ? "" : "s"}.</p></div>${list}</section><section class="card settings-section"><div class="settings-section-head"><h2>${selected ? "Edit dashboard" : "Create dashboard"}</h2><p>Add one widget per line using the selected saved report.</p></div><form data-dashboard-form class="settings-form"><input type="hidden" name="id" value="${selected?.id || ""}" /><div class="form-grid"><div class="field"><label>Name</label><input class="field-input" name="name" required value="${esc(selected?.name || "Sales leadership")}" /></div><div class="field"><label>Audience</label><input class="field-input" name="audience" value="${esc(definition.audience || "Sales team")}" /></div><div class="field field-full"><label>Widgets (JSON)</label><textarea class="field-input" name="components" rows="8">${esc(JSON.stringify(components.length ? components : [{type:"table", title:"Open pipeline", report_id: reports.items[0]?.id || 0, width: 6}], null, 2))}</textarea><small class="field-hint">Example: [{"type":"table","title":"Open pipeline","report_id":1,"width":6}]</small></div></div><div class="form-actions"><button class="button button-primary" type="submit">Save dashboard</button>${selected ? `<button type="button" class="button button-ghost" data-preview-dashboard="${selected.id}">Preview</button>` : ""}</div></form></section></div>${selected ? `<section class="card settings-section" data-dashboard-output><div class="settings-section-head"><h2>Dashboard preview</h2><p>Live widget output from saved report definitions.</p></div><div data-dashboard-widgets>${emptyState("▦", "Preview not loaded", "Save or preview this dashboard.")}</div></section>` : ""}`;
}

function reportFormPayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  for (const key of ["columns", "filters", "aggregate"]) {
    if (!String(data[key] || "").trim()) { data[key] = key === "columns" ? [] : key === "filters" ? [] : null; continue; }
    try { data[key] = JSON.parse(data[key]); } catch { throw new Error(`${titleCase(key)} must be valid JSON.`); }
  }
  data.status = "Active";
  return data;
}

function dashboardFormPayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try { data.components = JSON.parse(data.components); } catch { throw new Error("Widgets must be valid JSON."); }
  if (!Array.isArray(data.components)) throw new Error("Widgets must be a JSON list.");
  data.status = "Active";
  return data;
}

function bindReportDashboard() {
  $(`[data-new-report]`)?.addEventListener("click", () => { const editor = $(`[data-report-editor]`); editor.hidden = false; editor.scrollIntoView({behavior:"smooth", block:"start"}); });
  $(`[data-close-report]`)?.addEventListener("click", () => { $(`[data-report-editor]`).hidden = true; });
  $$(`[data-run-report]`).forEach((button) => button.addEventListener("click", async () => { try { const result = await api(`/api/reports/${button.dataset.runReport}/run`, {method:"POST", body:"{}"}); const output = $(`[data-report-output]`); output.hidden = false; $(`[data-report-run-meta]`).textContent = `${result.total} rows · run #${result.run.id}`; $(`[data-report-result]`).innerHTML = reportResultHtml(result); output.scrollIntoView({behavior:"smooth", block:"start"}); } catch (error) { toast("Report failed", error.message, "error"); } }));
  $$(`[data-report-edit]`).forEach((button) => button.addEventListener("click", async () => { try { const report = await api(`/api/platform/reports/${button.dataset.reportEdit}`); const editor = $(`[data-report-editor]`); editor.hidden = false; const form = $(`[data-report-form]`); form.elements.id.value = report.id; form.elements.name.value = report.name || ""; form.elements.module.value = report.module || "deals"; form.elements.report_type.value = report.report_type || "Tabular"; form.elements.group_by.value = report.group_by || ""; form.elements.columns.value = JSON.stringify(report.columns || []); form.elements.filters.value = JSON.stringify(report.filters || [], null, 2); form.elements.aggregate.value = report.aggregate ? JSON.stringify(report.aggregate) : ""; editor.scrollIntoView({behavior:"smooth", block:"start"}); } catch (error) { toast("Could not open report", error.message, "error"); } }));
  $(`[data-report-form]`)?.addEventListener("submit", async (event) => { event.preventDefault(); try { const data = reportFormPayload(event.currentTarget); const id = data.id; delete data.id; await api(`/api/platform/reports${id ? `/${id}` : ""}`, {method:id ? "PATCH" : "POST", body:JSON.stringify(data)}); toast("Report saved", "The report definition is ready to run."); await navigate("/reports", true); } catch (error) { toast("Could not save report", error.message, "error"); } });
  $$(`[data-open-dashboard]`).forEach((button) => button.addEventListener("click", () => navigate(`/dashboards/${button.dataset.openDashboard}`)));
  $(`[data-new-dashboard]`)?.addEventListener("click", () => navigate("/dashboards"));
  $(`[data-dashboard-form]`)?.addEventListener("submit", async (event) => { event.preventDefault(); try { const data = dashboardFormPayload(event.currentTarget); const id = data.id; delete data.id; await api(`/api/platform/dashboards${id ? `/${id}` : ""}`, {method:id ? "PATCH" : "POST", body:JSON.stringify(data)}); toast("Dashboard saved", "Your custom dashboard layout is ready."); await navigate("/dashboards", true); } catch (error) { toast("Could not save dashboard", error.message, "error"); } });
  $(`[data-preview-dashboard]`)?.addEventListener("click", async (event) => { try { const result = await api(`/api/dashboards/${event.currentTarget.dataset.previewDashboard}/view`, {method:"POST", body:"{}"}); $(`[data-dashboard-widgets]`).innerHTML = result.widgets.length ? `<div class="dashboard-grid">${result.widgets.map((widget) => `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>${esc(widget.title)}</h2><small>${esc(widget.type)} · ${widget.result ? `${widget.result.total} rows` : "Unavailable"}</small></div></div><div class="card-body">${reportResultHtml(widget.result || widget)}</div></section>`).join("")}</div>` : emptyState("▦", "No widgets", "Add a report widget to preview this dashboard."); } catch (error) { toast("Preview failed", error.message, "error"); } });
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
  const current = state.moduleState[resource] || { search: "", status: "", owner_id: "", sort: "created_desc", min_amount: "", max_amount: "", close_from: "", close_to: "", offset: 0, view: "list", selectedIds: [] };
  state.moduleState[resource] = current;
  const broadView = ["kanban","grid","split","chart","timeline"].includes(current.view);
  const params = new URLSearchParams({ limit: broadView ? "100" : "25", offset: broadView ? "0" : String(current.offset) });
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
  const viewOptions = [["list","List"],["grid","Grid"],["split","Split"],["chart","Chart"],["timeline","Timeline"]];
  if (resource === "deals") viewOptions.splice(1,0,["kanban","Pipeline"]);
  const viewToggle = `<div class="view-toggle">${viewOptions.map(([key,label]) => `<button class="${current.view === key ? "active" : ""}" data-toggle-view="${key}">${label}</button>`).join('')}</div>`;
  let body = tableView(resource, data);
  if (current.view === "kanban" && resource === "deals") body = kanbanView(data.items);
  else if (current.view === "grid") body = gridView(resource, data);
  else if (current.view === "split") body = splitView(resource, data);
  else if (current.view === "chart") body = chartView(resource, data);
  else if (current.view === "timeline") body = timelineModuleView(resource, data);
  return `${pageHeader("Workspace / " + config.label, config.label, config.description, `${viewToggle}${actions}`)}
    <div class="module-toolbar"><label class="toolbar-search"><span>⌕</span><input data-module-search="${resource}" value="${esc(current.search)}" placeholder="${esc(config.search)}" /></label>${config.status.length ? `<select class="filter-select" data-module-status="${resource}"><option value="">All statuses</option>${config.status.map((option) => `<option ${current.status === option ? "selected" : ""}>${esc(option)}</option>`).join("")}</select>` : ""}<select class="filter-select" data-module-owner="${resource}"><option value="">All owners</option>${(state.meta?.users || []).map((user) => `<option value="${user.id}" ${String(current.owner_id) === String(user.id) ? "selected" : ""}>${esc(user.name)}</option>`).join("")}</select><select class="filter-select" data-module-sort="${resource}"><option value="created_desc" ${current.sort === "created_desc" ? "selected" : ""}>Recently added</option><option value="name_asc" ${current.sort === "name_asc" ? "selected" : ""}>Name A–Z</option>${resource === "deals" ? `<option value="amount_desc" ${current.sort === "amount_desc" ? "selected" : ""}>Amount high–low</option><option value="close_asc" ${current.sort === "close_asc" ? "selected" : ""}>Close date soonest</option>` : ""}${resource === "leads" ? `<option value="score_desc" ${current.sort === "score_desc" ? "selected" : ""}>Lead score high–low</option>` : ""}</select>${resource === "deals" ? `<input class="field-input" style="width:105px" data-deal-filter="min_amount" type="number" placeholder="Min amount" value="${esc(current.min_amount)}" /><input class="field-input" style="width:105px" data-deal-filter="max_amount" type="number" placeholder="Max amount" value="${esc(current.max_amount)}" /><input class="field-input" style="width:140px" data-deal-filter="close_from" type="date" value="${esc(current.close_from)}" /><input class="field-input" style="width:140px" data-deal-filter="close_to" type="date" value="${esc(current.close_to)}" />` : ""}<button class="button button-ghost button-small" data-clear-filters="${resource}">Clear filters</button>${resource === "leads" ? `<button class="button button-ghost button-small" data-bulk-archive="leads" ${current.selectedIds.length ? "" : "disabled"}>Archive selected${current.selectedIds.length ? ` (${current.selectedIds.length})` : ""}</button>` : ""}<span style="margin-left:auto;color:var(--text-faint);font-size:11px">${data.total} record${data.total === 1 ? "" : "s"}</span></div>
    ${body}
    ${current.view === "list" ? pagination(resource, data) : ""}`;
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
  let hiddenGroups = []; let hiddenItems = [];
  try { hiddenGroups = JSON.parse(localStorage.getItem('yash.setup.hidden_groups') || '[]'); hiddenItems = JSON.parse(localStorage.getItem('yash.setup.hidden_items') || '[]'); } catch (_) {}
  const groups = Object.entries(state.platformCatalog.setup_navigation || {}).filter(([group]) => !hiddenGroups.includes(group));
  return `<section class="card settings-nav"><div class="setup-quick-actions"><a href="/setup/search_setup" class="${active === "search_setup" ? "active" : ""}">Search Setup</a><a href="/setup/customize_setup" class="${active === "customize_setup" ? "active" : ""}">Customize Setup</a></div>${groups.map(([group, links]) => `<div data-setup-group="${esc(group)}"><span class="eyebrow" style="display:block;padding:12px 12px 5px">${esc(group)}</span>${links.filter(([resource]) => !hiddenItems.includes(resource)).map(([resource, label]) => `<a href="/setup/${resource}" class="${active === resource ? "active" : ""}">${esc(label)}</a>`).join("")}</div>`).join("")}</section>`;
}

function setupSearchView() {
  const groups = state.platformCatalog.setup_navigation || {};
  const cards = Object.entries(groups).map(([group, links]) => `<section class="card settings-section setup-search-group" data-search-group="${esc(group.toLowerCase())}"><div class="settings-section-head"><h2>${esc(group)}</h2><p>${links.length} configuration surface${links.length === 1 ? "" : "s"}</p></div><div class="setup-search-links">${links.map(([resource,label]) => `<a class="rule-row setup-search-item" href="/setup/${resource}" data-search-text="${esc(`${group} ${label} ${resource}`.toLowerCase())}"><span class="related-dot">›</span><div class="rule-info"><strong>${esc(label)}</strong><small>${esc(resource)}</small></div><span class="table-action">Open</span></a>`).join("")}</div></section>`).join("");
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Search Setup</h2><p>Search every registered Yash CRM setup option.</p></div><label class="toolbar-search setup-global-search"><span>⌕</span><input data-setup-search-input placeholder="Search settings, channels, security, Apex, developer tools…" autofocus /></label><p class="related-empty" data-setup-search-count>Type to filter ${Object.values(groups).flat().length} setup options.</p></section><div data-setup-search-results>${cards}</div>`;
}

async function customizeSetupView() {
  let record = null;
  try { const data = await api('/api/platform/setup_preferences?limit=1'); record = data.items?.[0] || null; } catch (_) {}
  const hiddenGroups = new Set(record?.hidden_groups || []);
  const hiddenItems = new Set(record?.hidden_items || []);
  const rows = Object.entries(state.platformCatalog.setup_navigation || {}).map(([group, links]) => `<section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>${esc(group)}</h2><p>Show or hide this group and its items without deleting configuration.</p></div><label class="setup-check"><input type="checkbox" data-setup-group-visible="${esc(group)}" ${hiddenGroups.has(group) ? '' : 'checked'} /> Visible</label></div>${links.map(([resource,label]) => `<label class="rule-row setup-toggle-row"><span class="related-dot">◈</span><div class="rule-info"><strong>${esc(label)}</strong><small>${esc(resource)}</small></div><input type="checkbox" data-setup-item-visible="${esc(resource)}" ${hiddenItems.has(resource) ? '' : 'checked'} /></label>`).join('')}</section>`).join('');
  return `<section class="foundation-note">Customize Setup changes navigation visibility only. Existing configuration and records are preserved.</section><form data-customize-setup-form data-pref-id="${record?.id || ''}">${rows}<div class="form-actions"><button class="button button-primary" type="submit">Save Setup Navigation</button></div></form>`;
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

async function workflowRulesView() {
  const [rules, executions] = await Promise.all([platformPanel("workflow_rules", true), api("/api/automation/executions?limit=100")]);
  const rows = executions.items.length ? executions.items.map((item) => `<div class="rule-row"><span class="related-dot">${item.status === "completed" ? "✓" : item.status === "queued" ? "◷" : "!"}</span><div class="rule-info"><strong>Execution #${item.id} · ${esc(item.resource)} #${item.record_id}</strong><small>${esc(item.event)} · ${esc(item.status)} · ${item.scheduled_for ? `scheduled ${formatDateTime(item.scheduled_for)}` : formatDateTime(item.created_at)}</small></div>${badge(titleCase(item.status))}${item.status === "queued" ? `<button class="button button-small button-ghost" data-run-workflow="${item.id}">Run now</button>` : ""}</div>`).join("") : emptyState("◷", "No workflow executions yet", "Create a rule and trigger it from a CRM record.");
  return `${rules}<section class="card settings-section"><div class="settings-section-head"><h2>Execution history</h2><p>Every workflow run is idempotent, auditable, and queued when external delivery is required.</p></div>${rows}</section>`;
}

async function securityAdminView() {
  const data = await api("/api/security/overview");
  const configCard = (title, resource, items, description) => `<section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>${esc(title)}</h2><p>${esc(description)}</p></div><button class="button button-primary button-small" data-platform-create="${resource}">＋ Add</button></div>${items.length ? items.map((item) => `<div class="rule-row"><span class="related-dot">◈</span><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(item.data_scope || item.module || item.status || "Configured")} · updated ${formatDateTime(item.updated_at)}</small></div>${badge(item.status || "Active")}<a class="table-action" href="/setup/${resource}">›</a></div>`).join("") : `<p class="related-empty">No ${title.toLowerCase()} configured yet.</p>`}</section>`;
  const audit = data.audit.length ? `<div class="audit-list">${data.audit.map((item) => `<div class="audit-row"><small>${formatDateTime(item.occurred_at)}</small>${badge(titleCase(item.action))}<div><strong>${esc(item.summary)}</strong><small>${esc(item.resource)}${item.record_id ? ` · #${item.record_id}` : ""}</small></div></div>`).join("")}</div>` : emptyState("A", "No audit events", "Security and configuration changes will appear here.");
  const fieldSecurity = data.field_security.length ? data.field_security.map((module) => `<div class="rule-row"><span class="related-dot">ƒ</span><div class="rule-info"><strong>${esc(module.label)}</strong><small>${module.fields.length} metadata field${module.fields.length === 1 ? "" : "s"} with visibility and permission rules</small></div><a class="table-action" href="/setup-console/modules">Open</a></div>`).join("") : `<p class="related-empty">No custom field-security definitions yet.</p>`;
  return `${pageHeader("Administration", "Security Administration", "Control hierarchy, permissions, record sharing, field visibility, and audit evidence.", `<button class="button button-primary" data-go="/setup/roles">Open Setup Directory</button>`)}<section class="security-callout"><strong>Server-side controls</strong><span>Roles define visibility. Profiles define capability. Sharing rules extend access. Field security is carried into forms, reports, exports, and APIs.</span></section><div class="security-grid">${configCard("Roles", "roles", data.roles, "Define hierarchical record visibility and manager scope.")}${configCard("Profiles", "profiles", data.profiles, "Bundle module, setup, import, export, and developer permissions.")}${configCard("Data Sharing", "sharing_rules", data.sharing_rules, "Configure private, public read-only, public read/write, and role-based sharing.")}${configCard("Permission Sets", "permissions", data.permissions, "Assign granular grants for modules and administrative surfaces.")}</div><section class="card settings-section"><div class="settings-section-head"><h2>Field security</h2><p>Review field-level visibility and permission metadata applied to configurable modules.</p></div>${fieldSecurity}</section><section class="card settings-section"><div class="settings-section-head"><h2>Audit Log</h2><p>Immutable records of create, update, delete, ownership, permission, workflow, import, export, API, and security changes.</p></div>${audit}</section>`;
}

async function cpqView() {
  const data = await api("/api/cpq/catalog");
  const products = data.products.length ? data.products.map((product) => `<div class="cpq-product-row"><label><input type="checkbox" data-cpq-product="${product.id}" /><span><strong>${esc(product.name)}</strong><small>${esc(product.sku || product.category || "No SKU")} · ${formatMoney(product.unit_price)}</small></span></label><input class="field-input cpq-qty" data-cpq-qty="${product.id}" type="number" min="1" value="1" disabled /></div>`).join("") : `<p class="related-empty">No active products are available. Add products before configuring a quote.</p>`;
  const rules = data.price_rules.length ? data.price_rules.map((rule) => `<div class="rule-row"><span class="related-dot">%</span><div class="rule-info"><strong>${esc(rule.name)}</strong><small>${esc(rule.action_type || "Adjustment")} · ${esc(rule.scope || "All")} · priority ${esc(rule.priority || "100")}</small></div>${badge(rule.status || "Active")}<a class="table-action" href="/setup/price_rules">›</a></div>`).join("") : `<p class="related-empty">No active price rules. Prices will use product list prices.</p>`;
  return `${pageHeader("Sales & Inventory", "CPQ Workspace", "Configure products, apply transparent price rules, and create quote-ready pricing in one controlled flow.", `<button class="button button-primary" data-go="/setup/price_rules">Manage Price Rules</button>`)}<div class="cpq-layout"><section class="card settings-section"><div class="settings-section-head"><h2>Product Configurator</h2><p>Select products and quantities. Price rules are applied server-side and shown line by line.</p></div><form data-cpq-form><div class="cpq-product-list">${products}</div><div class="form-grid cpq-controls"><div class="field"><label>Customer type</label><select class="field-select" name="customer_type"><option value="">Not specified</option><option>Enterprise</option><option>SMB</option><option>Partner</option></select></div><div class="field"><label>Tax rate (%)</label><input class="field-input" name="tax_rate" type="number" min="0" step="0.01" value="18" /></div></div><div class="form-actions"><button class="button button-primary" type="submit">Calculate price</button></div></form><div data-cpq-output class="cpq-output"></div></section><section><section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>Price Rules</h2><p>Ordered discounts, markups, and fixed adjustments.</p></div><button class="button button-ghost button-small" data-platform-create="price_rules">＋ Add rule</button></div>${rules}</section><section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>Configurators</h2><p>Product dependencies and guided selling flows.</p></div><button class="button button-ghost button-small" data-platform-create="product_configurators">＋ Add</button></div>${data.configurators.length ? data.configurators.map((item) => `<div class="rule-row"><span class="related-dot">▦</span><div class="rule-info"><strong>${esc(item.name)}</strong><small>Product #${esc(item.product_id || "—")} · ${esc(item.status || "Draft")}</small></div>${badge(item.status || "Draft")}</div>`).join("") : `<p class="related-empty">No product configurators defined yet.</p>`}</section></section></div>`;
}

function bindSecurityAdmin() {
  $$(`[data-platform-create]`).forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
}

function bindCPQ() {
  $$(`[data-platform-create]`).forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
  $$(`[data-cpq-product]`).forEach((checkbox) => checkbox.addEventListener("change", () => { const qty = $(`[data-cpq-qty="${checkbox.dataset.cpqProduct}"]`); if (qty) qty.disabled = !checkbox.checked; }));
  $(`[data-cpq-form]`)?.addEventListener("submit", async (event) => { event.preventDefault(); const lines = $$(`[data-cpq-product]:checked`).map((checkbox) => ({product_id:Number(checkbox.dataset.cpqProduct), quantity:Number($(`[data-cpq-qty="${checkbox.dataset.cpqProduct}"]`)?.value || 1)})); const form = event.currentTarget; if (!lines.length) return toast("Select products", "Choose at least one product before calculating.", "error"); try { const pricing = await api("/api/cpq/price", {method:"POST", body:JSON.stringify({lines, context:{customer_type:form.elements.customer_type.value}, tax_rate:Number(form.elements.tax_rate.value || 0)})}); $(`[data-cpq-output]`).innerHTML = `<div class="cpq-result"><div class="cpq-total"><span>Total</span><strong>${formatMoney(pricing.total)}</strong><small>${esc(pricing.currency)} · ${pricing.applied_rule_count} price rule${pricing.applied_rule_count === 1 ? "" : "s"} applied</small></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Product</th><th>Qty</th><th>Base</th><th>Adjustments</th><th>Total</th></tr></thead><tbody>${pricing.lines.map((line) => `<tr><td><strong>${esc(line.name)}</strong><span class="sub-cell">${esc(line.sku || "")}</span></td><td>${line.quantity}</td><td>${formatMoney(line.base_total)}</td><td>${line.adjustments.length ? line.adjustments.map((item) => `<span class="table-subtext">${esc(item.rule)}: ${formatMoney(item.delta)}</span>`).join("") : "—"}</td><td><strong>${formatMoney(line.total)}</strong></td></tr>`).join("")}</tbody></table></div><form data-cpq-quote-form class="form-grid"><div class="field"><label>Quote name</label><input class="field-input" name="name" value="CPQ quote" required /></div><div class="field"><label>Terms</label><input class="field-input" name="terms" value="Prices valid for 30 days." /></div><div class="form-actions field-full"><button class="button button-primary" type="submit">Create draft quote</button></div></form></div>`; $(`[data-cpq-quote-form]`)?.addEventListener("submit", async (quoteEvent) => { quoteEvent.preventDefault(); const quoteForm = quoteEvent.currentTarget; try { const created = await api("/api/cpq/quotes", {method:"POST", body:JSON.stringify({lines, context:{customer_type:form.elements.customer_type.value}, tax_rate:Number(form.elements.tax_rate.value || 0), name:quoteForm.elements.name.value, terms:quoteForm.elements.terms.value})}); toast("Draft quote created", `${created.quote.quote_number || `Quote #${created.quote.id}`} · ${formatMoney(created.quote.amount)}`); } catch (error) { toast("Could not create quote", error.message, "error"); } }); } catch (error) { $(`[data-cpq-output]`).innerHTML = `<p class="apex-error">${esc(error.message)}</p>`; } });
}

async function developerHubView() {
  const [manifest, servers, tools, connections, functions] = await Promise.all([api("/api/developer/manifest"), api("/api/platform/mcp_servers?limit=100"), api("/api/platform/mcp_tools?limit=100"), api("/api/platform/connections?limit=100"), api("/api/platform/functions?limit=100")]);
  const stat = (label, value, detail) => `<article class="card developer-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`;
  const rows = manifest.endpoints.map((item) => `<tr><td><span class="method-pill ${item.method.toLowerCase()}">${item.method}</span></td><td><code>${esc(item.path)}</code></td><td>${esc(item.description)}</td></tr>`).join("");
  const resourceCard = (label, resource, data, icon) => `<section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>${icon} ${esc(label)}</h2><p>${data.total} configured record${data.total === 1 ? "" : "s"}.</p></div><button class="button button-primary button-small" data-platform-create="${resource}">＋ Add</button></div>${data.items.length ? data.items.slice(0, 5).map((item) => `<div class="rule-row"><span class="related-dot">${icon}</span><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(item.status || "Draft")} · updated ${formatDateTime(item.updated_at)}</small></div>${badge(item.status || "Draft")}<a class="table-action" href="/setup/${resource}">›</a></div>`).join("") : emptyState("◎", `No ${label.toLowerCase()} configured`, `Add a ${label.toLowerCase().replace(/s$/, "")} to make this surface available.`)}</section>`;
  return `${pageHeader("Administration", "Developer Hub", "Build secure integrations, MCP tools, REST clients, SDKs, functions, and data-model extensions.", `<button class="button button-primary" data-go="/setup-console/modules">Open Setup Console</button>`)}<section class="developer-stats">${stat("API version", manifest.api.version, manifest.api.base_path)}${stat("MCP servers", servers.total, "approved server registrations")}${stat("MCP tools", tools.total, "scoped agent tools")}${stat("Connections", connections.total, "secret references only")}${stat("Functions", functions.total, "server-side definitions")}</section><div class="developer-grid">${resourceCard("MCP Servers", "mcp_servers", servers, "⌘")}${resourceCard("MCP Tools", "mcp_tools", tools, "◆")}</div><section class="card settings-section"><div class="settings-section-head settings-heading-row"><div><h2>REST API Explorer</h2><p>Versioned contracts, supported scopes, and safe endpoint descriptions.</p></div><select class="field-select developer-sdk-select" data-developer-sdk><option value="python">Python SDK</option><option value="javascript">JavaScript SDK</option><option value="curl">cURL</option></select></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead><tbody>${rows}</tbody></table></div><div class="developer-sdk-output" data-developer-sdk-output><pre>Loading SDK example…</pre></div><p class="field-hint">Scopes: ${manifest.api.scopes.map((scope) => `<code>${esc(scope)}</code>`).join(" · ")} · Credentials remain outside source control.</p></section><div class="developer-grid">${resourceCard("Connections", "connections", connections, "↔")}${resourceCard("Functions", "functions", functions, "ƒ")}</div>`;
}

async function setupConsoleView() {
  const data = await api("/api/admin/metadata/modules");
  const moduleRows = data.items.length ? data.items.map((module) => `<section class="card setup-module-card"><div class="settings-section-head settings-heading-row"><div><h2>${esc(module.label)}</h2><p><code>${esc(module.api_name)}</code> · ${esc(module.description || "No description")}</p></div><span class="status-dot ${module.enabled ? "active" : "inactive"}">${module.enabled ? "Enabled" : "Disabled"}</span></div><div class="metadata-field-table"><div class="metadata-field-head"><span>Field</span><span>Type</span><span>Rules</span><span>Visibility</span></div>${module.fields.length ? module.fields.map((field) => `<div class="metadata-field-row"><strong>${esc(field.label)}<small>${esc(field.api_name)}</small></strong><span>${esc(field.field_type)}</span><span>${field.required ? "Required" : "Optional"}${field.read_only ? " · Read only" : ""}</span><span>${esc(JSON.stringify(field.visibility || {}))}</span></div>`).join("") : `<p class="related-empty">No custom fields yet.</p>`}</div><div class="setup-module-actions"><button class="button button-ghost button-small" data-add-metadata-field="${module.id}">＋ Add field</button><button class="button button-ghost button-small" data-add-metadata-layout="${module.id}">＋ Add layout</button><button class="button button-ghost button-small" data-add-metadata-view="${module.id}">＋ Add view</button></div></section>`).join("") : emptyState("◇", "No custom modules", "Create your first metadata-driven module below.");
  return `${pageHeader("Administration", "Setup Console", "Customize modules and fields with API names, validation, permissions, layouts, and saved views.", `<button class="button button-primary" data-focus-module-form>＋ New module</button>`)}<div class="setup-console-grid"><div>${moduleRows}</div><section class="card settings-section" data-module-form-card><div class="settings-section-head"><h2>New module</h2><p>Module definitions are stored in metadata tables and can be consumed by APIs, views, and AI agents.</p></div><form class="settings-form" data-metadata-module-form><div class="form-grid"><div class="field"><label>Label</label><input class="field-input" name="label" required placeholder="Service Requests" /></div><div class="field"><label>API name</label><input class="field-input" name="api_name" required pattern="[a-z][a-z0-9_]*" placeholder="service_requests" /></div><div class="field"><label>Plural label</label><input class="field-input" name="plural_label" placeholder="Service Requests" /></div><div class="field field-full"><label>Description</label><textarea class="field-textarea" name="description" rows="3"></textarea></div></div><div class="form-actions"><button class="button button-primary" type="submit">Create module</button></div></form></section></div><section class="card settings-section"><div class="settings-section-head"><h2>Field types and capabilities</h2><p>Supported metadata fields include text, rich text, numbers, currency, dates, picklists, lookups, formulas, files, images, and subforms.</p></div><div class="setup-capability-list"><span>Required / read-only</span><span>Unique values</span><span>Defaults</span><span>Validation rules</span><span>Field permissions</span><span>Layout visibility</span></div></section>`;
}

function bindDeveloperHub() {
  $$(`[data-platform-create]`).forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
  const select = $(`[data-developer-sdk]`), output = $(`[data-developer-sdk-output]`);
  const loadSdk = async () => { if (!select || !output) return; try { const data = await api(`/api/developer/sdk/${select.value}`); output.innerHTML = `<pre>${esc(data.code)}</pre>`; } catch (error) { output.innerHTML = `<p class="apex-error">${esc(error.message)}</p>`; } };
  select?.addEventListener("change", loadSdk); loadSdk();
}

function bindSetupConsole() {
  $(`[data-focus-module-form]`)?.addEventListener("click", () => $(`[data-module-form-card]`)?.scrollIntoView({behavior:"smooth"}));
  $(`[data-metadata-module-form]`)?.addEventListener("submit", async (event) => { event.preventDefault(); try { await api("/api/admin/metadata/modules", {method:"POST", body:JSON.stringify(Object.fromEntries(new FormData(event.currentTarget).entries()))}); toast("Module created", "The metadata module is ready for fields and layouts."); await navigate("/setup-console/modules", true); } catch (error) { toast("Could not create module", error.message, "error"); } });
  $$(`[data-add-metadata-field]`).forEach((button) => button.addEventListener("click", async () => { const label = window.prompt("Field label:"); if (!label) return; const apiName = window.prompt("Field API name:", label.toLowerCase().replace(/[^a-z0-9]+/g, "_")); if (!apiName) return; const type = window.prompt("Field type (text, number, currency, date, picklist, lookup):", "text"); try { await api(`/api/admin/metadata/modules/${button.dataset.addMetadataField}/fields`, {method:"POST", body:JSON.stringify({label, api_name:apiName, field_type:type || "text", position:0})}); toast("Field created", `${label} is available in the metadata model.`); await renderRoute(); } catch (error) { toast("Could not create field", error.message, "error"); } }));
  $$(`[data-add-metadata-layout]`).forEach((button) => button.addEventListener("click", async () => { const name = window.prompt("Layout name:", "Standard layout"); if (!name) return; try { await api(`/api/admin/metadata/modules/${button.dataset.addMetadataLayout}/layouts`, {method:"POST", body:JSON.stringify({name, sections:[]})}); toast("Layout created", "The layout is now stored in the metadata model."); await renderRoute(); } catch (error) { toast("Could not create layout", error.message, "error"); } }));
  $$(`[data-add-metadata-view]`).forEach((button) => button.addEventListener("click", async () => { const name = window.prompt("View name:", "My records"); if (!name) return; try { await api(`/api/admin/metadata/modules/${button.dataset.addMetadataView}/views`, {method:"POST", body:JSON.stringify({name, criteria:[], columns:[], sorting:[], visibility:{scope:"private"}})}); toast("View created", "The saved view is now available to the module engine."); await renderRoute(); } catch (error) { toast("Could not create view", error.message, "error"); } }));
}

function setupLandingView() {
  let hiddenGroups = []; let hiddenItems = [];
  try { hiddenGroups = JSON.parse(localStorage.getItem('yash.setup.hidden_groups') || '[]'); hiddenItems = JSON.parse(localStorage.getItem('yash.setup.hidden_items') || '[]'); } catch (_) {}
  const groups = Object.entries(state.platformCatalog.setup_navigation || {}).filter(([group]) => !hiddenGroups.includes(group));
  const cards = groups.map(([group, links]) => `<section class="card setup-hub-card setup-search-group" data-search-group="${esc(group.toLowerCase())}"><div class="setup-hub-head"><h2>${esc(group)}</h2></div><div class="setup-hub-links">${links.filter(([resource]) => !hiddenItems.includes(resource)).map(([resource, label]) => `<a href="/setup/${resource}" class="setup-hub-link setup-search-item" data-search-text="${esc(`${group} ${label} ${resource}`.toLowerCase())}">${esc(label)}</a>`).join("")}</div></section>`).join("");
  return `<section class="setup-page-shell"><div class="setup-toolbar"><div class="setup-toolbar-title">Setup</div><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input data-setup-search-input placeholder="Search Setup" autofocus /></label><button class="button button-ghost" data-go="/setup/customize_setup">Customize Setup</button></div><p class="related-empty setup-toolbar-note" data-setup-search-count>Browse ${Object.values(state.platformCatalog.setup_navigation || {}).flat().length} setup options.</p><div class="setup-hub-grid" data-setup-search-results>${cards}</div></section>`;
}

async function setupView(resource) {
  if (resource === 'index') return setupLandingView();
  let content;
  if (resource === "search_setup") content = setupSearchView();
  else if (resource === "customize_setup") content = await customizeSetupView();
  else if (resource === "personal_settings" || resource === "users") content = await profileUsersView();
  else if (resource === "approval_processes") content = await approvalSettingsView();
  else if (resource === "blueprints") content = await blueprintSettingsView();
  else if (resource === "workflow_rules") content = await workflowRulesView();
  else if (resource === "audit_log") content = await auditView();
  else if (resource === "recycle_bin") content = await recycleBinView();
  else if (resource === "import") content = importView();
  else if (resource === "export") content = exportView();
  else if (resource === "duplicates") content = duplicateView();
  else if (state.platformCatalog.resources[resource]) content = `<section class="foundation-note">This is a working foundation: records persist, validate, filter, sort, export, audit and recycle. External delivery, identity-provider enforcement and background scheduling require deployment-specific workers or integrations.</section>${await platformPanel(resource, true)}`;
  else content = `<section class="card">${emptyState("!", "Unknown setup page", "Choose a setup item from the directory.")}</section>`;
  return `<section class="setup-page-shell"><div class="setup-toolbar"><button class="button button-ghost button-small" data-go="/setup">← Back to Setup</button><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input data-setup-search-input placeholder="Search Setup" /></label><button class="button button-ghost" data-go="/setup/customize_setup">Customize Setup</button></div><div class="setup-workspace">${setupDirectory(resource)}<div class="settings-content">${content}</div></div></section>`;
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


function gridView(resource, data) {
  const config = MODULES[resource];
  if (!data.items.length) return `<section class="card">${emptyState(config.icon, `No ${config.label.toLowerCase()} found`, "Create a record or change filters.")}</section>`;
  return `<section class="record-grid">${data.items.map((row) => `<article class="card record-grid-card" data-open-record="${resource}" data-id="${row.id}"><div class="card-body"><span class="eyebrow">${esc(config.singular)} #${row.id}</span><h3>${esc(row.name || row.subject || row.full_name || row.title || `Record ${row.id}`)}</h3>${config.columns.slice(1,5).map((column) => `<p><small>${esc(column.label)}</small><strong>${esc(row[column.key] ?? '—')}</strong></p>`).join('')}</div></article>`).join('')}</section>`;
}

function splitView(resource, data) {
  const config = MODULES[resource];
  if (!data.items.length) return `<section class="card">${emptyState(config.icon, `No ${config.label.toLowerCase()} found`, "Create a record or change filters.")}</section>`;
  const first = data.items[0];
  return `<div class="module-split-view"><section class="card split-list">${data.items.map((row, index) => `<button class="related-item ${index === 0 ? 'active' : ''}" data-open-record="${resource}" data-id="${row.id}"><span class="related-dot">${esc(config.icon)}</span><span class="related-main"><strong>${esc(row.name || row.subject || row.full_name || row.title || `Record ${row.id}`)}</strong><small>${esc(row.status || row.stage || row.company || 'Active')}</small></span><span>›</span></button>`).join('')}</section><section class="card settings-section split-preview"><div class="settings-section-head"><h2>${esc(first.name || first.subject || first.full_name || first.title || `Record ${first.id}`)}</h2><p>Split preview. Open a row to view the full record and related lists.</p></div>${config.columns.map((column) => `<div class="rule-row"><div class="rule-info"><small>${esc(column.label)}</small><strong>${esc(first[column.key] ?? '—')}</strong></div></div>`).join('')}<div class="form-actions"><button class="button button-primary" data-open-record="${resource}" data-id="${first.id}">Open full record</button></div></section></div>`;
}

function chartView(resource, data) {
  const config = MODULES[resource];
  const key = resource === 'deals' ? 'stage' : 'status';
  const counts = {};
  data.items.forEach((row) => { const label = String(row[key] || 'Unspecified'); counts[label] = (counts[label] || 0) + 1; });
  const max = Math.max(1, ...Object.values(counts));
  return `<section class="card settings-section"><div class="settings-section-head"><h2>${esc(config.label)} distribution</h2><p>Current filtered records grouped by ${esc(key)}.</p></div><div class="pipeline-chart">${Object.entries(counts).map(([label,count]) => `<div class="pipeline-row"><span class="pipeline-label">${esc(label)}</span><div class="progress-track"><div class="progress-bar" style="width:${Math.max(4, Number(count) / max * 100)}%"></div></div><span class="pipeline-meta"><strong>${count}</strong> record${count === 1 ? '' : 's'}</span></div>`).join('') || `<p class="related-empty">No chart data available.</p>`}</div></section>`;
}

function timelineModuleView(resource, data) {
  const config = MODULES[resource];
  const rows = [...data.items].sort((a,b) => String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || '')));
  return `<section class="card settings-section"><div class="settings-section-head"><h2>${esc(config.label)} timeline</h2><p>Recent filtered records ordered by their latest change.</p></div><div class="activity-list">${rows.map((row) => `<button class="activity-item" data-open-record="${resource}" data-id="${row.id}"><span class="activity-icon task">${esc(config.icon)}</span><span class="activity-copy"><strong>${esc(row.name || row.subject || row.full_name || row.title || `Record ${row.id}`)}</strong><small>${esc(row.status || row.stage || 'Updated')}</small></span><span class="activity-time">${formatDateTime(row.updated_at || row.created_at)}</span></button>`).join('') || `<p class="related-empty">No timeline entries.</p>`}</div></section>`;
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
    <section class="card detail-summary"><div class="detail-title-row"><span class="detail-avatar">${initials(title)}</span><div class="detail-title-copy"><span class="eyebrow">${esc(config.singular)}</span><h2>${esc(title)}</h2><p>${esc(secondary || "No summary available")}</p></div><div class="detail-actions">${resource === "leads" && record.status !== "Converted" && !record.converted_contact_id ? `<button class="button button-small button-ghost" data-convert-lead="${id}">Convert</button>` : ""}<button class="button button-small button-ghost" data-delete-record="${resource}" data-id="${id}">Archive</button></div></div><div class="detail-meta-grid">${details.map((item) => `<div><span class="meta-label">${esc(item.label)}</span><span class="meta-value">${item.html || esc(item.value || "—")}</span></div>`).join("")}</div>${record.notes ? `<div class="notes-box"><h3>Notes</h3><p>${esc(record.notes)}</p></div>` : ""}</section>
    <div class="detail-record-layout"><aside class="detail-related-nav"><div class="detail-related-nav-head"><h3>Related List</h3></div>${relatedNavigation(resource, related)}</aside><section class="detail-record-main"><div class="detail-tab-strip"><button class="detail-tab active" type="button" data-detail-tab="overview">Overview</button><button class="detail-tab" type="button" data-detail-tab="timeline">Timeline</button></div><div class="detail-tab-panel" data-detail-panel="overview">${resource === "deals" ? `<section class="detail-plain-section" id="detail-section-stage_progress"><div class="detail-plain-head"><h3>Stage progress</h3></div><div class="detail-plain-body">${dealProgress(record)}</div></section>` : ""}${relatedContent(resource, related)}</div><div class="detail-tab-panel" data-detail-panel="timeline" hidden><section class="detail-plain-section" id="detail-section-timeline"><div class="detail-plain-head"><h3>Timeline</h3></div><div class="detail-plain-body"><div class="activity-list">${related.activities?.length ? related.activities.map(activityItem).join("") : `<p class="related-empty">No linked activity yet.</p>`}</div></div></section></div></section></div>`;
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

function relatedNavigation(resource, related) {
  const openActivities = (related.activities || []).filter((item) => item.status !== 'Completed').length;
  const closedActivities = (related.activities || []).filter((item) => item.status === 'Completed').length;
  const connectedCount = (related.accounts || []).length + (related.contacts || []).length + (related.deals || []).length;
  const items = [
    ['customer_journey', 'Customer journey', !!related.journey],
    ['notes', 'Notes', true],
    ['connected_records', 'Connected records', ['accounts', 'contacts', 'deals'].includes(resource) || connectedCount > 0],
    ['attachments', 'Attachments', true],
    ['products', 'Products', true],
    ['open_activities', 'Open activities', true, openActivities],
    ['closed_activities', 'Closed activities', closedActivities > 0, closedActivities],
    ['emails', 'Emails', true],
    ['timeline', 'Timeline', true],
  ].filter(([, , visible]) => visible);
  return `<nav class="detail-related-links">${items.map(([key, label, , count]) => `<button class="detail-related-link" type="button" data-detail-nav="${key}" data-detail-target="detail-section-${key}"><span>${esc(label)}</span>${count != null ? `<small>${count}</small>` : ''}</button>`).join('')}</nav>`;
}

function relatedPlainRow(title, meta, resource, id, navigable = true) {
  const action = navigable && MODULES[resource] ? `data-open-record="${resource}"` : `data-edit-record="${resource}"`;
  return `<button class="detail-related-row" ${action} data-id="${id}"><span class="detail-related-row-copy"><strong>${esc(title)}</strong><small>${esc(meta || '')}</small></span><span class="detail-related-row-action">${navigable && MODULES[resource] ? '›' : '✎'}</span></button>`;
}

function relatedPlainSection(id, label, rows, createResource, emptyMessage) {
  return `<section class="detail-plain-section" id="detail-section-${id}"><div class="detail-plain-head"><h3>${esc(label)}</h3>${createResource ? `<button class="card-head-link" data-create="${createResource}">Add</button>` : ''}</div><div class="detail-plain-body">${rows.length ? rows.join('') : `<p class="related-empty">${esc(emptyMessage)}</p>`}</div></section>`;
}

function relatedContent(resource, related) {
  const sections = [];
  if (related.journey) {
    const stages = related.journey.stages || [];
    sections.push(`<section class="detail-plain-section" id="detail-section-customer_journey"><div class="detail-plain-head"><h3>Customer journey</h3><span class="eyebrow">Lead to cash</span></div><div class="detail-plain-body"><div class="journey-track">${stages.map((stage) => `<span class="journey-stage ${stage.complete ? 'complete' : ''}"><i>${stage.complete ? '✓' : stage.count}</i><b>${esc(stage.label)}</b></span>`).join('')}</div><div class="journey-actions"><button class="button button-small button-ghost" data-platform-create="site_visits" data-lead-id="${related.journey.lead.id}">+ Site visit</button>${related.journey.lead.converted_deal_id ? `<button class="button button-small button-ghost" data-platform-create="quotes" data-deal-id="${related.journey.lead.converted_deal_id}">+ Quotation</button>` : ''}</div></div></section>`);
  }
  sections.push(relatedPlainSection('notes', 'Notes', (related.notes || []).map((item) => relatedPlainRow(item.title, item.content || 'Open note', 'notes', item.id, false)), 'notes', 'No notes yet.'));
  const connectedRows = [];
  if (related.accounts?.length) connectedRows.push(...related.accounts.map((item) => relatedPlainRow(item.name, item.industry || item.type || 'Account', 'accounts', item.id)));
  if (related.contacts?.length) connectedRows.push(...related.contacts.map((item) => relatedPlainRow(item.full_name || `${item.first_name} ${item.last_name}`, item.job_title || item.email || 'Contact', 'contacts', item.id)));
  if (related.deals?.length) connectedRows.push(...related.deals.map((item) => relatedPlainRow(item.name, `${formatMoney(item.amount)} · ${item.stage}`, 'deals', item.id)));
  sections.push(relatedPlainSection('connected_records', 'Connected records', connectedRows, null, 'No connected records found.'));
  sections.push(relatedPlainSection('attachments', 'Attachments', (related.attachments || []).map((item) => relatedPlainRow(item.name, `${item.file_type || 'File'} · ${item.file_size || 'Size not set'}`, 'attachments', item.id, false)), 'attachments', 'No attachments yet.'));
  sections.push(relatedPlainSection('products', 'Products', (related.products || []).map((item) => relatedPlainRow(item.name, `${formatMoney(item.unit_price)} · ${item.sku || 'No SKU'}`, 'products', item.id)), 'products', 'No products yet.'));
  sections.push(relatedPlainSection('open_activities', 'Open activities', (related.activities || []).filter((item) => item.status !== 'Completed').map((item) => relatedPlainRow(item.subject, `${titleCase(item.activity_type)} · ${formatDateTime(item.due_at)}`, 'activities', item.id)), 'activities', 'No open activities yet.'));
  const closedActivities = (related.activities || []).filter((item) => item.status === 'Completed').map((item) => relatedPlainRow(item.subject, `${titleCase(item.activity_type)} · completed ${formatDateTime(item.updated_at || item.due_at)}`, 'activities', item.id));
  if (closedActivities.length) sections.push(relatedPlainSection('closed_activities', 'Closed activities', closedActivities, 'activities', 'No closed activities yet.'));
  sections.push(relatedPlainSection('emails', 'Emails', (related.emails || []).map((item) => relatedPlainRow(item.subject, `${item.status} · ${item.to_email || 'No recipient'}`, 'emails', item.id, false)), 'emails', 'No email yet.'));
  return sections.join('');
}

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
  const showDetailTab = (tab) => {
    $$('[data-detail-tab]').forEach((button) => button.classList.toggle('active', button.dataset.detailTab === tab));
    $$('[data-detail-panel]').forEach((panel) => { panel.hidden = panel.dataset.detailPanel !== tab; });
  };
  $$('[data-detail-tab]').forEach((button) => button.addEventListener('click', () => showDetailTab(button.dataset.detailTab)));
  $$('[data-detail-nav]').forEach((button) => button.addEventListener('click', () => {
    const isTimeline = button.dataset.detailNav === 'timeline';
    showDetailTab(isTimeline ? 'timeline' : 'overview');
    requestAnimationFrame(() => {
      document.getElementById(button.dataset.detailTarget)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }));
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
    else if (input.dataset.json === "true" || ["conditions", "steps", "stages", "transitions", "transition_requirements", "criteria", "actions"].includes(input.name)) {
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
  if (["personal_settings", "users", "approval_processes", "blueprints", "search_setup", "customize_setup"].includes(resource)) bindSettings();
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
  const notificationsButton = $("#notifications-button");
  const notificationsPanel = $("#notifications-panel");
  notificationsButton?.addEventListener("click", async () => {
    const opening = notificationsPanel.hidden;
    notificationsPanel.hidden = !opening;
    notificationsButton.setAttribute("aria-expanded", String(opening));
    if (!opening) return;
    notificationsPanel.innerHTML = `<div class="notifications-loading">Loading notifications…</div>`;
    try {
      const data = await api("/api/notifications?limit=20");
      notificationsPanel.innerHTML = `<div class="notifications-head"><strong>Notifications</strong><span>${data.unread || 0} unread</span></div>${data.items?.length ? data.items.map((item) => `<button class="notification-row ${item.read_at ? "read" : "unread"}" data-notification-id="${item.id}"><span class="notification-kind">${item.kind === "error" ? "!" : "•"}</span><span><strong>${esc(item.title)}</strong><small>${esc(item.body || "")}</small></span></button>`).join("") : `<div class="notifications-empty">No notifications yet.</div>`}`;
      $$('[data-notification-id]', notificationsPanel).forEach((item) => item.addEventListener("click", async () => { await api(`/api/notifications/${item.dataset.notificationId}/read`, { method: "POST" }); item.classList.remove("unread"); item.classList.add("read"); }));
    } catch (error) { notificationsPanel.innerHTML = `<div class="notifications-empty">Could not load notifications.</div>`; }
  });
  const searchInput = $("#global-search"); let searchTimer;
  searchInput.addEventListener("input", () => { clearTimeout(searchTimer); if (!searchInput.value.trim()) { $("#search-results").classList.remove("open"); return; } searchTimer = setTimeout(async () => { try { const data = await api(`/api/search?q=${encodeURIComponent(searchInput.value)}`); const result = $("#search-results"); result.innerHTML = data.results.length ? data.results.map((item) => `<button class="search-result" data-search-route="/${item.resource}/${item.id}"><span class="result-icon">${MODULES[item.resource]?.icon || "◈"}</span><span><strong>${esc(item.label)}</strong><small>${esc(titleCase(item.resource))} · ${esc(item.meta || "")}</small></span></button>`).join("") : `<p style="padding:10px;color:var(--text-faint);font-size:11px">No matching records.</p>`; result.classList.add("open"); } catch (error) { /* search is best effort */ } }, 240); });
  document.addEventListener("click", (event) => { const result = event.target.closest("[data-search-route]"); if (result) { $("#search-results").classList.remove("open"); searchInput.value = ""; navigate(result.dataset.searchRoute); } else if (!event.target.closest("#global-search-wrap")) $("#search-results").classList.remove("open"); });
}

async function aiDashboardView() {
  const data = await api("/api/ai/dashboard");
  const totals = data.totals || {};
  const journey = data.journey || [];
  const performance = data.performance || {};
  const insight = data.insight;
  const stat = (label, value, detail, tone = "") => `<article class="card ai-cockpit-stat ${tone}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`;
  const journeyHtml = journey.map((item, index) => `<button class="ai-journey-stage" data-go="/${esc(item.key === "leads" ? "leads" : item.key === "conversations" ? "activities/tasks" : item.key)}"><span class="ai-journey-index">${index + 1}</span><strong>${esc(item.label)}</strong><small>${item.count} · ${esc(item.detail)}</small></button>`).join('<span class="ai-journey-arrow" aria-hidden="true">→</span>');
  const people = performance.people || [];
  const attention = performance.attention || {};
  const blockers = [
    ...(attention.stuck_leads || []).map((item) => `<button class="related-item" data-go="/leads/${item.id}"><span class="related-dot">!</span><span class="related-main"><strong>${esc(item.name)}</strong><small>Lead stuck at ${esc(item.status)}${item.next_follow_up ? ` · follow-up ${formatDate(item.next_follow_up)}` : ""}</small></span><span>›</span></button>`),
    ...(attention.quotes_needing_follow_up || []).map((item) => `<button class="related-item" data-go="/quotes"><span class="related-dot">₹</span><span class="related-main"><strong>${esc(item.name)}</strong><small>${esc(item.status)} · quotation needs follow-up</small></span><span>›</span></button>`),
  ].join("");
  const insightHtml = insight ? `<div class="ai-copilot-answer"><span class="eyebrow">GPT-4o mini · ${esc(insight.confidence || "advisory")} confidence</span><p>${esc(insight.answer || "").replace(/\n/g, "<br>")}</p>${(insight.actions || []).length ? `<strong>Recommended next actions</strong><ul>${insight.actions.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>` : ""}${(insight.risks || []).length ? `<strong>Risks and gaps</strong><ul>${insight.risks.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>` : ""}</div>` : `<div class="ai-copilot-answer ai-copilot-muted"><strong>GPT-4o mini is not connected</strong><p>${esc(data.insight_error || "Add the OpenAI configuration in Railway variables to enable management readouts.")}</p></div>`;
  return `${pageHeader("Intelligence", "Apex AI Copilot", "One source of truth for the complete Lead → Visit → Quotation → Invoice → Payment → Incentive journey.", `<button class="button button-ghost" data-go="/ai/exceptions">Quotation exceptions</button><button class="button button-primary" data-go="/settings/general">Settings &amp; General Setup</button>`)}
    <section class="card apex-assistant-card"><div class="card-head"><div class="card-head-copy"><h2>Ask APEX</h2><small>Natural-language CRM search, grounded summaries, and explainable lead scoring.</small></div><span class="ai-model-badge">APEX CRM engine</span></div><div class="card-body"><form data-apex-assistant-form class="apex-assistant-form"><input class="field-input" name="question" required minlength="3" placeholder="Show deals above ₹5 lakh closing this month" /><button class="button button-primary" type="submit">Ask APEX</button></form><div class="apex-quick-prompts"><button class="button button-ghost button-small" data-apex-prompt="Show stale deals">Show stale deals</button><button class="button button-ghost button-small" data-apex-prompt="Which leads have not been contacted for 7 days?">Uncontacted leads</button><button class="button button-ghost button-small" data-apex-prompt="Score all leads">Score leads</button></div><div data-apex-output class="apex-output"><p class="apex-muted">Try a CRM question. Results stay within YASH CRM and show their uncertainty.</p></div></div></section>
    <section class="ai-cockpit-stats">${stat("Leads received", totals.leads || 0, `${totals.assigned_leads || 0} assigned`)}${stat("Conversations", totals.conversations || 0, `${totals.open_followups || 0} open follow-ups`)}${stat("Team target", formatMoney(performance.totals?.target || 0), "active sales targets", "blue")}${stat("Achieved", formatMoney(performance.totals?.achieved || 0), "from cleared payments", "green")}${stat("Collected", formatMoney(totals.collected || 0), "received and cleared", "green")}${stat("Incentives", formatMoney(performance.totals?.incentive || 0), "earned by performance", "amber")}</section>
    <section class="card ai-journey-card"><div class="card-head"><div class="card-head-copy"><h2>Complete revenue journey</h2><small>Live counts from every connected CRM module</small></div><span class="ai-live-pill"><i></i>Live data</span></div><div class="ai-journey-track">${journeyHtml}</div></section>
    <div class="dashboard-grid management-grid"><section class="card"><div class="card-head"><div class="card-head-copy"><h2>Management readout</h2><small>GPT-4o mini analysis grounded in CRM records</small></div><span class="ai-model-badge">gpt-4o-mini</span></div><div class="card-body">${insightHtml}</div></section><section class="card"><div class="card-head"><div class="card-head-copy"><h2>Attention queue</h2><small>Where revenue is getting stuck</small></div></div><div class="card-body">${blockers || emptyState("✓", "Nothing urgent", "Leads and quotations are up to date.")}</div></section></div>
    <section class="card"><div class="card-head"><div class="card-head-copy"><h2>Individual sales performance</h2><small>Target vs achievement, conversions and earned incentive</small></div><button class="card-head-link" data-go="/sales_targets">Manage targets →</button></div><div class="card-body">${people.length ? performanceTable(people) : emptyState("◎", "No active salespeople", "Add active users and sales targets to see performance.")}</div></section>`;
}

function apexAssistantResultHtml(response) {
  const result = response.result || {};
  if (response.intent === "search") {
    const rows = result.results || [];
    return `<div class="apex-answer"><strong>${esc(response.answer)}</strong><small>${esc(response.provider || "APEX")} · ${esc(response.uncertainty || "Grounded in CRM records")}</small></div>${rows.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Record</th><th>Status / stage</th><th>Amount</th><th>Updated</th><th></th></tr></thead><tbody>${rows.map((row) => `<tr><td><a class="table-link" href="/${result.resource}/${row.id}">${esc(row.label)}</a></td><td>${esc(row.status || row.stage || "—")}</td><td>${row.amount != null ? formatMoney(row.amount) : "—"}</td><td>${formatDateTime(row.updated_at)}</td><td><button class="table-action" data-apex-summary-resource="${result.resource}" data-apex-summary-id="${row.id}">Summary</button></td></tr>`).join("")}</tbody></table></div>` : emptyState("◎", "No matching records", "APEX did not find records matching the interpreted filters.")}`;
  }
  if (response.intent === "summary") return `<div class="apex-answer"><strong>${esc(response.answer)}</strong><small>${esc(response.uncertainty || "Grounded in the current record")}</small></div><div class="apex-summary-grid">${(result.highlights || []).map((item) => `<div><span>${esc(item)}</span></div>`).join("")}</div><p class="apex-summary-text">${esc(result.record?.notes || result.record?.description || "No additional narrative is stored on this record.")}</p><a class="button button-ghost button-small" href="/${result.resource}/${result.record.id}">Open record</a>`;
  const leads = result.leads || [];
  return `<div class="apex-answer"><strong>${esc(response.answer)}</strong><small>${esc(result.method || "Explainable scoring")}</small></div>${leads.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Lead</th><th>Score</th><th>Confidence</th><th>Uncertainty</th><th></th></tr></thead><tbody>${leads.slice(0, 25).map((lead) => `<tr><td><a class="table-link" href="/leads/${lead.id}">${esc(lead.name)}</a><small class="table-subtext">${esc(lead.company || "No company")}</small></td><td><span class="score-pill">${lead.score}/100</span></td><td>${badge(lead.confidence)}</td><td>${esc(lead.uncertainty)}</td><td><button class="table-action" data-apex-score-detail='${esc(JSON.stringify(lead))}'>Why?</button></td></tr>`).join("")}</tbody></table></div>` : emptyState("◎", "No leads to score", "Add active leads to calculate explainable scores.")}`;
}

function bindApexAssistant() {
  const form = $(`[data-apex-assistant-form]`), output = $(`[data-apex-output]`);
  if (!form || !output) return;
  $$(`[data-apex-prompt]`).forEach((button) => button.addEventListener("click", () => { form.elements.question.value = button.dataset.apexPrompt; form.requestSubmit(); }));
  form.addEventListener("submit", async (event) => { event.preventDefault(); output.innerHTML = `<p class="apex-muted">APEX is reading current CRM records…</p>`; try { const result = await api("/api/ai/assistant", {method:"POST", body:JSON.stringify({question:form.elements.question.value.trim()})}); output.innerHTML = apexAssistantResultHtml(result); bindApexAssistantResult(); } catch (error) { output.innerHTML = `<p class="apex-error">${esc(error.message)}</p>`; } });
}

function bindApexAssistantResult() {
  $$(`[data-apex-summary-resource]`).forEach((button) => button.addEventListener("click", async () => { try { const result = await api("/api/ai/summary", {method:"POST", body:JSON.stringify({resource:button.dataset.apexSummaryResource, record_id:Number(button.dataset.apexSummaryId)})}); $(`[data-apex-output]`).innerHTML = apexAssistantResultHtml({intent:"summary", answer:`APEX summarized ${result.resource} #${result.record.id}.`, result, uncertainty:"Summary grounded in the current record and related activity counts."}); } catch (error) { toast("Summary unavailable", error.message, "error"); } }));
  $$(`[data-apex-score-detail]`).forEach((button) => button.addEventListener("click", () => { const lead = JSON.parse(button.dataset.apexScoreDetail); toast(`APEX score: ${lead.score}/100`, lead.factors.map((factor) => `${factor.name}: ${factor.points}/${factor.max_points}`).join(" · ")); }));
}

async function aiView() {
  // Status and readiness are advisory panels: if one fails (anything but a lost sign-in) the
  // deterministic queue must still render, so degrade them instead of failing the whole view.
  const soft = (request, fallback) => request.catch((error) => (error.status === 401 ? Promise.reject(error) : fallback(error)));
  const [status, readiness, deterministic] = await Promise.all([
    soft(api("/api/ai/status"), (error) => ({ configured: false, available: false, model: "unavailable", detail: error.message, csrf_token: state.aiStatus?.csrf_token })),
    soft(api("/api/ai/exceptions/readiness"), (error) => ({ deterministic_ready: false, approval_ready: false, ai_ready: false, checks: [{ key: "readiness", ready: false, detail: error.message }] })),
    api(`/api/ai/exceptions?view=${encodeURIComponent(state.aiExceptionView)}`),
  ]);
  state.aiStatus = status;
  const ranked = state.aiExceptionOrder === "ai_ranked" && state.aiRankedItems;
  const data = ranked ? { ...deterministic, items: state.aiRankedItems, order: "ai_ranked" } : deterministic;
  const viewLabels = { needs_review: "Needs review", acted_on: "Acted on", clarification: "Needs clarification", corrections: "Data corrections", dismissed: "Dismissed", all: "All active" };
  const views = Object.entries(viewLabels).map(([key, label]) => `<button class="ai-view-tab ${state.aiExceptionView === key ? "active" : ""}" data-ai-view="${key}">${esc(label)}</button>`).join("");
  const rows = data.items.length ? data.items.map((item) => {
    const selected = state.aiSelectedException === item.id;
    return `<article class="ai-exception-row ${selected ? "selected" : ""}" data-ai-exception="${esc(item.id)}">
      <div class="ai-trigger"><strong>${esc(item.trigger_label)}</strong><small>${esc(item.actionability.replaceAll("_", " "))}</small></div>
      <div class="ai-quote"><b>${esc(item.quote_label)}</b><small>${esc(item.owner_name || "Owner unavailable")} · ${item.valid_until ? formatDate(item.valid_until) : "No valid date"}</small></div>
      <div class="ai-amount"><strong>${formatMoney(item.amount)}</strong><small>${esc(item.review_state.replaceAll("_", " "))}</small></div>
      <button class="button button-small button-ghost" data-ai-review="${esc(item.id)}">Review</button>
    </article>`;
  }).join("") : `<div class="ai-empty"><span>✓</span><h3>${state.aiExceptionView === "needs_review" ? "No quotation exceptions need review" : "Nothing in this view"}</h3><p>Evaluated using ${esc(data.rule_version)}. Change the view or review the source quotations if this looks wrong.</p></div>`;
  const selected = data.items.find((item) => item.id === state.aiSelectedException) || null;
  const proposal = selected?.proposal;
  const detail = selected ? `<aside class="card ai-exception-detail" aria-labelledby="ai-detail-title">
    <div class="card-head"><div class="card-head-copy"><h2 id="ai-detail-title" tabindex="-1">${esc(selected.quote_label)}</h2><small>${esc(selected.trigger_label)} · ${esc(selected.rule_version)}</small></div><button class="card-head-link" data-ai-close-detail>Close</button></div>
    <div class="card-body ai-detail-body">
      <dl class="ai-facts"><div><dt>Owner</dt><dd>${esc(selected.owner_name || "Unavailable")}</dd></div><div><dt>Amount at risk</dt><dd>${formatMoney(selected.amount)}</dd></div><div><dt>Validity</dt><dd>${selected.valid_until ? formatDate(selected.valid_until) : "Missing"}</dd></div><div><dt>Source updated</dt><dd>${formatDateTime(selected.source_updated_at)}</dd></div></dl>
      <p class="ai-rule-reason">Included because ${esc(selected.trigger_label.toLowerCase())}. The CRM rule determined this exception; AI did not.</p>
      ${selected.rationale ? `<section class="ai-rationale"><strong>Why AI placed it here</strong><p>${esc(selected.rationale)}</p></section>` : ""}
      ${proposal ? `<section class="ai-task-preview"><span class="eyebrow">Exact Task preview</span><h3>${esc(proposal.subject)}</h3><dl><div><dt>Owner</dt><dd>${esc(proposal.owner_name || `#${proposal.owner_id}`)}</dd></div><div><dt>Priority</dt><dd>${esc(proposal.priority)}</dd></div><div><dt>Due</dt><dd>${formatDateTime(proposal.due_at)}</dd></div><div><dt>Status</dt><dd>Open</dd></div><div><dt>Source</dt><dd>${esc(proposal.source)}</dd></div></dl><p>${esc(proposal.description || "No drafted description")}</p><button class="button button-primary" data-ai-approve-proposal="${esc(proposal.id)}">Create Task</button></section>` : selected.actionability === "actionable" ? `<div class="ai-setup"><strong>Generate a Task proposal</strong><p>Switch to AI-ranked order to request a bounded explanation and exact Task draft.</p></div>` : `<div class="ai-setup"><strong>Task creation is blocked</strong><p>Resolve the ${esc(selected.actionability.replaceAll("_", " "))} condition in the source quotation first.</p></div>`}
      <div class="ai-review-actions"><button class="button button-ghost button-small" data-ai-review-state="dismissed">Dismiss for 7 days</button><button class="button button-ghost button-small" data-ai-review-state="corrected">Report data/rule issue</button><button class="button button-ghost button-small" data-ai-review-state="unclear">Mark unclear</button><a class="button button-ghost button-small" href="${esc(selected.quote_path || "/quotes")}">Open quotation</a></div>
    </div>
  </aside>` : "";
  const checks = readiness.checks.map((item) => `<li class="${item.ready ? "ready" : "blocked"}"><b>${item.ready ? "✓" : "!"}</b><span>${esc(titleCase(item.key))}<small>${esc(item.detail)}</small></span></li>`).join("");
  const orderLabel = data.order === "ai_ranked" ? `AI-ranked · ${status.model}` : "Deterministic order";
  return `${pageHeader("Revenue operations", "Quotation Follow-up Exceptions", `Open quotations with missing, elapsed or upcoming validity dates within 7 days. Evaluated ${formatDateTime(data.evaluated_at)} in ${esc(data.timezone)}.`, `<span class="ai-status ${readiness.deterministic_ready ? "ready" : "offline"}"><i></i>${esc(orderLabel)}</span>`)}
    <section class="ai-exception-summary"><div><strong>${data.matching_count}</strong><span>matching exceptions</span></div><div><strong>${data.counts.open || 0}</strong><span>need review</span></div><div><strong>${data.actionable_count}</strong><span>Task eligible</span></div><div><strong>${esc(data.rule_version)}</strong><span>rule version</span></div></section>
    <div class="ai-exception-toolbar card"><div class="ai-view-tabs">${views}</div><div class="ai-order-actions"><button class="button button-ghost button-small ${data.order === "deterministic" ? "active" : ""}" data-ai-deterministic>Deterministic order</button><button class="button button-primary button-small" data-ai-rank ${!readiness.ai_ready || !data.items.length ? "disabled" : ""}>AI-ranked order · 1 request</button></div></div>
    ${!readiness.ai_ready ? `<div class="ai-fallback-note"><strong>Queue ready · AI ranking unavailable</strong><span>${esc(status.detail)}. All deterministic records remain available.</span></div>` : ""}
    <div class="ai-exception-layout"><section class="card ai-exception-list" aria-live="polite">${rows}</section>${detail}</div>
    <details class="card ai-readiness"><summary>Readiness and cloud boundary</summary><div class="card-body"><ul>${checks}</ul><p>Only opaque references, trigger facts, amount, currency, date and owner-active status are sent for ranking. Customer names, notes, messages, attachments and credentials are excluded.</p></div></details>`;
}

function aiMessageHtml(message, messageIndex) {
  if (message.role === "user") return `<article class="ai-message user"><span>You</span><p>${esc(message.text)}</p></article>`;
  const result = message.result;
  const actions = (result.actions || []).length ? `<div class="ai-result-list"><strong>Recommended actions</strong><ol>${result.actions.map((item) => `<li>${esc(item)}</li>`).join("")}</ol></div>` : "";
  const risks = (result.risks || []).length ? `<div class="ai-result-list risks"><strong>Risks and gaps</strong><ul>${result.risks.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>` : "";
  const proposals = (result.proposed_activities || []).length ? `<div class="ai-proposals"><div class="ai-proposals-head"><div><strong>Proposed CRM activities</strong><small>Review each item. Approval writes selected activities to the CRM and audit history.</small></div></div>${result.proposed_activities.map((item, index) => `<label class="ai-proposal"><input type="checkbox" data-ai-proposal-index="${index}" checked ${result.approval_result ? "disabled" : ""}/><span><b>${esc(item.activity_type)} · ${esc(item.subject)}</b><small>${esc(titleCase(item.priority))} · due ${formatDateTime(item.due_at)} · ${esc(titleCase(item.related_type))} #${item.related_id}${item.owner_id ? ` · owner #${item.owner_id}` : ""}</small><em>${esc(item.reason)}</em></span></label>`).join("")}<div class="ai-approval-row">${result.approval_result ? `<span class="ai-approved">✓ ${result.approval_result.created.length} created · ${result.approval_result.skipped.length} duplicate${result.approval_result.skipped.length === 1 ? "" : "s"} skipped</span>` : `<button class="button button-primary button-small" data-ai-approve="${messageIndex}">Review and approve selected</button>`}</div></div>` : "";
  const sources = (result.sources || []).map((item) => `<span>${esc(item)}</span>`).join("");
  return `<article class="ai-message assistant" data-ai-message="${messageIndex}"><div class="ai-message-head"><span>Yash AI</span><small>${esc(result.model)} · ${esc(result.confidence)} confidence</small></div><p>${esc(result.answer).replace(/\n/g, "<br>")}</p>${actions}${risks}${proposals}<div class="ai-sources"><strong>CRM context used</strong>${sources}</div><small class="ai-disclaimer">${esc(result.disclaimer)}</small></article>`;
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
  $$('[data-ai-view]').forEach((button) => button.addEventListener("click", async () => {
    state.aiExceptionView = button.dataset.aiView;
    state.aiExceptionOrder = "deterministic";
    state.aiRankedItems = null;
    state.aiSelectedException = null;
    await renderRoute();
  }));
  $$('[data-ai-review]').forEach((button) => button.addEventListener("click", async () => {
    state.aiSelectedException = button.dataset.aiReview;
    await renderRoute();
    $("#ai-detail-title")?.focus();
  }));
  $("[data-ai-close-detail]")?.addEventListener("click", async () => {
    const previous = state.aiSelectedException;
    state.aiSelectedException = null;
    await renderRoute();
    $(`[data-ai-review="${previous}"]`)?.focus();
  });
  $("[data-ai-deterministic]")?.addEventListener("click", async () => {
    state.aiExceptionOrder = "deterministic";
    await renderRoute();
  });
  $("[data-ai-rank]")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = "Ranking complete set…";
    try {
      const current = await api(`/api/ai/exceptions?view=${encodeURIComponent(state.aiExceptionView)}`);
      const result = await api("/api/ai/exceptions/rank", { method: "POST", body: JSON.stringify({ occurrence_ids: current.items.map((item) => item.id) }) });
      state.aiRankedItems = result.items;
      state.aiExceptionOrder = "ai_ranked";
      if (state.aiSelectedException && !result.items.some((item) => item.id === state.aiSelectedException)) state.aiSelectedException = null;
      await renderRoute();
      toast("AI ranking applied", `Validated all ${result.items.length} exception references. Deterministic order remains available.`);
    } catch (error) {
      state.aiExceptionOrder = "deterministic";
      state.aiRankedItems = null;
      toast("AI ranking unavailable", error.message, "error");
      await renderRoute();
    }
  });
  $("[data-ai-approve-proposal]")?.addEventListener("click", async (event) => {
    const proposalId = event.currentTarget.dataset.aiApproveProposal;
    const confirmed = await confirmAction("Create this Task?", "This creates one persistent CRM Task using the exact owner, due date, priority, source and text shown above. The action is audited.", "Create Task");
    if (!confirmed) return;
    event.currentTarget.disabled = true;
    try {
      const result = await api(`/api/ai/proposals/${encodeURIComponent(proposalId)}/approve`, { method: "POST", body: "{}" });
      state.aiExceptionOrder = "deterministic";
      state.aiRankedItems = null;
      state.aiSelectedException = null;
      await renderRoute();
      toast(result.duplicate ? "Existing Task returned" : "Task created", `${result.activity.subject} · Task #${result.activity.id}`);
    } catch (error) {
      event.currentTarget.disabled = false;
      toast(error.code === "APPROVAL_NEEDS_RECONCILIATION" ? "Task outcome needs checking" : "Task was not created", error.message, "error");
    }
  });
  $$('[data-ai-review-state]').forEach((button) => button.addEventListener("click", async () => {
    const label = titleCase(button.dataset.aiReviewState);
    const reason = window.prompt(`${label}: enter a short reason or note.`);
    if (!reason?.trim()) return;
    button.disabled = true;
    try {
      await api(`/api/ai/exceptions/${encodeURIComponent(state.aiSelectedException)}/review`, { method: "PATCH", body: JSON.stringify({ state: button.dataset.aiReviewState, reason: reason.trim() }) });
      state.aiSelectedException = null;
      state.aiRankedItems = null;
      state.aiExceptionOrder = "deterministic";
      await renderRoute();
      toast("Review recorded", `${label} was written to the exception audit history.`);
    } catch (error) { button.disabled = false; toast("Could not record review", error.message, "error"); }
  }));
}

async function settingsView(tab) {
  let content = '';
  if (tab === 'general') content = `${await generalSettingsView()}${await settingsPlatformSummary("company_details", "Company details")}${await settingsPlatformSummary("fiscal_years", "Fiscal years")}`;
  if (tab === 'profile-users') content = await profileUsersView();
  if (tab === 'approval-process') content = await approvalSettingsView();
  if (tab === 'blueprint') content = await blueprintSettingsView();
  const labels = { general: 'General settings', 'profile-users': 'Profile & users', 'approval-process': 'Approval process', blueprint: 'Blueprint' };
  return `<section class="setup-page-shell"><div class="setup-toolbar"><button class="button button-ghost button-small" data-go="/setup">← Back to Setup</button><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input value="${esc(labels[tab] || 'Settings')}" disabled /></label><button class="button button-ghost" data-go="/setup/customize_setup">Customize Setup</button></div><div class="setup-workspace">${setupDirectory(tab === 'general' ? 'company_details' : tab === 'profile-users' ? 'users' : tab === 'approval-process' ? 'approval_processes' : 'blueprints')}<div class="settings-content">${content}</div></div></section>`;
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
  const [data, inbox] = await Promise.all([api("/api/approval_processes?limit=100"), api("/api/approvals/requests?status=Pending&limit=100")]);
  const processes = data.items.length ? data.items.map((rule) => `<div class="rule-row"><span class="related-dot">✓</span><div class="rule-info"><strong>${esc(rule.name)}</strong><small>${esc(rule.module)} · ${esc(rule.trigger)} · ${esc((rule.steps || []).length || 1)} approval level(s)</small></div>${badge(rule.status)}<div class="rule-actions"><button class="table-action" data-edit-record="approval_processes" data-id="${rule.id}">✎</button><button class="table-action" data-delete-record="approval_processes" data-id="${rule.id}">⌫</button></div></div>`).join("") : emptyState("✓", "No approval rules", "Create a multi-level approval process for deals, leads, or accounts.", `<button class="button button-primary" data-create="approval_processes">New rule</button>`);
  const requests = inbox.items.length ? inbox.items.map((request) => { const step = request.steps.find((item) => item.status === "Pending"); return `<div class="rule-row"><span class="related-dot">◷</span><div class="rule-info"><strong>${esc(request.process_name)} · ${esc(request.resource)} #${request.record_id}</strong><small>Level ${request.current_step} · ${esc(step?.approver_name || step?.approver_label || "Unassigned")} · submitted ${formatDateTime(request.submitted_at)}</small></div><button class="button button-small button-ghost" data-approval-action="approve" data-approval-id="${request.id}">Approve</button><button class="button button-small button-ghost" data-approval-action="reject" data-approval-id="${request.id}">Reject</button><button class="table-action" title="Delegate" data-approval-action="delegate" data-approval-id="${request.id}">↗</button></div>`; }).join("") : emptyState("◷", "No pending approvals", "Submitted records will appear here at the current approval level.");
  return `<section class="card settings-section"><div class="settings-section-head" style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start"><div><h2>Approval processes</h2><p>Configure ordered approval levels with approve, reject, delegate, and audit history.</p></div><button class="button button-primary button-small" data-create="approval_processes">＋ New process</button></div><div>${processes}</div></section><section class="card settings-section"><div class="settings-section-head"><h2>Approval inbox</h2><p>Actions advance only the current level; later levels remain waiting until their turn.</p></div>${requests}</section>`;
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
  const setupSearch = $('[data-setup-search-input]');
  setupSearch?.addEventListener('input', () => {
    const query = setupSearch.value.trim().toLowerCase();
    let visible = 0;
    $$('.setup-search-item').forEach((item) => { const match = !query || item.dataset.searchText.includes(query); item.hidden = !match; if (match) visible += 1; });
    $$('.setup-search-group').forEach((group) => { group.hidden = !$$('.setup-search-item', group).some((item) => !item.hidden); });
    const count = $('[data-setup-search-count]'); if (count) count.textContent = `${visible} setup option${visible === 1 ? '' : 's'} matched.`;
  });
  $('[data-customize-setup-form]')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const hidden_groups = $$('[data-setup-group-visible]', form).filter((input) => !input.checked).map((input) => input.dataset.setupGroupVisible);
    const hidden_items = $$('[data-setup-item-visible]', form).filter((input) => !input.checked).map((input) => input.dataset.setupItemVisible);
    const payload = {name:'Default Setup Navigation', hidden_groups, hidden_items, group_order:Object.keys(state.platformCatalog.setup_navigation || {})};
    try {
      const id = form.dataset.prefId;
      await api(`/api/platform/setup_preferences${id ? `/${id}` : ''}`, {method:id ? 'PATCH' : 'POST', body:JSON.stringify(payload)});
      localStorage.setItem('yash.setup.hidden_groups', JSON.stringify(hidden_groups));
      localStorage.setItem('yash.setup.hidden_items', JSON.stringify(hidden_items));
      toast('Setup navigation saved', 'Visibility preferences were saved without deleting configuration.'); await renderRoute();
    } catch (error) { toast('Could not save Setup navigation', error.message, 'error'); }
  });
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create)));
  $$('[data-run-workflow]').forEach((button) => button.addEventListener("click", async () => { button.disabled = true; try { await api(`/api/automation/executions/${button.dataset.runWorkflow}/run`, { method: "POST" }); toast("Workflow executed", "The queued actions completed successfully."); await renderRoute(); } catch (error) { button.disabled = false; toast("Workflow failed", error.message, "error"); } }));
  $$('[data-approval-action]').forEach((button) => button.addEventListener("click", async () => { const action = button.dataset.approvalAction; try { if (action === "delegate") { const delegateTo = window.prompt("Delegate to active user ID:"); if (!delegateTo) return; await api(`/api/approvals/requests/${button.dataset.approvalId}/delegate`, { method: "POST", body: JSON.stringify({ delegate_to: Number(delegateTo) }) }); toast("Approval delegated", `Approval #${button.dataset.approvalId} was delegated.`); } else { const comment = window.prompt(`${titleCase(action)} comment (optional):`) || undefined; await api(`/api/approvals/requests/${button.dataset.approvalId}/${action}`, { method: "POST", body: JSON.stringify({ comment }) }); toast(`Approval ${action}d`, `Approval #${button.dataset.approvalId} was updated.`); } await renderRoute(); } catch (error) { toast("Approval action failed", error.message, "error"); } }));
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

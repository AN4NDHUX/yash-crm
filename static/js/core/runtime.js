// Shared SPA runtime state and presentation utilities.
// Kept dependency-light so feature modules can consume it without circular imports.

export const state = {
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
  customModules: [],
  customBuilder: null,
  aiMessages: [],
  aiStatus: null,
  aiExceptionView: "needs_review",
  aiExceptionOrder: "deterministic",
  aiRankedItems: null,
  aiSelectedException: null,
};

export const PLATFORM_MODULE_ROUTES = [
  "price_books", "vendors", "quotes", "sales_orders", "purchase_orders", "invoices", "payments",
  "campaigns", "cases", "solutions", "documents", "site_visits", "forecasts", "reports", "dashboards", "sales_targets",
];
export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
export const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
export const titleCase = (value) => String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
export const initials = (value) => String(value || "Y").split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
export const formatDate = (value) => {
  if (!value) return "—";
  const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric" }).formatToParts(parsed).reduce((acc, part) => ({ ...acc, [part.type]: part.value }), {});
  if (state.settingsCache.date_format === "MM/DD/YYYY") return `${parts.month}/${parts.day}/${parts.year}`;
  if (state.settingsCache.date_format === "YYYY-MM-DD") return `${parts.year}-${parts.month}-${parts.day}`;
  return `${parts.day} ${parts.month} ${parts.year}`;
};
export const formatDateTime = (value) => value ? new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "—";
export const formatMoney = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: state.settingsCache.currency || "INR", maximumFractionDigits: 0 }).format(Number(value || 0));
export const slug = (value) => String(value || "").toLowerCase().replace(/\s+/g, "-");
export const pathFor = (resource, id) => `/${resource}${id ? `/${id}` : ""}`;

export function badge(value) {
  const label = value || "Not set";
  const cls = { "Closed Won": "won", "Closed Lost": "lost", Completed: "green", Active: "active", Qualified: "qualified", Proposal: "progress", Negotiation: "progress", High: "amber", Open: "blue", New: "indigo" }[label] || slug(label);
  return `<span class="status-badge ${esc(cls)}">${esc(label)}</span>`;
}

export function lookupName(resource, id) {
  if (!id) return "—";
  const item = state.lookups[resource]?.find((entry) => Number(entry.id) === Number(id));
  if (!item) return `#${id}`;
  return item.full_name || item.name || `${item.first_name} ${item.last_name}`;
}

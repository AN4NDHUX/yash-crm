import { installAttachmentPicker, createAttachmentFromFile } from "./features/attachments.js";
import { requestJson } from "./core/http.js";
import { renderPricingView, bindPricingInteractions } from "./features/pricing.js?v=20261008-convosis-ui-v2";

import { state, PLATFORM_MODULE_ROUTES, $, $$, esc, titleCase, initials, formatDate, formatDateTime, formatMoney, slug, pathFor, badge, lookupName } from "./core/runtime.js";
import { MODULES } from "./features/modules.js";
import { FILTERABLE_MODULES, renderModuleFilters, bindModuleFilters } from "./features/module-filters.js";
import { createSetupFeature } from "./features/setup.js";
import { createImportWizardFeature } from "./features/import-wizard.js";
import { createBlueprintFeature } from "./features/blueprints.js";
import { createWorkflowRulesUI } from "./features/workflow-rules.js";
import { createAiFeature } from "./features/ai.js";
import { createTeamspacesFeature } from "./features/teamspaces.js";
import { createDashboardSupport } from "./features/dashboard-support.js";
import { createPlatformDetailFeature } from "./features/platform-detail.js";
import { createContextActions } from "./features/context-actions.js";
import { createQuoteDetails } from "./features/quote-details.js";
import { renderPlatformTable } from "./features/platform-table.js";

async function api(path, options = {}, retried = false) {
  try {
    return await requestJson(path, options, state.aiStatus?.csrf_token || null);
  } catch (error) {
    if (error.status === 403 && error.code === "CSRF_REJECTED" && !retried && path !== "/api/ai/status") {
      let refreshed = null;
      try {
        refreshed = await requestJson("/api/ai/status", {}, null);
      } catch {
        throw error;
      }
      if (refreshed?.csrf_token) {
        state.aiStatus = refreshed;
        return api(path, options, true);
      }
    }
    throw error;
  }
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
  const parts = route.split("/").filter(Boolean);
  const root = parts[0] || "dashboard";
  $$('[data-route]').forEach((link) => link.classList.toggle("active", link.dataset.route === root));
  $$('[data-custom-module-route]').forEach((link) => link.classList.toggle("active", root === "custom" && link.dataset.customModuleRoute === parts[1]));
}

function enhanceNavigation() {
  const setupLink = $('[data-route="setup"]');
  if (setupLink) setupLink.textContent = "Settings & Setup";
  const settingsLink = $('[data-route="settings"]');
  if (settingsLink) settingsLink.remove();
  const addAfter = (route, nextRoute, label) => {
    const anchor = $(`[data-route="${route}"]`);
    if (anchor && !$(`[data-route="${nextRoute}"]`)) anchor.insertAdjacentHTML("afterend", `<a href="/${nextRoute}" data-route="${nextRoute}">${label}</a>`);
  };
  addAfter("invoices", "payments", "Payments");
  addAfter("documents", "site_visits", "Site Visits");
  addAfter("reports", "sales_targets", "Sales Targets & Incentives");
  addAfter("sales_targets", "ai", "AI Copilot");
}

async function pricingView() {
  return renderPricingView({ api, esc, pageHeader });
}

function bindPricing() {
  return bindPricingInteractions({
    api,
    toast,
    state,
    applyProfile,
    renderRoute,
    titleCase,
    queryOne: $,
    queryAll: $$,
  });
}

function pageHeader(eyebrow, title, copy, actions = "") {
  return `<div class="page-heading"><div><span class="eyebrow">${esc(eyebrow)}</span><h1>${esc(title)}</h1><p class="subheading">${esc(copy)}</p></div><div class="heading-actions">${actions}</div></div>`;
}

function loading() { return `<div class="loading" role="status" aria-live="polite"><div class="yash-radial-loader" aria-hidden="true"><span class="yash-loader-spokes"><i style="--i:0"></i><i style="--i:1"></i><i style="--i:2"></i><i style="--i:3"></i><i style="--i:4"></i><i style="--i:5"></i><i style="--i:6"></i><i style="--i:7"></i><i style="--i:8"></i><i style="--i:9"></i><i style="--i:10"></i><i style="--i:11"></i></span><img class="uploaded-loader-logo" src="/static/loader-logo.png?v=20261006-radial-v2" alt="" /></div><span class="loading-label">Connecting your customer journey</span><span class="loading-steps" aria-hidden="true"><i>Lead</i><b></b><i>Visit</i><b></b><i>Quote</i><b></b><i>Payment</i></span><span class="loading-progress" aria-hidden="true"><i></i></span></div>`; }

function emptyState(icon, title, copy, button = "") { return `<div class="empty-state"><span class="empty-icon">${icon}</span><h3>${esc(title)}</h3><p>${esc(copy)}</p>${button ? `<div style="margin-top:16px">${button}</div>` : ""}</div>`; }

async function ensureLookups() {
  if (state.lookups.loaded) return;
  const resources = ["accounts", "contacts", "leads", "deals"];
  const results = await Promise.allSettled(
    resources.map((resource) => api(`/api/${resource}?limit=100`))
  );
  results.forEach((result, index) => {
    const resource = resources[index];
    state.lookups[resource] = result.status === "fulfilled"
      ? (result.value?.items || [])
      : [];
  });

  state.lookups.loaded = true;
}

async function ensurePlatformLookup(resource) {
  if (state.platformLookups[resource]) return;
  try {
    state.platformLookups[resource] = (await api(`/api/platform/${resource}?limit=100&sort=name_asc`)).items || [];
  } catch (error) {


    // only if the user actually needs that lookup.
    state.platformLookups[resource] = [];
  }
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


async function ensureCustomModules() {
  try {
    const data = await api("/api/admin/metadata/modules");
    state.customModules = data.items || [];
  } catch {
    state.customModules = [];
  }
  return state.customModules;
}

function enhanceCustomModuleNavigation() {
  $$('.dynamic-custom-module-link').forEach((node) => node.remove());
  $('.dynamic-custom-module-label')?.remove();
  const enabled = (state.customModules || []).filter((module) => module.enabled);
  if (!enabled.length) return;
  const anchor = $('[data-route="deals"]') || $('[data-route="teamspaces"]');
  if (!anchor) return;
  const html = `<span class="nav-label dynamic-custom-module-label">CUSTOM MODULES</span>${enabled.map((module) => `<a class="dynamic-custom-module-link" href="/custom/${esc(module.api_name)}" data-custom-module-route="${esc(module.api_name)}">${esc(module.plural_label || module.label)}</a>`).join("")}`;
  anchor.insertAdjacentHTML("afterend", html);
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function applyProfile() {
  const profile = state.profile;
  if (!profile) return;

  const username = String(profile.username || profile.name || "Account").trim() || "Account";
  const role = String(profile.role || "CRM user").trim() || "CRM user";
  const planName = String(profile.plan_name || profile.subscription?.plan_name || "Free").trim() || "Free";
  const isOwnerAdmin = profile.owner_console_access === true;
  const isAdministrator = role.toLowerCase() === "administrator";




  document.querySelectorAll("[data-admin-only]").forEach((node) => {
    node.hidden = !isAdministrator;
    node.setAttribute("aria-hidden", String(!isAdministrator));
  });


  $$(".user-mini .avatar").forEach((node) => { node.textContent = initials(username); });
  $$(".user-mini strong").forEach((node) => { node.textContent = username; });
  $$(".user-mini-role").forEach((node) => { node.textContent = role; });
  $$(".user-mini-plan").forEach((node) => { node.textContent = planName; });


  const topProfile = $("#top-profile");
  const ownerButton = $("#owner-console-button");
  if (topProfile) {
    topProfile.hidden = !isOwnerAdmin;
    topProfile.setAttribute("aria-hidden", String(!isOwnerAdmin));
  }
  if (ownerButton) {
    ownerButton.hidden = !isOwnerAdmin;
    ownerButton.setAttribute("aria-hidden", String(!isOwnerAdmin));
  }

  if (isOwnerAdmin) {
    $$(".top-profile .avatar").forEach((node) => { node.textContent = initials(username); });
    $$(".top-profile-copy strong").forEach((node) => { node.textContent = username; });
    $$(".top-profile-copy small").forEach((node) => { node.textContent = role; });
  }
}

async function refreshNavCount() {
  try {
    const data = await api("/api/leads?limit=1");
    const badgeNode = $("#nav-leads-count");
    if (badgeNode) { badgeNode.textContent = data.total; badgeNode.hidden = !data.total; }
  } catch (error) { /* counts are best effort */ }
}

const workflowRulesUI = createWorkflowRulesUI({api, esc, toast, navigate, renderRoute, state});
const importWizardUI = createImportWizardFeature({api, toast, navigate, esc, MODULES});
const { platformDetailView, bindPlatformDetail } = createPlatformDetailFeature({ api, state, esc, formatDateTime, formatMoney, navigate, openPlatformModal, deletePlatformRecord, selectAll: $ });
const { openDealForAccount, bindContextCreationActions } = createContextActions({ api, openPlatformModal, openRecordModal, state, toast, selectAll: $ });
const quoteDetails = createQuoteDetails({ api, esc, badge, formatDate, formatDateTime, formatMoney, lookupName, navigate, openPlatformModal, deletePlatformRecord, toast, renderRoute });
const { teamspacesView, bindTeamspaces } = createTeamspacesFeature({ api, pageHeader, esc, emptyState, $, $$, readForm, toast, navigate });
const { dashboardReportView, performanceTable, attentionQueue, activityItem, bindDashboard } = createDashboardSupport({ api, formatDate, formatDateTime, formatMoney, esc, badge, pageHeader, emptyState, titleCase, $$, openRecordModal });

async function navigate(path, replace = false) {
  if (replace) history.replaceState({}, "", path); else history.pushState({}, "", path);
  state.route = path;
  await renderRoute();
  $("#sidebar").classList.remove("open");
}

async function renderRoute() {

  const route = window.location.pathname.replace(/^\/app(?=\/|$)/, "") || "/dashboard";
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
    if (parts[0] === "dashboard" && parts[1] === "report" && parts[2] && parts.length === 3) {
      setBreadcrumb("Dashboard report", "Dashboard");
      content.innerHTML = await dashboardReportView(parts[2]);
      return;
    }
    if (parts[0] === "teamspaces") {
      setBreadcrumb("Teamspaces", "Workspace");
      content.innerHTML = await teamspacesView();
      bindTeamspaces();
      return;
    }
    if (parts[0] === "pricing") {
      return navigate("/subscriptions", true);
    }
    if (parts[0] === "subscriptions") {
      setBreadcrumb("Upgrade plan", "Account");
      content.innerHTML = await pricingView();
      bindPricing();
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
      const role = String(state.profile?.role || "").trim().toLowerCase();
      if (role !== "administrator") return navigate("/dashboard", true);
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
      if (resource === "workflow_rules") {
        setBreadcrumb("Workflow Rules", "Setup");
        content.innerHTML = `<section class="setup-page-shell"><div class="setup-toolbar setup-toolbar-search-only"><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input data-setup-search-input placeholder="Search Setup" /></label></div><div class="setup-workspace">${setupDirectory("workflow_rules")}<div class="settings-content" id="workflow-rules-container">${await workflowRulesUI.view()}</div></div></section>`;
        bindSettings();
        workflowRulesUI.bind($("#workflow-rules-container"));
        return;
      }
      setBreadcrumb(resource === "index" ? "Setup" : titleCase(resource), "Setup");
      content.innerHTML = await setupView(resource, parts.slice(2));
      bindSettings();
      return;
    }
    if (parts[0] === "custom" && parts[1]) {
      const module = (state.customModules || []).find((item) => item.api_name === parts[1] && item.enabled);
      if (!module) return navigate("/dashboard", true);
      setBreadcrumb(module.plural_label || module.label, "Custom Modules");
      content.innerHTML = await customRuntimeView(module);
      bindCustomRuntime(module);
      return;
    }
    if (parts[0] === "import" && ["leads", "deals", "accounts", "contacts"].includes(parts[1])) {
      setBreadcrumb("Import " + MODULES[parts[1]].label, "Data Administration");
      content.innerHTML = importWizardUI.view(parts[1]);
      importWizardUI.bind(content);
      return;
    }
    if (parts[0] === "settings") {
      const validTabs = ["general", "profile-users", "organization", "approval-process", "blueprint"];
      if (parts[1] && !validTabs.includes(parts[1])) return navigate("/settings/general", true);
      const tab = parts[1] || "general";
      setBreadcrumb("Settings", "Manage");
      content.innerHTML = await settingsView(tab);
      bindSettings();
      if (tab === 'organization') bindOrganizationManagement();
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
        content.innerHTML = `<div class="card empty-state"><span class="empty-icon">!</span><h3>${esc(titleCase(resource))} is temporarily unavailable</h3><p>CONVOSIS CRM could not load the module catalog. Please retry without leaving this module.</p><div style="margin-top:16px"><button class="button button-primary" data-retry>Retry module</button></div></div>`;
        return;
      }
      if (parts[1]) {
        const id = Number(parts[1]);
        if (parts.length !== 2 || !Number.isSafeInteger(id) || id <= 0) return navigate(`/${resource}`, true);
        setBreadcrumb(`${state.platformCatalog.resources[resource].singular} detail`, state.platformCatalog.resources[resource].label);
        if (resource === "quotes") {
          content.innerHTML = await quoteDetails.view(id);
          quoteDetails.bind(id);
        } else {
          content.innerHTML = await platformDetailView(resource, id);
          bindPlatformDetail(resource, id);
        }
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
    if (parts[0] === "leads" && parts[1] && parts[2] === "convert") {
      setBreadcrumb("Convert Lead", "Leads");
      content.innerHTML = await leadConvertPage(Number(parts[1]));
      bindLeadConvertPage(Number(parts[1]));
      return;
    }
    if (parts[0] === "leads" && parts[1] && parts[2] === "converted") {
      setBreadcrumb("Lead Converted", "Leads");
      content.innerHTML = leadConversionSuccess();
      document.querySelectorAll("[data-conversion-go]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.conversionGo)));
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
      if (parts[1] && /^\\d+$/.test(parts[1])) {
        content.innerHTML = await platformDetailView(resource, Number(parts[1]));
        bindPlatformDetail(resource, Number(parts[1]));
      } else {
        content.innerHTML = await platformModuleView(resource);
        bindPlatform(resource);
      }
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
  const maxPipeline = Math.max(...data.pipeline.map((row) => row.amount), 1);
  const maxLeads = Math.max(...data.lead_funnel.map((row) => row.count), 1);
  const performancePanel = `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>Sales performance</h2><small>Target, collections, conversion and earned incentive</small></div><button class="card-head-link" data-go="/sales_targets">Manage targets →</button></div><div class="card-body">${performanceTable(data.sales_performance || [])}</div></section>`;
  const attentionPanel = `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>AI action queue</h2><small>Prioritized from live CRM dates and statuses</small></div><button type="button" class="card-head-link" data-go="/dashboard/report/ai-action-queue">View queue ↗</button></div><div class="card-body">${attentionQueue(data.attention || {})}</div></section>`;
  return `${pageHeader("Overview", `${greeting()}, ${String(state.profile?.name || "there").split(" ")[0]}`, "Here is what is happening across your customer workspace.", `<button class="button button-ghost" data-go="/ai"><span class="button-icon">✦</span>Ask AI</button><button class="button button-ghost" data-create="activities"><span class="button-icon">＋</span>Log activity</button><button class="button button-primary" data-create="leads"><span class="button-icon">＋</span>Add lead</button>`)}
    <div class="stats-grid">
      <button type="button" class="card stat-card dashboard-metric-link" data-go="/dashboard/report/total-leads" aria-label="Open Total leads report"><div class="stat-top"><span class="stat-label">Total leads</span><span class="stat-icon">✦</span></div><div class="stat-value">${metrics.total_leads}</div><div class="stat-foot"><span class="trend-up">Live</span><span>from CRM records</span></div></button>
      <button type="button" class="card stat-card dashboard-metric-link" data-go="/dashboard/report/open-deals" aria-label="Open Open deals report"><div class="stat-top"><span class="stat-label">Open deals</span><span class="stat-icon">◇</span></div><div class="stat-value">${metrics.open_deals}</div><div class="stat-foot"><span class="trend-up">Live</span><span>from CRM records</span></div></button>
      <button type="button" class="card stat-card dashboard-metric-link" data-go="/dashboard/report/pipeline-value" aria-label="Open Pipeline value report"><div class="stat-top"><span class="stat-label">Pipeline value</span><span class="stat-icon">₹</span></div><div class="stat-value">${formatMoney(metrics.pipeline_value)}</div><div class="stat-foot"><span class="trend-up">Live</span><span>open opportunities</span></div></button>
      <button type="button" class="card stat-card dashboard-metric-link" data-go="/dashboard/report/activities-due" aria-label="Open Activities due report"><div class="stat-top"><span class="stat-label">Activities due</span><span class="stat-icon">✓</span></div><div class="stat-value">${metrics.activities_due}</div><div class="stat-foot"><span class="trend-warm">Needs attention</span><span>next 7 days</span></div></button>
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
  const reportRows = data.items.length ? data.items.map((report) => `<div class="rule-row"><input type="checkbox" data-report-select="${report.id}" aria-label="Select ${esc(report.name)}"/><span class="related-dot">▤</span><div class="rule-info"><strong>${esc(report.name)}</strong><small>${esc(report.module || report.data?.module || "deals")} · ${esc(report.report_type || report.data?.report_type || "Tabular")} · ${report.data?.columns?.length || 0} columns</small></div>${badge(report.status)}<button class="button button-small button-ghost" data-run-report="${report.id}">Run</button><button class="table-action" data-report-edit="${report.id}" title="Edit report">✎</button><button class="table-action" data-report-delete="${report.id}" title="Delete report">Delete</button></div>`).join("") : emptyState("▤", "No saved reports", "Create a report definition to query CRM records.");
  return `${pageHeader("Analytics", "Report Engine", "Build secure, reusable reports over CRM modules with filters, grouping, and aggregates.", `<button class="button button-primary" data-new-report>＋ New report</button>`)}<div class="analytics-layout"><section class="card settings-section"><div class="settings-section-head"><h2>Saved reports</h2><p>Definitions are stored as metadata and executed through the server-side Report Engine.</p><button class="button button-small" data-reports-delete-selected>Delete selected</button></div>${reportRows}</section><section class="card settings-section" data-report-editor hidden><div class="settings-section-head"><h2>Report definition</h2><p>Use API names for fields. Filters accept equals, contains, comparisons, and empty checks.</p></div><form data-report-form class="settings-form"><input type="hidden" name="id" /><div class="form-grid"><div class="field"><label>Name</label><input class="field-input" name="name" required placeholder="Open pipeline by stage" /></div><div class="field"><label>Module</label><select class="field-select" name="module"><option value="deals">Deals</option><option value="leads">Leads</option><option value="accounts">Accounts</option><option value="contacts">Contacts</option><option value="quotes">Quotes</option><option value="invoices">Invoices</option></select></div><div class="field"><label>Type</label><select class="field-select" name="report_type"><option>Tabular</option><option>Summary</option><option>Matrix</option></select></div><div class="field"><label>Group by</label><input class="field-input" name="group_by" placeholder="stage" /></div><div class="field field-full"><label>Columns (JSON)</label><textarea class="field-input" name="columns" rows="2">["name","status","amount","owner_name"]</textarea></div><div class="field field-full"><label>Filters (JSON)</label><textarea class="field-input" name="filters" rows="3">[]</textarea></div><div class="field"><label>Aggregate (JSON)</label><input class="field-input" name="aggregate" placeholder='{"field":"amount","operation":"sum"}' /></div></div><div class="form-actions"><button class="button button-primary" type="submit">Save report</button><button class="button button-ghost" type="button" data-close-report>Cancel</button></div></form></section></div><section class="card settings-section" data-report-output hidden><div class="settings-section-head"><h2>Report output</h2><p data-report-run-meta></p></div><div data-report-result></div></section>`;
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
  $('[data-reports-delete-selected]')?.addEventListener("click",async()=>{
    const ids=$$('[data-report-select]:checked').map(el=>Number(el.dataset.reportSelect));
    if(!ids.length){toast("Select reports","Choose one or more reports to delete.");return;}
    if(!confirm("Move "+ids.length+" selected reports to Recycle Bin for 30 days?"))return;
    try {const result=await api("/api/administration/bulk-delete",{method:"POST",body:JSON.stringify({resource:"reports",ids})});toast("Reports deleted",result.deleted+" reports moved to Recycle Bin.");await renderRoute();}
    catch(error){toast("Delete failed",error.message,"error");}
  });
  $$('[data-report-delete]').forEach(button=>button.addEventListener("click",async()=>{
    if (!confirm("Delete this report? It can be restored from Recycle Bin for 30 days.")) return;
    try {await api("/api/platform/reports/"+button.dataset.reportDelete,{method:"DELETE"});toast("Report deleted","Moved to 30-day Recycle Bin.");await renderRoute();}
    catch(error){toast("Delete failed",error.message,"error");}
  }));
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

async function moduleView(resource) {
  const config = MODULES[resource];
  const current = state.moduleState[resource] || { search: "", status: "", owner_id: "", sort: "created_desc", min_amount: "", max_amount: "", close_from: "", close_to: "", offset: 0, view: "list", selectedIds: [] };
  state.moduleState[resource] = current;
  const advanced = FILTERABLE_MODULES.includes(resource);
  if (advanced && !current.filterCatalog) {
    current.filterCatalog = await api(`/api/module-filter-options/${resource}`);
  }
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
  if (advanced && current.advancedFilters?.rules?.length) {
    params.set("filters", JSON.stringify(current.advancedFilters));
  }
  const data = await api(`/api/${resource}?${params}`);
  const importAction = ["leads","deals","accounts","contacts"].includes(resource) ? `<button class="button button-ghost" data-start-import="${resource}">Import ${config.label}</button>` : "";
  const actions = `${importAction}<button class="button button-primary" data-create="${resource}"><span class="button-icon">＋</span>Add ${config.singular.toLowerCase()}</button>`;
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
    <div class="module-toolbar">${advanced ? `<button type="button" class="button button-ghost button-small advanced-filter-toggle" data-filter-toggle aria-expanded="${Boolean(current.filtersOpen)}" aria-controls="module-filter-sidebar">⚲ Filter${current.advancedFilters?.rules?.length ? ` (${current.advancedFilters.rules.length})` : ""}</button>` : ""}<label class="toolbar-search"><span>⌕</span><input data-module-search="${resource}" value="${esc(current.search)}" placeholder="${esc(config.search)}" /></label>${config.status.length ? `<select class="filter-select" data-module-status="${resource}"><option value="">All statuses</option>${config.status.map((option) => `<option ${current.status === option ? "selected" : ""}>${esc(option)}</option>`).join("")}</select>` : ""}<select class="filter-select" data-module-owner="${resource}"><option value="">All owners</option>${(state.meta?.users || []).map((user) => `<option value="${user.id}" ${String(current.owner_id) === String(user.id) ? "selected" : ""}>${esc(user.name)}</option>`).join("")}</select><select class="filter-select" data-module-sort="${resource}"><option value="created_desc" ${current.sort === "created_desc" ? "selected" : ""}>Recently added</option><option value="name_asc" ${current.sort === "name_asc" ? "selected" : ""}>Name A–Z</option>${resource === "deals" ? `<option value="amount_desc" ${current.sort === "amount_desc" ? "selected" : ""}>Amount high–low</option><option value="close_asc" ${current.sort === "close_asc" ? "selected" : ""}>Close date soonest</option>` : ""}${resource === "leads" ? `<option value="score_desc" ${current.sort === "score_desc" ? "selected" : ""}>Lead score high–low</option>` : ""}</select>${resource === "deals" ? `<input class="field-input" style="width:105px" data-deal-filter="min_amount" type="number" placeholder="Min amount" value="${esc(current.min_amount)}" /><input class="field-input" style="width:105px" data-deal-filter="max_amount" type="number" placeholder="Max amount" value="${esc(current.max_amount)}" /><input class="field-input" style="width:140px" data-deal-filter="close_from" type="date" value="${esc(current.close_from)}" /><input class="field-input" style="width:140px" data-deal-filter="close_to" type="date" value="${esc(current.close_to)}" />` : ""}<button class="button button-ghost button-small" data-clear-filters="${resource}">Clear filters</button>${resource === "accounts" ? `<button type="button" class="button button-primary button-small" data-selected-account-deal ${current.selectedIds.length === 1 ? "" : "disabled"}>Convert to Deal${current.selectedIds.length === 1 ? " (1 selected)" : ""}</button>` : ""}<button class="button button-ghost button-small" data-bulk-delete="${resource}" ${current.selectedIds.length ? "" : "disabled"}>Delete selected${current.selectedIds.length ? ` (${current.selectedIds.length})` : ""}</button><span style="margin-left:auto;color:var(--text-faint);font-size:11px">${data.total} record${data.total === 1 ? "" : "s"}</span></div>
    ${advanced
      ? `<div class="advanced-filter-layout ${current.filtersOpen ? "filters-visible" : ""}" data-filter-layout>
            ${renderModuleFilters(resource, current, current.filterCatalog, esc)}
            <div class="advanced-filter-results">${body}${current.view === "list" ? pagination(resource, data) : ""}</div>
          </div>`
      : `${body}${current.view === "list" ? pagination(resource, data) : ""}`}`;
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
  if (!state.moduleState[`platform:${resource}`]) state.moduleState[`platform:${resource}`] = { search: "", status: "", owner_id: "", sort: "updated_desc", offset: 0, selectedIds: [] };
  return state.moduleState[`platform:${resource}`];
}

function platformTable(resource, data) {
  return renderPlatformTable(resource, data, { state, platformState, emptyState, esc, formatMoney, formatDate, formatDateTime, badge, platformDisplay });
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
  const toolbar = `<div class="module-toolbar"><button class="button button-small" data-platform-bulk-delete ${current.selectedIds?.length ? "" : "disabled"}>Delete selected (${current.selectedIds?.length || 0})</button><label class="toolbar-search"><span>?</span><input data-platform-search="${resource}" value="${esc(current.search)}" placeholder="Search ${esc(config.label.toLowerCase())}..." /></label><select class="filter-select" data-platform-status="${resource}"><option value="">All statuses</option><option ${current.status === "Active" ? "selected" : ""}>Active</option><option ${current.status === "Inactive" ? "selected" : ""}>Inactive</option></select><select class="filter-select" data-platform-owner="${resource}"><option value="">All owners</option>${(state.meta?.users || []).map((user) => `<option value="${user.id}" ${String(current.owner_id) === String(user.id) ? "selected" : ""}>${esc(user.name)}</option>`).join("")}</select><select class="filter-select" data-platform-sort="${resource}"><option value="updated_desc">Recently updated</option><option value="name_asc" ${current.sort === "name_asc" ? "selected" : ""}>Name A-Z</option><option value="created_desc" ${current.sort === "created_desc" ? "selected" : ""}>Recently created</option></select><a class="button button-ghost button-small" href="/api/export/${resource}.csv" download>Export CSV</a><span style="margin-left:auto;color:var(--text-faint);font-size:11px">${data.total} record${data.total === 1 ? "" : "s"}</span></div>`;
  return `${toolbar}${platformTable(resource, data)}${compact ? "" : pagination(`platform:${resource}`, data)}`;
}

async function platformModuleView(resource) {
  const config = state.platformCatalog.resources[resource];
  await Promise.all((config.fields || []).filter((field) => String(field.type || "").startsWith("platform:")).map((field) => ensurePlatformLookup(field.type.split(":")[1])));
  return `${pageHeader(config.group || "Workspace", config.label, config.description, `<button class="button button-primary" data-platform-create="${resource}">+ Add ${config.singular.toLowerCase()}</button>`)}${await platformPanel(resource)}`;
}

let setupFeature;
function setupDirectory(...args) { return setupFeature.setupDirectory(...args); }
function setupSearchView(...args) { return setupFeature.setupSearchView(...args); }
function customizeSetupView(...args) { return setupFeature.customizeSetupView(...args); }
function auditView(...args) { return setupFeature.auditView(...args); }
function recycleBinView(...args) { return setupFeature.recycleBinView(...args); }
function importView(...args) { return setupFeature.importView(...args); }
function exportView(...args) { return setupFeature.exportView(...args); }
function duplicateView(...args) { return setupFeature.duplicateView(...args); }
function workflowRulesView(...args) { return setupFeature.workflowRulesView(...args); }
function securityAdminView(...args) { return setupFeature.securityAdminView(...args); }
function cpqView(...args) { return setupFeature.cpqView(...args); }
function bindSecurityAdmin(...args) { return setupFeature.bindSecurityAdmin(...args); }
function bindCPQ(...args) { return setupFeature.bindCPQ(...args); }
function developerHubView(...args) { return setupFeature.developerHubView(...args); }
function setupConsoleView(...args) { return setupFeature.setupConsoleView(...args); }
function bindDeveloperHub(...args) { return setupFeature.bindDeveloperHub(...args); }
function bindMetadataModuleActions(...args) { return setupFeature.bindMetadataModuleActions(...args); }
function bindSetupConsole(...args) { return setupFeature.bindSetupConsole(...args); }
function metadataFieldEnabled(...args) { return setupFeature.metadataFieldEnabled(...args); }
function customModulesAdminView(...args) { return setupFeature.customModulesAdminView(...args); }
function customModuleBuilderView(...args) { return setupFeature.customModuleBuilderView(...args); }
function builderFieldCards(...args) { return setupFeature.builderFieldCards(...args); }
function builderSlug(...args) { return setupFeature.builderSlug(...args); }
function renderBuilderFields(...args) { return setupFeature.renderBuilderFields(...args); }
function bindBuilderFieldActions(...args) { return setupFeature.bindBuilderFieldActions(...args); }
function saveCustomBuilder(...args) { return setupFeature.saveCustomBuilder(...args); }
function bindCustomModuleAdmin(...args) { return setupFeature.bindCustomModuleAdmin(...args); }
function customRuntimeFieldControl(...args) { return setupFeature.customRuntimeFieldControl(...args); }
function customRuntimeView(...args) { return setupFeature.customRuntimeView(...args); }
function bindCustomRuntime(...args) { return setupFeature.bindCustomRuntime(...args); }
function setupLandingView(...args) { return setupFeature.setupLandingView(...args); }
function setupView(...args) { return setupFeature.setupView(...args); }

function tableView(resource, data) {
  const config = MODULES[resource];
  if (!data.items.length) return `<section class="card">${emptyState(config.icon, `No ${config.label.toLowerCase()} found`, "Try changing your filters or create a new record.", `<button class="button button-primary" data-create="${resource}">Add ${config.singular.toLowerCase()}</button>`)}</section>`;
  const selectionHeader = `<th><input type="checkbox" data-select-all="${resource}" aria-label="Select all displayed records" /></th>`;
  return `<section class="card table-card"><div class="table-wrap"><table class="data-table"><thead><tr>${selectionHeader}${config.columns.map((column) => `<th>${column.label}</th>`).join("")}<th></th></tr></thead><tbody>${data.items.map((row) => `<tr><td><input type="checkbox" data-select-record="${resource}" data-id="${row.id}" ${state.moduleState[resource].selectedIds.includes(row.id) ? "checked" : ""} /></td>${config.columns.map((column) => `<td class="${column.key === "name" ? "primary-cell" : ""}">${column.cell ? column.cell(row) : esc(row[column.key] ?? "—")}</td>`).join("")}<td><div class="table-actions">${resource === "activities" && row.status !== "Completed" ? `<button class="table-action" title="Mark complete" data-complete-activity="${row.id}">✓</button>` : ""}${resource === "accounts" ? `<button class="table-action" title="Convert to Deal" data-create-account-deal="${row.id}">Convert to Deal</button>` : ""}<button class="table-action" title="Edit" data-edit-record="${resource}" data-id="${row.id}">✎</button><button class="table-action" title="Delete (30-day Recycle Bin)" data-delete-record="${resource}" data-id="${row.id}">⌫</button></div></td></tr>`).join("")}</tbody></table></div></section>`;
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

function flatSplitPreview(resource, row) {
  const config=MODULES[resource], name=row.name||row.subject||row.full_name||row.title||`Record ${row.id}`;
  const labels={status:"Status",stage:"Stage",company:"Company",source:"Source",email:"Email",phone:"Phone",lead_score:"Lead score",next_follow_up:"Follow-up",owner_name:"Owner",account_name:"Account",amount:"Amount",probability:"Probability",expected_close_date:"Closing date"};
  const keys=resource==="leads"?["status","company","source","email","phone","lead_score","next_follow_up","owner_name"]:
    resource==="deals"?["stage","account_name","amount","probability","expected_close_date","owner_name"]:
    (config.columns||[]).map(c=>c.key).filter(k=>k&&k!=="name").slice(0,8);
  const details=[...new Set(keys)].filter(key=>row[key]!=null&&row[key]!=="").map(key=>{
    const label=labels[key]||(config.columns||[]).find(c=>c.key===key)?.label||titleCase(key);
    const value=key==="amount"?formatMoney(row[key]):["next_follow_up","expected_close_date"].includes(key)?formatDate(row[key]):
      key==="probability"?`${Number(row[key])}%`:String(row[key]);
    return `<div class="flat-preview-field"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
  }).join("");
  return `<div class="flat-preview-heading"><div><span class="flat-section-eyebrow">${esc(config.singular)} preview</span><h2>${esc(name)}</h2>
    <p>Choose a record on the left to inspect its details.</p></div>
    <button type="button" class="button button-primary button-small" data-split-open="${resource}" data-id="${row.id}">Open record ↗</button></div>
    <dl class="flat-preview-fields">${details||'<p class="flat-muted">No additional details available.</p>'}</dl>`;
}

function splitView(resource,data) {
  const config=MODULES[resource], current=state.moduleState[resource];
  if(!data.items.length)return `<section class="flat-empty">${emptyState(config.icon,`No ${config.label.toLowerCase()} found`,"Change filters or create a new record.")}</section>`;
  const selected=data.items.find(item=>String(item.id)===String(current.splitSelectedId))||data.items[0];
  current.splitSelectedId=selected.id;current.splitRows=data.items;
  return `<div class="module-split-flat"><nav class="flat-split-list" aria-label="${esc(config.label)} records">
    <div class="flat-split-heading"><strong>Records</strong><span>${data.items.length} shown</span></div>
    ${data.items.map(item=>{
      const name=item.name||item.subject||item.full_name||item.title||`Record ${item.id}`;
      const active=String(item.id)===String(selected.id);
      return `<button type="button" class="flat-split-item ${active?"active":""}" data-split-select="${resource}" data-id="${item.id}" aria-pressed="${active}">
        <span class="flat-split-avatar" aria-hidden="true">${esc(initials(name))}</span>
        <span class="flat-split-copy"><strong>${esc(name)}</strong><small>${esc(item.status||item.stage||item.company||"Record")}</small></span>
        <span class="flat-split-chevron" aria-hidden="true">›</span></button>`;
    }).join("")}</nav>
    <section class="flat-split-preview" data-split-preview aria-live="polite">${flatSplitPreview(resource,selected)}</section></div>`;
}

function chartView(resource, data) {
  const config = MODULES[resource];
  const key = resource === 'deals' ? 'stage' : 'status';
  const counts = {};
  data.items.forEach((row) => { const label = String(row[key] || 'Unspecified'); counts[label] = (counts[label] || 0) + 1; });
  const max = Math.max(1, ...Object.values(counts));
  return `<section class="card settings-section"><div class="settings-section-head"><h2>${esc(config.label)} distribution</h2><p>Current filtered records grouped by ${esc(key)}.</p></div><div class="pipeline-chart">${Object.entries(counts).map(([label,count]) => `<div class="pipeline-row"><span class="pipeline-label">${esc(label)}</span><div class="progress-track"><div class="progress-bar" style="width:${Math.max(4, Number(count) / max * 100)}%"></div></div><span class="pipeline-meta"><strong>${count}</strong> record${count === 1 ? '' : 's'}</span></div>`).join('') || `<p class="related-empty">No chart data available.</p>`}</div></section>`;
}

function timelineModuleView(resource,data) {
  const config=MODULES[resource];
  const rows=[...data.items].sort((a,b)=>String(b.updated_at||b.created_at||"").localeCompare(String(a.updated_at||a.created_at||"")));
  let previousDay="";
  const items=rows.map(item=>{
    const name=item.name||item.subject||item.full_name||item.title||`Record ${item.id}`;
    const date=String(item.updated_at||item.created_at||""),day=date.slice(0,10);
    const heading=day&&day!==previousDay?`<h3 class="flat-timeline-day">${esc(formatDate(date))}</h3>`:"";
    previousDay=day;
    return `${heading}<button type="button" class="flat-timeline-entry" data-open-record="${resource}" data-id="${item.id}">
      <span class="flat-timeline-rail" aria-hidden="true"><span class="flat-timeline-point"></span></span>
      <span class="flat-timeline-copy"><strong>${esc(name)}</strong>
        <small>${esc(item.status||item.stage||"Updated")}${item.company?` · ${esc(item.company)}`:""}</small></span>
      <time class="flat-timeline-time" datetime="${esc(date)}">${esc(formatDateTime(date))}</time>
      <span class="flat-timeline-open" aria-hidden="true">↗</span></button>`;
  }).join("");
  return `<section class="flat-timeline-view"><header class="flat-timeline-heading"><h2>${esc(config.label)} timeline</h2>
    <p>Recent filtered records, newest changes first.</p></header>
    <div class="flat-timeline-entries">${items||'<p class="flat-muted">No timeline entries match the filters.</p>'}</div></section>`;
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
  bindModuleFilters({resource, current, renderRoute, toast});
  $$("[data-start-import]").forEach(button => button.addEventListener("click", () => navigate("/import/" + button.dataset.startImport)));
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create, null, button.dataset.activityType ? { activity_type: button.dataset.activityType } : {})));
  $$('[data-open-record]').forEach((button) => button.addEventListener("click", () => navigate(pathFor(button.dataset.openRecord, button.dataset.id))));

  const splitRoot = $(".module-split-flat");
  splitRoot?.addEventListener("click", event => {
    const open = event.target.closest("[data-split-open]");
    if (open) { navigate(pathFor(open.dataset.splitOpen, open.dataset.id)); return; }
    const button = event.target.closest("[data-split-select]");
    if (!button) return;
    const record = current.splitRows?.find(row => String(row.id) === button.dataset.id);
    if (!record) return;
    current.splitSelectedId = record.id;
    $$("[data-split-select]", splitRoot).forEach(item => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    const preview = $("[data-split-preview]", splitRoot);
    if (preview) preview.innerHTML = flatSplitPreview(resource, record);
  });
  bindContextCreationActions();
  $("[data-selected-account-deal]")?.addEventListener("click", () => {
    if (current.selectedIds.length === 1) openDealForAccount(current.selectedIds[0]);
  });
  $$('[data-edit-record]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.editRecord, Number(button.dataset.id))));
  $$('[data-delete-record]').forEach((button) => button.addEventListener("click", () => deleteRecord(button.dataset.deleteRecord, Number(button.dataset.id))));
  const search = $("[data-module-search]");
  let searchTimer;
  search?.addEventListener("input", (event) => { clearTimeout(searchTimer); current.search = event.target.value; current.offset = 0; searchTimer = setTimeout(renderRoute, 260); });
  $("[data-module-status]")?.addEventListener("change", (event) => { current.status = event.target.value; current.offset = 0; renderRoute(); });
  $("[data-module-owner]")?.addEventListener("change", (event) => { current.owner_id = event.target.value; current.offset = 0; renderRoute(); });
  $("[data-module-sort]")?.addEventListener("change", (event) => { current.sort = event.target.value; current.offset = 0; renderRoute(); });
  $$('[data-deal-filter]').forEach((input) => input.addEventListener("change", (event) => { current[event.target.dataset.dealFilter] = event.target.value; current.offset = 0; renderRoute(); }));
  $("[data-clear-filters]")?.addEventListener("click", () => { Object.assign(current, { search: "", status: "", owner_id: "", sort: "created_desc", min_amount: "", max_amount: "", close_from: "", close_to: "", offset: 0, advancedFilters: {join:"all", rules:[]}, selectedIds: [] }); renderRoute(); });
  $$('[data-select-record]').forEach((input) => input.addEventListener("change", (event) => { const id = Number(event.target.dataset.id); current.selectedIds = event.target.checked ? [...new Set([...current.selectedIds, id])] : current.selectedIds.filter((selected) => selected !== id); renderRoute(); }));
  $("[data-select-all]")?.addEventListener("change", (event) => { current.selectedIds = event.target.checked ? [...new Set([...current.selectedIds, ...dataIds(resource)])] : current.selectedIds.filter((id) => !dataIds(resource).includes(id)); renderRoute(); });
  $("[data-bulk-delete]")?.addEventListener("click", async () => {
    if (!current.selectedIds.length || !confirm("Move selected records to Recycle Bin for 30 days?")) return;
    try {
      const result = await api("/api/administration/bulk-delete",{method:"POST",body:JSON.stringify({resource,ids:current.selectedIds})});
      current.selectedIds=[];
      toast("Records deleted",result.deleted+" records moved to Recycle Bin.");
      await renderRoute();
    } catch(error) {toast("Bulk delete failed",error.message,"error");}
  });
  $$('[data-toggle-view]').forEach((button) => button.addEventListener("click", () => { current.view = button.dataset.toggleView; renderRoute(); }));
  $$('[data-complete-activity]').forEach((button) => button.addEventListener("click", async () => { try { await api(`/api/activities/${button.dataset.completeActivity}`, { method: "PATCH", body: JSON.stringify({ status: "Completed" }) }); toast("Activity completed", "Nice work — it has been marked as done."); await renderRoute(); } catch (error) { toast("Could not update activity", error.message, "error"); } }));
  $$('[data-page]').forEach((button) => button.addEventListener("click", () => { current.offset += button.dataset.page === "next" ? 25 : -25; renderRoute(); }));
}

async function detailView(resource, id) {
  const [record, related, timeline] = await Promise.all([api(`/api/${resource}/${id}`), api(`/api/${resource}/${id}/related`), ["leads", "deals"].includes(resource) ? api(`/api/${resource}/${id}/timeline`) : Promise.resolve(null)]);
  const config = MODULES[resource];
  const title = resource === "contacts" ? record.full_name : record.name || record.subject;
  const secondary = resource === "leads" ? record.company || record.email : resource === "contacts" ? record.email || record.job_title : resource === "accounts" ? record.website || record.industry : resource === "deals" ? `${record.stage} · ${formatMoney(record.amount)}` : resource === "products" ? `${record.category || "Product"} · ${formatMoney(record.unit_price)}` : `${titleCase(record.activity_type)} · ${formatDateTime(record.due_at)}`;
  const details = detailFields(resource, record);
  const contextualActions = resource === "deals"
    ? `<button type="button" class="button button-primary" data-create-deal-quote="${id}">Create Quote</button>`
    : resource === "accounts"
      ? `<button type="button" class="button button-primary" data-create-account-deal="${id}">Convert to Deal</button>`
      : "";
  return `${pageHeader(config.label, title, secondary || "Record detail", `${resource === "leads" ? `<button class="button button-ghost" data-go="/ai?lead=${id}">✦ Analyze with AI</button>` : ""}${contextualActions}<button class="button button-ghost" data-go="/${resource}">← Back to ${config.label.toLowerCase()}</button><button class="button button-primary" data-edit-record="${resource}" data-id="${id}">Edit ${config.singular.toLowerCase()}</button>`)}
    <section class="card detail-summary"><div class="detail-title-row"><span class="detail-avatar">${initials(title)}</span><div class="detail-title-copy"><span class="eyebrow">${esc(config.singular)}</span><h2>${esc(title)}</h2><p>${esc(secondary || "No summary available")}</p></div><div class="detail-actions">${resource === "leads" && record.status !== "Converted" && !timeline?.blueprint_enabled ? `<button class="button button-small button-ghost" data-convert-lead="${id}">Convert</button>` : ""}<button class="button button-small button-ghost" data-delete-record="${resource}" data-id="${id}">Archive</button></div></div><div class="detail-meta-grid">${details.map((item) => `<div><span class="meta-label">${esc(item.label)}</span><span class="meta-value">${item.html || esc(item.value || "—")}</span></div>`).join("")}</div>${record.notes ? `<div class="notes-box"><h3>Notes</h3><p>${esc(record.notes)}</p></div>` : ""}</section>
    <div class="detail-record-layout"><aside class="detail-related-nav"><div class="detail-related-nav-head"><h3>Related List</h3></div>${relatedNavigation(resource, related, timeline)}</aside><section class="detail-record-main"><div class="detail-tab-strip"><button class="detail-tab active" type="button" data-detail-tab="overview">Overview</button><button class="detail-tab" type="button" data-detail-tab="timeline">Timeline</button></div><div class="detail-tab-panel" data-detail-panel="overview">${resource === "leads" ? leadStagePanel(record, timeline) : ""}${resource === "deals" ? `<section class="detail-plain-section" id="detail-section-stage_progress"><div class="detail-plain-head"><h3>Stage progress</h3></div><div class="detail-plain-body">${blueprintDealProgress(record,timeline)}</div></section>` : ""}${relatedContent(resource, related)}</div><div class="detail-tab-panel" data-detail-panel="timeline" hidden><section class="detail-plain-section" id="detail-section-timeline"><div class="detail-plain-head"><h3>Timeline</h3></div><div class="detail-plain-body">${(resource === "leads" || resource === "deals") ? timelineHtml(timeline?.items || []) : `<div class="activity-list">${related.activities?.length ? related.activities.map(activityItem).join("") : `<p class="related-empty">No linked activity yet.</p>`}</div>`}</div></section></div></section></div>`;
}

function detailFields(resource, record) {
  const owner = record.owner_name || "Unassigned";
  if (resource === "leads") return [{ label: "Status", html: badge(record.status) }, { label: "Owner", value: owner }, { label: "Lead score", value: `${record.lead_score || 0}/100` }, { label: "Email", value: record.email }, { label: "Phone", value: record.phone }, { label: "Follow-up", value: formatDate(record.next_follow_up) }];
  if (resource === "contacts") return [{ label: "Email", value: record.email }, { label: "Phone", value: record.phone }, { label: "Job title", value: record.job_title }, { label: "Department", value: record.department }, { label: "Account", value: lookupName("accounts", record.account_id) }, { label: "Owner", value: owner }];
  if (resource === "accounts") return [{ label: "Type", value: record.type }, { label: "Industry", value: record.industry }, { label: "Employees", value: record.employees }, { label: "Website", value: record.website }, { label: "Location", value: [record.billing_city, record.billing_country].filter(Boolean).join(", ") }, { label: "Owner", value: owner }];
  if (resource === "deals") return [{ label: "Current stage", html: badge(record.stage) }, { label: "Amount", value: formatMoney(record.amount) }, { label: "Probability", value: `${record.probability || 0}%` }, { label: "Account", value: lookupName("accounts", record.account_id) }, { label: "Close date", value: formatDate(record.expected_close_date) }, { label: "Owner", value: owner }];
  if (resource === "products") return [{ label: "SKU", value: record.sku }, { label: "Category", value: record.category }, { label: "Unit price", value: formatMoney(record.unit_price) }, { label: "Stock", value: record.stock_quantity }, { label: "Status", html: badge(record.status) }, { label: "Owner", value: owner }];
  return [{ label: "Type", value: titleCase(record.activity_type) }, { label: "Status", html: badge(record.status) }, { label: "Priority", html: badge(record.priority) }, { label: "Starts", value: formatDateTime(record.start_at) }, { label: "Due", value: formatDateTime(record.due_at) }, { label: "Owner", value: owner }, { label: "Related to", value: record.related_label }];
}

function relatedNavigation(resource, related, timeline = null) {
  const openActivities = (related.activities || []).filter((item) => item.status !== 'Completed').length;
  const closedActivities = (related.activities || []).filter((item) => item.status === 'Completed').length;
  const connectedCount = (related.accounts || []).length + (related.contacts || []).length + (related.deals || []).length;
  const items = [
    ['current_stage', 'Current stage & transitions', resource === 'leads'],
    ['stage_progress', 'Stage progress', resource === 'deals'],
    ['notes', 'Notes', true, (related.notes || []).length],
    ['connected_records', 'Connected records', ['accounts', 'contacts', 'deals'].includes(resource) || connectedCount > 0, connectedCount],
    ['attachments', 'Attachments', true, (related.attachments || []).length],
    ['products', 'Products', true, (related.products || []).length],
    ['open_activities', 'Open activities', true, openActivities],
    ['closed_activities', 'Closed activities', closedActivities > 0, closedActivities],
    ['custom_records', 'Custom & related modules', (related.custom_records || []).length > 0, (related.custom_records || []).length],
    ['emails', 'Emails', true, (related.emails || []).length],
    ['timeline', 'Timeline', true, timeline ? (timeline.items || []).length : (related.activities || []).length],
  ].filter(([, , visible]) => visible);
  return `<nav class="detail-related-links">${items.map(([key, label, , count]) => `<button class="detail-related-link" type="button" data-detail-nav="${key}" data-detail-target="detail-section-${key}"><span>${esc(label)}</span>${count > 0 ? `<small>${count}</small>` : ''}</button>`).join('')}</nav>`;
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
  sections.push(relatedPlainSection('notes', 'Notes', (related.notes || []).map((item) => relatedPlainRow(item.title, item.content || 'Open note', 'notes', item.id, false)), 'notes', 'No notes yet.'));
  const connectedRows = [];
  if (related.accounts?.length) connectedRows.push(...related.accounts.map((item) => relatedPlainRow(item.name, item.industry || item.type || 'Account', 'accounts', item.id)));
  if (related.contacts?.length) connectedRows.push(...related.contacts.map((item) => relatedPlainRow(item.full_name || `${item.first_name} ${item.last_name}`, item.job_title || item.email || 'Contact', 'contacts', item.id)));
  if (related.deals?.length) connectedRows.push(...related.deals.map((item) => relatedPlainRow(item.name, `${formatMoney(item.amount)} · ${item.stage}`, 'deals', item.id)));
  sections.push(relatedPlainSection('connected_records', 'Connected records', connectedRows, null, 'No connected records found.'));
  sections.push(relatedPlainSection('attachments', 'Attachments', (related.attachments || []).map((item) => item.url && /^\/api\/documents\/\d+\/download$/.test(item.url) ? `<a class="detail-related-row" href="${esc(item.url)}"><span class="detail-related-row-copy"><strong>${esc(item.name)}</strong><small>${esc(item.file_type || 'File')} · ${esc(item.file_size || 'Size not set')}</small></span><span class="detail-related-row-action">Download ↓</span></a>` : relatedPlainRow(item.name, `${item.file_type || 'File'} · ${item.file_size || 'Size not set'}`, 'attachments', item.id, false)), 'attachments', 'No attachments yet.'));
  sections.push(relatedPlainSection('products', 'Products', (related.products || []).map((item) => relatedPlainRow(item.name, `${formatMoney(item.unit_price)} · ${item.sku || 'No SKU'}`, 'products', item.id)), 'products', 'No products yet.'));
  sections.push(relatedPlainSection('open_activities', 'Open activities', (related.activities || []).filter((item) => item.status !== 'Completed').map((item) => relatedPlainRow(item.subject, `${titleCase(item.activity_type)} · ${formatDateTime(item.due_at)}`, 'activities', item.id)), 'activities', 'No open activities yet.'));
  const closedActivities = (related.activities || []).filter((item) => item.status === 'Completed').map((item) => relatedPlainRow(item.subject, `${titleCase(item.activity_type)} · completed ${formatDateTime(item.updated_at || item.due_at)}`, 'activities', item.id));
  if (closedActivities.length) sections.push(relatedPlainSection('closed_activities', 'Closed activities', closedActivities, 'activities', 'No closed activities yet.'));
  if ((related.custom_records || []).length) {
    sections.push(relatedPlainSection('custom_records', 'Custom & related modules',
      related.custom_records.map(item => `<button class="detail-related-row" type="button" data-related-platform="${esc(item.resource)}" data-id="${Number(item.id)}"><span class="detail-related-row-copy"><strong>${esc(item.title || 'Related record')}</strong><small>${esc(item.resource)} · ${esc(item.status || '')}</small></span><span class="detail-related-row-action">›</span></button>`),
      null, 'No custom records.'));
  }
  sections.push(relatedPlainSection('emails', 'Emails', (related.emails || []).map((item) => relatedPlainRow(item.subject, `${item.status} · ${item.to_email || 'No recipient'}`, 'emails', item.id, false)), 'emails', 'No email yet.'));
  return sections.join('');
}

function leadStagePanel(record,timeline) {
  const current = timeline?.current_stage || record.status || "New";
  const custom = !!timeline?.blueprint_enabled;
  const choices = custom ? (timeline.transition_details || []) : MODULES.leads.status.filter(s => s !== current).map(s => ({label:s,to:s}));
  const converted = current === "Converted" && record.status === "Converted" && Boolean(record.converted_deal_id);
  return `<section class="detail-plain-section crm-lead-state" id="detail-section-current_stage"><div class="detail-plain-head"><h3>Current stage &amp; transitions</h3><span class="crm-stage-label">${custom ? esc(timeline.blueprint_name || "Custom Blueprint") : "Lead process"}</span></div>
    <div class="crm-state-body"><div class="crm-state-current"><span>Current stage</span><strong>${esc(current)}</strong></div>
    <div class="crm-state-actions"><span>Available transitions</span><div class="crm-transition-options">${converted ? `<div class="crm-conversion-confirmation"><p class="related-empty">This lead has been converted.</p><button class="crm-transition-action" type="button" data-go="/deals/${Number(record.converted_deal_id)}">View created Deal →</button></div>` : choices.length ? choices.map(choice =>
      custom ? `<button type="button" class="crm-transition-action" data-blueprint-move="${esc(choice.id)}" data-blueprint-resource="leads" data-blueprint-record="${record.id}" data-blueprint-required="${esc(JSON.stringify(choice.required || []))}" title="${esc(choice.message || choice.to)}">${esc(choice.label || choice.to)} <span aria-hidden="true">→</span></button>` :
      `<button type="button" class="crm-transition-action" data-lead-transition="${record.id}" data-status="${esc(choice.to)}">${esc(choice.label)} <span aria-hidden="true">→</span></button>`).join("") : `<p class="related-empty">${custom ? "No outgoing transitions from this stage in the published Blueprint." : "No transitions are available from this stage."}</p>`}
    </div><small>${custom ? "Transitions and rules are supplied by the published Blueprint." : "Contacted creates or links an Account and Contact; Converted creates a Deal."}</small></div></div></section>`;
}

function timelineHtml(events) {
  const ordered = [...events].sort((a,b) => String(b.occurred_at).localeCompare(String(a.occurred_at)));
  const renderEntries = (rows) => {
    if (!rows.length) return `<p class="crm-timeline-empty">No record history yet.</p>`;
    let dateKey = "";
    return rows.map((item) => {
      const key = String(item.occurred_at || "").slice(0,10);
      const dayHeading = key && key !== dateKey ? `<div class="crm-timeline-day">${esc(formatDate(key))}</div>` : "";
      dateKey = key;
      const kind = ["activity","note"].includes(item.kind) ? item.kind : "audit";
      const time = item.occurred_at ? formatDateTime(item.occurred_at) : "";
      return `${dayHeading}<article class="crm-timeline-event" data-timeline-entry="${kind}"><div class="crm-timeline-dot ${kind}" aria-hidden="true">${kind === "activity" ? "✓" : kind === "note" ? "✎" : "↻"}</div><div class="crm-timeline-event-body"><strong>${esc(item.title || "Record updated")}</strong>${item.detail ? `<p>${esc(item.detail)}</p>` : ""}<small>${esc(item.actor_name || "System")} · ${esc(time)}</small></div></article>`;
    }).join("");
  };
  const interactions = ordered.filter((item) => ["activity","note"].includes(item.kind));
  return `<div class="crm-timeline"><div class="crm-timeline-toolbar"><div class="crm-timeline-tabs" role="group" aria-label="Timeline view"><button type="button" class="crm-timeline-tab active" data-timeline-kind="history" aria-pressed="true">History</button><button type="button" class="crm-timeline-tab" data-timeline-kind="interactions" aria-pressed="false">Interactions</button></div><label class="crm-timeline-filter-label">Filter <select class="crm-timeline-filter" data-timeline-filter><option value="all">All events</option><option value="audit">Record changes</option><option value="activity">Activities</option><option value="note">Notes</option></select></label></div><div data-timeline-content="history" class="crm-timeline-list">${renderEntries(ordered)}</div><div data-timeline-content="interactions" class="crm-timeline-list" hidden>${renderEntries(interactions)}</div></div>`;
}

function dealProgress(record) {
  const stages = MODULES.deals.status.filter((stage) => stage !== "Closed Lost");
  const current = record.stage || stages[0];
  const selectedIndex = stages.indexOf(current);
  const completed = current === "Closed Lost" ? stages.length - 2 : selectedIndex;
  return `<div class="crm-deal-pipeline" aria-label="Deal stage process">
    <div class="crm-pipeline-header">
      <div><span>START</span><strong>${esc(formatDate(record.created_at))}</strong></div>
      <div class="crm-pipeline-current"><span>Current stage</span><strong>${esc(current)}</strong></div>
      <div><span>CLOSING</span><strong>${esc(formatDate(record.expected_close_date))}</strong></div>
    </div>
    <div class="crm-pipeline-track" role="group" aria-label="Select deal stage">${stages.map((stage,index) => `<button type="button" class="crm-pipeline-step ${current === stage ? "is-current" : index < completed ? "is-complete" : "is-upcoming"}" data-stage-update="${record.id}" data-stage="${esc(stage)}" aria-label="Move deal to ${esc(stage)}" ${current === stage ? `aria-current="step" disabled` : ""}><span>${esc(stage)}</span><small>${current === stage ? "Current stage" : index < completed ? "Completed" : "Select stage"}</small></button>`).join("")}</div>
    <div class="crm-pipeline-footer"><span>Click a stage to update this deal. Blueprint rules and permissions still apply.</span><button type="button" class="crm-pipeline-lost ${current === "Closed Lost" ? "is-current" : ""}" data-stage-update="${record.id}" data-stage="Closed Lost" ${current === "Closed Lost" ? 'aria-current="step" disabled' : ""}>${current === "Closed Lost" ? "Closed Lost · Current stage" : "Mark Closed Lost"}</button></div>
  </div>`;
}

function blueprintDealProgress(record,timeline) {
  if (!timeline?.blueprint_enabled) return dealProgress(record);
  const stages = (timeline.blueprint_states || []).filter(Boolean);
  const current = timeline.current_stage || record.stage;
  const choices = timeline.transition_details || [];
  return `<div class="crm-deal-pipeline" aria-label="Published Blueprint process">
    <div class="crm-pipeline-header"><div><span>BLUEPRINT</span><strong>${esc(timeline.blueprint_name || "Custom process")}</strong></div>
    <div class="crm-pipeline-current"><span>Current stage</span><strong>${esc(current)}</strong></div>
    <div><span>CLOSING</span><strong>${esc(formatDate(record.expected_close_date))}</strong></div></div>
    <div class="crm-pipeline-track" role="group" aria-label="Blueprint states">${stages.map(stage => {
      const edge = choices.find(item => item.to === stage);
      const isCurrent = stage === current;
      return `<button type="button" class="crm-pipeline-step ${isCurrent ? "is-current" : edge ? "is-upcoming" : "is-complete"}" ${edge ? `data-blueprint-move="${esc(edge.id)}" data-blueprint-resource="deals" data-blueprint-record="${record.id}" data-blueprint-required="${esc(JSON.stringify(edge.required || []))}"` : "disabled"} ${isCurrent ? 'aria-current="step"' : ""}><span>${esc(stage)}</span><small>${isCurrent ? "Current stage" : edge ? "Available" : "Not available"}</small></button>`;
    }).join("")}</div>
    <div class="crm-pipeline-footer"><span>Available Blueprint transitions</span><div class="crm-transition-options">${choices.length ? choices.map(edge => `<button class="crm-transition-action" data-blueprint-move="${esc(edge.id)}" data-blueprint-resource="deals" data-blueprint-record="${record.id}" data-blueprint-required="${esc(JSON.stringify(edge.required || []))}" title="${esc(edge.message || edge.to)}">${esc(edge.label)} →</button>`).join("") : "<span>No available transitions</span>"}</div></div></div>`;
}

function bindBlueprintMoves(){
  $$('[data-blueprint-move]').forEach(button=>button.addEventListener("click", async()=>{
    const resource = button.dataset.blueprintResource;
    const recordId = button.dataset.blueprintRecord;
    const required = JSON.parse(button.dataset.blueprintRequired || "[]");
    const fields = {};
    for(const name of required){
      const answer = window.prompt(`Required field: ${name}`);
      if(answer===null)return;
      const trimmed=answer.trim();
      if(!trimmed){toast("Required field",`${name} cannot be empty.`,"error");return;}
      fields[name]=["amount","probability","lead_score"].includes(name)?Number(trimmed):trimmed;
    }
    button.disabled=true;
    try {
      const changed = await api(`/api/blueprint-records/${resource}/${recordId}/transition`,{method:"POST",body:JSON.stringify({transition_id:button.dataset.blueprintMove,fields})});
      toast("Blueprint transition completed","Current stage and transitions updated.");
      if(resource==="leads" && changed.status==="Converted" && changed.converted_deal_id) toast("Lead converted","Account, Contact and Deal records are now linked.");
      await renderRoute();
    }catch(error){button.disabled=false;toast("Transition blocked",error.message,"error");}
  }));
}

function bindDetail(resource, id) {
  bindBlueprintMoves();
  $$('[data-go]').forEach((button) => button.addEventListener("click", () => navigate(button.dataset.go)));
  $$('[data-edit-record]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.editRecord, Number(button.dataset.id))));
  $$('[data-delete-record]').forEach((button) => button.addEventListener("click", () => deleteRecord(button.dataset.deleteRecord, Number(button.dataset.id))));
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create, null, { related_type: resource, related_id: id })));
  $$('[data-platform-create]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate, null, { lead_id: button.dataset.leadId ? Number(button.dataset.leadId) : null, deal_id: button.dataset.dealId ? Number(button.dataset.dealId) : null })));
  $$('[data-related-platform]').forEach(button => button.addEventListener('click', () => navigate('/' + encodeURIComponent(button.dataset.relatedPlatform))));
  $$('[data-open-record]').forEach((button) => button.addEventListener("click", () => navigate(pathFor(button.dataset.openRecord, button.dataset.id))));
  $("[data-convert-lead]")?.addEventListener("click", () => openConvertModal(Number(id)));
  bindContextCreationActions();
  $$('[data-lead-transition]').forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const changed = await api(`/api/leads/${button.dataset.leadTransition}`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.status }) });
      toast("Lead updated", `Stage changed to ${button.dataset.status}`);
      if(changed.status==="Converted" && changed.converted_deal_id) await navigate(`/deals/${changed.converted_deal_id}`);
      else await renderRoute();
    } catch (error) { button.disabled = false; toast("Lead transition failed", error.message, "error"); }
  }));
  $$('[data-stage-update]').forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await api(`/api/deals/${button.dataset.stageUpdate}`, { method: "PATCH", body: JSON.stringify({ stage: button.dataset.stage }) });
      toast("Deal updated", `Current stage: ${button.dataset.stage}`);
      await renderRoute();
    } catch (error) { button.disabled = false; toast("Deal transition failed", error.message, "error"); }
  }));
  $$('[data-timeline-kind]').forEach((button) => button.addEventListener("click", () => {
    $$('[data-timeline-kind]').forEach((entry) => { entry.classList.toggle('active', entry === button); entry.setAttribute('aria-pressed', entry === button ? 'true' : 'false'); });
    $$('[data-timeline-content]').forEach((panel) => { panel.hidden = panel.dataset.timelineContent !== button.dataset.timelineKind; });
    const filter = $('[data-timeline-filter]');
    if (filter) { filter.value = 'all'; filter.dispatchEvent(new Event('change')); }
  }));
  $('[data-timeline-filter]')?.addEventListener('change', (event) => {
    const selected = event.target.value;
    $$('[data-timeline-content] .crm-timeline-event').forEach((item) => {
      item.hidden = selected !== 'all' && item.dataset.timelineEntry !== selected;
    });
  });
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
  const isNumberField = ["record_number","quote_number","order_number","po_number","invoice_number"].includes(field.key);
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
    input = `<input class="field-input" id="${id}" name="${field.key}" type="${type}" value="${esc(isNumberField && !rendered ? "Assigned on save" : rendered)}" ${isNumberField ? "readonly aria-readonly=true" : ""} ${type === "number" ? 'step="any" data-numeric="true"' : ""} ${required} />`;
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
  $("#modal-submit").textContent = id ? "Save changes" : resource === "users" ? "Send invitation" : `Create ${config.singular.toLowerCase()}`;
  $("#modal-body").innerHTML = `<div class="form-grid">${config.fields.map((field) => fieldHtml(field, record[field.key])).join("")}</div>`;
  if (resource === "attachments" && !id) installAttachmentPicker($("#modal-body"));
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
  $("#modal-body").innerHTML = `<div class="form-grid">${config.fields.filter((field) => !["record_number","quote_number","order_number","po_number","invoice_number"].includes(field.key)).map((field) => fieldHtml(field, record[field.key])).join("")}${config.fields.some((field) => field.key === "owner_id") ? "" : fieldHtml({ key: "owner_id", label: "Owner", type: "user" }, record.owner_id)}</div>`;
  $("#modal-backdrop").hidden = false;
  $("#modal-body input, #modal-body select, #modal-body textarea")?.focus();
}

function settingsResourceConfig(resource) {
  if (resource === "users") return { label: "Users", singular: "User", fields: [{ key: "name", label: "Name", required: true }, { key: "email", label: "Email", type: "email", required: true }, { key: "role", label: "Role", type: "select", options: ["Administrator", "Sales manager", "Sales rep"] }, { key: "status", label: "Status", type: "select", options: ["Active", "Inactive"], hint: "For new teammates, access begins after they accept the invitation." }] };
  if (resource === "notes") return { label: "Notes", singular: "Note", fields: [{ key: "title", label: "Title", required: true }, { key: "content", label: "Note", type: "textarea", full: true }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" }] };
  if (resource === "attachments") return { label: "Attachments", singular: "Attachment", fields: [{ key: "name", label: "File name", required: true }, { key: "file_type", label: "File type" }, { key: "file_size", label: "File size" }, { key: "url", label: "File URL" }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" }] };
  if (resource === "emails") return { label: "Emails", singular: "Email", fields: [{ key: "subject", label: "Subject", required: true }, { key: "from_email", label: "From", type: "email" }, { key: "to_email", label: "To", type: "email" }, { key: "status", label: "Status", type: "select", options: ["Draft", "Sent", "Scheduled"] }, { key: "sent_at", label: "Sent at", type: "datetime-local" }, { key: "body", label: "Message", type: "textarea", full: true }, { key: "related_type", label: "Related module", type: "select", options: ["leads", "contacts", "accounts", "deals"] }, { key: "related_id", label: "Related record", type: "number" }] };
  if (resource === "approval_processes") return { label: "Approval process", singular: "Approval rule", fields: [{ key: "name", label: "Rule name", required: true }, { key: "module", label: "Module", type: "select", options: ["Deals", "Leads", "Accounts"] }, { key: "trigger", label: "Trigger", required: true }, { key: "approver", label: "Approver", required: true }, { key: "status", label: "Status", type: "select", options: ["Active", "Inactive"] }, { key: "conditions", label: "Conditions (JSON)", type: "textarea", hint: "Example: [{\"field\":\"amount\",\"operator\":\">\",\"value\":\"100000\"}]", full: true }, { key: "steps", label: "Approval steps (JSON)", type: "textarea", hint: "Example: [{\"order\":1,\"approver\":\"Sales manager\"}]", full: true }] };

  return null;
}

function readForm(form) {
  const data = {};
  $$('[name]', form).forEach((input) => {
    if (input.type === "file" || input.readOnly && ["record_number","quote_number","order_number","po_number","invoice_number"].includes(input.name)) return;
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
  const { resource, id, context } = state.modal;
  const singular = MODULES[resource]?.singular || settingsResourceConfig(resource)?.singular || "record";
  const submit = $("#modal-submit");
  try {
    if (submit.disabled) return;
    const data = readForm(event.currentTarget);
    if (context?.kind === "account-deal") data.account_id = context.sourceId;
    submit.disabled = true;
    let created = null;
    if (resource === "attachments" && !id) {
      await createAttachmentFromFile(event.currentTarget, data, api);
    } else if (resource === "users" && !id) {
      await api("/api/admin/users/invite", { method: "POST", body: JSON.stringify(data) });
    } else {
      created = await api(`/api/${resource}${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", body: JSON.stringify(data) });
    }
    if (["accounts", "contacts", "deals"].includes(resource)) invalidateLookups();
    if (resource === "users") { await refreshMeta(); if (id && id === state.profile?.id) { state.profile = await api("/api/settings/profile"); applyProfile(); } }
    closeModal();
    if (context?.kind === "account-deal" && created?.id) {
      toast("Deal created", "The new Deal is linked to the selected Account.");
      await navigate(`/deals/${created.id}`);
      return;
    }
    toast(resource === "users" && !id ? "Invitation created" : `${id ? "Updated" : "Created"} ${singular}`, resource === "users" && !id ? "The teammate can join this organization using the invitation link." : "");
    await renderRoute();
  } catch (error) { toast("Could not save record", error.message, "error"); }
  finally { submit.disabled = false; }
}

async function submitPlatformRecord(form) {
  const { resource, id, context } = state.modal;
  const config = state.platformCatalog.resources[resource];
  const submit = $("#modal-submit");
  try {
    if (submit.disabled) return;
    const data = readForm(form);
    if (context?.kind === "deal-quote") data.deal_id = context.sourceId;
    submit.disabled = true;
    let created = null;
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
      created = await api(`/api/platform/${resource}${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", body: JSON.stringify(data) });
    }
    invalidateLookups();
    closeModal();
    if (context?.kind === "deal-quote" && created?.id) {
      toast("Quote created", `${created.quote_number || "Quote"} is linked to the Deal.`);
      await navigate("/quotes");
      return;
    }
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
  const permanent = false;
  const confirmed = resource === "users"
    ? await confirmAction("Deactivate this user?", "This user can be reactivated later.", "Deactivate")
    : await confirmAction("Delete this record?", "The record will remain in Settings > Recycle Bin for 30 days.", "Delete");
  if (!confirmed) return;
  try {
    await api(`/api/${resource}/${id}`, { method: "DELETE" });
    if (["accounts", "contacts"].includes(resource)) invalidateLookups();
    if (resource === "users") await refreshMeta();
    toast(resource === "users" ? "User deactivated" : "Record deleted", resource === "users" ? "User deactivated; access removed." : "Moved to Recycle Bin for 30 days.");
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (MODULES[resource] && parts[0] === resource && parts[1]) await navigate(`/${resource}`);
    else await renderRoute();
  } catch (error) { toast("Could not complete that action", error.message, "error"); }
}

async function deletePlatformRecord(resource, id) {
  const config = state.platformCatalog.resources[resource];
  const confirmed = await confirmAction(`Delete this ${config.singular.toLowerCase()}?`, "The record will remain in Recycle Bin for 30 days.", "Delete");
  if (!confirmed) return;
  try {
    await api(`/api/platform/${resource}/${id}`, { method: "DELETE" });
    toast("Record deleted", "It can be restored from Settings > Recycle Bin for 30 days.");
    if (window.location.pathname === `/${resource}/${id}`) await navigate(`/${resource}`);
    else await renderRoute();
  } catch (error) { toast("Could not archive record", error.message, "error"); }
}

function bindPlatform(resource) {
  if (["personal_settings", "users", "approval_processes", "blueprints", "search_setup", "customize_setup"].includes(resource)) bindSettings();
  $$('[data-platform-create]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
  $('[data-platform-open]').forEach(button => button.addEventListener("click", () => navigate(`/${button.dataset.platformOpen}/${Number(button.dataset.id)}`)));
  $('[data-platform-edit]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformEdit, Number(button.dataset.id))));
  $$('[data-platform-delete]').forEach((button) => button.addEventListener("click", () => deletePlatformRecord(button.dataset.platformDelete, Number(button.dataset.id))));
  const current = state.platformCatalog.resources[resource] ? platformState(resource) : null;
  $$('[data-platform-select-record]').forEach(input=>input.addEventListener("change",event=>{
    const id=Number(input.dataset.id);
    current.selectedIds=event.target.checked?[...new Set([...current.selectedIds,id])]:current.selectedIds.filter(value=>value!==id);
    renderRoute();
  }));
  $('[data-platform-select-all]')?.addEventListener("change",event=>{
    const ids=$$('[data-platform-select-record]').map(el=>Number(el.dataset.id));
    current.selectedIds=event.target.checked?[...new Set([...current.selectedIds,...ids])]:current.selectedIds.filter(id=>!ids.includes(id));
    renderRoute();
  });
  $('[data-platform-bulk-delete]')?.addEventListener("click",async()=>{
    if (!current.selectedIds.length || !confirm("Move selected records to the 30-day Recycle Bin?")) return;
    try {
      const result=await api("/api/administration/bulk-delete",{method:"POST",body:JSON.stringify({resource,ids:current.selectedIds})});
      current.selectedIds=[];
      toast("Records deleted",result.deleted+" records moved to Recycle Bin.");
      await renderRoute();
    } catch(error){toast("Bulk delete failed",error.message,"error");}
  });
  let timer;
  $('[data-platform-search]')?.addEventListener("input", (event) => { clearTimeout(timer); current.search = event.target.value; current.offset = 0; timer = setTimeout(renderRoute, 250); });
  $('[data-platform-status]')?.addEventListener("change", (event) => { current.status = event.target.value; current.offset = 0; renderRoute(); });
  $('[data-platform-owner]')?.addEventListener("change", (event) => { current.owner_id = event.target.value; current.offset = 0; renderRoute(); });
  $('[data-platform-sort]')?.addEventListener("change", (event) => { current.sort = event.target.value; current.offset = 0; renderRoute(); });
  $$('[data-page]').forEach((button) => button.addEventListener("click", () => { if (!current) return; current.offset += button.dataset.page === "next" ? 25 : -25; renderRoute(); }));
  const recycleSelection = () => $$('[data-recycle-select]:checked').map(el=>({resource:el.dataset.resource,id:Number(el.dataset.id)}));
  function syncRecycleButtons() {
    const checked=recycleSelection();
    const restore=$('[data-recycle-restore-selected]');
    const permanent=$('[data-recycle-permanent-selected]');
    if(restore) restore.disabled=!checked.length;
    if(permanent) permanent.disabled=!checked.length;
  }
  $$('[data-recycle-select]').forEach(el=>el.addEventListener('change',syncRecycleButtons));
  $('[data-recycle-select-all]')?.addEventListener('change',event=>{
    $$('[data-recycle-select]').forEach(el=>{el.checked=event.target.checked;});
    syncRecycleButtons();
  });
  async function recycleBatch(restore) {
    const entries=recycleSelection();
    if(!entries.length)return;
    if(!restore && !confirm("Permanently delete selected records? This cannot be undone."))return;
    const grouped={};
    for(const item of entries)(grouped[item.resource]??=[]).push(item.id);
    try{
      for(const [resource,ids] of Object.entries(grouped)){
        await api(restore?'/api/administration/recycle-bin/bulk-restore':'/api/administration/recycle-bin/permanent-delete',{
          method:'POST',body:JSON.stringify({resource,ids})
        });
      }
      toast(restore?'Records restored':'Records permanently deleted',entries.length+' records processed.');
      await renderRoute();
    }catch(error){toast('Recycle Bin operation failed',error.message,'error');}
  }
  $('[data-recycle-restore-selected]')?.addEventListener('click',()=>recycleBatch(true));
  $('[data-recycle-permanent-selected]')?.addEventListener('click',()=>recycleBatch(false));
  $$('[data-recycle-permanent]').forEach(button=>button.addEventListener('click',async()=>{
    if(!confirm('Permanently delete this record? This cannot be undone.'))return;
    try{
      await api('/api/administration/recycle-bin/permanent-delete',{method:'POST',body:JSON.stringify({resource:button.dataset.resource,ids:[Number(button.dataset.id)]})});
      toast('Record permanently deleted');await renderRoute();
    }catch(error){toast('Permanent delete failed',error.message,'error');}
  }));
  $('[data-recycle-purge-expired]')?.addEventListener('click',async()=>{
    try{
      const result=await api('/api/administration/recycle-bin/purge-expired',{method:'POST'});
      toast('Cleanup finished',result.purged+' expired records purged.');
      await renderRoute();
    }catch(error){toast('Cleanup failed',error.message,'error');}
  });
  $$('[data-restore-resource]').forEach((button) => button.addEventListener("click", async () => { try { await api("/api/administration/restore", { method: "POST", body: JSON.stringify({ resource: button.dataset.restoreResource, record_id: Number(button.dataset.id) }) }); toast("Record restored"); await renderRoute(); } catch (error) { toast("Could not restore record", error.message, "error"); } }));
  $('[data-import-form]')?.addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; const file = form.querySelector('[name="file"]').files[0]; if (!file) return; const body = new FormData(); body.append("file", file); try { const response = await fetch(`/api/import/${form.elements.resource.value}`, { method: "POST", body }); const result = await response.json(); if (!response.ok) throw new Error(result.detail || "Import failed"); toast("Import complete", `${result.imported} rows imported; ${result.errors.length} errors.`); form.reset(); } catch (error) { toast("Could not import CSV", error.message, "error"); } });
  $('[data-duplicate-form]')?.addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; const target = $('[data-duplicate-results]'); try { const result = await api(`/api/administration/duplicates?resource=${encodeURIComponent(form.elements.resource.value)}`); target.innerHTML = result.groups.length ? result.groups.map((group) => `<div class="rule-row"><div class="rule-info"><strong>${esc(group.value)}</strong><small>${group.count} records match on ${esc(group.match_on)}</small></div>${badge("Review")}</div>`).join("") : emptyState("✓", "No duplicates found", "No exact normalized matches were detected."); } catch (error) { toast("Duplicate scan failed", error.message, "error"); } });
}

function bindGlobal() {
  document.addEventListener("click", (event) => {
    const go = event.target.closest("[data-go]");
    if (go) {
      event.preventDefault();
      const target = go.dataset.go;
      if (target) navigate(target);
      return;
    }
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
  $("#logout-button")?.addEventListener("click", async () => {
    const button = $("#logout-button");
    button.disabled = true;
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" } });
    } finally {
      window.location.replace("/login");
    }
  });
  const notificationPopupRegion = $("#notification-popup-region");
  const shownNotificationIds = new Set();

  const dismissNotificationPopup = async (popup, notificationId) => {
    popup?.remove();
    if (!notificationId) return;
    try {
      await api(`/api/notifications/${notificationId}/read`, { method: "POST" });
    } catch {
      // Popup dismissal must never interrupt the CRM.
    }
  };

  const showNotificationPopup = (item) => {
    if (!notificationPopupRegion || !item?.id || shownNotificationIds.has(item.id)) return;
    shownNotificationIds.add(item.id);

    const popup = document.createElement("article");
    popup.className = `notification-popup ${item.kind === "error" ? "is-error" : ""}`;
    popup.dataset.notificationId = String(item.id);
    popup.innerHTML = `
      <div class="notification-popup-icon" aria-hidden="true">!</div>
      <div class="notification-popup-copy">
        <strong>${esc(item.title || "Notification")}</strong>
        ${item.body ? `<p>${esc(item.body)}</p>` : ""}
      </div>
      <button class="notification-popup-close" type="button" aria-label="Dismiss notification">×</button>
    `;

    notificationPopupRegion.appendChild(popup);

    const close = $(".notification-popup-close", popup);
    close?.addEventListener("click", () => dismissNotificationPopup(popup, item.id));

    window.setTimeout(() => {
      if (popup.isConnected) dismissNotificationPopup(popup, item.id);
    }, 9000);
  };

  const checkForNotifications = async () => {
    try {
      const data = await api("/api/notifications?unread_only=true&limit=4");
      const items = Array.isArray(data.items) ? data.items : [];
      items.slice().reverse().forEach(showNotificationPopup);
    } catch {
      // Notifications are optional UI; never show an error popup if the feed is unavailable.
    }
  };

  checkForNotifications();
  window.setInterval(checkForNotifications, 60000);

  const searchInput = $("#global-search"); let searchTimer;
  searchInput.addEventListener("input", () => { clearTimeout(searchTimer); if (!searchInput.value.trim()) { $("#search-results").classList.remove("open"); return; } searchTimer = setTimeout(async () => { try { const data = await api(`/api/search?q=${encodeURIComponent(searchInput.value)}`); const result = $("#search-results"); result.innerHTML = data.results.length ? data.results.map((item) => `<button class="search-result" data-search-route="/${item.resource}/${item.id}"><span class="result-icon">${MODULES[item.resource]?.icon || "◈"}</span><span><strong>${esc(item.label)}</strong><small>${esc(titleCase(item.resource))} · ${esc(item.meta || "")}</small></span></button>`).join("") : `<p style="padding:10px;color:var(--text-faint);font-size:11px">No matching records.</p>`; result.classList.add("open"); } catch (error) { /* search is best effort */ } }, 240); });
  document.addEventListener("click", (event) => { const result = event.target.closest("[data-search-route]"); if (result) { $("#search-results").classList.remove("open"); searchInput.value = ""; navigate(result.dataset.searchRoute); } else if (!event.target.closest("#global-search-wrap")) $("#search-results").classList.remove("open"); });
}

let aiFeature;
function aiDashboardView(...args) { return aiFeature.aiDashboardView(...args); }
function apexAssistantResultHtml(...args) { return aiFeature.apexAssistantResultHtml(...args); }
function bindApexAssistant(...args) { return aiFeature.bindApexAssistant(...args); }
function bindApexAssistantResult(...args) { return aiFeature.bindApexAssistantResult(...args); }
function aiView(...args) { return aiFeature.aiView(...args); }
function aiMessageHtml(...args) { return aiFeature.aiMessageHtml(...args); }
function renderAIConversation(...args) { return aiFeature.renderAIConversation(...args); }
function bindAIProposalActions(...args) { return aiFeature.bindAIProposalActions(...args); }
function bindAI(...args) { return aiFeature.bindAI(...args); }

async function settingsView(tab) {
  let content = '';
  if (tab === 'general') content = `<section class="card settings-section"><h2>Organization Management</h2><p>Manage your organization profile, members, invitations, and ownership.</p><a class="button button-primary" href="/settings/organization">Open Organization Management</a></section>${await generalSettingsView()}${await settingsPlatformSummary("company_details", "Company details")}${await settingsPlatformSummary("fiscal_years", "Fiscal years")}`;
  if (tab === 'profile-users') content = await profileUsersView();
  if (tab === 'organization') content = await organizationManagementView();
  if (tab === 'approval-process') content = await approvalSettingsView();
  if (tab === 'blueprint') content = await blueprintSettingsView();
  const labels = { general: 'General settings', 'profile-users': 'Profile & users', 'approval-process': 'Approval process', blueprint: 'Blueprint' };
  return `<section class="setup-page-shell"><div class="setup-toolbar setup-toolbar-search-only"><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input data-setup-search-input placeholder="Search Setup" /></label></div><div class="setup-workspace">${setupDirectory(tab === 'general' ? 'company_details' : tab === 'profile-users' ? 'users' : tab === 'approval-process' ? 'approval_processes' : 'blueprints')}<div class="settings-content">${content}</div></div></section>`;
}

async function organizationManagementView() {
  const org = await api("/api/organization");
  const members = await api("/api/organization/members");
  const canAdmin = ["owner", "admin", "administrator"].includes(String(org.membership_role || "").toLowerCase());
  const isOwner = String(org.membership_role || "").toLowerCase() === "owner";
  let invitations = {items: []};
  if (canAdmin) invitations = await api("/api/organization/invitations");
  const roleOptions = (value) => ["Member", "Admin"].map(role => `<option value="${role}" ${value === role ? "selected" : ""}>${role}</option>`).join("");
  const memberRows = (members.items || []).map(member => {
    const selfOwner = member.membership_role === "Owner";
    const actions = canAdmin && !selfOwner ? `<select class="field-select" aria-label="Role for ${esc(member.name)}" data-org-role="${member.user_id}">${roleOptions(member.membership_role)}</select><button class="button button-small" data-org-member-save="${member.user_id}">Save role</button><button class="button button-small" data-org-member-status="${member.user_id}" data-next-status="${member.status === "Active" ? "Inactive" : "Active"}">${member.status === "Active" ? "Deactivate" : "Activate"}</button>` : "";
    const transfer = isOwner && !selfOwner && member.status === "Active" ? `<button class="button button-small" data-org-transfer="${member.user_id}" data-org-target="${esc(member.name)}">Transfer ownership</button>` : "";
    return `<tr><td>${esc(member.name)}<br><small>${esc(member.email)}</small></td><td>${esc(member.membership_role)}</td><td>${esc(member.status)}</td><td>${actions} ${transfer}</td></tr>`;
  }).join("");
  const invitationRows = (invitations.items || []).map(invite => `<tr><td>${esc(invite.email)}</td><td>${esc(invite.membership_role)}</td><td>${esc(invite.status)}</td><td>${canAdmin && invite.status === "Pending" ? `<button class="button button-small" data-org-invite-revoke="${invite.id}">Revoke</button>` : ""}</td></tr>`).join("");
  return `<section class="card settings-section"><div class="settings-section-head"><h2>Organization Profile</h2><p>Workspace identity and organization membership.</p></div>
    <form data-org-profile><div class="form-grid"><div class="field"><label>Organization name</label><input name="name" class="field-input" required minlength="2" maxlength="160" value="${esc(org.name)}" ${canAdmin ? "" : "disabled"} /></div><div class="field"><label>Organization ID</label><input class="field-input" value="${org.id}" disabled /></div><div class="field"><label>Slug</label><input class="field-input" value="${esc(org.slug)}" disabled /></div></div>${canAdmin ? '<div class="form-actions"><button type="submit" class="button button-primary">Save organization</button></div>' : ""}</form></section>
    <section class="card settings-section"><div class="settings-section-head"><h2>Members</h2><p>Manage organization membership and roles.</p></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>${memberRows}</tbody></table></div></section>
    ${canAdmin ? `<section class="card settings-section"><div class="settings-section-head"><h2>Invite member</h2><p>Invitations expire after seven days. Delivery requires configured email settings.</p></div><form data-org-invite><div class="form-grid"><div class="field"><label>Email address</label><input name="email" type="email" class="field-input" required /></div><div class="field"><label>Member role</label><select name="membership_role" class="field-select"><option>Member</option><option>Admin</option></select></div></div><div class="form-actions"><button class="button button-primary" type="submit">Send invitation</button></div></form><div class="table-wrap"><table class="data-table"><thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>${invitationRows}</tbody></table></div></section>` : ""}`;
}

function bindOrganizationManagement() {
  const perform = async (request, success) => { try { await request(); toast("Organization updated", success); await renderRoute(); } catch (error) { toast("Organization update failed", error.message, "error"); } };
  $('[data-org-profile]')?.addEventListener('submit', event => {
    event.preventDefault();
    perform(() => api("/api/organization", {method:"PATCH", body:JSON.stringify({name: event.currentTarget.elements.name.value.trim()})}), "Organization profile saved.");
  });
  $('[data-org-invite]')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    perform(async () => {
      const result = await api("/api/organization/invitations", {method:"POST", body:JSON.stringify({email:form.elements.email.value.trim(),membership_role:form.elements.membership_role.value})});
      if (result.delivery === "not_configured") toast("Email delivery unavailable", "Configure SMTP to send invitations.", "error");
    }, "Invitation created.");
  });
  $$('[data-org-member-save]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.orgMemberSave;
    const role = $('[data-org-role="' + id + '"]')?.value;
    perform(() => api("/api/organization/members/" + id, {method:"PATCH", body:JSON.stringify({membership_role:role})}), "Member role updated.");
  }));
  $$('[data-org-member-status]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.orgMemberStatus;
    const status = button.dataset.nextStatus;
    if (!window.confirm(status + " this member?")) return;
    perform(() => api("/api/organization/members/" + id, {method:"PATCH", body:JSON.stringify({status})}), "Member status updated.");
  }));
  $$('[data-org-invite-revoke]').forEach(button => button.addEventListener('click', () => {
    if (!window.confirm("Revoke this invitation?")) return;
    perform(() => api("/api/organization/invitations/" + button.dataset.orgInviteRevoke, {method:"DELETE"}), "Invitation revoked.");
  }));
  $$('[data-org-transfer]').forEach(button => button.addEventListener('click', () => {
    const target = button.dataset.orgTarget;
    if (window.prompt("Transfer ownership permanently to " + target + "? Type TRANSFER to confirm.") !== "TRANSFER") return;
    perform(() => api("/api/organization/transfer-ownership", {method:"POST", body:JSON.stringify({user_id:Number(button.dataset.orgTransfer)})}), "Ownership transferred.");
  }));
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

async function blueprintSettingsView() { return blueprintFeature.view(); }

function bindSettings() {
  bindCustomModuleAdmin();
  blueprintFeature?.bind();
  const setupSearch = $('[data-setup-search-input]');
  setupSearch?.addEventListener('input', () => {
    const query = setupSearch.value.trim().toLowerCase();
    let visible = 0;
    $$('.setup-search-item').forEach((item) => { const match = !query || item.dataset.searchText.includes(query); item.hidden = !match; if (match) visible += 1; });
    $$('.setup-search-group').forEach((group) => { group.hidden = !$$('.setup-search-item', group).some((item) => !item.hidden); });
    const count = $('[data-setup-search-count]'); if (count) count.textContent = `${visible} setup option${visible === 1 ? '' : 's'} matched.`;
  });
  $('[data-setup-import-selector]')?.addEventListener("submit", (event) => {
    event.preventDefault();
    const selected = event.currentTarget.elements.resource.value;
    if (!["leads", "deals", "accounts", "contacts"].includes(selected)) {
      toast("Unsupported module", "Choose Leads, Deals, Accounts or Contacts.", "error");
      return;
    }
    navigate("/import/" + selected);
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
  await navigate(`/leads/${id}/convert`);
}

async function leadConvertPage(id) {
  const lead = await api(`/api/leads/${id}`);
  if (lead.status === "Converted") {
    return `<section class="card" style="padding:28px"><h2>Lead already converted</h2><p>This lead has already been converted. Additional records will not be created.</p><button class="button button-primary" data-conversion-go="/leads">Go to Leads</button></section>`;
  }
  const timeline = await api(`/api/leads/${id}/timeline`);
  if (timeline.blueprint_enabled) return `<section class="card" style="padding:28px"><h2>Use the Blueprint transition</h2><p>Advance this lead through the published Blueprint and click Convert at the final stage.</p><button class="button button-primary" data-conversion-go="/leads/${id}">Go to lead</button></section>`;
  const name = esc(lead.name || "Lead");
  const company = esc(lead.company || "");
  return `<section class="card" style="padding:0;overflow:visible;min-height:70vh">
    <header style="padding:22px 28px;border-bottom:1px solid var(--border,#dde3ed)"><h2 style="margin:0">Convert Lead <span style="font-size:14px;color:#66758c">(${name})</span></h2></header>
    <form id="lead-conversion-form" style="padding:26px 32px;max-width:920px">
      <p style="margin-bottom:24px"><strong>Create New Contact</strong> <span style="color:#66758c">${name}</span></p>
      <div class="field" style="max-width:560px;margin-bottom:22px"><label for="convert-account">Company / Account (match existing when available)</label><input class="field-input" id="convert-account" name="account_name" value="${company}" placeholder="Optional company name"></div>
      <label style="display:flex;align-items:center;gap:10px;margin-bottom:24px;cursor:pointer"><input type="checkbox" id="convert-deal" name="create_deal" value="true"> Create a new Deal for this Contact</label>
      <div id="convert-deal-fields" hidden style="max-width:650px;margin-bottom:26px">
        <div class="form-grid">
          <div class="field full"><label for="convert-name">Deal Name *</label><input class="field-input" name="deal_name" id="convert-name" value="${company || name}" placeholder="Deal name"></div>
          <div class="field"><label for="convert-date">Closing Date *</label><input class="field-input" type="date" name="expected_close_date" id="convert-date"></div>
          <div class="field"><label for="convert-stage">Stage *</label><select class="field-select" name="stage" id="convert-stage"><option>Qualification</option><option>Needs Analysis</option><option>Identify Decision Makers</option><option>Value Proposition</option><option>Proposal/Price Quote</option><option>Negotiation/Review</option><option>Closed Won</option><option>Closed Lost</option></select></div>
          <div class="field"><label for="convert-pipeline">Pipeline</label><select class="field-select" name="pipeline" id="convert-pipeline"><option value="Standard">Standard</option></select></div>
          <div class="field"><label for="convert-role">Contact Role</label><select class="field-select" name="contact_role" id="convert-role"><option>None</option><option>Developer/Evaluator</option><option>Decision Maker</option><option>Purchasing</option><option>Executive Sponsor</option><option>Engineering Lead</option><option>Economic Decision Maker</option><option>Product Management</option></select></div>
          <div class="field"><label for="convert-amount">Deal Amount</label><input class="field-input" name="deal_amount" id="convert-amount" type="number" min="0" step="any" value="0"></div>
        </div>
      </div>
      <p style="font-size:13px;color:#66758c;margin-bottom:20px">Existing notes, activities, attachments and related records remain linked to the converted contact or deal. Matching accounts and contacts are reused.</p>
      <div style="display:flex;gap:12px"><button class="button button-primary" type="submit" id="convert-submit">Convert</button><button class="button button-ghost" type="button" id="convert-cancel">Cancel</button></div>
    </form>
  </section>`;
}

function bindLeadConvertPage(id) {
  const form = $("#lead-conversion-form");
  if (!form) {
    $("[data-conversion-go]")?.addEventListener("click", (event) => navigate(event.currentTarget.dataset.conversionGo || "/leads"));
    return;
  }
  const checkbox = $("#convert-deal");
  const fields = $("#convert-deal-fields");
  checkbox.addEventListener("change", () => {
    fields.hidden = !checkbox.checked;
    $("#convert-name").required = checkbox.checked;
    $("#convert-date").required = checkbox.checked;
  });
  $("#convert-cancel").addEventListener("click", () => navigate(`/leads/${id}`));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const submit = $("#convert-submit");
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.create_deal = checkbox.checked;
    payload.deal_amount = checkbox.checked ? Number(payload.deal_amount || 0) : 0;
    submit.disabled = true;
    try {
      const converted = await api(`/api/leads/${id}/convert`, {method:"POST",body:JSON.stringify(payload)});
      invalidateLookups();
      state.conversionResult = converted;
      await navigate(`/leads/${id}/converted`);
    } catch (error) {
      toast("Lead conversion failed", error.message, "error");
    } finally { submit.disabled = false; }
  });
}

function leadConversionSuccess() {
  const result = state.conversionResult;
  if (!result) return `<section class="card" style="padding:28px"><h2>Conversion details unavailable</h2><button class="button button-primary" data-conversion-go="/leads">Go to Leads</button></section>`;
  const links = [
    ["Contact",result.contact,"contacts",result.contact?.full_name || [result.contact?.first_name,result.contact?.last_name].filter(Boolean).join(" ")],
    ["Deal",result.deal,"deals",result.deal?.name],
    ["Account",result.account,"accounts",result.account?.name]
  ].filter(item=>item[1]);
  return `<section class="card" style="padding:30px;min-height:55vh">
    <h2>Lead converted successfully</h2><p>Conversion Details</p>
    <div style="max-width:760px">${links.map(([label,item,resource,name])=>`<div style="display:grid;grid-template-columns:160px 1fr;padding:14px 0;border-bottom:1px solid #dde3ed"><span>${label}</span><a href="/${resource}/${item.id}" data-conversion-go="/${resource}/${item.id}">${esc(name||label)}</a></div>`).join("")}</div>
    <button class="button button-primary" style="margin-top:26px" data-conversion-go="/leads">Go to Leads</button>
  </section>`;
}

let blueprintFeature;
async function init() {
  blueprintFeature = createBlueprintFeature({api,esc,toast,renderRoute});
  aiFeature = createAiFeature({ state, MODULES, $, $$, esc, titleCase, initials, formatDate, formatDateTime, formatMoney, slug, pathFor, badge, lookupName, api, toast, pageHeader, loading, emptyState, navigate, openRecordModal, openPlatformModal, closeModal, confirmAction, fieldHtml, platformDisplay, platformTable, platformPanel, ensureLookups, ensurePlatformLookup, invalidateLookups, refreshMeta, performanceTable, renderRoute });
  setupFeature = createSetupFeature({ state, PLATFORM_MODULE_ROUTES, MODULES, $, $$, esc, titleCase, initials, formatDate, formatDateTime, formatMoney, slug, pathFor, badge, lookupName, api, toast, setBreadcrumb, activeNav, enhanceNavigation, pricingView, bindPricing, pageHeader, loading, emptyState, ensureLookups, ensurePlatformLookup, invalidateLookups, refreshMeta, ensurePlatformCatalog, ensureCustomModules, enhanceCustomModuleNavigation, greeting, applyProfile, refreshNavCount, navigate, renderRoute, teamspacesView, bindTeamspaces, dashboardView, reportResultHtml, reportEngineView, dashboardBuilderView, reportFormPayload, dashboardFormPayload, bindReportDashboard, performanceTable, attentionQueue, activityItem, bindDashboard, moduleView, activityTypeView, platformState, platformTable, platformDisplay, platformPanel, platformModuleView, tableView, kanbanView, gridView, splitView, chartView, timelineModuleView, pagination, dataIds, bulkArchiveLeads, bindModule, detailView, detailFields, relatedNavigation, relatedPlainRow, relatedPlainSection, relatedContent, dealProgress, bindDetail, fieldHtml, openRecordModal, openPlatformModal, settingsResourceConfig, readForm, submitRecord, submitPlatformRecord, submitConvert, closeModal, closeConfirm, confirmAction, deleteRecord, deletePlatformRecord, bindPlatform, bindGlobal, settingsView, profileUsersView, approvalSettingsView, blueprintSettingsView });
  bindGlobal();
  try { await ensurePlatformCatalog(); } catch (error) { toast("Module catalog unavailable", error.message, "error"); }
  await ensureCustomModules();
  enhanceNavigation();
  enhanceCustomModuleNavigation();
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

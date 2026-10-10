// Setup, customization, metadata-builder, security, CPQ and developer UI domain.
// Dependencies are injected to keep this feature independent from the SPA entrypoint.
export function createSetupFeature(ctx) {
  const { state, PLATFORM_MODULE_ROUTES, MODULES, $, $$, esc, titleCase, initials, formatDate, formatDateTime, formatMoney, slug, pathFor, badge, lookupName, api, toast, setBreadcrumb, activeNav, enhanceNavigation, pricingView, bindPricing, pageHeader, loading, emptyState, ensureLookups, ensurePlatformLookup, invalidateLookups, refreshMeta, ensurePlatformCatalog, ensureCustomModules, enhanceCustomModuleNavigation, greeting, applyProfile, refreshNavCount, navigate, renderRoute, teamspacesView, bindTeamspaces, dashboardView, reportResultHtml, reportEngineView, dashboardBuilderView, reportFormPayload, dashboardFormPayload, bindReportDashboard, performanceTable, attentionQueue, activityItem, bindDashboard, moduleView, activityTypeView, platformState, platformTable, platformDisplay, platformPanel, platformModuleView, tableView, kanbanView, gridView, splitView, chartView, timelineModuleView, pagination, dataIds, bulkArchiveLeads, bindModule, detailView, detailFields, relatedNavigation, relatedPlainRow, relatedPlainSection, relatedContent, dealProgress, bindDetail, fieldHtml, openRecordModal, openPlatformModal, settingsResourceConfig, readForm, submitRecord, submitPlatformRecord, submitConvert, closeModal, closeConfirm, confirmAction, deleteRecord, deletePlatformRecord, bindPlatform, bindGlobal, settingsView, profileUsersView, approvalSettingsView, blueprintSettingsView } = ctx;

  function setupDirectory(active) {
    let hiddenGroups = []; let hiddenItems = [];
    try { hiddenGroups = JSON.parse(localStorage.getItem('yash.setup.hidden_groups') || '[]'); hiddenItems = JSON.parse(localStorage.getItem('yash.setup.hidden_items') || '[]'); } catch (_) {}
    const groups = Object.entries(state.platformCatalog.setup_navigation || {}).filter(([group]) => !hiddenGroups.includes(group));
    return `<section class="card settings-nav"><div class="setup-quick-actions"><a href="/setup/search_setup" class="${active === "search_setup" ? "active" : ""}">Search Setup</a></div>${groups.map(([group, links]) => `<div data-setup-group="${esc(group)}"><span class="eyebrow setup-directory-group">${esc(group)}</span>${links.filter(([resource]) => !hiddenItems.includes(resource)).map(([resource, label]) => `<a href="/setup/${resource}" class="${active === resource ? "active" : ""}">${esc(label)}</a>`).join("")}</div>`).join("")}</section>`;
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
    return `<section class="card settings-section"><div class="settings-section-head"><h2>Recycle Bin</h2><p>Deleted records are retained for 30 days. Restore before expiry. Owner-only permanent deletion cannot be undone.</p></div>
    <div class="form-actions"><button class="button button-small" data-recycle-restore-selected disabled>Restore selected</button><button class="button button-small" data-recycle-permanent-selected disabled>Permanently delete selected</button><button class="button button-small" data-recycle-purge-expired>Clean up expired records</button></div>
    ${data.items.length ? `<label><input type="checkbox" data-recycle-select-all/> Select all displayed</label>` + data.items.map(item=>`<div class="rule-row"><label><input type="checkbox" data-recycle-select data-resource="${esc(item.resource)}" data-id="${Number(item.id)}" /> </label><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(titleCase(item.resource))} · #${item.id} · Deleted: ${esc(item.archived_at || "—")} · Expires after 30 days</small></div><button class="button button-small button-ghost" data-restore-resource="${esc(item.resource)}" data-id="${item.id}">Restore</button><button class="button button-small" data-recycle-permanent data-resource="${esc(item.resource)}" data-id="${item.id}">Delete permanently</button></div>`).join("") : emptyState("R", "Recycle bin is empty", "Deleted records will appear here.")}</section>`;
  }
  
  function importView() {
    const choices = ["leads", "deals", "accounts", "contacts"];
    return `<section class="card settings-section"><div class="settings-section-head"><h2>Import</h2><p>Choose a CRM module, then upload CSV, XLS, XLSX or VCF files and map the required Phone Number field.</p></div>
      <form data-setup-import-selector>
        <div class="form-grid"><div class="field"><label for="setup-import-module">Module</label>
          <select class="field-select" id="setup-import-module" name="resource" required>
            ${choices.map(resource=>`<option value="${resource}">${esc(MODULES[resource].label)}</option>`).join("")}
          </select>
        </div></div>
        <div class="form-actions"><button class="button button-primary" type="submit">Import records</button></div>
      </form>
      <div class="form-actions"><a class="button button-ghost" href="/setup/import_history">View Import History</a><a class="button button-ghost" href="/setup/export">Export Records</a><a class="button button-ghost" href="/setup/recycle_bin">Recycle Bin</a></div>
      </section>`;
  }

  async function importHistoryView() {
    const data = await api("/api/import-jobs");
    return `<section class="card settings-section"><div class="settings-section-head"><h2>Import History</h2><p>Review completed imports, skipped rows and row-level errors.</p></div>
    <div class="form-actions"><a class="button button-ghost" href="/setup/import">New Import</a></div>
    ${data.items?.length ? data.items.map(item=>`<div class="rule-row"><div class="rule-info"><strong>${esc(titleCase(item.resource))} Imported — ${esc(item.filename)}</strong>
    <small>${esc(item.created_at)} · ${esc(item.status)} · ${item.imported_rows}/${item.total_rows} created or updated · ${item.error_rows} errors</small>
    ${item.errors?.length ? `<details><summary>View errors</summary>${item.errors.map(error=>`<div>Row ${Number(error.row)}: ${esc(error.error)}</div>`).join("")}</details>` : ""}</div></div>`).join("") : emptyState("▤","No imports yet","Start an import from Leads, Deals, Accounts or Contacts.")}</section>`;
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
    const moduleRows = data.items.length ? data.items.map((module) => `
      <section class="card setup-module-card">
        <div class="setup-module-head">
          <div class="setup-module-title">
            <div class="setup-module-title-line"><h2>${esc(module.label)}</h2><span class="status-dot ${module.enabled ? "active" : "inactive"}">${module.enabled ? "Enabled" : "Disabled"}</span></div>
            <p><code>${esc(module.api_name)}</code><span>·</span><span>${esc(module.description || "No description")}</span></p>
          </div>
          <details class="action-menu">
            <summary class="action-menu-trigger" aria-label="Module actions" title="Module actions">⋯</summary>
            <div class="action-menu-popover">
              <button type="button" data-custom-module-builder="${module.id}">Edit fields</button>
              <button type="button" data-custom-module-toggle="${module.id}" data-enabled="${module.enabled}">${module.enabled ? "Disable module" : "Enable module"}</button>
              <button type="button" class="danger-action" data-custom-module-delete="${module.id}">Delete module</button>
            </div>
          </details>
        </div>
        <div class="metadata-field-table">
          <div class="metadata-field-head"><span>Field</span><span>Type</span><span>Rules</span><span>Visibility</span></div>
          ${module.fields.length ? module.fields.map((field) => `<div class="metadata-field-row"><strong>${esc(field.label)}<small>${esc(field.api_name)}</small></strong><span>${esc(field.field_type)}</span><span>${field.required ? "Required" : "Optional"}${field.read_only ? " · Read only" : ""}</span><span class="metadata-visibility">${metadataFieldEnabled(field) ? "Visible" : "Hidden"}</span></div>`).join("") : `<p class="related-empty metadata-empty">No custom fields yet.</p>`}
        </div>
        <div class="setup-module-actions">
          <button class="button button-ghost button-small" data-add-metadata-field="${module.id}">＋ Add field</button>
          <button class="button button-ghost button-small" data-add-metadata-layout="${module.id}">＋ Add layout</button>
          <button class="button button-ghost button-small" data-add-metadata-view="${module.id}">＋ Add view</button>
        </div>
      </section>`).join("") : emptyState("◇", "No custom modules", "Create your first metadata-driven module below.");
    return `${pageHeader("Administration", "Setup Console", "Customize modules and fields with API names, validation, permissions, layouts, and saved views.", `<button class="button button-primary" data-focus-module-form>＋ New module</button>`)}
      <div class="setup-console-grid">
        <div class="setup-console-modules">${moduleRows}</div>
        <section class="card settings-section setup-module-create-card" data-module-form-card>
          <div class="settings-section-head"><h2>New module</h2><p>Module definitions are stored in metadata tables and can be consumed by APIs, views, and AI agents.</p></div>
          <form class="settings-form" data-metadata-module-form>
            <div class="form-grid">
              <div class="field"><label>Label</label><input class="field-input" name="label" required placeholder="Service Requests" /></div>
              <div class="field"><label>API name</label><input class="field-input" name="api_name" required pattern="[a-z][a-z0-9_]*" placeholder="service_requests" /></div>
              <div class="field"><label>Plural label</label><input class="field-input" name="plural_label" placeholder="Service Requests" /></div>
              <div class="field field-full"><label>Description</label><textarea class="field-textarea" name="description" rows="3"></textarea></div>
            </div>
            <div class="form-actions"><button class="button button-primary" type="submit">Create module</button></div>
          </form>
        </section>
      </div>
      <section class="card settings-section setup-capabilities-card"><div class="settings-section-head"><h2>Field types and capabilities</h2><p>Supported metadata fields include text, rich text, numbers, currency, dates, picklists, lookups, formulas, files, images, and subforms.</p></div><div class="setup-capability-list"><span>Required / read-only</span><span>Unique values</span><span>Defaults</span><span>Validation rules</span><span>Field permissions</span><span>Layout visibility</span></div></section>`;
  }
  
  function bindDeveloperHub() {
    $$(`[data-platform-create]`).forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate)));
    const select = $(`[data-developer-sdk]`), output = $(`[data-developer-sdk-output]`);
    const loadSdk = async () => { if (!select || !output) return; try { const data = await api(`/api/developer/sdk/${select.value}`); output.innerHTML = `<pre>${esc(data.code)}</pre>`; } catch (error) { output.innerHTML = `<p class="apex-error">${esc(error.message)}</p>`; } };
    select?.addEventListener("change", loadSdk); loadSdk();
  }
  
  function bindMetadataModuleActions() {
    $$('[data-custom-module-builder]').forEach((button) => button.addEventListener("click", () => navigate(`/setup/custom_modules/builder/${button.dataset.customModuleBuilder}`)));
    $$('[data-custom-module-toggle]').forEach((button) => button.addEventListener("click", async () => {
      const id = Number(button.dataset.customModuleToggle);
      const enabled = button.dataset.enabled !== "true";
      try {
        await api(`/api/admin/metadata/modules/${id}`, {method:"PATCH", body:JSON.stringify({enabled})});
        await ensureCustomModules();
        enhanceCustomModuleNavigation();
        toast(enabled ? "Module enabled" : "Module disabled");
        await renderRoute();
      } catch (error) { toast("Could not update module", error.message, "error"); }
    }));
    $$('[data-custom-module-delete]').forEach((button) => button.addEventListener("click", async () => {
      const id = Number(button.dataset.customModuleDelete);
      if (!await confirmAction("Delete this custom module?","Its active custom records will be archived and the module definition, fields, layouts and views will be removed.","Delete module")) return;
      try {
        await api(`/api/admin/metadata/modules/${id}`, {method:"DELETE"});
        await ensureCustomModules();
        enhanceCustomModuleNavigation();
        toast("Custom module deleted");
        await renderRoute();
      } catch (error) { toast("Could not delete module", error.message, "error"); }
    }));
    $$('details.action-menu').forEach((menu) => menu.addEventListener("toggle", () => {
      if (!menu.open) return;
      $$('details.action-menu').forEach((other) => { if (other !== menu) other.open = false; });
    }));
  }
  
  function bindSetupConsole() {
    bindMetadataModuleActions();
    $(`[data-focus-module-form]`)?.addEventListener("click", () => $(`[data-module-form-card]`)?.scrollIntoView({behavior:"smooth"}));
    $(`[data-metadata-module-form]`)?.addEventListener("submit", async (event) => { event.preventDefault(); try { await api("/api/admin/metadata/modules", {method:"POST", body:JSON.stringify(Object.fromEntries(new FormData(event.currentTarget).entries()))}); toast("Module created", "The metadata module is ready for fields and layouts."); await navigate("/setup-console/modules", true); } catch (error) { toast("Could not create module", error.message, "error"); } });
    $$(`[data-add-metadata-field]`).forEach((button) => button.addEventListener("click", async () => { const label = window.prompt("Field label:"); if (!label) return; const apiName = window.prompt("Field API name:", label.toLowerCase().replace(/[^a-z0-9]+/g, "_")); if (!apiName) return; const type = window.prompt("Field type (text, number, currency, date, picklist, lookup):", "text"); try { await api(`/api/admin/metadata/modules/${button.dataset.addMetadataField}/fields`, {method:"POST", body:JSON.stringify({label, api_name:apiName, field_type:type || "text", position:0})}); toast("Field created", `${label} is available in the metadata model.`); await renderRoute(); } catch (error) { toast("Could not create field", error.message, "error"); } }));
    $$(`[data-add-metadata-layout]`).forEach((button) => button.addEventListener("click", async () => { const name = window.prompt("Layout name:", "Standard layout"); if (!name) return; try { await api(`/api/admin/metadata/modules/${button.dataset.addMetadataLayout}/layouts`, {method:"POST", body:JSON.stringify({name, sections:[]})}); toast("Layout created", "The layout is now stored in the metadata model."); await renderRoute(); } catch (error) { toast("Could not create layout", error.message, "error"); } }));
    $$(`[data-add-metadata-view]`).forEach((button) => button.addEventListener("click", async () => { const name = window.prompt("View name:", "My records"); if (!name) return; try { await api(`/api/admin/metadata/modules/${button.dataset.addMetadataView}/views`, {method:"POST", body:JSON.stringify({name, criteria:[], columns:[], sorting:[], visibility:{scope:"private"}})}); toast("View created", "The saved view is now available to the module engine."); await renderRoute(); } catch (error) { toast("Could not create view", error.message, "error"); } }));
  }
  
  
  const CUSTOM_FIELD_TYPES = [
    ["text","Single Line","↔"],["multiline","Multi-Line","☰"],["email","Email","✉"],["phone","Phone","⌕"],
    ["picklist","Pick List","▾"],["multi_select","Multi-Select","☷"],["date","Date","□"],["datetime","Date/Time","◫"],
    ["number","Number","123"],["auto_number","Auto-Number","№"],["currency","Currency","¤"],["decimal","Decimal",".00"],
    ["percentage","Percent","%"],["checkbox","Checkbox","☑"],["url","URL","↗"],["lookup","Lookup","⌕"],
    ["formula","Formula","ƒx"],["user_lookup","User","♙"],["file","File Upload","⇧"],["image","Image Upload","▧"],
    ["subform","Subform","▦"],["rich_text","Rich Text","¶"]
  ];
  
  function metadataFieldEnabled(field) {
    return field?.visibility?.enabled !== false;
  }
  
  async function customModulesAdminView() {
    const data = await api("/api/admin/metadata/modules");
    state.customModules = data.items || [];
    enhanceCustomModuleNavigation();
    const rows = state.customModules.length ? state.customModules.map((module) => `
      <article class="custom-module-row">
        <div class="custom-module-primary"><strong>${esc(module.label)}</strong><span>${esc(module.api_name)}</span></div>
        <div class="custom-module-cell"><span class="mobile-cell-label">Plural label</span><strong>${esc(module.plural_label || module.label)}</strong></div>
        <div class="custom-module-cell"><span class="mobile-cell-label">Fields</span><strong>${module.fields?.length || 0}</strong></div>
        <div class="custom-module-cell"><span class="mobile-cell-label">Status</span>${badge(module.enabled ? "Active" : "Inactive")}</div>
        <div class="custom-module-cell"><span class="mobile-cell-label">Updated</span><span>${formatDateTime(module.updated_at)}</span></div>
        <div class="custom-module-actions">
          <details class="action-menu">
            <summary class="action-menu-trigger" aria-label="Module actions" title="Module actions">⋯</summary>
            <div class="action-menu-popover">
              <button type="button" data-custom-module-builder="${module.id}">Edit fields</button>
              <button type="button" data-custom-module-toggle="${module.id}" data-enabled="${module.enabled}">${module.enabled ? "Disable" : "Enable"}</button>
              <button type="button" class="danger-action" data-custom-module-delete="${module.id}">Delete</button>
            </div>
          </details>
        </div>
      </article>`).join("") : `<div class="custom-module-empty">${emptyState("◇","No custom modules yet","Create your first custom module and design its fields visually.")}</div>`;
    return `${pageHeader("Customization", "Custom Modules & Fields", "Create unlimited metadata-driven modules, design fields visually, and control whether each module is available to users.", `<button class="button button-primary" data-custom-module-new>＋ Create Custom Module</button>`)}
      <section class="card custom-module-list">
        <div class="custom-module-list-head"><span>Module</span><span>Plural label</span><span>Fields</span><span>Status</span><span>Updated</span><span></span></div>
        ${rows}
      </section>`;
  }
  
  async function customModuleBuilderView(moduleId = null) {
    let module = null;
    if (moduleId) {
      const data = await api("/api/admin/metadata/modules");
      module = (data.items || []).find((item) => Number(item.id) === Number(moduleId));
      if (!module) return `<section class="card">${emptyState("!","Custom module not found","Return to Custom Modules & Fields and choose another module.")}</section>`;
    }
    state.customBuilder = {
      moduleId: module?.id || null,
      label: module?.label || "Untitled",
      api_name: module?.api_name || "",
      plural_label: module?.plural_label || "",
      description: module?.description || "",
      fields: module ? (module.fields || []).map((field) => ({...field, enabled: metadataFieldEnabled(field)})) : [{label:"Name", api_name:"name", field_type:"text", enabled:true, required:true}],
      newFields: [],
      activeTab: "create",
    };
    const palette = CUSTOM_FIELD_TYPES.map(([type,label,icon]) => `<button type="button" class="builder-palette-field" draggable="true" data-builder-field-type="${type}" data-builder-field-label="${esc(label)}"><span>${icon}</span><strong>${esc(label)}</strong></button>`).join("");
    return `<section class="module-builder-shell">
      <header class="module-builder-topbar">
        <div class="builder-module-title"><input class="builder-title-input" data-builder-module-label value="${esc(state.customBuilder.label)}" aria-label="Module name" /><span>Standard</span></div>
        <div class="builder-top-actions"><button class="button button-ghost" data-builder-cancel>Cancel</button><button class="button button-ghost" data-builder-save-close>Save and Close</button><button class="button button-primary" data-builder-save>Save</button></div>
      </header>
      <div class="module-builder-body">
        <aside class="builder-palette"><div class="builder-palette-head"><strong>New Fields</strong><small>Drag fields into the layout</small></div><div class="builder-palette-grid">${palette}</div><button type="button" class="builder-palette-field builder-section-button" draggable="true" data-builder-field-type="section" data-builder-field-label="New Section"><span>▤</span><strong>NEW SECTION</strong></button></aside>
        <main class="builder-canvas">
          <nav class="builder-tabs"><button class="active" data-builder-tab="create">Create</button><button data-builder-tab="quick">Quick Create</button><button data-builder-tab="detail">Detail View</button></nav>
          <section class="builder-module-meta">
            <div class="form-grid"><div class="field"><label>Module Name</label><input class="field-input" data-builder-label value="${esc(state.customBuilder.label)}" /></div><div class="field"><label>Plural Label</label><input class="field-input" data-builder-plural value="${esc(state.customBuilder.plural_label)}" placeholder="e.g. Service Requests" /></div><div class="field"><label>API Name</label><input class="field-input" data-builder-api value="${esc(state.customBuilder.api_name)}" placeholder="service_requests" ${module ? "readonly" : ""} /></div><div class="field"><label>Description</label><input class="field-input" data-builder-description value="${esc(state.customBuilder.description)}" /></div></div>
          </section>
          <section class="builder-layout-frame">
            <div class="builder-layout-head"><div><h2 data-builder-layout-heading>Create ${esc(state.customBuilder.label)}</h2><p>Drag fields from the left panel into this layout.</p></div></div>
            <div class="builder-drop-zone" data-builder-drop>
              ${builderFieldCards(state.customBuilder.fields)}
              <div class="builder-drop-hint" data-builder-empty ${state.customBuilder.fields.length ? "hidden" : ""}>Drag a field here to add it to this custom module.</div>
            </div>
          </section>
        </main>
      </div>
    </section>`;
  }
  
  function builderFieldCards(fields) {
    return (fields || []).map((field, index) => `<article class="builder-field-card ${field.enabled === false ? "disabled" : ""}" draggable="true" data-builder-field-id="${field.id || ""}" data-builder-local-index="${index}">
      <span class="builder-field-grip">⋮⋮</span>
      <div class="builder-field-copy"><strong>${esc(field.label)}</strong><small>${esc(field.field_type)} · ${esc(field.api_name || "new field")}</small></div>
      <span class="status-dot ${field.enabled === false ? "inactive" : "active"}">${field.enabled === false ? "Disabled" : "Enabled"}</span>
      <details class="action-menu builder-field-menu">
        <summary class="action-menu-trigger" aria-label="Field actions" title="Field actions">⋯</summary>
        <div class="action-menu-popover">
          <button type="button" data-builder-field-edit="${index}">Edit field</button>
          <button type="button" data-builder-field-toggle="${index}">${field.enabled === false ? "Enable field" : "Disable field"}</button>
          <button type="button" class="danger-action" data-builder-field-delete="${index}">Delete field</button>
        </div>
      </details>
    </article>`).join("");
  }
  
  function builderSlug(value) {
    return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"").slice(0,100);
  }
  
  function renderBuilderFields() {
    const zone = $('[data-builder-drop]');
    if (!zone || !state.customBuilder) return;
    const hint = `<div class="builder-drop-hint" data-builder-empty ${state.customBuilder.fields.length ? "hidden" : ""}>Drag a field here to add it to this custom module.</div>`;
    zone.innerHTML = builderFieldCards(state.customBuilder.fields) + hint;
    bindBuilderFieldActions();
  }
  
  function bindBuilderFieldActions() {
    $$('[data-builder-local-index]').forEach((card) => {
      card.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("application/x-yash-field-index", card.dataset.builderLocalIndex);
        event.dataTransfer.effectAllowed = "move";
      });
      card.addEventListener("dragover", (event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; });
      card.addEventListener("drop", (event) => {
        event.preventDefault();
        const from = Number(event.dataTransfer.getData("application/x-yash-field-index"));
        const to = Number(card.dataset.builderLocalIndex);
        if (!Number.isInteger(from) || !Number.isInteger(to) || from === to) return;
        const [moved] = state.customBuilder.fields.splice(from, 1);
        state.customBuilder.fields.splice(to, 0, moved);
        renderBuilderFields();
      });
    });
    $$('[data-builder-field-toggle]').forEach((button) => button.addEventListener("click", async () => {
      const index = Number(button.dataset.builderFieldToggle);
      const field = state.customBuilder.fields[index];
      field.enabled = field.enabled === false;
      if (field.id) await api(`/api/admin/metadata/fields/${field.id}`, {method:"PATCH", body:JSON.stringify({enabled:field.enabled})});
      renderBuilderFields();
    }));
    $$('[data-builder-field-edit]').forEach((button) => button.addEventListener("click", async () => {
      const index = Number(button.dataset.builderFieldEdit);
      const field = state.customBuilder.fields[index];
      const label = window.prompt("Field label:", field.label);
      if (!label) return;
      field.label = label.trim();
      if (!field.id) field.api_name = builderSlug(window.prompt("Field API name:", field.api_name || label) || field.api_name || label);
      if (field.id) await api(`/api/admin/metadata/fields/${field.id}`, {method:"PATCH", body:JSON.stringify({label:field.label})});
      renderBuilderFields();
    }));
    $$('[data-builder-field-delete]').forEach((button) => button.addEventListener("click", async () => {
      const index = Number(button.dataset.builderFieldDelete);
      const field = state.customBuilder.fields[index];
      if (!await confirmAction("Delete this custom field?", `The field "${field.label}" will be removed from this module. Existing stored values are not displayed after removal.`, "Delete field")) return;
      if (field.id) await api(`/api/admin/metadata/fields/${field.id}`, {method:"DELETE"});
      state.customBuilder.fields.splice(index,1);
      renderBuilderFields();
    }));
  }
  
  async function saveCustomBuilder(closeAfter = false) {
    const b = state.customBuilder;
    if (!b) return;
    b.label = $('[data-builder-label]')?.value.trim() || $('[data-builder-module-label]')?.value.trim() || b.label;
    b.plural_label = $('[data-builder-plural]')?.value.trim() || b.plural_label || b.label;
    b.api_name = builderSlug($('[data-builder-api]')?.value || b.api_name || b.plural_label || b.label);
    b.description = $('[data-builder-description]')?.value.trim() || "";
    if (!b.label || !b.api_name) return toast("Module details required","Enter a module name and API name.","error");
    try {
      let moduleId = b.moduleId;
      if (!moduleId) {
        const created = await api("/api/admin/metadata/modules", {method:"POST", body:JSON.stringify({label:b.label, plural_label:b.plural_label, api_name:b.api_name, description:b.description, enabled:true, config:{record_name_field:"name"}})});
        moduleId = created.id; b.moduleId = moduleId;
      } else {
        await api(`/api/admin/metadata/modules/${moduleId}`, {method:"PATCH", body:JSON.stringify({label:b.label, plural_label:b.plural_label, description:b.description})});
      }
      for (let i=0;i<b.fields.length;i++) {
        const field = b.fields[i];
        if (field.id) {
          await api(`/api/admin/metadata/fields/${field.id}`, {method:"PATCH", body:JSON.stringify({position:i, label:field.label, required:!!field.required, enabled:field.enabled !== false})});
        } else {
          const created = await api(`/api/admin/metadata/modules/${moduleId}/fields`, {method:"POST", body:JSON.stringify({label:field.label, api_name:field.api_name, field_type:field.field_type, position:i, required:!!field.required, enabled:field.enabled !== false})});
          field.id = created.id;
        }
      }
      const modules = await ensureCustomModules();
      enhanceCustomModuleNavigation();
      toast("Custom module saved", `${b.label} is now available in the CRM navigation.`);
      if (closeAfter) return navigate("/setup/custom_modules", true);
      return navigate(`/setup/custom_modules/builder/${moduleId}`, true);
    } catch (error) { toast("Could not save custom module", error.message, "error"); }
  }
  
  function bindCustomModuleAdmin() {
    $('[data-custom-module-new]')?.addEventListener("click", () => navigate("/setup/custom_modules/new"));
    bindMetadataModuleActions();
  
    const drop = $('[data-builder-drop]');
    $$('[data-builder-field-type]').forEach((item) => {
      item.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("application/x-yash-field", JSON.stringify({type:item.dataset.builderFieldType,label:item.dataset.builderFieldLabel}));
        event.dataTransfer.effectAllowed = "copy";
      });
      item.addEventListener("dblclick", () => {
        if (item.dataset.builderFieldType === "section") return;
        const label = item.dataset.builderFieldLabel;
        state.customBuilder.fields.push({label, api_name:builderSlug(label), field_type:item.dataset.builderFieldType, enabled:true, required:false});
        renderBuilderFields();
      });
    });
    drop?.addEventListener("dragover", (event) => { event.preventDefault(); drop.classList.add("drag-over"); event.dataTransfer.dropEffect = "copy"; });
    drop?.addEventListener("dragleave", () => drop.classList.remove("drag-over"));
    drop?.addEventListener("drop", (event) => {
      event.preventDefault(); drop.classList.remove("drag-over");
      try {
        const data = JSON.parse(event.dataTransfer.getData("application/x-yash-field"));
        if (!data.type) return;
        if (data.type === "section") {
          toast("Section added","Sections are represented through saved layouts; field ordering remains editable here.");
          return;
        }
        const label = data.label;
        let apiName = builderSlug(label);
        let suffix = 2;
        while (state.customBuilder.fields.some((field) => field.api_name === apiName)) apiName = `${builderSlug(label)}_${suffix++}`;
        state.customBuilder.fields.push({label, api_name:apiName, field_type:data.type, enabled:true, required:false});
        renderBuilderFields();
      } catch {}
    });
    bindBuilderFieldActions();
    $('[data-builder-cancel]')?.addEventListener("click", () => navigate("/setup/custom_modules"));
    $('[data-builder-save]')?.addEventListener("click", () => saveCustomBuilder(false));
    $('[data-builder-save-close]')?.addEventListener("click", () => saveCustomBuilder(true));
    $$('[data-builder-tab]').forEach((button) => button.addEventListener("click", () => {
      $$('[data-builder-tab]').forEach((node)=>node.classList.toggle("active",node===button));
      state.customBuilder.activeTab = button.dataset.builderTab;
      $('[data-builder-layout-heading]').textContent = `${titleCase(button.dataset.builderTab)} ${state.customBuilder.label}`;
    }));
  }
  
  function customRuntimeFieldControl(field) {
    const required = field.required ? "required" : "";
    const marker = field.required ? ' <span class="required">*</span>' : "";
    const name = esc(field.api_name);
    const label = esc(field.label);
    const type = String(field.field_type || "text");
    const validation = field.validation || {};
    const min = validation.min != null ? `min="${esc(validation.min)}"` : "";
    const max = validation.max != null ? `max="${esc(validation.max)}"` : "";
    const minLength = validation.min_length != null ? `minlength="${esc(validation.min_length)}"` : "";
    const maxLength = validation.max_length != null ? `maxlength="${esc(validation.max_length)}"` : "";
    const pattern = validation.regex ? `pattern="${esc(validation.regex)}"` : "";
    if (field.read_only) return "";
    if (type === "multiline" || type === "rich_text") {
      return `<div class="field field-full"><label>${label}${marker}</label><textarea class="field-textarea" name="${name}" rows="4" ${required} ${minLength} ${maxLength}></textarea></div>`;
    }
    if (type === "checkbox") {
      return `<label class="custom-runtime-check"><input type="checkbox" name="${name}" value="true" /><span>${label}${marker}</span></label>`;
    }
    if (type === "picklist") {
      const options = validation.options || validation.allowed_values || [];
      return `<div class="field"><label>${label}${marker}</label><select class="field-select" name="${name}" ${required}><option value="">Select</option>${options.map((item)=>`<option value="${esc(item)}">${esc(item)}</option>`).join("")}</select></div>`;
    }
    const inputType = ({email:"email",phone:"tel",url:"url",date:"date",datetime:"datetime-local",number:"number",decimal:"number",currency:"number",percentage:"number"})[type] || "text";
    const step = ["decimal","currency","percentage"].includes(type) ? 'step="any"' : "";
    return `<div class="field"><label>${label}${marker}</label><input class="field-input" type="${inputType}" name="${name}" ${required} ${step} ${min} ${max} ${minLength} ${maxLength} ${pattern} /></div>`;
  }
  
  async function customRuntimeView(module) {
    const schema = await api(`/api/custom/${module.api_name}/schema`);
    const data = await api(`/api/custom/${module.api_name}?limit=100`);
    const fields = (schema.fields || []).filter((field)=>field.visibility?.enabled !== false);
    const tableFields = fields.slice(0,5);
    const rows = data.items?.length ? data.items.map((row)=>`<tr><td><strong>${esc(row.name || row.title || `${module.label} #${row.id}`)}</strong></td>${tableFields.map((field)=>`<td>${esc(Array.isArray(row[field.api_name]) ? row[field.api_name].join(", ") : (row[field.api_name] ?? "—"))}</td>`).join("")}<td>${badge(row.status || "Active")}</td></tr>`).join("") : "";
    const formFields = fields.map(customRuntimeFieldControl).join("");
    const addButton = fields.length ? `<button class="button button-primary" data-custom-runtime-new>＋ Add Report</button>` : "";
    return `${pageHeader("Custom Modules", module.plural_label || module.label, module.description || "Custom CRM module.", `${addButton}<button class="button button-ghost" data-go="/setup/custom_modules/builder/${module.id}">Customize fields</button>`)}
      ${fields.length ? `<section class="card custom-runtime-form-card" data-custom-runtime-form-card hidden>
        <div class="settings-section-head"><h2>Add report</h2><p>Complete the fields configured for ${esc(module.label)}. Required fields are marked with *.</p></div>
        <form class="settings-form" data-custom-runtime-form>
          <div class="form-grid">${formFields}</div>
          <div class="form-actions"><button type="button" class="button button-ghost" data-custom-runtime-cancel>Cancel</button><button type="submit" class="button button-primary">Save Report</button></div>
        </form>
      </section>` : `<section class="card settings-section"><div class="settings-section-head"><h2>Configure fields first</h2><p>This module has no active fields. Add fields in the visual builder before adding reports.</p></div><button class="button button-primary" data-go="/setup/custom_modules/builder/${module.id}">Customize fields</button></section>`}
      <section class="card table-card custom-runtime-table">${rows ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>${esc(module.label)}</th>${tableFields.map((field)=>`<th>${esc(field.label)}</th>`).join("")}<th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyState("◇","No reports yet","Use Add Report to create the first record for this module.")}</section>`;
  }
  
  function bindCustomRuntime(module) {
    $$('[data-go]').forEach((button)=>button.addEventListener("click",()=>navigate(button.dataset.go)));
    const card = $('[data-custom-runtime-form-card]');
    const form = $('[data-custom-runtime-form]');
    $('[data-custom-runtime-new]')?.addEventListener("click", () => {
      if (!card) return;
      card.hidden = false;
      card.scrollIntoView({behavior:"smooth",block:"start"});
      card.querySelector("input,select,textarea")?.focus();
    });
    $('[data-custom-runtime-cancel]')?.addEventListener("click", () => {
      if (card) card.hidden = true;
      form?.reset();
    });
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const payload = {};
      const data = new FormData(form);
      for (const [key,value] of data.entries()) {
        if (value === "") continue;
        payload[key] = value;
      }
      form.querySelectorAll('input[type="checkbox"]').forEach((input)=>{ payload[input.name] = input.checked; });
      try {
        await api(`/api/custom/${module.api_name}`, {method:"POST", body:JSON.stringify(payload)});
        toast("Report saved", `The report was saved in ${module.plural_label || module.label}.`);
        form.reset();
        if (card) card.hidden = true;
        await renderRoute();
      } catch(error) {
        toast("Could not save report", error.message, "error");
      }
    });
  }
  
  function setupLandingView() {
    let hiddenGroups = []; let hiddenItems = [];
    try { hiddenGroups = JSON.parse(localStorage.getItem('yash.setup.hidden_groups') || '[]'); hiddenItems = JSON.parse(localStorage.getItem('yash.setup.hidden_items') || '[]'); } catch (_) {}
    const groups = Object.entries(state.platformCatalog.setup_navigation || {}).filter(([group]) => !hiddenGroups.includes(group));
    const icons = {
      "General":"♙","Security Control":"◇","Channels":"◔","Customization":"⚙","Automation":"⚙",
      "Process Management":"⌘","Experience Center":"⌘","Data Administration":"▤","Marketplace":"▣",
      "Developer Hub":"◈","Apex":"✦","CPQ":"▦"
    };
    const sparkle = new Set(["Canvas","Teamspace","Agents","MCP for AI Agents","StyleUI","Voice of the Customer"]);
    const cards = groups.map(([group, links]) => `<section class="card setup-hub-card setup-search-group" data-search-group="${esc(group.toLowerCase())}"><div class="setup-hub-head"><span class="setup-hub-icon">${icons[group] || "◈"}</span><h2>${esc(group)}</h2></div><div class="setup-hub-links">${links.filter(([resource]) => !hiddenItems.includes(resource)).map(([resource, label]) => `<a href="/setup/${resource}" class="setup-hub-link setup-search-item" data-search-text="${esc(`${group} ${label} ${resource}`.toLowerCase())}"><span>${esc(label)}</span>${sparkle.has(label) ? '<b class="setup-sparkle">✦</b>' : ""}</a>`).join("")}</div></section>`).join("");
    return `<section class="setup-page-shell setup-home"><div class="setup-home-toolbar"><h1>Setup</h1><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input data-setup-search-input placeholder="Search Setup" autofocus /></label></div><p class="related-empty setup-toolbar-note" data-setup-search-count>Browse ${Object.values(state.platformCatalog.setup_navigation || {}).flat().length} setup options.</p><div class="setup-hub-grid" data-setup-search-results>${cards}</div></section>`;
  }
  
  async function setupView(resource, subparts = []) {
    if (resource === 'index') return setupLandingView();
    if (resource === "custom_modules" && subparts[0] === "new") return customModuleBuilderView(null);
    if (resource === "custom_modules" && subparts[0] === "builder") return customModuleBuilderView(Number(subparts[1]));
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
    else if (resource === "import_history") content = await importHistoryView();
    else if (resource === "export") content = exportView();
    else if (resource === "duplicates") content = duplicateView();
    else if (resource === "custom_modules") content = await customModulesAdminView();
    else if (state.platformCatalog.resources[resource]) content = `<section class="foundation-note">This is a working foundation: records persist, validate, filter, sort, export, audit and recycle. External delivery, identity-provider enforcement and background scheduling require deployment-specific workers or integrations.</section>${await platformPanel(resource, true)}`;
    else content = `<section class="card">${emptyState("!", "Unknown setup page", "Choose a setup item from the directory.")}</section>`;
    return `<section class="setup-page-shell"><div class="setup-toolbar setup-toolbar-search-only"><label class="toolbar-search setup-toolbar-search"><span>⌕</span><input data-setup-search-input placeholder="Search Setup" /></label></div><div class="setup-workspace">${setupDirectory(resource)}<div class="settings-content">${content}</div></div></section>`;
  }

  return { setupDirectory, setupSearchView, customizeSetupView, auditView, recycleBinView, importView, exportView, duplicateView, workflowRulesView, securityAdminView, cpqView, bindSecurityAdmin, bindCPQ, developerHubView, setupConsoleView, bindDeveloperHub, bindMetadataModuleActions, bindSetupConsole, metadataFieldEnabled, customModulesAdminView, customModuleBuilderView, builderFieldCards, builderSlug, renderBuilderFields, bindBuilderFieldActions, saveCustomBuilder, bindCustomModuleAdmin, customRuntimeFieldControl, customRuntimeView, bindCustomRuntime, setupLandingView, setupView };
}

/*
 * Yash CRM related-list UI script
 *
 * This is extracted from static/js/app.js. It expects the existing app
 * helpers and state to already be available: $, $$, api, esc, titleCase,
 * formatDate, formatDateTime, formatMoney, detailFields, dealProgress,
 * activityItem, openRecordModal, openPlatformModal, openConvertModal,
 * deleteRecord, navigate, renderRoute, MODULES, and state.
 */

async function detailView(resource, id) {
  const [record, related] = await Promise.all([api(`/api/${resource}/${id}`), api(`/api/${resource}/${id}/related`)]);
  if (resource === "leads") related.journey = await api(`/api/journey/leads/${id}`);
  const config = MODULES[resource];
  const title = resource === "contacts" ? record.full_name : record.name || record.subject;
  const secondary = resource === "leads" ? record.company || record.email : resource === "contacts" ? record.email || record.job_title : resource === "accounts" ? record.website || record.industry : resource === "deals" ? `${record.stage} · ${formatMoney(record.amount)}` : resource === "products" ? `${record.category || "Product"} · ${formatMoney(record.unit_price)}` : `${titleCase(record.activity_type)} · ${formatDateTime(record.due_at)}`;
  const details = detailFields(resource, record);
  const summary = `<section class="card detail-summary"><div class="detail-title-row"><span class="detail-avatar">${initials(title)}</span><div class="detail-title-copy"><span class="eyebrow">${esc(config.singular)}</span><h2>${esc(title)}</h2><p>${esc(secondary || "No summary available")}</p></div><div class="detail-actions">${resource === "leads" && record.status !== "Converted" && !record.converted_contact_id ? `<button class="button button-small button-ghost" data-convert-lead="${id}">Convert</button>` : ""}<button class="button button-small button-ghost" data-delete-record="${resource}" data-id="${id}">Archive</button></div></div><div class="detail-meta-grid">${details.map((item) => `<div><span class="meta-label">${esc(item.label)}</span><span class="meta-value">${item.html || esc(item.value || "—")}</span></div>`).join("")}</div>${record.notes ? `<div class="notes-box"><h3>Notes</h3><p>${esc(record.notes)}</p></div>` : ""}</section>`;
  const stage = resource === "deals" ? `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>Stage progress</h2><small>Move the deal forward as the conversation evolves.</small></div></div><div class="card-body">${dealProgress(record)}</div></section>` : "";
  const timeline = `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>Timeline</h2><small>Latest activity updates</small></div></div><div class="card-body"><div class="activity-list">${related.activities?.length ? related.activities.map(activityItem).join("") : `<p style="color:var(--text-faint);font-size:11px">No linked activity yet.</p>`}</div></div></section>`;
  return `${pageHeader(config.label, title, secondary || "Record detail", `${resource === "leads" ? `<button class="button button-ghost" data-go="/ai?lead=${id}">✦ Analyze with AI</button>` : ""}<button class="button button-ghost" data-go="/${resource}">← Back to ${config.label.toLowerCase()}</button><button class="button button-primary" data-edit-record="${resource}" data-id="${id}">Edit ${config.singular.toLowerCase()}</button>`)}
    <div class="detail-layout"><aside class="related-panel" aria-label="Related records"><div class="related-panel-head"><div><span class="eyebrow">Context</span><h2>Related records</h2><p>Choose an option to view it here.</p></div><button class="button button-small button-ghost" data-create="activities">＋ Activity</button></div><div class="related-panel-body">${relatedContent(resource, related)}</div></aside><div class="detail-main"><div id="inline-related-view" class="inline-related-view" hidden></div>${summary}${stage}${timeline}</div></div>`;
}

function relatedContent(resource, related) {
  const sections = [];
  const addSection = (key, label, icon, rows, createResource) => {
    sections.push(`<section class="related-group" data-related-group="${key}"><div class="related-group-head"><strong>${icon} ${label}</strong><button class="card-head-link" data-create="${createResource}">＋ Add</button></div>${rows.length ? rows.join("") : `<p class="related-empty">No ${label.toLowerCase()} yet.</p>`}</section>`);
  };
  if (related.journey) {
    const stages = related.journey.stages || [];
    sections.push(`<section class="related-group journey-group"><div class="related-group-head"><strong>Customer journey</strong><span class="eyebrow">Lead to cash</span></div><div class="journey-track">${stages.map((stage) => `<span class="journey-stage ${stage.complete ? "complete" : ""}"><i>${stage.complete ? "✓" : stage.count}</i><b>${esc(stage.label)}</b></span>`).join("")}</div><div class="journey-actions"><button class="button button-small button-ghost" data-platform-create="site_visits" data-lead-id="${related.journey.lead.id}">+ Site visit</button>${related.journey.lead.converted_deal_id ? `<button class="button button-small button-ghost" data-platform-create="quotes" data-deal-id="${related.journey.lead.converted_deal_id}">+ Quotation</button>` : ""}</div></section>`);
  }
  addSection("activities", "Activities", "✓", (related.activities || []).map((item) => relatedRow("✓", item.subject, `${titleCase(item.activity_type)} · ${formatDateTime(item.due_at)}`, "activities", item.id)), "activities");
  addSection("notes", "Notes", "▤", (related.notes || []).map((item) => relatedRow("▤", item.title, item.content || "Open note", "notes", item.id)), "notes");
  addSection("products", "Products", "□", (related.products || []).map((item) => relatedRow("□", item.name, `${formatMoney(item.unit_price)} · ${item.sku || "No SKU"}`, "products", item.id)), "products");
  addSection("attachments", "Attachments", "↗", (related.attachments || []).map((item) => relatedRow("↗", item.name, `${item.file_type || "File"} · ${item.file_size || "Size not set"}`, "attachments", item.id)), "attachments");
  addSection("emails", "Emails", "@", (related.emails || []).map((item) => relatedRow("@", item.subject, `${item.status} · ${item.to_email || "No recipient"}`, "emails", item.id)), "emails");
  addSection("leads", "Leads", "✦", (related.leads || []).map((item) => relatedRow("✦", item.name, item.company || item.email, "leads", item.id)), "leads");
  addSection("accounts", "Accounts", "▣", (related.accounts || []).map((item) => relatedRow("▣", item.name, item.industry || item.type, "accounts", item.id)), "accounts");
  addSection("contacts", "Contacts", "◎", (related.contacts || []).map((item) => relatedRow("◎", item.full_name || `${item.first_name} ${item.last_name}`, item.job_title || item.email, "contacts", item.id)), "contacts");
  addSection("deals", "Deals", "◇", (related.deals || []).map((item) => relatedRow("◇", item.name, `${formatMoney(item.amount)} · ${item.stage}`, "deals", item.id)), "deals");
  if (related.platform_records?.length) {
    const grouped = related.platform_records.reduce((groups, item) => { (groups[item.resource] ||= []).push(item); return groups; }, {});
    Object.entries(grouped).forEach(([key, rows]) => {
      const config = state.platformCatalog.resources[key] || {};
      addSection(key, config.label || titleCase(key), config.icon || "◈", rows.map((item) => relatedRow(config.icon || "◈", item.name || item.title, `${item.status || "Active"} · #${item.id}`, key, item.id, true)), key);
    });
  }
  return sections.join("");
}

function relatedRow(icon, title, meta, resource, id, platform = false) {
  return `<button class="related-item" data-inline-related="${esc(resource)}" data-inline-platform="${platform}" data-id="${id}"><span class="related-dot">${icon}</span><span class="related-main"><strong>${esc(title)}</strong><small>${esc(meta || "")}</small></span><span class="related-arrow" aria-hidden="true">›</span></button>`;
}

async function showInlineRelated(resource, id, platform = false) {
  const target = $("#inline-related-view");
  if (!target) return;
  target.hidden = false;
  target.innerHTML = `<div class="inline-related-loading">Loading ${esc(titleCase(resource))}…</div>`;
  try {
    const record = await api(`${platform ? "/api/platform" : "/api"}/${resource}/${id}`);
    const config = platform ? (state.platformCatalog.resources[resource] || {}) : MODULES[resource];
    const title = platform ? record.name || record.title : resource === "contacts" ? record.full_name : record.name || record.subject || record.title;
    const fields = platform ? Object.entries(record.data || record).filter(([key, value]) => !["id", "resource", "data", "archived", "created_at", "updated_at"].includes(key) && value !== null && value !== "").slice(0, 12) : detailFields(resource, record).map((item) => [item.label, item.html || item.value || "—"]);
    target.innerHTML = `<div class="inline-related-head"><div><span class="eyebrow">${esc(config.singular || titleCase(resource))}</span><h2>${esc(title || `${titleCase(resource)} #${id}`)}</h2></div><button class="button button-small button-ghost" data-close-inline-related>Close</button></div><div class="inline-related-fields">${fields.map(([label, value]) => `<div><span class="meta-label">${esc(label)}</span><span class="meta-value">${typeof value === "string" && value.includes("<") ? value : esc(value)}</span></div>`).join("")}</div><div class="inline-related-actions"><button class="button button-small button-primary" data-inline-edit="${esc(resource)}" data-inline-platform="${platform}" data-id="${id}">Edit ${esc(config.singular || titleCase(resource))}</button></div>`;
    target.querySelector("[data-close-inline-related]")?.addEventListener("click", () => { target.hidden = true; target.innerHTML = ""; });
    target.querySelector("[data-inline-edit]")?.addEventListener("click", () => platform ? openPlatformModal(resource, id) : openRecordModal(resource, id));
  } catch (error) {
    target.innerHTML = `<div class="inline-related-error">Could not load this related record. ${esc(error.message)}</div>`;
  }
}

function bindDetail(resource, id) {
  $$('[data-go]').forEach((button) => button.addEventListener("click", () => navigate(button.dataset.go)));
  $$('[data-edit-record]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.editRecord, Number(button.dataset.id))));
  $$('[data-delete-record]').forEach((button) => button.addEventListener("click", () => deleteRecord(button.dataset.deleteRecord, Number(button.dataset.id))));
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create, null, { related_type: resource, related_id: id })));
  $$('[data-platform-create]').forEach((button) => button.addEventListener("click", () => openPlatformModal(button.dataset.platformCreate, null, { lead_id: button.dataset.leadId ? Number(button.dataset.leadId) : null, deal_id: button.dataset.dealId ? Number(button.dataset.dealId) : null })));
  $$('[data-inline-related]').forEach((button) => button.addEventListener("click", () => showInlineRelated(button.dataset.inlineRelated, Number(button.dataset.id), button.dataset.inlinePlatform === "true")));
  $('[data-convert-lead]')?.addEventListener("click", () => openConvertModal(Number(id)));
  $$('[data-stage-update]').forEach((button) => button.addEventListener("click", async () => { try { await api(`/api/deals/${button.dataset.stageUpdate}`, { method: "PATCH", body: JSON.stringify({ stage: button.dataset.stage }) }); toast("Deal updated", `Moved to ${button.dataset.stage}`); await renderRoute(); } catch (error) { toast("Could not update deal", error.message, "error"); } }));
}

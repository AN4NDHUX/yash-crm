// Shared accessible record-detail page for all platform modules.
export function createPlatformDetailFeature({ api, state, esc, formatDateTime, formatMoney, navigate, openPlatformModal, deletePlatformRecord, selectAll }) {
  function valueFor(field, value) {
    if (value === null || value === undefined || value === "") return "—";
    if (field.type === "number" && ["amount", "target_amount"].includes(field.key)) return formatMoney(value);
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  async function platformDetailView(resource, id) {
    const config = state.platformCatalog.resources[resource];
    const [record, related] = await Promise.all([
      api(`/api/platform/${resource}/${id}`),
      api(`/api/platform/${resource}/${id}/related`),
    ]);
    const fields = (config.fields || []).filter(f => f.type !== "file");
    const visible = fields.map(field =>
      `<div><span class="meta-label">${esc(field.label)}</span><span class="meta-value">${esc(valueFor(field, record[field.key]))}</span></div>`
    ).join("");
    const connected = ["accounts","contacts","deals"].flatMap(module =>
      (related[module] || []).map(item =>
        `<button type="button" class="detail-related-row" data-platform-related="${module}" data-id="${item.id}">${esc(item.name || item.full_name || "Open related record")} ›</button>`
      )
    ).join("");
    const linked = (related.platform_records || []).map(item =>
      `<button type="button" class="detail-related-row" data-platform-related="${esc(item.resource)}" data-id="${Number(item.id)}">${esc(item.record_number || item.name || "Open record")} ›</button>`
    ).join("");
    return `<div class="page-heading"><div><span class="eyebrow">${esc(config.label)}</span>
      <h1>${esc(record.name || config.singular)}</h1>
      <p class="subheading">${esc(record.record_number || "Record detail")}</p></div>
      <div class="heading-actions">
        <button class="button button-ghost" type="button" data-platform-return>← Back to ${esc(config.label)}</button>
        <button class="button button-primary" type="button" data-platform-detail-edit="${id}">Edit ${esc(config.singular)}</button>
        <button class="button button-ghost" type="button" data-platform-detail-delete="${id}">Delete</button>
      </div></div>
      <section class="card detail-summary"><div class="detail-meta-grid">${visible}</div></section>
      <section class="card detail-summary"><div class="card-head"><div class="card-head-copy"><h2>Related Records</h2><small>Linked CRM records</small></div></div>
      <div class="card-body">${connected || linked ? connected+linked : '<p class="related-empty">No linked records yet.</p>'}</div></section>
      <div class="caption">Last updated: ${esc(formatDateTime(record.updated_at))}</div>`;
  }

  function bindPlatformDetail(resource, id) {
    selectAll("[data-platform-return]").forEach(button => button.addEventListener("click", () => navigate(`/${resource}`)));
    selectAll("[data-platform-detail-edit]").forEach(button => button.addEventListener("click", () => openPlatformModal(resource, id)));
    selectAll("[data-platform-detail-delete]").forEach(button => button.addEventListener("click", () => deletePlatformRecord(resource, id)));
    selectAll("[data-platform-related]").forEach(button => button.addEventListener("click", () =>
      navigate(`/${button.dataset.platformRelated}/${Number(button.dataset.id)}`)
    ));
  }
  return { platformDetailView, bindPlatformDetail };
}

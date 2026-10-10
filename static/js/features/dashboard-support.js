// Dashboard reports and reusable dashboard presentation helpers.
export function createDashboardSupport({ api, formatDate, formatDateTime, formatMoney, esc, badge, pageHeader, emptyState, titleCase, $$, openRecordModal }) {
async function dashboardReportView(key) {
  const rawOffset = Number(new URLSearchParams(window.location.search).get("offset") || "0");
  const offset = Number.isSafeInteger(rawOffset) && rawOffset >= 0 ? rawOffset : 0;
  const report = await api(`/api/dashboard/report/${encodeURIComponent(key)}?limit=25&offset=${offset}`);
  const isDeal = ["open-deals", "pipeline-value"].includes(key);
  const isActivity = key === "activities-due";
  const column = isDeal ? "Amount" : isActivity ? "Due date" : key === "ai-action-queue" ? "Follow-up / validity" : "Next follow-up";
  const rows = (report.items || []).map((item) => {
    const date = item.date ? (isActivity ? formatDateTime(item.date) : formatDate(item.date)) : "—";
    const value = isDeal ? formatMoney(item.amount || 0) : date;
    return `<tr><td><strong>${esc(item.title)}</strong><span class="sub-cell">${esc(item.context || item.resource)}</span></td><td>${badge(item.status || "Unspecified")}</td><td>${esc(value)}</td><td><button type="button" class="button button-small button-ghost" data-go="${esc(item.url)}">Open ↗</button></td></tr>`;
  }).join("");
  const base = `/dashboard/report/${encodeURIComponent(key)}`;
  const previous = offset > 0 ? `<button type="button" class="button button-small button-ghost" data-go="${base}?offset=${Math.max(0, offset - report.limit)}">← Previous</button>` : "";
  const next = report.has_more ? `<button type="button" class="button button-small button-ghost" data-go="${base}?offset=${offset + report.limit}">Next →</button>` : "";
  const from = report.total ? offset + 1 : 0;
  const to = Math.min(offset + (report.items || []).length, report.total);
  return `${pageHeader("Dashboard / Reports", report.title, report.description, '<button type="button" class="button button-ghost" data-go="/dashboard">← Back to dashboard</button>')}
    <section class="card dashboard-report" data-dashboard-report="${esc(key)}">
      <div class="card-head"><div class="card-head-copy"><h2>${report.total} matching record${report.total === 1 ? "" : "s"}</h2><small>Live CRM records${report.amount != null ? " · Open pipeline: " + formatMoney(report.amount) : ""}</small></div></div>
      <div class="card-body">${rows ? `<div class="table-wrap"><table class="data-table dashboard-report-table"><thead><tr><th>Record</th><th>Status / Stage</th><th>${column}</th><th>Details</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyState("◎", "No matching records", "There are no records matching this dashboard metric right now.")}</div>
      <div class="dashboard-report-footer"><span>${from}–${to} of ${report.total}</span><div class="dashboard-report-pages">${previous}${next}</div></div>
    </section>`;
}


function performanceTable(rows) {
  if (!rows.length) return emptyState("◎", "No active salespeople", "Add active users and targets to calculate performance.");
  return `<div class="table-wrap"><table class="data-table performance-table"><thead><tr><th>Salesperson</th><th>Target</th><th>Achieved</th><th>Achievement</th><th>Conversions</th><th>Incentive</th></tr></thead><tbody>${rows.map((row) => `<tr><td><strong>${esc(row.name)}</strong><span class="sub-cell">${esc(row.role)}${row.target_configured ? "" : " · target missing"}</span></td><td>${formatMoney(row.target)}</td><td>${formatMoney(row.achieved)}</td><td><span class="achievement-meter"><i style="width:${Math.min(Number(row.achievement_percent || 0), 100)}%"></i></span><strong>${Number(row.achievement_percent || 0).toFixed(1)}%</strong></td><td>${row.conversions}</td><td>${formatMoney(row.incentive)}</td></tr>`).join("")}</tbody></table></div>`;
}

function attentionQueue(attention) {
  const leads = attention.stuck_leads || [];
  const quotes = attention.quotes_needing_follow_up || [];
  // Flat rows, rather than browser-default boxed buttons, keep the queue readable.
  // Buttons retain keyboard activation and the delegated data-go navigation.
  const items = [
    ...leads.map((item) => `<button type="button" class="ai-queue-row" data-go="/leads/${Number(item.id)}"><span class="ai-queue-icon" aria-hidden="true">!</span><span class="ai-queue-copy"><strong>${esc(item.name)}</strong><small>Lead stuck at ${esc(item.status)}${item.next_follow_up ? ` · follow-up ${formatDate(item.next_follow_up)}` : ""}</small></span><span class="ai-queue-chevron" aria-hidden="true">›</span></button>`),
    ...quotes.map((item) => `<button type="button" class="ai-queue-row" data-go="/quotes/${Number(item.id)}"><span class="ai-queue-icon" aria-hidden="true">₹</span><span class="ai-queue-copy"><strong>${esc(item.name)}</strong><small>${esc(item.status)}${item.valid_until ? ` · valid until ${formatDate(item.valid_until)}` : " · no expiry date"}</small></span><span class="ai-queue-chevron" aria-hidden="true">›</span></button>`),
  ];
  return items.length ? `<div class="ai-queue-list" aria-label="Records requiring action">${items.join("")}</div>` : emptyState("✓", "Nothing urgent", "No stale leads or quotations need immediate follow-up.");
}

function attentionPanel(attention) {
  return `<section class="card"><div class="card-head"><div class="card-head-copy"><h2>AI action queue</h2><small>Prioritized from live CRM dates and statuses</small></div><button type="button" class="card-head-link" data-go="/dashboard/report/ai-action-queue">View queue ↗</button></div><div class="card-body">${attentionQueue(attention)}</div></section>`;
}

function activityItem(item) {
  const rawKind = String(item.activity_type || "task").toLowerCase();
  const kind = ["call", "meeting"].includes(rawKind) ? rawKind : "task";
  const icon = kind === "call" ? "⌕" : kind === "meeting" ? "◷" : "✓";
  return `<div class="activity-item"><span class="activity-icon ${kind}">${icon}</span><div class="activity-copy"><strong>${esc(item.subject)}</strong><small>${esc(item.related_label || "Unlinked record")} · ${esc(titleCase(item.status))}</small></div><span class="activity-time">${formatDateTime(item.due_at)}</span></div>`;
}

function bindDashboard() {
  $$('[data-create]').forEach((button) => button.addEventListener("click", () => openRecordModal(button.dataset.create)));
  // The global delegated data-go handler performs dashboard navigation once.
}


return { dashboardReportView, performanceTable, attentionQueue, attentionPanel, activityItem, bindDashboard };
}

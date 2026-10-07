// APEX/AI cockpit, assistant and approval UI domain.
export function createAiFeature(ctx) {
  const { state, MODULES, $, $$, esc, titleCase, initials, formatDate, formatDateTime, formatMoney, slug, pathFor, badge, lookupName, api, toast, pageHeader, loading, emptyState, navigate, openRecordModal, openPlatformModal, closeModal, confirmAction, fieldHtml, platformDisplay, platformTable, platformPanel, ensureLookups, ensurePlatformLookup, invalidateLookups, refreshMeta } = ctx;

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

  return { aiDashboardView, apexAssistantResultHtml, bindApexAssistant, bindApexAssistantResult, aiView, aiMessageHtml, renderAIConversation, bindAIProposalActions, bindAI };
}

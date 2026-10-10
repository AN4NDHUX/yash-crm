/** Dedicated quote record experience. Keeps CONVOSIS design while following
 * the CRM record-detail hierarchy: action header, related rail, tabs, fields. */
export function createQuoteDetails(ctx) {
  const { api, esc, badge, formatDate, formatDateTime, formatMoney, lookupName,
    navigate, openPlatformModal, deletePlatformRecord, toast, renderRoute } = ctx;
  let current = null;

  function field(label, value, html = false) {
    const shown = value === undefined || value === null || value === "" ? "—" : value;
    return `<div class="quote-field"><dt>${esc(label)}</dt><dd>${html ? shown : esc(shown)}</dd></div>`;
  }
  function link(resource, item, caption) {
    if (!item?.id) return "—";
    return `<a href="/${resource}/${Number(item.id)}" class="quote-inline-link" data-go="/${resource}/${Number(item.id)}">${esc(caption || item.name || item.title || ("Record #" + item.id))}</a>`;
  }
  function entry(label, detail, path) {
    const line = `<span class="quote-related-line"><strong>${esc(label)}</strong><small>${esc(detail || "")}</small></span>`;
    return path ? `<a href="${path}" data-go="${path}" class="quote-related-item">${line}<span aria-hidden="true">›</span></a>`
      : `<div class="quote-related-item">${line}</div>`;
  }
  function section(id, title, rows, emptyText = "No related records yet.", action = "") {
    return `<section class="quote-section" id="quote-section-${esc(id)}"><header class="quote-section-head"><h3>${esc(title)}</h3>${action}</header><div class="quote-section-body">${rows.length ? rows.join("") : `<p class="quote-empty">${esc(emptyText)}</p>`}</div></section>`;
  }
  function relatedRows(related, key, resource, titleKey) {
    return (related[key] || []).map(item => {
      const title = item[titleKey] || item.name || item.title || item.subject || "Record";
      const detail = item.status || item.email || item.updated_at?.slice(0, 10) || "";
      if (["sales_orders", "invoices"].includes(resource)) return `<button class="quote-related-item" type="button" data-quote-related-open="${resource}" data-id="${Number(item.id)}"><span class="quote-related-line"><strong>${esc(title)}</strong><small>${esc(detail)}</small></span><span aria-hidden="true">›</span></button>`;
      return entry(title, detail, resource ? `/${resource}/${Number(item.id)}` : "");
    });
  }
  function rail(related) {
    const groups = [
      ["notes", "Notes", related.notes?.length || 0],
      ["connected", "Connected Records", (related.accounts?.length || 0) + (related.contacts?.length || 0) + (related.deals?.length || 0)],
      ["sales-orders", "Sales Orders", related.sales_orders?.length || 0],
      ["invoices", "Invoices", related.invoices?.length || 0],
      ["attachments", "Attachments", related.attachments?.length || 0],
      ["open-activities", "Open Activities", (related.activities || []).filter(x => x.status !== "Completed").length],
      ["closed-activities", "Closed Activities", (related.activities || []).filter(x => x.status === "Completed").length],
      ["emails", "Emails", related.emails?.length || 0],
    ];
    return `<aside class="quote-related-nav"><h3>Related List</h3>${groups.map(([id, name, count]) =>
      `<button type="button" data-quote-scroll="${id}"><span>${esc(name)}</span><small>${count}</small></button>`).join("")}
      <button type="button" data-quote-tab="timeline"><span>Timeline</span><small>${related.timeline?.length || 0}</small></button></aside>`;
  }
  function showOverview(quote, related) {
    const account = related.accounts?.[0];
    const contact = related.contacts?.[0];
    const deal = related.deals?.[0];
    const number = quote.quote_number || `QUO-${quote.id}`;
    const summary = `<section class="quote-section quote-summary" id="quote-section-information">
      <header class="quote-section-head"><h3>Quote Information</h3></header>
      <dl class="quote-field-grid">
        ${field("Quote Owner", quote.owner_name || "Unassigned")}
        ${field("Quote Number", number)}
        ${field("Subject", quote.name)}
        ${field("Deal Name", deal ? link("deals", deal) : lookupName("deals", quote.deal_id), true)}
        ${field("Quote Stage", badge(quote.status), true)}
        ${field("Account Name", account ? link("accounts", account) : lookupName("accounts", quote.account_id), true)}
        ${field("Valid Until", formatDate(quote.valid_until))}
        ${field("Contact Name", contact ? link("contacts", contact, contact.full_name || [contact.first_name, contact.last_name].filter(Boolean).join(" ")) : lookupName("contacts", quote.contact_id), true)}
        ${field("Total", formatMoney(quote.amount))}
        ${field("Last Updated", formatDateTime(quote.updated_at))}
      </dl></section>`;
    const noteRows = (related.notes || []).map(note =>
      entry(note.title || "Note", note.content || "No content"));
    const connected = [
      ...relatedRows(related, "accounts", "accounts", "name"),
      ...relatedRows(related, "contacts", "contacts", "full_name"),
      ...relatedRows(related, "deals", "deals", "name"),
    ];
    const attachments = (related.attachments || []).map(item => entry(item.name || "Attachment", item.file_type || "File"));
    const open = (related.activities || []).filter(item => item.status !== "Completed")
      .map(item => entry(item.subject || item.activity_type || "Activity", item.status));
    const closed = (related.activities || []).filter(item => item.status === "Completed")
      .map(item => entry(item.subject || "Activity", item.status));
    const emails = (related.emails || []).map(item => entry(item.subject || "Email", item.status));
    return summary +
      section("notes", "Notes", noteRows, "No notes yet.",
        '<button class="quote-text-action" type="button" data-quote-add-note>Add</button>') +
      section("connected", "Connected Records", connected) +
      section("sales-orders", "Sales Orders", relatedRows(related, "sales_orders", "sales_orders", "name")) +
      section("invoices", "Invoices", relatedRows(related, "invoices", "invoices", "name")) +
      section("attachments", "Attachments", attachments) +
      section("open-activities", "Open Activities", open) +
      section("closed-activities", "Closed Activities", closed) +
      section("emails", "Emails", emails) +
      section("terms", "Terms & Conditions", quote.terms ? [`<p class="quote-terms">${esc(quote.terms)}</p>`] : [], "No terms specified.");
  }
  function showTimeline(related, quote) {
    const events = [...(related.timeline || [])].map(item => ({
      title: item.title || "Quote updated", occurred_at: item.occurred_at, action: item.action,
    }));
    if (!events.some(item => item.action === "create")) events.push({
      title: "Quote created", action: "create", occurred_at: quote.created_at,
    });
    events.sort((a, b) => String(b.occurred_at || "").localeCompare(String(a.occurred_at || "")));
    return `<section class="quote-section"><header class="quote-section-head"><h3>Quote Timeline</h3></header>
      <div class="quote-timeline">${events.map(event => `<div class="quote-event">
        <span class="quote-event-dot"></span><div><strong>${esc(event.title)}</strong><small>${esc(formatDateTime(event.occurred_at))}</small></div>
      </div>`).join("") || '<p class="quote-empty">No timeline entries yet.</p>'}</div></section>`;
  }

  async function view(id) {
    const quote = await api(`/api/platform/quotes/${id}`);
    const related = await api(`/api/platform/quotes/${id}/related`);
    current = { quote, related };
    const number = quote.quote_number || `QUO-${id}`;
    return `<div class="quote-detail-page">
      <header class="quote-record-header">
        <div class="quote-record-heading">
          <a href="/quotes" data-go="/quotes" class="quote-back" aria-label="Back to quotes">←</a>
          <div><span class="quote-eyebrow">Quotes / ${esc(number)}</span><h1>${esc(quote.name || number)}</h1>
          <p>${esc(number)} · ${esc(quote.owner_name || "Unassigned")} · ${badge(quote.status)}</p></div>
        </div>
        <div class="quote-action-bar">
          <div class="quote-convert-wrapper"><button type="button" class="button button-primary" data-quote-convert-menu aria-expanded="false" aria-haspopup="true">Convert <span aria-hidden="true">▾</span></button>
            <div class="quote-convert-options" data-quote-convert-options hidden role="group" aria-label="Convert quote">
              <button type="button" data-quote-convert="sales_orders">Sales Order</button>
              <button type="button" data-quote-convert="invoices">Invoice</button>
            </div></div>
          <button type="button" class="button button-ghost" data-quote-edit>Edit</button>
          <button type="button" class="button button-ghost" data-quote-archive>Archive</button>
        </div>
      </header>
      <div class="quote-record-layout">
        ${rail(related)}
        <main class="quote-record-main">
          <div class="quote-tab-strip" role="tablist" aria-label="Quote detail sections">
            <button role="tab" aria-selected="true" type="button" class="active" data-quote-tab="overview">Overview</button>
            <button role="tab" aria-selected="false" type="button" data-quote-tab="timeline">Timeline</button>
          </div>
          <div data-quote-panel="overview" role="tabpanel">
            <div class="quote-highlights">
              <div><span>QUOTE NUMBER</span><strong>${esc(number)}</strong></div>
              <div><span>QUOTE STAGE</span><strong>${badge(quote.status)}</strong></div>
              <div><span>QUOTE OWNER</span><strong>${esc(quote.owner_name || "Unassigned")}</strong></div>
              <div><span>VALID UNTIL</span><strong>${esc(formatDate(quote.valid_until))}</strong></div>
            </div>
            ${showOverview(quote, related)}
          </div>
          <div data-quote-panel="timeline" role="tabpanel" hidden>${showTimeline(related, quote)}</div>
        </main>
      </div>
    </div>`;
  }

  function selectTab(name) {
    document.querySelectorAll("[data-quote-panel]").forEach(panel => {
      panel.hidden = panel.dataset.quotePanel !== name;
    });
    document.querySelectorAll(".quote-tab-strip [data-quote-tab]").forEach(button => {
      const active = button.dataset.quoteTab === name;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
  }
  async function convert(destination) {
    if (!current) return;
    const { quote, related } = current;
    const existing = related[destination] || [];
    if (existing.length) {
      toast("Existing record", "Opening the existing converted record to avoid duplicates.");
      await openPlatformModal(destination, Number(existing[0].id));
      return;
    }
    const kind = destination === "sales_orders" ? "Sales Order" : "Invoice";
    if (!window.confirm(`Create a linked ${kind} from quote ${quote.quote_number || quote.name}?`)) return;
    const data = {
      name: `${quote.name} - ${kind}`,
      account_id: quote.account_id || null,
      deal_id: quote.deal_id || null,
      amount: Number(quote.amount || 0),
      status: "Draft",
    };
    if (destination === "sales_orders") data.quote_id = quote.id;
    else { data.related_type = "quotes"; data.related_id = quote.id; }
    const button = document.querySelector(`[data-quote-convert="${destination}"]`);
    if (button) button.disabled = true;
    try {
      const created = await api(`/api/platform/${destination}`, { method: "POST", body: JSON.stringify(data) });
      toast(`${kind} created`, "The new record is linked to this Quote.");
      await navigate(`/quotes/${quote.id}`);
    } catch (error) {
      toast("Conversion failed", error.message, "error");
      if (button) button.disabled = false;
    }
  }
  function bind(id) {
    const menu = document.querySelector("[data-quote-convert-menu]");
    const options = document.querySelector("[data-quote-convert-options]");
    menu?.addEventListener("click", () => {
      options.hidden = !options.hidden;
      menu.setAttribute("aria-expanded", String(!options.hidden));
    });
    document.querySelectorAll("[data-quote-convert]").forEach(button =>
      button.addEventListener("click", () => convert(button.dataset.quoteConvert)));
    document.querySelectorAll("[data-quote-related-open]").forEach(button => button.addEventListener("click", () => openPlatformModal(button.dataset.quoteRelatedOpen, Number(button.dataset.id))));
    document.querySelector("[data-quote-edit]")?.addEventListener("click", () => openPlatformModal("quotes", id));
    document.querySelector("[data-quote-archive]")?.addEventListener("click", () => deletePlatformRecord("quotes", id));
    document.querySelectorAll("[data-quote-tab]").forEach(button =>
      button.addEventListener("click", () => selectTab(button.dataset.quoteTab)));
    document.querySelectorAll("[data-quote-scroll]").forEach(button => button.addEventListener("click", () => {
      selectTab("overview");
      document.getElementById("quote-section-" + button.dataset.quoteScroll)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }));
    document.querySelector("[data-quote-add-note]")?.addEventListener("click", () => {
      const section = document.getElementById("quote-section-notes");
      if (section.querySelector("[data-quote-note-form]")) return;
      const form = document.createElement("form");
      form.className = "quote-note-form";
      form.dataset.quoteNoteForm = "true";
      form.innerHTML = '<label>Title<input name="title" maxlength="160" required placeholder="Note title"></label><label>Note<textarea name="content" rows="3" placeholder="Write a note..."></textarea></label><div><button class="button button-primary" type="submit">Save note</button><button class="button button-ghost" type="button" data-quote-note-cancel>Cancel</button></div>';
      section.querySelector(".quote-section-body").prepend(form);
      form.querySelector("[name=title]").focus();
      form.querySelector("[data-quote-note-cancel]").addEventListener("click", () => form.remove());
      form.addEventListener("submit", async event => {
        event.preventDefault();
        const submit = form.querySelector('[type="submit"]');
        submit.disabled = true;
        try {
          await api("/api/notes", { method: "POST", body: JSON.stringify({
            title: form.elements.title.value.trim(),
            content: form.elements.content.value.trim(),
            related_type: "quotes", related_id: id,
          }) });
          toast("Note added", "Saved to this Quote.");
          await renderRoute();
        } catch (error) {
          toast("Could not add note", error.message, "error");
          submit.disabled = false;
        }
      });
    });
  }
  return { view, bind };
}

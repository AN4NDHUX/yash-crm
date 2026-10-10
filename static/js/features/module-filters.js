// Reusable Zoho-style advanced filter drawer for Leads, Deals, Accounts and Contacts.
// Server supplies the real field and relationship catalog; every rule is enforced in
// GET /api/{resource} before pagination, not by hiding rows in the browser.

const keyOf = (kind, key) => `${kind}:${key}`;
const safeRule = (rules, kind, key) => (rules || []).find(rule => rule.kind === kind && rule.key === key);
const DISPLAY_OPERATORS = {
  text: [["contains", "Contains"], ["equals", "Is"], ["not_equals", "Is not"], ["is_empty", "Is empty"], ["is_not_empty", "Is not empty"]],
  number: [["equals", "Equals"], ["gt", "Greater than"], ["gte", "At least"], ["lt", "Less than"], ["lte", "At most"], ["is_empty", "Is empty"], ["is_not_empty", "Is not empty"]],
  date: [["equals", "On"], ["gt", "After"], ["gte", "On or after"], ["lt", "Before"], ["lte", "On or before"], ["is_empty", "Is empty"], ["is_not_empty", "Is not empty"]],
  boolean: [["equals", "Is"], ["not_equals", "Is not"], ["is_empty", "Is empty"], ["is_not_empty", "Is not empty"]],
};

export const FILTERABLE_MODULES = Object.freeze(["leads", "deals", "accounts", "contacts"]);

export function renderModuleFilters(resource, current, catalog, esc) {
  if (!catalog || !FILTERABLE_MODULES.includes(resource)) return "";
  const rules = current.advancedFilters?.rules || [];
  const count = rules.length;
  const section = (label, list, kind, controls) => `<details class="advanced-filter-group" open><summary>${esc(label)} <span>${list.length}</span></summary>
    <div class="advanced-filter-options">${list.map((item) => {
      const old = safeRule(rules, kind, item.key);
      const id = keyOf(kind, item.key);
      const checked = old ? "checked" : "";
      return `<div class="advanced-filter-option" data-filter-item data-filter-name="${esc(item.label.toLowerCase())}">
        <label><input type="checkbox" data-filter-check="${esc(id)}" ${checked}/><span>${esc(item.label)}</span></label>
        <div class="advanced-filter-condition" data-filter-condition="${esc(id)}" ${old ? "" : "hidden"}>${controls(item, old, kind)}</div>
      </div>`;
    }).join("")}</div></details>`;

  const control = (item, old, kind) => {
    if (kind === "system") return '<span class="advanced-filter-hint">Include matching records</span>';
    const type = item.type || "text";
    const choices = kind === "related"
      ? [["exists", "Has related records"], ["not_exists", "Has no related records"]]
      : DISPLAY_OPERATORS[type] || DISPLAY_OPERATORS.text;
    const op = old?.operator || (kind === "related" ? "exists" : type === "text" ? "contains" : "equals");
    const inputType = kind === "related" ? "search" : (type === "date" ? "date" : type === "number" ? "number" : "text");
    const noValue = ["is_empty", "is_not_empty", "not_exists"].includes(op) || (kind === "system");
    return `<select class="advanced-filter-operator" data-filter-operator aria-label="${esc(item.label)} condition">
      ${choices.map(([value, label]) => `<option value="${value}" ${op === value ? "selected" : ""}>${esc(label)}</option>`).join("")}
      </select><input class="advanced-filter-value" data-filter-value type="${inputType}" ${type === "number" ? 'step="any"' : ""} value="${esc(old?.value || "")}" placeholder="${kind === "related" ? "Optional related-record name" : "Filter value"}" aria-label="${esc(item.label)} value" ${noValue ? "hidden" : ""}/>`;
  };
  const title = resource[0].toUpperCase() + resource.slice(1);
  return `<aside id="module-filter-sidebar" class="advanced-filter-sidebar" data-filter-sidebar ${current.filtersOpen ? "" : "hidden"} aria-label="${esc(title)} filters">
    <div class="advanced-filter-head"><strong>Filter ${esc(title)} by</strong><button type="button" class="advanced-filter-close" data-filter-close aria-label="Close filters">×</button></div>
    <label class="advanced-filter-search-label"><span>⌕</span><input type="search" data-filter-search placeholder="Search filters" aria-label="Search available filters"/></label>
    <div class="advanced-filter-scroll">
      ${section("System Defined Filters", catalog.system || [], "system", control)}
      ${section("Filter By Fields", catalog.fields || [], "field", control)}
      ${section("Filter By Related Modules", catalog.related || [], "related", control)}
    </div>
    <div class="advanced-filter-actions">
      <label>Match <select data-filter-join aria-label="Filter combination"><option value="all" ${current.advancedFilters?.join !== "any" ? "selected" : ""}>all conditions</option><option value="any" ${current.advancedFilters?.join === "any" ? "selected" : ""}>any condition</option></select></label>
      <div class="advanced-filter-buttons"><button type="button" class="button button-small button-ghost" data-filter-reset>Reset</button><button type="button" class="button button-small button-primary" data-filter-apply>Apply filters</button></div>
      <small data-filter-message aria-live="polite">${count ? count + " applied filter" + (count === 1 ? "" : "s") : "Select filters to refine records"}</small>
    </div>
  </aside>`;
}

export function bindModuleFilters({resource, current, renderRoute, toast, root = document}) {
  if (!FILTERABLE_MODULES.includes(resource)) return;
  const sidebar = root.querySelector("[data-filter-sidebar]");
  const layout = root.querySelector("[data-filter-layout]");
  const toggle = root.querySelector("[data-filter-toggle]");
  if (!sidebar || !layout || !toggle) return;
  const setOpen = (open) => {
    current.filtersOpen = open;
    sidebar.hidden = !open;
    layout.classList.toggle("filters-visible", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (open) sidebar.querySelector("[data-filter-search]")?.focus();
    else toggle.focus();
  };
  toggle.addEventListener("click", () => setOpen(!current.filtersOpen));
  sidebar.querySelector("[data-filter-close]")?.addEventListener("click", () => setOpen(false));
  sidebar.querySelector("[data-filter-search]")?.addEventListener("input", (event) => {
    const needle = event.target.value.toLowerCase().trim();
    sidebar.querySelectorAll("[data-filter-item]").forEach(item => {
      item.hidden = Boolean(needle) && !item.dataset.filterName.includes(needle);
    });
    if (needle) sidebar.querySelectorAll("details").forEach(group => { group.open = true; });
  });
  sidebar.querySelectorAll("[data-filter-check]").forEach(box => box.addEventListener("change", () => {
    const controls = [...sidebar.querySelectorAll("[data-filter-condition]")].find(item => item.dataset.filterCondition === box.dataset.filterCheck);
    if (controls) controls.hidden = !box.checked;
  }));
  sidebar.querySelectorAll("[data-filter-operator]").forEach(select => select.addEventListener("change", () => {
    const value = select.closest("[data-filter-condition]")?.querySelector("[data-filter-value]");
    if (value) value.hidden = ["is_empty", "is_not_empty", "not_exists"].includes(select.value);
  }));
  sidebar.querySelector("[data-filter-apply]")?.addEventListener("click", () => {
    const rules = [];
    let invalid = false;
    sidebar.querySelectorAll("[data-filter-check]:checked").forEach(box => {
      const [kind, key] = box.dataset.filterCheck.split(":");
      const container = [...sidebar.querySelectorAll("[data-filter-condition]")].find(el => el.dataset.filterCondition === box.dataset.filterCheck);
      const operator = kind === "system" ? "enabled" : container.querySelector("[data-filter-operator]").value;
      const needsValue = kind === "field" && !["is_empty", "is_not_empty"].includes(operator);
      const value = ["is_empty", "is_not_empty", "not_exists"].includes(operator) ? "" : (container.querySelector("[data-filter-value]")?.value || "").trim();
      if (needsValue && !value) { invalid = true; container.querySelector("[data-filter-value]")?.focus(); return; }
      rules.push({kind, key, operator, value});
    });
    if (invalid) {
      sidebar.querySelector("[data-filter-message]").textContent = "Enter a value for each selected field condition.";
      toast("Incomplete filter", "Provide a value or choose Is empty / Is not empty.", "error");
      return;
    }
    if (rules.length > 12) {
      toast("Too many filters", "Select up to 12 conditions.", "error");
      return;
    }
    current.advancedFilters = {join: sidebar.querySelector("[data-filter-join]").value, rules};
    current.offset = 0;
    current.selectedIds = [];
    renderRoute();
  });
  sidebar.querySelector("[data-filter-reset]")?.addEventListener("click", () => {
    current.advancedFilters = {join:"all", rules:[]};
    current.offset = 0;
    current.selectedIds = [];
    renderRoute();
  });
}

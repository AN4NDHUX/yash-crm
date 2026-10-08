import { MODULES } from "./modules.js";
// Zoho-inspired workflow rule list and WHEN / CONDITION / ACTION wizard.
// Existing /api/platform/workflow_rules endpoints remain the source of truth.
const operators = [
  ["equals", "is"], ["not_equals", "isn't"], ["contains", "contains"],
  ["does_not_contain", "doesn't contain"], ["starts_with", "starts with"],
  ["ends_with", "ends with"], ["greater_than", "greater than"],
  ["less_than", "less than"], ["is_empty", "is empty"], ["is_not_empty", "is not empty"]
];
// Group actions by the Zoho-style instant-action categories while preserving
// the existing backend action identifiers and stored workflow compatibility.
const actions = [
  ["field_update", "Field Update"],
  ["tag", "Tags"],
  ["email", "Email Notification"],
  ["create_task", "Activities — Task"],
  ["webhook_queue", "Webhook"],
  ["function", "Function"],
  ["audit", "Audit activity"],
  ["notification", "Notification"]
];
const opts = (items, selected, escape) => items.map(([value, label]) =>
  `<option value="${escape(value)}" ${String(selected) === String(value) ? "selected" : ""}>${escape(label)}</option>`).join("");
const newCondition = () => ({field:"",operator:"equals",value:""});
const draftRule = () => ({
  name:"", description:"", module:"", event:"create_or_edit", trigger_field:"",
  criteria_mode:"conditions", logic:"AND", conditions:[newCondition()],
  actions:[{type:"audit",value:""}], scheduled_for:"", status:"Active"
});

export function createWorkflowRulesUI({api, esc, toast, navigate, renderRoute, state}) {
  let draft = null;
  let editingId = null;
  let step = 0;
  let rules = [];
  let activity = [];
  let customFunctions = [];
  let functionPicker = false;
  let functionSearch = "";
  let functionConfiguration = false;
  let functionEditor = false;
  let functionEditingId = null;
  let functionDraft = null;
  let listQuery = "";
  let moduleFilter = "all";
  const selectedRuleIds = new Set();
  const el = (root, selector) => root.querySelector(selector);
  const els = (root, selector) => [...root.querySelectorAll(selector)];
  const moduleOptions = () => {
    // Restrict workflow creation to the primary CRM business modules.
    // Do not expose administration, billing, or platform configuration resources.
    const primary = [
      ["leads","Leads"],["contacts","Contacts"],["accounts","Accounts"],
      ["deals","Deals"],["tasks","Tasks"],["meetings","Meetings"],
      ["calls","Calls"],["products","Products"],["quotes","Quotes"],
      ["sales_orders","Sales Orders"],["purchase_orders","Purchase Orders"],
      ["invoices","Invoices"],["vendors","Vendors"],
      ["campaigns","Campaigns"],["cases","Cases"]
    ];
    const available = state.platformCatalog?.resources || {};
    return primary.filter(([key]) => available[key] || MODULES[key]);
  };
  const fieldsFor = () => {
    const catalog = state.platformCatalog?.resources?.[draft.module];
    const fields = catalog?.fields || MODULES[draft.module]?.fields || [];
    const map = new Map([["name","Record name"],["status","Status"],["owner_id","Owner ID"]]);
    for (const field of fields) {
      const key = field.key || field.name || field.api_name;
      if (key) map.set(key, field.label || key);
    }
    const module = state.platformCatalog?.resources?.[draft.module];
    if (!module && !MODULES[draft.module]) for (const key of ["website","company","email","phone","amount","stage","source"]) map.set(key, key.replaceAll("_"," "));
    return [...map].map(([key,label]) => [key,label]);
  };
  const asDraft = (record) => {
    const criteria = record.criteria;
    return {
      name:record.name || record.title || "",
      description:record.description || "",
      module:record.module || "leads",
      event:record.event === "update" ? "edit" : record.event === "create" ? "create" : (record.event || "create_or_edit"),
      trigger_field:record.trigger_field || "",
      criteria_mode:criteria ? "conditions" : "all",
      logic:criteria?.logic === "OR" ? "OR" : "AND",
      conditions:criteria?.conditions?.length ? criteria.conditions.map(c=>({...newCondition(),...c})) : criteria?.field ? [{...newCondition(),...criteria}] : [newCondition()],
      actions:Array.isArray(record.actions) && record.actions.length ? record.actions.map(a=>({...a})) : [{type:record.action_type || "audit",value:record.action_value || ""}],
      scheduled_for:record.scheduled_for || "",
      status:record.status || "Active"
    };
  };
  const stepLabels = ["Rule details","WHEN","CONDITION","ACTIONS"];
  const conditionRows = () => draft.conditions.map((item,index) => `<div class="wf-condition-row" data-condition-row="${index}"><input class="field-input wf-field-search" data-wf-field-search="${index}" aria-label="Search condition fields" placeholder="Search fields…" autocomplete="off" />
    <span class="wf-condition-number">${index+1}</span>
    <select class="field-select" data-wf-field="${index}" aria-label="Condition field">${opts([["","Select field"],...fieldsFor()],item.field,esc)}</select>
    <select class="field-select" data-wf-operator="${index}" aria-label="Condition operator">${opts(operators,item.operator,esc)}</select>
    <input class="field-input" data-wf-value="${index}" aria-label="Condition value" placeholder="Value" value="${esc(item.value ?? "")}" ${["is_empty","is_not_empty"].includes(item.operator) ? "disabled" : ""}/>
    <button type="button" class="button button-small" data-wf-remove-condition="${index}" aria-label="Remove condition" ${draft.conditions.length === 1 ? "disabled" : ""}>−</button>
  </div>`).join("");
  const actionRows = () => draft.actions.map((item,index) => `<div class="wf-action-row" data-action-row="${index}">
    <select class="field-select" data-wf-action-type="${index}">${opts(actions,item.type,esc)}</select>
    ${item.type === "field_update" ? `<select class="field-select" data-wf-action-field="${index}">${opts([["","Select field"],...fieldsFor()],item.field || "",esc)}</select>` : ""}
    ${item.type === "email" ? `<input class="field-input" data-wf-action-to="${index}" type="email" aria-label="Recipient email" placeholder="Approved recipient email" value="${esc(item.to || "")}"/><input class="field-input" data-wf-action-subject="${index}" aria-label="Email subject" placeholder="Email subject" value="${esc(item.subject || "")}"/>` : ""}
    ${item.type === "function" ? `<select class="field-select" data-wf-action-value="${index}" aria-label="Custom function">${opts([["","Select active custom function"],...customFunctions.filter(fn=>fn.status === "Active").map(fn=>[String(fn.id),fn.name || fn.title])],item.value ?? "",esc)}</select>` : `<input class="field-input" data-wf-action-value="${index}" placeholder="${item.type === "field_update" ? "New value" : item.type === "create_task" ? "Task subject" : "Action details (optional)"}" value="${esc(item.value ?? "")}"/>`}
    <button class="button button-small" type="button" data-wf-remove-action="${index}" ${draft.actions.length === 1 ? "disabled" : ""}>Remove</button>
  </div>`).join("");
  const functionEditorDialog = () => `<div class="wf-rule-overlay"><div class="wf-rule-dialog" role="dialog" aria-modal="true" aria-label="Edit Python Function" style="max-width:900px;width:min(94vw,900px)">
    <header><h2>${functionEditingId ? "Edit" : "Create"} Python Function</h2><p>Save a function definition for this organization. Script execution is not enabled.</p></header>
    <div class="form-grid" style="padding:16px">
      <div class="field"><label>Function name</label><input class="field-input" data-wf-new-function-name maxlength="160" required value="${esc(functionDraft?.name || "")}"/></div>
      <div class="field"><label>Entrypoint</label><input class="field-input" data-wf-new-function-entry value="${esc(functionDraft?.entrypoint || "main")}" maxlength="80"/></div>
      <div class="field full"><label>Python source</label><textarea class="field-input" data-wf-new-function-source rows="13" spellcheck="false" placeholder="def main(record):&#10;    return {&quot;record_id&quot;: record.get(&quot;id&quot;)}">${esc(functionDraft?.code || "")}</textarea></div>
    </div>
    <footer class="wf-editor-footer"><button type="button" class="button" data-wf-editor-close>Cancel</button><button type="button" class="button button-primary" data-wf-editor-save>Save Draft</button></footer>
  </div></div>`;
  const configureFunctionDialog = () => `<div class="wf-rule-overlay"><div class="wf-rule-dialog" role="dialog" aria-modal="true" aria-label="Configure Function" style="max-width:680px;width:min(92vw,680px)">
    <header><h2>Configure Function</h2><p>Choose how to configure your workflow function.</p></header>
    <div style="display:grid;gap:12px;padding:16px">
      <button type="button" class="button" data-wf-function-method="gallery"><strong>Gallery</strong> — Browse preconfigured examples</button>
      <button type="button" class="button" data-wf-function-method="existing"><strong>Functions</strong> — Use an existing organization function</button>
      <button type="button" class="button" data-wf-function-method="create"><strong>Write your own</strong> — Create a function in Developer Hub</button>
    </div>
    <footer class="wf-editor-footer"><button type="button" class="button" data-wf-function-config-close>Cancel</button></footer>
  </div></div>`;
  const functionDialog = () => {
    const filtered = customFunctions.filter(fn => { const modules = fn.associations?.modules; return (!Array.isArray(modules) || modules.length === 0 || modules.includes(draft.module)) && String(fn.name || fn.title || "").toLowerCase().includes(functionSearch.toLowerCase()); });
    return `<div class="wf-rule-overlay" data-wf-function-overlay><div class="wf-rule-dialog" role="dialog" aria-modal="true" aria-label="Associate custom function" style="max-width:900px;width:min(92vw,900px)">
      <header><h2>Functions - ${esc(moduleOptions().find(([key])=>key===draft.module)?.[1] || draft.module)}</h2></header>
      <div class="wf-list-actions"><label>Search <input class="field-input" data-wf-function-search placeholder="Search functions" value="${esc(functionSearch)}"/></label><button type="button" class="button" data-wf-configure-function>Configure Function</button></div>
      <div style="max-height:45vh;overflow:auto"><table class="table"><thead><tr><th>Name</th><th>Description</th><th>Language</th><th>Modified On</th></tr></thead><tbody>
      ${filtered.map(fn=>`<tr><td><label><input type="radio" name="wf-function-choice" value="${esc(String(fn.id))}" ${fn.status !== "Active" ? "disabled" : ""} ${draft.actions.some(a=>a.type==="function"&&String(a.value)===String(fn.id))?"checked":""}/> ${esc(fn.name || fn.title || "")} (${esc(fn.status || "Draft")})</label> <button type="button" class="button button-small" data-wf-edit-function="${esc(String(fn.id))}">Edit</button></td><td>${esc(fn.description || "")}</td><td>${esc(fn.language || "Configured")}</td><td>${esc(fn.updated_at || fn.modified_at || "")}</td></tr>`).join("") || '<tr><td colspan="4">No functions found. Choose Configure Function to create a draft.</td></tr>'}
      </tbody></table></div><footer class="wf-editor-footer"><button type="button" class="button" data-wf-close-function>Cancel</button><button type="button" class="button button-primary" data-wf-associate-function>Associate</button></footer>
    </div></div>`;
  };
  const editor = () => {
    const back = `<button class="button button-small" data-wf-back type="button">← Workflow Rules</button>`;
    const heading = `<header class="wf-editor-heading">${back}<div><h2>${esc(draft.name || "Create New Rule")}</h2><p>@ ${esc(moduleOptions().find(([key])=>key===draft.module)?.[1] || draft.module)}</p><small>${esc(draft.description)}</small></div></header>`;
    let body = "";
    if (step === 0) body = `<div class="wf-details-card"><h3>${editingId ? "Edit Workflow Rule" : "Create New Rule"}</h3><div class="form-grid">
      <div class="field"><label>Module</label><select class="field-select" data-wf-module>${opts([["","Select Module"],...moduleOptions()],draft.module,esc)}</select></div>
      <div class="field"><label>Rule Name</label><input class="field-input" data-wf-name maxlength="160" required value="${esc(draft.name)}"/></div>
      <div class="field full"><label>Description</label><textarea class="field-input" data-wf-description rows="2">${esc(draft.description)}</textarea></div>
      </div></div>`;
    if (step === 1) body = `<section class="wf-stage"><div class="wf-stage-marker">WHEN</div><div class="wf-stage-content"><h3>Execute this workflow rule based on</h3>
      <select class="field-select" data-wf-event>${opts([["create","Create"],["create_or_edit","Create or Edit"],["edit","Edit"],["field_change","Specific field changes"]],draft.event,esc)}</select>${draft.event === "field_change" ? `<label>Field to monitor</label><select class="field-select" data-wf-trigger-field>${opts([["","Select a field"],...fieldsFor()],draft.trigger_field,esc)}</select>` : ""}
      <p>This workflow will run ${draft.event === "create" ? "when a record is created" : draft.event === "edit" ? "when a record is edited" : "when a record is created or edited"} and its conditions are met.</p></div></section>`;
    if (step === 2) body = `<section class="wf-stage"><div class="wf-stage-marker">CONDITION 1</div><div class="wf-stage-content"><h3>Which records should this rule apply to?</h3>
      <div class="wf-mode"><label><input type="radio" name="wf-criteria-mode" value="conditions" ${draft.criteria_mode === "conditions" ? "checked" : ""}/> Records matching certain conditions</label>
      <label><input type="radio" name="wf-criteria-mode" value="all" ${draft.criteria_mode === "all" ? "checked" : ""}/> All records</label></div>
      ${draft.criteria_mode === "conditions" ? `<div class="wf-conditions"><label>Match <select class="field-select" data-wf-logic>${opts([["AND","All (AND)"],["OR","Any (OR)"]],draft.logic,esc)}</select> conditions</label>${conditionRows()}<button class="button button-small" data-wf-add-condition>+ Add condition</button></div>` : ""}
      </div></section>`;
    if (step === 3) body = `<section class="wf-stage"><div class="wf-stage-marker">ACTION</div><div class="wf-stage-content"><h3>Immediate actions</h3><p>Choose actions executed when the rule matches. External delivery actions are queued for configured integrations.</p>
      ${actionRows()}<button type="button" class="button button-small" data-wf-open-function>Browse Functions</button><button class="button button-small" data-wf-add-action>+ Add action</button><div class="field"><label>Schedule execution (optional)</label><input type="datetime-local" class="field-input" data-wf-scheduled-for value="${esc((draft.scheduled_for || "").slice(0,16))}"/><small>Scheduled actions remain queued until a worker or authorized user runs them.</small></div></div></section>`;
    if (step === 0) return `<div class="wf-rule-overlay"><div class="wf-rule-dialog" role="dialog" aria-modal="true" aria-label="Create New Rule">${body}<footer class="wf-editor-footer"><button class="button" type="button" data-wf-back-step>Cancel</button><button class="button button-primary" type="button" data-wf-next>Next</button></footer></div></div>`;
    return `${functionEditor ? functionEditorDialog() : functionConfiguration ? configureFunctionDialog() : functionPicker ? functionDialog() : ""}<section class="wf-editor">${heading}<div class="wf-progress">${stepLabels.map((label,i)=>`<span class="${i===step?"active":""}">${i+1}. ${label}</span>`).join("")}</div>${body}
      <footer class="wf-editor-footer"><button class="button" data-wf-back-step type="button">${step===0?"Cancel":"Previous"}</button>
      <button class="button button-primary" data-wf-next type="button">${step===3?"Save Rule":"Next"}</button></footer></section>`;
  };
  const list = () => `<section class="card settings-section wf-list"><div class="settings-section-head"><h2>Workflow Rules</h2><p>Automate CRM records based on event triggers, conditions and actions.</p></div>
    <div class="wf-list-actions"><label class="wf-list-search"><span>Search rules</span><input class="field-input" data-wf-search placeholder="Search workflow rules" value="${esc(listQuery)}"/></label><label class="wf-list-filter"><span>Module</span><select class="field-select" data-wf-module-filter>${opts([["all","All modules"],...moduleOptions()],moduleFilter,esc)}</select></label><button class="button button-small" data-wf-delete-selected ${selectedRuleIds.size ? "" : "disabled"}>Delete selected (${selectedRuleIds.size})</button><button class="button button-primary" data-wf-create>Create Rule</button></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th><input type="checkbox" data-wf-select-all aria-label="Select all visible workflow rules"/></th><th>Rule Name</th><th>Module</th><th>Execute On</th><th>Actions</th><th>Modified On</th><th>Status</th></tr></thead><tbody>
    ${rules.filter(rule=>(moduleFilter === "all" || rule.module === moduleFilter) && (!listQuery || String(rule.name || rule.title || "").toLowerCase().includes(listQuery.toLowerCase()))).map(rule=>`<tr><td><input type="checkbox" data-wf-select="${rule.id}" ${selectedRuleIds.has(Number(rule.id)) ? "checked" : ""} aria-label="Select workflow rule"/></td><td><button class="wf-rule-link" data-wf-edit="${rule.id}">${esc(rule.name || rule.title)}</button></td><td>${esc(rule.module || "")}</td><td>${esc(rule.event === "create" ? "Create" : rule.event === "edit" || rule.event === "update" ? "Edit" : "Create or Edit")}</td><td>${Array.isArray(rule.actions) ? rule.actions.length : 1}</td><td>${esc(rule.updated_at || rule.created_at || "—")}</td><td><label class="wf-status"><input type="checkbox" data-wf-toggle="${rule.id}" ${rule.status === "Active" ? "checked" : ""} aria-label="Enable ${esc(rule.name || rule.title)}"/><span>${rule.status === "Active" ? "Active" : "Inactive"}</span></label><button class="button button-small" type="button" data-wf-delete="${rule.id}" aria-label="Delete ${esc(rule.name || rule.title)}">Delete</button></td></tr>`).join("") || '<tr><td colspan="7">No workflow rules have been created.</td></tr>'}
    </tbody></table></div></section>
    <section class="card settings-section"><h3>Execution history</h3>${activity.length ? activity.map(x=>`<div class="rule-row"><div class="rule-info"><strong>${esc(x.resource)} #${x.record_id}</strong><small>${esc(x.event)} · ${esc(x.status)} · Attempts: ${Number(x.attempts || 0)}${x.next_attempt_at ? " · Retry: "+esc(x.next_attempt_at) : ""}</small>${x.error ? `<small title="${esc(x.error)}">Error: ${esc(x.error)}</small>` : ""}</div>${x.status === "failed" ? `<button class="button button-small" data-wf-retry="${x.id}">Retry</button>` : ""}</div>`).join("") : "<p>No workflow executions yet.</p>"}</section>`;
  async function view() {
    if (draft) return editor();
    const [records, executions, functionRecords] = await Promise.all([
      api("/api/platform/workflow_rules?limit=100"),
      api("/api/automation/executions?limit=100"),
      api("/api/platform/functions?limit=100")
    ]);
    customFunctions = (functionRecords.items || []);
    rules = records.items || [];
    activity = executions.items || [];
    return list();
  }
  async function refresh(root) { root.innerHTML = await view(); bind(root); }
  function readCurrent(root) {
    if (!draft) return;
    const get = selector => el(root,selector)?.value;
    if (step === 0) {
      draft.module = get("[data-wf-module]") || draft.module;
      draft.name = (get("[data-wf-name]") || "").trim();
      draft.description = get("[data-wf-description]") || "";
    } else if(step === 1) { draft.event = get("[data-wf-event]") || draft.event; if (draft.event === "field_change") draft.trigger_field = get("[data-wf-trigger-field]") || draft.trigger_field; }
    else if(step === 2) {
      draft.criteria_mode = el(root,'input[name="wf-criteria-mode"]:checked')?.value || "all";
      draft.logic = get("[data-wf-logic]") || "AND";
      draft.conditions = els(root,"[data-condition-row]").map(row=>({
        field:el(row,"[data-wf-field]").value,
        operator:el(row,"[data-wf-operator]").value,
        value:el(row,"[data-wf-value]").value
      }));
    } else if (step === 3) { draft.scheduled_for = get("[data-wf-scheduled-for]") || ""; draft.actions = els(root,"[data-action-row]").map(row=>({
      type:el(row,"[data-wf-action-type]").value,
      field:el(row,"[data-wf-action-field]")?.value || "",
      to:el(row,"[data-wf-action-to]")?.value || "",
      subject:el(row,"[data-wf-action-subject]")?.value || "",
      value:el(row,"[data-wf-action-value]").value
    })); }
  }
  function validateStep() {
    if (step === 1 && draft.event === "field_change" && !draft.trigger_field) return "Select the field to monitor.";
    if (step === 0 && (!draft.name || !draft.module)) return "Select a module and enter a rule name.";
    if (step === 2 && draft.criteria_mode === "conditions" && draft.conditions.some(c=>!c.field || (!["is_empty","is_not_empty"].includes(c.operator) && !String(c.value ?? "").trim()))) return "Choose a field, operator and value for each condition.";
    if (step === 3 && draft.actions.some(a=>a.type === "field_update" && !a.field)) return "Select a target field for every field update.";
    if (step === 3 && draft.actions.some(a=>a.type === "function" && !a.value)) return "Select an active custom function."
    if (step === 3 && draft.actions.some(a=>a.type === "email" && (!a.to || !a.subject))) return "Email actions require an approved recipient and subject.";;
    return "";
  }
  function bind(root) {
    el(root,"[data-wf-open-function]")?.addEventListener("click",async()=>{readCurrent(root);functionPicker=true;await refresh(root);});
    el(root,"[data-wf-close-function]")?.addEventListener("click",async()=>{functionPicker=false;await refresh(root);});
    el(root,"[data-wf-function-search]")?.addEventListener("input",async event=>{functionSearch=event.target.value;await refresh(root);el(root,"[data-wf-function-search]")?.focus();});
    el(root,"[data-wf-configure-function]")?.addEventListener("click",async()=>{functionConfiguration=true;await refresh(root);});
    els(root,"[data-wf-edit-function]").forEach(button=>button.addEventListener("click",async()=>{
      const fn=customFunctions.find(item=>String(item.id)===button.dataset.wfEditFunction);
      if(!fn)return;
      if(Array.isArray(fn.source) || Array.isArray(fn.source?.steps)){toast("Declarative function","This function uses approved CRM actions and cannot be edited in the Python source editor.","error");return;}
      functionEditingId=fn.id;
      functionDraft={name:fn.name || "",entrypoint:fn.entrypoint || "main",code:fn.source?.code || ""};
      functionEditor=true;functionPicker=false;await refresh(root);
    }));
    el(root,"[data-wf-editor-close]")?.addEventListener("click",async()=>{functionEditor=false;functionPicker=true;await refresh(root);});
    el(root,"[data-wf-editor-save]")?.addEventListener("click",async()=>{
      const name=el(root,"[data-wf-new-function-name]")?.value.trim();
      const entrypoint=el(root,"[data-wf-new-function-entry]")?.value.trim();
      const source=el(root,"[data-wf-new-function-source]")?.value || "";
      if(!name || !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(entrypoint) || !source.trim() || new TextEncoder().encode(source).length>32768){
        toast("Invalid function","Provide a name, valid entrypoint and source of at most 32 KiB.","error");return;
      }
      try{
        await api("/api/platform/functions"+(functionEditingId?"/"+functionEditingId:""),{method:functionEditingId?"PATCH":"POST",body:JSON.stringify({
          name,runtime:"Python",entrypoint,source:{code:source,language:"Python"},
          input_schema:{type:"object"},associations:{modules:[draft.module]},
          status:"Inactive"
        })});
        functionEditor=false;functionPicker=true;functionEditingId=null;functionDraft=null;
        toast("Function draft saved","Activate only after isolated execution is available.");
        await refresh(root);
      }catch(error){toast("Function save failed",error.message,"error");}
    });
    el(root,"[data-wf-function-config-close]")?.addEventListener("click",async()=>{functionConfiguration=false;await refresh(root);});
    els(root,"[data-wf-function-method]").forEach(button=>button.addEventListener("click",async()=>{
      const method=button.dataset.wfFunctionMethod;
      functionConfiguration=false;
      if(method==="existing"){functionPicker=true;await refresh(root);return;}
      if(method==="gallery"){
        const templates=[
          {name:"Add Follow-up Task",steps:[{type:"create_task",subject:"Follow up with CRM record"}]},
          {name:"Add Reviewed Tag",steps:[{type:"tag",value:"Reviewed"}]},
          {name:"Audit Record",steps:[{type:"audit"}]}
        ];
        const choice=prompt("Function gallery: enter 1 for Follow-up Task, 2 for Reviewed Tag, or 3 for Audit Record.");
        if(choice===null){await refresh(root);return;}
        const selected=templates[Number(choice)-1];
        if(!selected){toast("Invalid selection","Choose 1, 2, or 3.","error");await refresh(root);return;}
        try{
          await api("/api/platform/functions",{method:"POST",body:JSON.stringify({
            name:selected.name,runtime:"Python",entrypoint:"steps",source:selected.steps,
            associations:{modules:[draft.module]},status:"Active"
          })});
          toast("Gallery function created",selected.name);
          functionPicker=true;
        }catch(error){toast("Gallery function failed",error.message,"error");}
        await refresh(root);return;
      }
      functionPicker=false;
      functionEditingId=null;functionDraft=null;functionEditor=true;
      await refresh(root);
    }));
    el(root,"[data-wf-associate-function]")?.addEventListener("click",async()=>{
      const selected=el(root,'input[name="wf-function-choice"]:checked')?.value;
      if(!selected){toast("Select a function","Choose an active function to associate.","error");return;}
      const action=draft.actions.find(a=>a.type==="function");
      if(action)action.value=selected;else draft.actions.push({type:"function",value:selected});
      functionPicker=false;await refresh(root);
    });
    els(root,"[data-wf-select]").forEach(input=>input.addEventListener("change",()=>{
      const id=Number(input.dataset.wfSelect);
      if(input.checked) selectedRuleIds.add(id); else selectedRuleIds.delete(id);
      const button=el(root,"[data-wf-delete-selected]");
      if(button){button.disabled=!selectedRuleIds.size;button.textContent="Delete selected ("+selectedRuleIds.size+")";}
    }));
    el(root,"[data-wf-select-all]")?.addEventListener("change",event=>{
      els(root,"[data-wf-select]").forEach(input=>{
        input.checked=event.target.checked;
        const id=Number(input.dataset.wfSelect);
        if(event.target.checked)selectedRuleIds.add(id);else selectedRuleIds.delete(id);
      });
      const button=el(root,"[data-wf-delete-selected]");
      if(button){button.disabled=!selectedRuleIds.size;button.textContent="Delete selected ("+selectedRuleIds.size+")";}
    });
    el(root,"[data-wf-delete-selected]")?.addEventListener("click",async()=>{
      if(!selectedRuleIds.size||!confirm("Move selected workflow rules to the 30-day Recycle Bin?"))return;
      try{
        const result=await api("/api/administration/bulk-delete",{method:"POST",body:JSON.stringify({resource:"workflow_rules",ids:[...selectedRuleIds]})});
        selectedRuleIds.clear();
        toast("Workflows deleted",result.deleted+" rules moved to Recycle Bin.");
        await refresh(root);
      }catch(error){toast("Bulk delete failed",error.message,"error");}
    });
    els(root,"[data-wf-delete]").forEach(button=>button.addEventListener("click",async()=>{
      if (!confirm("Delete this workflow rule? It will remain in Recycle Bin for 30 days.")) return;
      try {
        await api("/api/platform/workflow_rules/"+button.dataset.wfDelete,{method:"DELETE"});
        toast("Workflow deleted","Rule moved to the 30-day Recycle Bin.");
        await refresh(root);
      } catch(error){toast("Delete failed",error.message,"error");}
    }));
    els(root,"[data-wf-retry]").forEach(button=>button.addEventListener("click",async()=>{try{await api("/api/automation/executions/"+button.dataset.wfRetry+"/retry",{method:"POST"});toast("Workflow requeued","The worker will retry the execution.");await refresh(root);}catch(error){toast("Retry failed",error.message,"error");}}));
    el(root,"[data-wf-search]")?.addEventListener("input",event=>{
      listQuery=event.target.value;
      els(root,"[data-wf-edit]").forEach(button=>{
        const row=button.closest("tr");
        if(row) row.hidden=!(String(button.textContent || "").toLowerCase().includes(listQuery.toLowerCase()) &&
          (moduleFilter==="all" || rules.find(rule=>String(rule.id)===button.dataset.wfEdit)?.module===moduleFilter));
      });
    });
    el(root,"[data-wf-module-filter]")?.addEventListener("change",event=>{
      moduleFilter=event.target.value;
      els(root,"[data-wf-edit]").forEach(button=>{
        const row=button.closest("tr");
        const record=rules.find(rule=>String(rule.id)===button.dataset.wfEdit);
        if(row) row.hidden=!(record && (moduleFilter==="all" || record.module===moduleFilter) &&
          String(record.name || record.title || "").toLowerCase().includes(listQuery.toLowerCase()));
      });
    });
    els(root,"[data-wf-field-search]").forEach(input=>input.addEventListener("input",event=>{
      const select=el(root,'[data-wf-field="'+input.dataset.wfFieldSearch+'"]');
      const query=event.target.value.toLowerCase();
      [...(select?.options || [])].forEach(option=>{option.hidden=!!query && !option.textContent.toLowerCase().includes(query) && option.value!==select.value;});
    }));
    el(root,"[data-wf-create]")?.addEventListener("click",async()=>{draft=draftRule();editingId=null;step=0;await refresh(root);});
    els(root,"[data-wf-edit]").forEach(b=>b.addEventListener("click",async()=>{const found=rules.find(r=>String(r.id)===b.dataset.wfEdit);if(!found)return;draft=asDraft(found);editingId=found.id;step=0;await refresh(root);}));
    els(root,"[data-wf-toggle]").forEach(b=>b.addEventListener("change",async()=>{try{await api("/api/platform/workflow_rules/"+b.dataset.wfToggle,{method:"PATCH",body:JSON.stringify({status:b.checked?"Active":"Inactive"})});toast("Workflow updated","Rule status saved.");await refresh(root);}catch(error){toast("Workflow update failed",error.message,"error");b.checked=!b.checked;}}));
    el(root,"[data-wf-back]")?.addEventListener("click",async()=>{draft=null;editingId=null;step=0;await refresh(root);});
    el(root,"[data-wf-back-step]")?.addEventListener("click",async()=>{readCurrent(root);if(step===0){draft=null;editingId=null;}else step--;await refresh(root);});
    el(root,"[data-wf-next]")?.addEventListener("click",async()=>{
      readCurrent(root);const error=validateStep();if(error){toast("Complete the rule",error,"error");return;}
      if(step<3){step++;await refresh(root);return;}
      const payload={name:draft.name,description:draft.description,module:draft.module,
        event:draft.event,trigger_field:draft.event==="field_change"?draft.trigger_field:"",scheduled_for:draft.scheduled_for || null,status:draft.status,
        criteria:draft.criteria_mode==="all"?null:{logic:draft.logic,conditions:draft.conditions},
        actions:draft.actions};
      try{
        await api("/api/platform/workflow_rules"+(editingId?"/"+editingId:""),{method:editingId?"PATCH":"POST",body:JSON.stringify(payload)});
        draft=null;editingId=null;step=0;toast("Workflow saved","The rule is ready to evaluate CRM records.");await refresh(root);
      }catch(e){toast("Could not save workflow",e.message,"error");}
    });
    el(root,"[data-wf-event]")?.addEventListener("change",async event=>{draft.event=event.target.value;await refresh(root);});
    el(root,"[data-wf-module]")?.addEventListener("change",e=>{draft.module=e.target.value;});
    els(root,'input[name="wf-criteria-mode"]').forEach(b=>b.addEventListener("change",async()=>{readCurrent(root);await refresh(root);}));
    el(root,"[data-wf-add-condition]")?.addEventListener("click",async()=>{readCurrent(root);draft.conditions.push(newCondition());await refresh(root);});
    els(root,"[data-wf-remove-condition]").forEach(b=>b.addEventListener("click",async()=>{readCurrent(root);draft.conditions.splice(Number(b.dataset.wfRemoveCondition),1);await refresh(root);}));
    els(root,"[data-wf-operator]").forEach(b=>b.addEventListener("change",e=>{el(root,'[data-wf-value="'+e.target.dataset.wfOperator+'"]').disabled=["is_empty","is_not_empty"].includes(e.target.value);}));
    el(root,"[data-wf-add-action]")?.addEventListener("click",async()=>{readCurrent(root);draft.actions.push({type:"audit",value:""});await refresh(root);});
    els(root,"[data-wf-remove-action]").forEach(b=>b.addEventListener("click",async()=>{readCurrent(root);draft.actions.splice(Number(b.dataset.wfRemoveAction),1);await refresh(root);}));
    els(root,"[data-wf-action-type]").forEach(b=>b.addEventListener("change",async()=>{readCurrent(root);await refresh(root);}));
  }
  return {view,bind};
}

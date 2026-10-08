import { MODULES } from "./modules.js";
// Zoho-inspired workflow rule list and WHEN / CONDITION / ACTION wizard.
// Existing /api/platform/workflow_rules endpoints remain the source of truth.
const operators = [
  ["equals", "is"], ["not_equals", "isn't"], ["contains", "contains"],
  ["does_not_contain", "doesn't contain"], ["starts_with", "starts with"],
  ["ends_with", "ends with"], ["greater_than", "greater than"],
  ["less_than", "less than"], ["is_empty", "is empty"], ["is_not_empty", "is not empty"]
];
const actions = [
  ["audit", "Audit activity"], ["field_update", "Update field"],
  ["create_task", "Create task"], ["notification", "Notification"],
  ["tag", "Add tag"], ["webhook_queue", "Queue webhook"],
  ["email", "Queue email"], ["function", "Custom function"]
];
const opts = (items, selected, escape) => items.map(([value, label]) =>
  `<option value="${escape(value)}" ${String(selected) === String(value) ? "selected" : ""}>${escape(label)}</option>`).join("");
const newCondition = () => ({field:"",operator:"equals",value:""});
const draftRule = () => ({
  name:"", description:"", module:"", event:"create_or_edit",
  criteria_mode:"conditions", logic:"AND", conditions:[newCondition()],
  actions:[{type:"audit",value:""}], status:"Active"
});

export function createWorkflowRulesUI({api, esc, toast, navigate, renderRoute, state}) {
  let draft = null;
  let editingId = null;
  let step = 0;
  let rules = [];
  let activity = [];
  const el = (root, selector) => root.querySelector(selector);
  const els = (root, selector) => [...root.querySelectorAll(selector)];
  const moduleOptions = () => {
    const modules = new Map();
    for (const [key, config] of Object.entries(state.platformCatalog?.resources || {})) {
      if (config.group === "Automation" || config.group === "Administration") continue;
      modules.set(key, config.label || key);
    }
    for (const [key, config] of Object.entries(MODULES)) {
      if (!modules.has(key)) modules.set(key, config.label || key);
    }
    for (const key of ["quotes","invoices"]) {
      if (!modules.has(key)) modules.set(key, key[0].toUpperCase() + key.slice(1));
    }
    return [...modules].map(([key, label]) => [key, label]);
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
      criteria_mode:criteria ? "conditions" : "all",
      logic:criteria?.logic === "OR" ? "OR" : "AND",
      conditions:criteria?.conditions?.length ? criteria.conditions.map(c=>({...newCondition(),...c})) : criteria?.field ? [{...newCondition(),...criteria}] : [newCondition()],
      actions:Array.isArray(record.actions) && record.actions.length ? record.actions.map(a=>({...a})) : [{type:record.action_type || "audit",value:record.action_value || ""}],
      status:record.status || "Active"
    };
  };
  const stepLabels = ["Rule details","WHEN","CONDITION","ACTIONS"];
  const conditionRows = () => draft.conditions.map((item,index) => `<div class="wf-condition-row" data-condition-row="${index}">
    <span class="wf-condition-number">${index+1}</span>
    <select class="field-select" data-wf-field="${index}" aria-label="Condition field">${opts([["","Select field"],...fieldsFor()],item.field,esc)}</select>
    <select class="field-select" data-wf-operator="${index}" aria-label="Condition operator">${opts(operators,item.operator,esc)}</select>
    <input class="field-input" data-wf-value="${index}" aria-label="Condition value" placeholder="Value" value="${esc(item.value ?? "")}" ${["is_empty","is_not_empty"].includes(item.operator) ? "disabled" : ""}/>
    <button type="button" class="button button-small" data-wf-remove-condition="${index}" aria-label="Remove condition" ${draft.conditions.length === 1 ? "disabled" : ""}>−</button>
  </div>`).join("");
  const actionRows = () => draft.actions.map((item,index) => `<div class="wf-action-row" data-action-row="${index}">
    <select class="field-select" data-wf-action-type="${index}">${opts(actions,item.type,esc)}</select>
    ${item.type === "field_update" ? `<select class="field-select" data-wf-action-field="${index}">${opts([["","Select field"],...fieldsFor()],item.field || "",esc)}</select>` : ""}
    <input class="field-input" data-wf-action-value="${index}" placeholder="${item.type === "field_update" ? "New value" : item.type === "create_task" ? "Task subject" : "Action details (optional)"}" value="${esc(item.value ?? "")}"/>
    <button class="button button-small" type="button" data-wf-remove-action="${index}" ${draft.actions.length === 1 ? "disabled" : ""}>Remove</button>
  </div>`).join("");
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
      <select class="field-select" data-wf-event>${opts([["create","Create"],["create_or_edit","Create or Edit"],["edit","Edit"]],draft.event,esc)}</select>
      <p>This workflow will run ${draft.event === "create" ? "when a record is created" : draft.event === "edit" ? "when a record is edited" : "when a record is created or edited"} and its conditions are met.</p></div></section>`;
    if (step === 2) body = `<section class="wf-stage"><div class="wf-stage-marker">CONDITION 1</div><div class="wf-stage-content"><h3>Which records should this rule apply to?</h3>
      <div class="wf-mode"><label><input type="radio" name="wf-criteria-mode" value="conditions" ${draft.criteria_mode === "conditions" ? "checked" : ""}/> Records matching certain conditions</label>
      <label><input type="radio" name="wf-criteria-mode" value="all" ${draft.criteria_mode === "all" ? "checked" : ""}/> All records</label></div>
      ${draft.criteria_mode === "conditions" ? `<div class="wf-conditions"><label>Match <select class="field-select" data-wf-logic>${opts([["AND","All (AND)"],["OR","Any (OR)"]],draft.logic,esc)}</select> conditions</label>${conditionRows()}<button class="button button-small" data-wf-add-condition>+ Add condition</button></div>` : ""}
      </div></section>`;
    if (step === 3) body = `<section class="wf-stage"><div class="wf-stage-marker">ACTION</div><div class="wf-stage-content"><h3>Immediate actions</h3><p>Choose actions executed when the rule matches. External delivery actions are queued for configured integrations.</p>
      ${actionRows()}<button class="button button-small" data-wf-add-action>+ Add action</button></div></section>`;
    if (step === 0) return `<div class="wf-rule-overlay"><div class="wf-rule-dialog" role="dialog" aria-modal="true" aria-label="Create New Rule">${body}<footer class="wf-editor-footer"><button class="button" type="button" data-wf-back-step>Cancel</button><button class="button button-primary" type="button" data-wf-next>Next</button></footer></div></div>`;
    return `<section class="wf-editor">${heading}<div class="wf-progress">${stepLabels.map((label,i)=>`<span class="${i===step?"active":""}">${i+1}. ${label}</span>`).join("")}</div>${body}
      <footer class="wf-editor-footer"><button class="button" data-wf-back-step type="button">${step===0?"Cancel":"Previous"}</button>
      <button class="button button-primary" data-wf-next type="button">${step===3?"Save Rule":"Next"}</button></footer></section>`;
  };
  const list = () => `<section class="card settings-section wf-list"><div class="settings-section-head"><h2>Workflow Rules</h2><p>Automate CRM records based on event triggers, conditions and actions.</p></div>
    <div class="wf-list-actions"><button class="button button-primary" data-wf-create>Create Rule</button></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Rule Name</th><th>Module</th><th>Execute On</th><th>Actions</th><th>Modified On</th><th>Status</th></tr></thead><tbody>
    ${rules.map(rule=>`<tr><td><button class="wf-rule-link" data-wf-edit="${rule.id}">${esc(rule.name || rule.title)}</button></td><td>${esc(rule.module || "")}</td><td>${esc(rule.event === "create" ? "Create" : rule.event === "edit" || rule.event === "update" ? "Edit" : "Create or Edit")}</td><td>${Array.isArray(rule.actions) ? rule.actions.length : 1}</td><td>${esc(rule.updated_at || rule.created_at || "—")}</td><td><label class="wf-status"><input type="checkbox" data-wf-toggle="${rule.id}" ${rule.status === "Active" ? "checked" : ""} aria-label="Enable ${esc(rule.name || rule.title)}"/><span>${rule.status === "Active" ? "Active" : "Inactive"}</span></label></td></tr>`).join("") || '<tr><td colspan="6">No workflow rules have been created.</td></tr>'}
    </tbody></table></div></section>
    <section class="card settings-section"><h3>Execution history</h3>${activity.length ? activity.map(x=>`<div class="rule-row"><div class="rule-info"><strong>${esc(x.resource)} #${x.record_id}</strong><small>${esc(x.event)} · ${esc(x.status)}</small></div></div>`).join("") : "<p>No workflow executions yet.</p>"}</section>`;
  async function view() {
    if (draft) return editor();
    const [records, executions] = await Promise.all([
      api("/api/platform/workflow_rules?limit=100"),
      api("/api/automation/executions?limit=100")
    ]);
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
    } else if(step === 1) draft.event = get("[data-wf-event]") || draft.event;
    else if(step === 2) {
      draft.criteria_mode = el(root,'input[name="wf-criteria-mode"]:checked')?.value || "all";
      draft.logic = get("[data-wf-logic]") || "AND";
      draft.conditions = els(root,"[data-condition-row]").map(row=>({
        field:el(row,"[data-wf-field]").value,
        operator:el(row,"[data-wf-operator]").value,
        value:el(row,"[data-wf-value]").value
      }));
    } else if (step === 3) draft.actions = els(root,"[data-action-row]").map(row=>({
      type:el(row,"[data-wf-action-type]").value,
      field:el(row,"[data-wf-action-field]")?.value || "",
      value:el(row,"[data-wf-action-value]").value
    }));
  }
  function validateStep() {
    if (step === 0 && (!draft.name || !draft.module)) return "Select a module and enter a rule name.";
    if (step === 2 && draft.criteria_mode === "conditions" && draft.conditions.some(c=>!c.field || (!["is_empty","is_not_empty"].includes(c.operator) && !String(c.value ?? "").trim()))) return "Choose a field, operator and value for each condition.";
    if (step === 3 && draft.actions.some(a=>a.type === "field_update" && !a.field)) return "Select a target field for every field update.";
    return "";
  }
  function bind(root) {
    el(root,"[data-wf-create]")?.addEventListener("click",async()=>{draft=draftRule();editingId=null;step=0;await refresh(root);});
    els(root,"[data-wf-edit]").forEach(b=>b.addEventListener("click",async()=>{const found=rules.find(r=>String(r.id)===b.dataset.wfEdit);if(!found)return;draft=asDraft(found);editingId=found.id;step=0;await refresh(root);}));
    els(root,"[data-wf-toggle]").forEach(b=>b.addEventListener("change",async()=>{try{await api("/api/platform/workflow_rules/"+b.dataset.wfToggle,{method:"PATCH",body:JSON.stringify({status:b.checked?"Active":"Inactive"})});toast("Workflow updated","Rule status saved.");await refresh(root);}catch(error){toast("Workflow update failed",error.message,"error");b.checked=!b.checked;}}));
    el(root,"[data-wf-back]")?.addEventListener("click",async()=>{draft=null;editingId=null;step=0;await refresh(root);});
    el(root,"[data-wf-back-step]")?.addEventListener("click",async()=>{readCurrent(root);if(step===0){draft=null;editingId=null;}else step--;await refresh(root);});
    el(root,"[data-wf-next]")?.addEventListener("click",async()=>{
      readCurrent(root);const error=validateStep();if(error){toast("Complete the rule",error,"error");return;}
      if(step<3){step++;await refresh(root);return;}
      const payload={name:draft.name,description:draft.description,module:draft.module,
        event:draft.event,status:draft.status,
        criteria:draft.criteria_mode==="all"?null:{logic:draft.logic,conditions:draft.conditions},
        actions:draft.actions};
      try{
        await api("/api/platform/workflow_rules"+(editingId?"/"+editingId:""),{method:editingId?"PATCH":"POST",body:JSON.stringify(payload)});
        draft=null;editingId=null;step=0;toast("Workflow saved","The rule is ready to evaluate CRM records.");await refresh(root);
      }catch(e){toast("Could not save workflow",e.message,"error");}
    });
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

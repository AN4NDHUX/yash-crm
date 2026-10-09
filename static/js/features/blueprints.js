export function createBlueprintFeature({api,esc,toast,renderRoute}) {
  const $=(q,r=document)=>r.querySelector(q), $$=(q,r=document)=>[...r.querySelectorAll(q)];
  const operators=[["is","is"],["is_not","isn't"],["contains","contains"],["not_contains","doesn't contain"],["starts_with","starts with"],["ends_with","ends with"],["is_empty","is empty"],["is_not_empty","is not empty"],["greater_than","greater than"],["less_than","less than"]];
  const actions=[["audit","Audit message"],["create_task","Create task"],["tag","Add tag"],["notification","Notification"]];
  let list=[],tab="Blueprints",draft=null,opts=null,step="details",side="states",phase="before",picked=null,overlay=null,drag=null,connectingFrom=null,connectorDrag=null;
  const select=(name,values,value)=>`<select class="bp-control" name="${esc(name)}">${values.map(item=>{const k=Array.isArray(item)?item[0]:item,v=Array.isArray(item)?item[1]:item;return `<option value="${esc(k)}" ${k===value?"selected":""}>${esc(v)}</option>`}).join("")}</select>`;
  function stateFieldSelect(value) {
    const fields=opts?.fields||[];
    const enabled=fields.filter(f=>f.supported);
    const unavailable=fields.filter(f=>!f.supported);
    const option=(f,disabled=false)=>`<option value="${esc(f.name)}" ${f.name===value?"selected":""} ${disabled?"disabled":""} title="${esc(f.reason||"")}">${esc(f.label)}${disabled?" — not a state field":""}</option>`;
    return `<select class="bp-control" name="field_name" aria-label="Choose Blueprint state field">
      <optgroup label="Editable picklist fields">${enabled.map(f=>option(f)).join("")}</optgroup>
      <optgroup label="Other module fields (view only)">${unavailable.map(f=>option(f,true)).join("")}</optgroup>
    </select>`;
  }
  function paletteStates() {
    return opts?.state_values?.[draft.field_name] || opts?.criteria_meta?.[draft.field_name]?.options || opts?.initial_states || [];
  }
  async function view() {
    list=(await api("/api/blueprint-designer")).items||[];
    const rows=list.map(bp=>`<tr data-bp-row data-name="${esc(bp.name.toLowerCase())}" data-module="${esc(String(bp.module).toLowerCase())}" data-active="${bp.active&&!bp.draft}">
      <td><button class="bp-link" data-bp-open="${bp.id}">${esc(bp.name)}</button></td><td>${esc(bp.module)}</td><td>${esc(bp.layout_name||"Default")}</td><td>${esc(bp.field_name||"status")}</td>
      <td>${bp.updated_at?esc(new Date(bp.updated_at).toLocaleDateString()):"—"}</td>
      <td><span class="bp-status ${bp.active&&!bp.draft?"published":bp.draft?"draft":"inactive"}">${bp.active&&!bp.draft?"Published":bp.draft?"Draft":"Inactive"}</span></td>
      <td><button class="bp-toggle ${bp.active&&!bp.draft?"on":""}" aria-label="Toggle Blueprint" data-bp-toggle="${bp.id}"></button></td></tr>`).join("");
    return `<section class="bp-shell" data-bp-app><div class="bp-tabs">${["Blueprints","Filters","Usage"].map(t=>`<button data-bp-tab="${t}" class="${tab===t?"active":""}">${t}</button>`).join("")}</div><div class="bp-board">
      <h2>Blueprint</h2><p>Design and publish stage transitions that match your team's organizational process.</p>
      <div class="bp-toolbar"><label class="bp-search">⌕ <input data-bp-search placeholder="Search Blueprints" aria-label="Search Blueprints"></label>
      <button class="button button-primary" data-bp-open="new">＋ Create Blueprint</button></div>
      ${tab==="Filters"?`<div class="bp-filters"><label>Module ${select("bp-module-filter",[["all","All modules"],["leads","Leads"],["deals","Deals"]],"all")}</label><label>Status ${select("bp-status-filter",[["all","All statuses"],["true","Published"],["false","Draft / Inactive"]],"all")}</label></div>`:""}
      ${tab==="Usage"?`<p class="bp-usage">${list.length} configured · ${list.filter(x=>x.active&&!x.draft).length} published. Transition counts can be viewed through the Blueprint history API.</p>`:""}
      <div class="bp-table-wrap"><table class="bp-table"><thead><tr><th>Blueprint</th><th>Module</th><th>Layout</th><th>Field</th><th>Last modified</th><th>Status</th><th>Active</th></tr></thead><tbody>${rows||'<tr><td colspan="7">No blueprints yet. Create a Blueprint to begin.</td></tr>'}</tbody></table></div></div></section>`;
  }
  function bind() {
    const root=$("[data-bp-app]"); if(!root)return;
    $$("[data-bp-tab]",root).forEach(b=>b.onclick=()=>{tab=b.dataset.bpTab;renderRoute()});
    $$("[data-bp-open]",root).forEach(b=>b.onclick=()=>open(b.dataset.bpOpen==="new"?null:Number(b.dataset.bpOpen)));
    const filt=()=>{const text=($("[data-bp-search]",root)?.value||"").toLowerCase(),m=$('[name="bp-module-filter"]',root)?.value||"all",s=$('[name="bp-status-filter"]',root)?.value||"all";$$("[data-bp-row]",root).forEach(row=>row.hidden=!(row.dataset.name.includes(text)&&(m==="all"||m===row.dataset.module)&&(s==="all"||s===row.dataset.active)))};
    $("[data-bp-search]",root)?.addEventListener("input",filt);$$(".bp-filters select",root).forEach(x=>x.addEventListener("change",filt));
    $$("[data-bp-toggle]",root).forEach(b=>b.onclick=async()=>{b.disabled=true;try{const bp=list.find(r=>r.id===Number(b.dataset.bpToggle));await api(`/api/blueprint-designer/${bp.id}/${bp.active&&!bp.draft?"deactivate":"publish"}`,{method:"POST"});toast("Blueprint updated","The published process has been updated.");await renderRoute()}catch(e){toast("Blueprint update failed",e.message,"error");b.disabled=false;}});
  }
  async function open(id=null) {
    try {
      draft=id?await api(`/api/blueprint-designer/${id}`):{name:"",module:"Leads",layout_name:"Default",field_name:"status",description:"",entry_conditions:[],stages:[],transitions:[],continuous:false};
      draft.module=String(draft.module||"Leads").toLowerCase()==="deals"?"deals":"leads";
      opts=await api(`/api/blueprint-designer/options?module=${draft.module}`);
      draft.entry_conditions=draft.entry_conditions||[];
      draft.stages=(draft.stages||[]).map((s,i)=>({...s,label:s.label||s.name||`State ${i+1}`,x:Number(s.x??130+i%3*210),y:Number(s.y??130+Math.floor(i/3)*140)}));
      draft.transitions=(draft.transitions||[]).map((t,i)=>({...t,id:String(t.id??i),after:t.after||[],required:t.required||[]}));
      step="details";side="states";phase="before";picked=null;connectingFrom=null;connectorDrag=null;
      overlay=document.createElement("div");overlay.className="bp-overlay";document.body.appendChild(overlay);
      overlay.addEventListener("click",click);overlay.addEventListener("change",change);overlay.addEventListener("submit",submit);
      overlay.addEventListener("keydown",e=>{if(e.key==="Escape"&&connectingFrom!==null){connectingFrom=null;render();return;}if((e.key==="Enter"||e.key===" ")&&e.target.matches(".bp-node[data-bp-state]")){e.preventDefault();click({target:e.target});}});
      overlay.addEventListener("pointerdown",pointerDown);overlay.addEventListener("pointermove",pointerMove);overlay.addEventListener("pointerup",pointerUp);
      overlay.addEventListener("dragstart",e=>{const node=e.target.closest("[data-bp-palette]");if(node)e.dataTransfer.setData("text/plain",node.dataset.bpPalette)});
      overlay.addEventListener("dragover",e=>{if(e.target.closest("[data-bp-canvas]"))e.preventDefault()});
      overlay.addEventListener("drop",e=>{const c=e.target.closest("[data-bp-canvas]");if(!c)return;e.preventDefault();const label=e.dataTransfer.getData("text/plain"),rect=c.getBoundingClientRect();if(label)addState(label,e.clientX-rect.left,e.clientY-rect.top)});
      render();
    } catch(e){toast("Cannot open Blueprint designer",e.message,"error")}
  }
  const close=()=>{overlay?.remove();overlay=null};
  function render(){if(overlay)overlay.innerHTML=step==="details"?basic():studio()}
  function criteriaValue(condition) {
    const field = condition.field;
    const meta = opts?.criteria_meta?.[field] || {options:[],type:"text",allow_custom:true};
    const missingValue = ["is_empty","is_not_empty"].includes(condition.operator);
    const options = (meta.options || []).map(value=>String(value));
    const saved = String(condition.value ?? "");
    const isCustom = !!saved && !options.includes(saved) && meta.allow_custom;
    const selected = isCustom ? "__custom__" : saved;
    const prompt = missingValue ? "Not required" : "Select value";
    const choices = [["",prompt],...options.map(value=>[value,value])];
    if (saved && !options.includes(saved) && !meta.allow_custom) choices.push([saved,saved]);
    if (meta.allow_custom) choices.push(["__custom__","＋ Enter custom value"]);
    return `<div class="bp-value-control">
      ${select("value_choice",choices,selected).replace('name="value_choice"','name="value_choice" aria-label="Value for '+esc(field)+'"')}
      ${meta.allow_custom ? `<input class="bp-control bp-custom-value" type="${meta.type==="number"?"number":"text"}" step="any" name="value_custom" value="${esc(isCustom?saved:"")}" placeholder="${meta.type==="number"?"Enter number":"Enter custom value"}" ${isCustom&&!missingValue?"":"hidden"}>` : ""}
    </div>`;
  }
  function criteria() {return draft.entry_conditions.map((c,i)=>`<div class="bp-condition" data-bp-condition="${i}"><span>${i+1}</span>
    ${select("field",opts.criteria_fields.map(field=>[field,opts?.criteria_meta?.[field]?.label||field]),c.field)}
    ${select("operator",operators,c.operator)}
    ${criteriaValue(c)}
    <button data-bp="remove-condition" data-index="${i}" type="button" aria-label="Remove">×</button></div>`).join("")}
  function basic(){
    return `<div class="bp-shade"></div><section class="bp-wizard" role="dialog" aria-modal="true" aria-label="Create new Blueprint"><header><h2>${draft.id?"Edit":"Create new"} Blueprint</h2><button data-bp="close" class="bp-close" aria-label="Close">×</button></header>
      <form data-bp-details><div class="bp-wizard-content"><label class="bp-row"><span>Blueprint name *</span><input class="bp-control" name="name" maxlength="160" required value="${esc(draft.name||"")}" placeholder="Process name"></label>
      <label class="bp-row"><span>Module</span>${select("module",[["leads","Leads"],["deals","Deals"]],draft.module)}</label>
      <label class="bp-row"><span>Choose layout</span>${select("layout_name",opts.layouts,draft.layout_name||"Default")}</label>
      <label class="bp-row"><span>Choose field</span><div class="bp-controller-select">${stateFieldSelect(draft.field_name||opts.fields.find(f=>f.supported)?.name)}<small>All fields are listed. Only picklists can control process states.</small></div></label>
      <div class="bp-criteria"><h3>Define criteria for records associated with this Blueprint</h3><p>Leave blank to include every record in this module and layout.</p>${criteria()}<button data-bp="add-condition" class="bp-text-button" type="button">＋ Add condition</button></div>
      <label class="bp-row"><span>Description</span><textarea class="bp-control" name="description" rows="3">${esc(draft.description||"")}</textarea></label>
      <label class="bp-checkbox"><input type="checkbox" name="continuous" ${draft.continuous?"checked":""}> Continuous process</label></div><footer><button type="button" class="button button-ghost" data-bp="close">Cancel</button><button type="submit" class="button button-primary">Next →</button></footer></form></section>`;
  }
  function capture(){
    const form=$("[data-bp-details]",overlay);if(!form)return false;
    if(!form.reportValidity())return false;
    draft.name=form.elements.name.value.trim();draft.module=form.elements.module.value;
    draft.layout_name=form.elements.layout_name.value;draft.field_name=form.elements.field_name.value;
    draft.description=form.elements.description.value;draft.continuous=form.elements.continuous.checked;
    draft.entry_conditions=$$("[data-bp-condition]",form).map(row=>{
      const field=$('[name="field"]',row).value,operator=$('[name="operator"]',row).value;
      const choice=$('[name="value_choice"]',row).value;
      const value=["is_empty","is_not_empty"].includes(operator) ? "" :
        choice==="__custom__" ? ($('[name="value_custom"]',row)?.value||"") : choice;
      return {field,operator,value};
    });
    return true;
  }
  function graph(){
    const nodes=Object.fromEntries(draft.stages.map((state,index)=>[state.label,{...state,index}]));
    const routes=draft.transitions.map((edge,index)=>{
      const a=nodes[edge.from],b=nodes[edge.to];if(!a||!b)return null;
      const w=145,h=42,ac={x:a.x+w/2,y:a.y+h/2},bc={x:b.x+w/2,y:b.y+h/2};
      const dx=bc.x-ac.x,dy=bc.y-ac.y;
      // Use the closest facing sides so links never cross through a state card.
      let x1,y1,x2,y2,c1x,c1y,c2x,c2y;
      if(Math.abs(dx)>=Math.abs(dy)*0.85){
        const dir=dx>=0?1:-1;
        x1=ac.x+dir*w/2;y1=ac.y;x2=bc.x-dir*w/2;y2=bc.y;
        const distance=Math.max(40,Math.abs(x2-x1)*0.5);
        c1x=x1+dir*distance;c1y=y1;c2x=x2-dir*distance;c2y=y2;
      }else{
        const dir=dy>=0?1:-1;
        x1=ac.x;y1=ac.y+dir*h/2;x2=bc.x;y2=bc.y-dir*h/2;
        const distance=Math.max(35,Math.abs(y2-y1)*0.5);
        c1x=x1;c1y=y1+dir*distance;c2x=x2;c2y=y2-dir*distance;
      }
      const d=`M${x1} ${y1} C${c1x} ${c1y},${c2x} ${c2y},${x2} ${y2}`;
      // Midpoint of the Bezier keeps labels aligned with their actual routes.
      const midX=(x1+3*c1x+3*c2x+x2)/8;
      const midY=(y1+3*c1y+3*c2y+y2)/8;
      return {d,midX,midY,edge,index};
    }).filter(Boolean);
    return routes;
  }
  function graphSvg(routes) {
    const first=draft.stages[0];
    const x=first?.x+72.5,y=first?.y;
    const entry=first?`<path class="bp-entry-path" d="M170 72 Q${Math.min(250,x)} 72,${x} ${Math.max(0,y-8)}" stroke-dasharray="5 6"/>`:"";
    return `<svg class="bp-lines" width="1000" height="670" viewBox="0 0 1000 670" aria-hidden="true">
      <defs><marker id="bp-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" fill="#6684b9"/></marker></defs>
      ${entry}
      ${routes.map(route=>`<path class="bp-edge-path ${picked?.type==="edge"&&picked.index===route.index?"selected":""}" d="${route.d}" marker-end="url(#bp-arrow)" />`).join("")}
      <path class="bp-link-preview" d="" stroke="#2368dd" stroke-width="2" stroke-dasharray="6 5" fill="none" />
    </svg>`;
  }
  function graphLabels(routes){
    return routes.map(route=>`<button type="button" class="bp-edge-label ${picked?.type==="edge"&&picked.index===route.index?"selected":""}"
      style="left:${Math.max(75,Math.min(920,route.midX))}px;top:${Math.max(65,Math.min(610,route.midY-12-(route.index%2)*6))}px"
      data-bp-edge="${route.index}" aria-label="Edit transition ${esc(route.edge.label || route.edge.to)}"
      title="${esc(route.edge.from)} → ${esc(route.edge.to)}">${esc(route.edge.label||route.edge.to)}</button>`).join("");
  }

    function studio(){
    const routes=graph();
    const chips=draft.stages.map((s,i)=>`<div class="bp-node ${picked?.type==="state"&&picked.index===i?"selected":""} ${connectingFrom===i?"link-source":""}" role="button" tabindex="0" aria-label="State ${esc(s.label)}" style="left:${s.x}px;top:${s.y}px" data-bp-state="${i}"><span>${esc(s.label)}</span><button class="bp-connect-handle" type="button" data-bp-connect="${i}" aria-label="Connect from ${esc(s.label)}" title="Connect ${esc(s.label)} to another state">＋</button></div>`).join("");
    const palette=paletteStates().filter(s=>!draft.stages.some(x=>x.label===s)).map(s=>`<button type="button" draggable="true" class="bp-state-chip" data-bp-palette="${esc(s)}" data-bp-add-state="${esc(s)}">⠿ ${esc(s)}</button>`).join("");
    return `<section class="bp-studio" role="dialog" aria-modal="true" aria-label="Blueprint visual designer"><header><button data-bp="back" class="bp-text-button">← Details</button><h2>${esc(draft.name)}</h2><span class="bp-status draft">Designer</span><button data-bp="close" class="bp-close">×</button></header>
      <div class="bp-studio-grid"><main class="bp-canvas-scroll"><div class="bp-canvas" data-bp-canvas>${graphSvg(routes)}${graphLabels(routes)}<div class="bp-start"><span>START</span></div><div class="bp-canvas-hint">${connectingFrom===null ? "Connect states: click the + on a state, then click the destination state. Drag nodes to arrange the flow." : connectingFrom===-1 ? `Select a source state to start connecting. ` + `<button type="button" data-bp="cancel-link">Cancel</button>` : `Connecting from ${esc(draft.stages[connectingFrom]?.label||"")} — select a destination state or ` + `<button type="button" data-bp="cancel-link">Cancel</button>`}</div>${chips}${!draft.stages.length?'<p class="bp-empty-canvas">Drag states here or add them from the right panel.</p>':""}</div></main>
      <aside class="bp-inspector"><div class="bp-inspector-tabs"><button data-bp-side="states" class="${side==="states"?"active":""}">Info and States</button><button data-bp-side="transitions" class="${side==="transitions"?"active":""}">Transitions</button></div><div class="bp-inspector-content">${side==="states"?`
        <h3>${esc(draft.name)}</h3><p>Module: ${esc(draft.module)} · Layout: ${esc(draft.layout_name)} · Field: ${esc(draft.field_name)}</p>
        <label class="bp-checkbox"><input type="checkbox" data-bp-continuous ${draft.continuous?"checked":""}> Continuous</label>
        <h4>Available States</h4><div class="bp-chip-list">${palette}</div><div class="bp-add-row"><input class="bp-control" data-bp-new-state maxlength="80" placeholder="Custom state name"><button data-bp="add-custom" class="button button-ghost">＋ Add</button></div>
        <h4>Process States (${draft.stages.length})</h4>${draft.stages.map((s,i)=>`<button class="bp-state-chip" data-bp-state="${i}">${esc(s.label)}</button>`).join("")}
        ${picked?.type==="state"?`<div class="bp-editor"><label>State name<input class="bp-control" data-bp-rename value="${esc(draft.stages[picked.index]?.label||"")}"></label><button class="bp-danger" data-bp="delete-state">Delete state</button></div>`:""}
      `:`
        <h3>Transitions</h3><p>Connect states, configure permissions and required fields, and add supported actions.</p>
        <button data-bp="add-edge" class="button button-primary" ${draft.stages.length<2?"disabled":""}>＋ Connect two states</button>
        <div class="bp-edge-list">${draft.transitions.map((e,i)=>`<button data-bp-edge="${i}" class="${picked?.type==="edge"&&picked.index===i?"active":""}"><strong>${esc(e.label)}</strong><small>${esc(e.from)} → ${esc(e.to)}</small></button>`).join("")}</div>
        ${picked?.type==="edge"?edgeEditor():"<p>Select a transition to configure its Before, During and After phases.</p>"}
      `}</div></aside></div><footer class="bp-studio-footer"><button class="button button-ghost" data-bp="close">Cancel</button><div><button class="button button-ghost" data-bp="save">Save as Draft</button><button class="button button-primary" data-bp="publish">Publish Blueprint</button></div></footer></section>`;
  }
  function edgeEditor(){
    const e=draft.transitions[picked.index],stages=draft.stages.map(x=>x.label);
    if(!e)return "";
    return `<div class="bp-editor"><h4>Edit transition</h4><label>Label<input class="bp-control" data-bp-edge-label value="${esc(e.label)}"></label>
    <label>From ${select("from",stages,e.from)}</label><label>To ${select("to",stages,e.to)}</label>
    <div class="bp-phase-tabs">${["before","during","after"].map(p=>`<button data-bp-phase="${p}" class="${phase===p?"active":""}">${p.toUpperCase()}</button>`).join("")}</div>
    ${phase==="before"?`<label>Eligible owners ${select("owner_scope",[["any","Users with edit permission"],["owner","Record owner only"]],e.owner_scope||"any")}</label><label class="bp-checkbox"><input type="checkbox" name="common" ${e.common?"checked":""}> Common transition</label>`:
    phase==="during"?`<label>Instruction<textarea class="bp-control" data-bp-message rows="3">${esc(e.message||"")}</textarea></label><h4>Required fields</h4>${opts.criteria_fields.filter(f=>f!==draft.field_name).map(f=>`<label class="bp-checkbox"><input type="checkbox" data-bp-required="${esc(f)}" ${(e.required||[]).includes(f)?"checked":""}> ${esc(f)}</label>`).join("")}`:
    `<h4>After actions</h4>${(e.after||[]).map((act,i)=>`<div class="bp-after-row"><span>${esc(act.type)}</span><input class="bp-control" data-bp-action-value="${i}" value="${esc(act.value||"")}"><button data-bp-delete-action="${i}">×</button></div>`).join("")}
    <div class="bp-add-row">${select("action_type",actions,"create_task")}<input class="bp-control" data-bp-action-new placeholder="Task / tag / message"><button data-bp="add-action" class="button button-ghost">Add</button></div><small>Actions run through CRM permissions. External integrations are configured separately.</small>`}
    <button data-bp="delete-edge" class="bp-danger">Delete transition</button></div>`;
  }
  function connectStates(fromIndex,toIndex){
  if(fromIndex===toIndex) {toast("Choose a different state","A transition must connect two distinct states.","error");return;}
  const from=draft.stages[fromIndex]?.label,to=draft.stages[toIndex]?.label;
  if(!from||!to)return;
  if(draft.transitions.some(e=>e.from===from&&e.to===to)) {
    toast("Already connected",`${from} → ${to} already has a transition.`,"error");connectingFrom=null;render();return;
  }
  const index=draft.transitions.length;
  const maxId=Math.max(0,...draft.transitions.map(t=>Number(String(t.id||"").replace(/^t-/,""))||0));
  draft.transitions.push({id:`t-${maxId+1}`,label:`Move to ${to}`,from,to,owner_scope:"any",required:[],message:"",after:[]});
  connectingFrom=null;connectorDrag=null;picked={type:"edge",index};side="transitions";phase="before";render();
}
  function addState(label,x,y){
    label=String(label||"").trim();if(!label||draft.stages.some(s=>s.label===label))return toast("Duplicate state","Use a unique state name.","error");
    const i=draft.stages.length;
    draft.stages.push({id:"s-"+(i+1),label,x:Math.max(8,Math.min(830,Math.round(x??110+(i%3)*210))),y:Math.max(10,Math.min(590,Math.round(y??120+Math.floor(i/3)*135)))});
    picked={type:"state",index:i};side="states";render();
  }
  async function save(publish){
    const btn=$(`[data-bp="${publish?"publish":"save"}"]`,overlay);if(btn)btn.disabled=true;
    try {
      const body=JSON.stringify(draft);
      const record=await api(draft.id?`/api/blueprint-designer/${draft.id}`:"/api/blueprint-designer",{method:draft.id?"PUT":"POST",body});
      draft.id=record.id;
      if(publish)await api(`/api/blueprint-designer/${draft.id}/publish`,{method:"POST"});
      toast(publish?"Blueprint published":"Draft saved",publish?"Matching records now show the configured transitions.":"This draft does not affect live records.");
      close();await renderRoute();
    }catch(e){if(btn)btn.disabled=false;toast("Could not save Blueprint",e.message,"error")}
  }
  function submit(event){if(!event.target.matches("[data-bp-details]"))return;event.preventDefault();if(capture()){step="designer";render()}}
  async function change(event){
    const node=event.target;
    if(step==="details" && node.closest("[data-bp-condition]")) {
      const row=node.closest("[data-bp-condition]");
      const index=Number(row.dataset.bpCondition);
      if(node.name==="value_choice"){
        const custom=node.value==="__custom__";
        const input=$('[name="value_custom"]',row);
        if(input){input.hidden=!custom;input.required=custom;if(custom)input.focus();}
        return;
      }
      if(node.name==="field" || node.name==="operator"){
        const previous=draft.entry_conditions.map(c=>({...c}));
        // Capture without blocking change on an incomplete criteria row.
        draft.entry_conditions=$$("[data-bp-condition]",overlay).map((r,i)=>{
          const field=$('[name="field"]',r).value, operator=$('[name="operator"]',r).value;
          const choice=$('[name="value_choice"]',r).value;
          const value=choice==="__custom__"?$('[name="value_custom"]',r)?.value||"":choice;
          return {field,operator,value:previous[i]?.field!==field||["is_empty","is_not_empty"].includes(operator)?"":value};
        });
        render();
        return;
      }
    }
    if(step==="details"&&node.name==="field_name"){
      const next=node.value;
      if(next===draft.field_name)return;
      if(draft.stages.length&&!window.confirm("Changing the controlling field clears the existing states and connections. Continue?")){
        node.value=draft.field_name;return;
      }
      draft.field_name=next;
      draft.stages=[];draft.transitions=[];picked=null;connectingFrom=null;
      return;
    }
    if(step==="details"&&node.name==="module"){
      const next=node.value;if(draft.module===next)return;
      if(draft.stages.length&&!window.confirm("Changing module clears the existing process. Continue?"))return render();
      draft.module=next;draft.field_name=next==="deals"?"stage":"status";draft.layout_name="Default";draft.stages=[];draft.transitions=[];draft.entry_conditions=[];
      opts=await api(`/api/blueprint-designer/options?module=${next}`);render();return;
    }
    if(step!=="designer")return;
    if(node.matches("[data-bp-continuous]"))draft.continuous=node.checked;
    if(node.matches("[data-bp-rename]")&&picked?.type==="state"){
      const old=draft.stages[picked.index].label,v=node.value.trim();
      if(v&&!draft.stages.some((s,i)=>i!==picked.index&&s.label===v)){draft.stages[picked.index].label=v;draft.transitions.forEach(t=>{if(t.from===old)t.from=v;if(t.to===old)t.to=v});render()}
    }
    if(picked?.type!=="edge")return;
    const e=draft.transitions[picked.index];
    if(["from","to","owner_scope"].includes(node.name)){e[node.name]=node.value;if(node.name!=="owner_scope")render();}
    if(node.name==="common")e.common=node.checked;
    if(node.matches("[data-bp-edge-label]"))e.label=node.value.trim();
    if(node.matches("[data-bp-message]"))e.message=node.value;
    if(node.matches("[data-bp-required]"))e.required=$$("[data-bp-required]:checked",overlay).map(n=>n.dataset.bpRequired);
    if(node.matches("[data-bp-action-value]"))e.after[Number(node.dataset.bpActionValue)].value=node.value;
  }
  function click(event){
    const t=event.target.closest("[data-bp],[data-bp-add-state],[data-bp-state],[data-bp-edge],[data-bp-side],[data-bp-phase],[data-bp-delete-action],[data-bp-connect]");if(!t)return;
    const action=t.dataset.bp;
    if(t.dataset.bpConnect!==undefined){const n=Number(t.dataset.bpConnect);if(connectingFrom===null||connectingFrom===-1){connectingFrom=n;render();}else{connectStates(connectingFrom,n);}return;}
    if(action==="cancel-link"){connectingFrom=null;render();return;}
    if(action==="close")return close();
    if(action==="back"){step="details";render();return}
    if(action==="save")return save(false);
    if(action==="publish")return save(true);
    if(action==="add-condition"){if(!capture())return;draft.entry_conditions.push({field:opts.criteria_fields[0],operator:"is",value:""});render();return}
    if(action==="remove-condition"){if(!capture())return;draft.entry_conditions.splice(Number(t.dataset.index),1);render();return}
    if(t.dataset.bpAddState)return addState(t.dataset.bpAddState);
    if(action==="add-custom")return addState($("[data-bp-new-state]",overlay)?.value);
    if(t.dataset.bpState!==undefined){const n=Number(t.dataset.bpState);if(connectingFrom===-1){connectingFrom=n;render();return;}if(connectingFrom!==null){connectStates(connectingFrom,n);return;}picked={type:"state",index:n};side="states";render();return}
    if(t.dataset.bpEdge!==undefined){picked={type:"edge",index:Number(t.dataset.bpEdge)};side="transitions";render();return}
    if(t.dataset.bpSide){side=t.dataset.bpSide;render();return}
    if(t.dataset.bpPhase){phase=t.dataset.bpPhase;render();return}
    if(action==="delete-state"&&picked?.type==="state"){const name=draft.stages[picked.index].label;draft.stages.splice(picked.index,1);draft.transitions=draft.transitions.filter(e=>e.from!==name&&e.to!==name);picked=null;render();return}
    if(action==="add-edge"&&draft.stages.length>1){connectingFrom=-1;render();return;}
    if(action==="delete-edge"&&picked?.type==="edge"){draft.transitions.splice(picked.index,1);picked=null;render();return}
    if(action==="add-action"&&picked?.type==="edge"){
      const value=$("[data-bp-action-new]",overlay)?.value.trim(),type=$('[name="action_type"]',overlay)?.value;
      if(!value)return toast("Value required","Provide an action message.","error");
      draft.transitions[picked.index].after.push({type,value});render();return;
    }
    if(t.dataset.bpDeleteAction!==undefined&&picked?.type==="edge"){draft.transitions[picked.index].after.splice(Number(t.dataset.bpDeleteAction),1);render()}
  }
  function pointerDown(e){
  if(e.button!==0)return;
  const handle=e.target.closest("[data-bp-connect]");
  if(handle){
    const from=Number(handle.dataset.bpConnect),stage=draft.stages[from];
    connectorDrag={from,startX:e.clientX,startY:e.clientY,x:stage.x+145,y:stage.y+21,moved:false};
    return;
  }
  if(connectingFrom!==null)return;
  const node=e.target.closest(".bp-node[data-bp-state]");if(!node)return;
  const i=Number(node.dataset.bpState),s=draft.stages[i];
  drag={i,node,startX:e.clientX,startY:e.clientY,x:s.x,y:s.y,moved:false};
}
  function pointerMove(e){
  if(connectorDrag){
    const link=connectorDrag;
    if(Math.hypot(e.clientX-link.startX,e.clientY-link.startY)>7)link.moved=true;
    const canvas=$("[data-bp-canvas]",overlay),preview=$(".bp-link-preview",canvas);
    if(canvas&&preview&&link.moved){
      const rect=canvas.getBoundingClientRect();
      const x2=Math.min(999,Math.max(0,e.clientX-rect.left)),y2=Math.min(669,Math.max(0,e.clientY-rect.top));
      preview.setAttribute("d",`M ${link.x} ${link.y} L ${x2} ${y2}`);
    }
    return;
  }
  if(!drag)return;
  const dx=e.clientX-drag.startX,dy=e.clientY-drag.startY;
  if(Math.hypot(dx,dy)>4)drag.moved=true;
  if(!drag.moved)return;
  const s=draft.stages[drag.i];s.x=Math.max(8,Math.min(830,Math.round(drag.x+dx)));
  s.y=Math.max(10,Math.min(590,Math.round(drag.y+dy)));
  drag.node.style.left=s.x+"px";drag.node.style.top=s.y+"px";
}
  function pointerUp(e){
  if(connectorDrag){
    const link=connectorDrag;connectorDrag=null;
    if(link.moved){
      // Hit-test the drop location rather than the captured pointer target.
      const node=document.elementFromPoint(e.clientX,e.clientY)?.closest(".bp-node[data-bp-state]") || e.target.closest(".bp-node[data-bp-state]");
      if(node && Number(node.dataset.bpState)!==link.from){connectStates(link.from,Number(node.dataset.bpState));return;}
      connectingFrom=link.from;render();return;
    }
    return; // Click handler starts the connection.
  }
  if(drag){const moved=drag.moved;drag=null;if(moved)render();}
}

    return {view,bind};
}

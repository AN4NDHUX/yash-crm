// Five-step Zoho-style guided import for Leads, Deals, Accounts and Contacts.
const SUPPORTED = ["csv", "xlsx", "xls", "vcf"];
const STEPS = ["Upload", "Actions", "Module - File Mapping", "Field Mapping", "Assign"];
const CHARSETS = ["auto", "utf-8", "utf-16", "iso-8859-1", "iso-8859-2", "iso-8859-8", "iso-8859-9", "iso-8859-11", "gb2312", "gbk", "big5", "shift_jis"];
const ALIASES = {
  "phone number": "phone", "mobile number": "phone", "mobile": "phone", "telephone": "phone",
  "contact number": "phone", "lead name": "name", "full name": "name", "account name": "name",
  "deal name": "name", "lead status": "status", "lead source": "source",
  "assigned to": "owner_id", "remarks": "notes", "next follow up date": "next_follow_up", "next follow-up date": "next_follow_up",
};

export function createImportWizardFeature({ toast, navigate, esc, MODULES }) {
  let current = null;
  const $ = (selector, node = document) => node.querySelector(selector);
  const caption = (key) => MODULES[key]?.label || key;
  const defaultMapping = (resource, columns, fields) => {
    const used = new Set(), mapping = {};
    for (const column of columns) {
      const normalized = column.toLowerCase().trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
      let field = ALIASES[normalized] || normalized.replace(/ /g, "_");
      if (resource === "leads" && normalized === "last name") field = "name";
      const valid = fields.some(item => item.key === field);
      if (valid && !used.has(field)) { mapping[column] = field; used.add(field); }
    }
    return mapping;
  };
  function initialize(resource) {
    if (!MODULES[resource] || !["leads", "deals", "accounts", "contacts"].includes(resource)) throw Error("Unsupported import module");
    current = { resource, step: 0, files: [], charset: "auto", preview: null, mapping: {},
      operation: "add", duplicate: "none", layout: "Default", automation: false,
      assignment: false, followup: "", tab: "all", query: "", busy: false, result: null };
  }
  function status() { return current?.step || 0; }
  function fileList() {
    return current.files.map(file => `<div class="import-uploaded-file"><strong>▤ ${esc(file.name)}</strong><span>${(file.size / 1024).toFixed(1)} KB</span></div>`).join("");
  }
  function actionView() {
    const resource = current.resource;
    const canMatchEmail = ["leads", "contacts"].includes(resource);
    return `<div class="import-form-section"><h3>Choose layout</h3><label class="import-input-row">Select layout to import ${esc(caption(resource))}
      <select data-import-layout>${(current.preview?.layouts || ["Default"]).map(name=>`<option value="${esc(name)}" ${current.layout===name?"selected":""}>${esc(name)}</option>`).join("")}</select></label></div>
      <div class="import-form-section"><h3>How should the records in these files be processed?</h3>
      ${[["add","Add as new"],["update","Update existing only"],["both","Both - add and update"]].map(([value,label])=>`
      <label class="import-choice"><input type="radio" name="import-operation" value="${value}" ${current.operation===value?"checked":""} /> ${esc(label)} ${esc(caption(resource))}</label>`).join("")}
      <label class="import-input-row">Skip or match existing records based on
        <select data-import-duplicate>
          ${[["none","None"],["phone","Phone Number"],...(canMatchEmail?[["email","Email"]]:[]),["id","Record ID"]]
          .filter(([value])=>current.operation==="add"||value!=="none")
          .map(([value,label])=>`<option value="${value}" ${current.duplicate===value?"selected":""}>${label}</option>`).join("")}
        </select>
      </label>
      <p class="import-help">New records can skip duplicates. Update and Both use the matching field to identify existing records; records from other organizations cannot be updated.</p></div>`;
  }
  function moduleMappingView() {
    const query = current.query.toLowerCase();
    const items = current.preview.files.filter(file => file.name.toLowerCase().includes(query));
    return `<div class="import-mapping-layout"><aside class="import-mapping-aside">
      <h3>Mapped Files <span>${current.preview.files.length}</span></h3>${fileList()}
      <p>Unmapped Files <strong>0</strong></p><p>Unsupported Files <strong>0</strong></p>
      </aside><div class="import-mapping-body"><div class="import-mapping-head">
      <div class="import-tabs"><button data-import-tab="all" class="active">All Modules (1)</button><button data-import-tab="mapped">Mapped Modules (1)</button><button data-import-tab="unmapped">Unmapped Modules (0)</button></div>
      <input data-import-module-search placeholder="Search modules and files" value="${esc(current.query)}" /></div>
      ${current.tab==="unmapped"?`<p class="import-help">No Matching Modules found</p>`:`<div class="import-target-card"><strong>${esc(caption(current.resource))}</strong><small>${current.preview.files.length} file(s) mapped</small></div>`}
      ${items.length?"":'<p class="import-help">No matching files found.</p>'}
      </div></div>`;
  }
  function mappingView() {
    const p = current.preview, mapped = Object.keys(current.mapping).filter(k=>current.mapping[k]).length;
    const filtered = p.columns.filter(column => {
      const exists = Boolean(current.mapping[column]);
      return (current.tab==="all" || (current.tab==="mapped" && exists) || (current.tab==="unmapped" && !exists))
        && column.toLowerCase().includes(current.query.toLowerCase());
    });
    return `<div class="import-mapping-layout"><aside class="import-mapping-aside"><h3>Mapped Modules</h3><p>${esc(caption(current.resource))}</p>
      <button data-import-tab="all" class="${current.tab==="all"?"active":""}">All Columns <span>${p.columns.length}</span></button>
      <button data-import-tab="mapped" class="${current.tab==="mapped"?"active":""}">Mapped Columns <span>${mapped}</span></button>
      <button data-import-tab="unmapped" class="${current.tab==="unmapped"?"active":""}">Unmapped Columns <span>${p.columns.length-mapped}</span></button>
      </aside><div class="import-mapping-body">
      <div class="import-mapping-head"><h3>${esc(caption(current.resource))}</h3><input data-import-column-search placeholder="Search file columns" value="${esc(current.query)}" /><button data-import-auto-map>Auto Map</button><button data-import-reset-map>Reset Mapping</button></div>
      <div class="import-scroll-table"><table class="import-table"><thead><tr><th>Columns in File</th><th>Fields in CRM</th><th>Sample Data from File</th></tr></thead><tbody>
        ${filtered.map(column=>`<tr><td>${esc(column)}</td><td><select data-import-map="${esc(column)}" aria-label="CRM field for ${esc(column)}">
        <option value="">Select Field</option>${p.fields.map(field=>`<option value="${esc(field.key)}" ${current.mapping[column]===field.key?"selected":""} ${Object.entries(current.mapping).some(([other,key])=>other!==column && key===field.key)?"disabled":""}>${esc(field.label)}${field.key==="phone"?" *":""}</option>`).join("")}
        </select></td><td>${p.sample.map(row=>esc(row[column]||"—")).join("　　")}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="import-mapping-required">${Object.values(current.mapping).includes("phone")?"✓ Phone Number mapped":"Phone Number * must be mapped before continuing."}</p>
      </div></div>`;
  }
  function assignView() {
    return `<div class="import-assign"><section><h3>Assignment Rules</h3>
      <label><input type="checkbox" data-import-assignment ${current.assignment?"checked":""}/> Assign owner based on matching assignment rules</label>
      <p>When no assignment rule matches, the imported record belongs to you.</p></section>
      <section><h3>Manual Record Approval</h3><label title="Manual approval for import is not available in this CRM build">
      <input type="checkbox" disabled/> Enable manual record approval (not available)</label></section>
      <section><h3>Trigger Automation and Process Management</h3><label><input type="checkbox" data-import-automation ${current.automation?"checked":""}/> Trigger configured automations for imported and updated records</label></section>
      <section><h3>Assign follow-up tasks</h3><label>Add follow-up task to new records and assign it to record owner <select data-import-followup><option value="">No follow-up task</option>${["Call","Meeting","Email","Follow up"].map(name=>`<option value="${name}" ${current.followup===name?"selected":""}>${name}</option>`).join("")}</select></label><p>Task due date is the next day. <a href="/setup/automation_actions">Create Workflow Task</a></p></section>
      <section><h3>Import Summary</h3><p>${current.preview.total} rows in ${current.preview.files.length} files; ${esc(current.operation)} records in ${esc(caption(current.resource))}.</p>
      <p>Phone Number is required in every row. Rows with validation errors will be reported in Import History.</p></section></div>`;
  }
  function uploadView() {
    return `<div class="import-upload-zone" data-import-drop>
      <div class="import-upload-icon">⇧</div>
      <strong>Drag and drop files here</strong><p>- or -</p>
      <label class="button import-browse">Browse Files<input data-import-files type="file" multiple accept=".xlsx,.csv,.vcf,.xls" hidden /></label>
      <p>Supported file formats: XLSX, CSV, VCF and XLS</p><p>Download sample file: <a href="/api/import-wizard/${current.resource}/sample.csv" download>CSV</a> or <a href="/api/import-wizard/${current.resource}/sample.xlsx" download>XLSX</a></p>
      ${fileList()}</div>
      <label class="import-input-row">Charset <select data-import-charset>${CHARSETS.map(k=>`<option value="${k}" ${current.charset===k?"selected":""}>${k==="auto"?"Auto-Detect":k.toUpperCase()}</option>`).join("")}</select></label>
      <div class="import-help">Up to 3 files, 25 MB per file, maximum 100,000 records per job. The files are previewed before importing.</div>`;
  }
  function screen() {
    if (!current) return "";
    const s = current.step;
    return `<section class="import-wizard"><header class="import-wizard-header"><h2>Import ${esc(caption(current.resource))}</h2>
      <nav class="import-progress" aria-label="Import steps">${STEPS.map((label,index)=>`<span class="${index===s?"current":index<s?"complete":""}">${index<s?"✓ ":index===s?"● ":"○ "}${label}</span>`).join("")}</nav></header>
      <div class="import-wizard-panel">${[uploadView,actionView,moduleMappingView,mappingView,assignView][s]()}</div>
      <footer class="import-footer"><button data-import-cancel>Cancel</button><div>
        ${s>0?'<button data-import-back>Previous</button>':""}
        <button class="button button-primary" data-import-next ${current.busy|| (s===0&&!current.files.length)?"disabled":""}>${current.busy?"Working…":s===4?"Submit":s===3?"Save and Next":"Next"}</button>
      </div></footer></section>`;
  }
  function view(resource) { initialize(resource); return screen(); }
  function refresh() { const root = $("#app-content"); if(root) { root.innerHTML = screen(); bind(root); } }
  function addFiles(files) {
    const selection = [...files];
    if (!selection.length) return;
    if (selection.length>3 || selection.some(f=>f.size>25*1024*1024 || !SUPPORTED.includes(f.name.split(".").pop().toLowerCase()))) {
      toast("Invalid upload", "Choose 1–3 CSV, XLSX, XLS or VCF files, each up to 25 MB.", "error"); return;
    }
    current.files=selection;current.preview=null;current.mapping={};refresh();
  }
  function formData(execute=false) {
    const data = new FormData();
    current.files.forEach(file=>data.append("files",file));
    data.append("charset",current.charset);
    if (execute) {
      data.append("mapping",JSON.stringify(current.mapping));
      data.append("operation",current.operation);
      data.append("duplicate_key",current.duplicate);
      data.append("layout",current.layout);
      data.append("trigger_automation",String(current.automation));
      data.append("apply_assignment",String(current.assignment));
      data.append("followup_task",current.followup);
    }
    return data;
  }
  async function post(endpoint, data) {
    const response=await fetch(endpoint,{method:"POST",body:data,credentials:"same-origin"});
    const json=await response.json();
    if (!response.ok) throw new Error(typeof json.detail==="string"?json.detail:JSON.stringify(json.detail||"Import failed"));
    return json;
  }
  async function next() {
    if (current.busy) return;
    if (current.step===1 && current.operation!=="add" && current.duplicate==="none") {
      toast("Select a matching field", "Update operations require Phone Number, Email or Record ID.","error");return;
    }
    if (current.step===3) {
      if (!Object.values(current.mapping).includes("phone")) {
        toast("Phone Number required", "Map a file column to Phone Number before continuing.", "error"); return;
      }
      const required=current.resource==="contacts"?"first_name":"name";
      if (!Object.values(current.mapping).includes(required)) {
        toast("Required mapping",`Map ${required.replace("_"," ")} to continue.`,"error");return;
      }
      if (current.resource==="contacts" && !Object.values(current.mapping).includes("last_name")) {
        toast("Last Name required", "Map Last Name before continuing with Contacts.", "error"); return;
      }
      if (["phone","email"].includes(current.duplicate) && !Object.values(current.mapping).includes(current.duplicate)) {
        toast("Matching field required", "Map the selected duplicate matching field.", "error");return;
      }
    }
    try {
      current.busy=true;
      if (current.step===0) {
        current.preview=await post(`/api/import-wizard/${current.resource}/preview`,formData());
        current.mapping=defaultMapping(current.resource,current.preview.columns,current.preview.fields);
      } else if (current.step===4) {
        current.result=await post(`/api/import-wizard/${current.resource}/submit`,formData(true));
        toast("Import complete",`${current.result.imported} imported, ${current.result.updated} updated, ${current.result.skipped} skipped, ${current.result.errors.length} errors.`);
        await navigate("/setup/import_history"); return;
      }
      current.step++;current.tab="all";current.query="";
    } catch(error) { toast("Import failed",error.message,"error"); }
    finally {current.busy=false;if(current.step!==4 || !current.result)refresh();}
  }
  function bind(root=$("#app-content")) {
    if(!current) return;
    $("[data-import-next]",root)?.addEventListener("click",next);
    $("[data-import-back]",root)?.addEventListener("click",()=>{current.step=Math.max(0,current.step-1);refresh();});
    $("[data-import-cancel]",root)?.addEventListener("click",()=>navigate("/"+current.resource));
    $("[data-import-files]",root)?.addEventListener("change",event=>addFiles(event.target.files));
    const drop=$("[data-import-drop]",root);
    drop?.addEventListener("dragover",e=>{e.preventDefault();drop.classList.add("dragging");});
    drop?.addEventListener("dragleave",()=>drop.classList.remove("dragging"));
    drop?.addEventListener("drop",e=>{e.preventDefault();addFiles(e.dataTransfer.files);});
    $("[data-import-charset]",root)?.addEventListener("change",e=>{current.charset=e.target.value;});
    root.querySelectorAll("[name=import-operation]").forEach(el=>el.addEventListener("change",e=>{
      current.operation=e.target.value;if(current.operation!=="add" && current.duplicate==="none")current.duplicate="phone";refresh();
    }));
    $("[data-import-duplicate]",root)?.addEventListener("change",e=>current.duplicate=e.target.value);
    $("[data-import-layout]",root)?.addEventListener("change",e=>current.layout=e.target.value);
    root.querySelectorAll("[data-import-tab]").forEach(el=>el.addEventListener("click",()=>{current.tab=el.dataset.importTab;refresh();}));
    const updateSearch = e => {
      const selector = e.target.hasAttribute("data-import-column-search") ? "[data-import-column-search]" : "[data-import-module-search]";
      const position = e.target.selectionStart;
      current.query=e.target.value;
      refresh();
      const replacement=$(selector,$("#app-content"));
      replacement?.focus();
      if(position!==null)replacement?.setSelectionRange(position,position);
    };
    $("[data-import-module-search]",root)?.addEventListener("input",updateSearch);
    $("[data-import-column-search]",root)?.addEventListener("input",updateSearch);
    root.querySelectorAll("[data-import-map]").forEach(el=>el.addEventListener("change",e=>{
      if(e.target.value)current.mapping[e.target.dataset.importMap]=e.target.value;
      else delete current.mapping[e.target.dataset.importMap];
      refresh();
    }));
    $("[data-import-auto-map]",root)?.addEventListener("click",()=>{current.mapping=defaultMapping(current.resource,current.preview.columns,current.preview.fields);refresh();});
    $("[data-import-reset-map]",root)?.addEventListener("click",()=>{current.mapping={};refresh();});
    $("[data-import-assignment]",root)?.addEventListener("change",e=>current.assignment=e.target.checked);
    $("[data-import-automation]",root)?.addEventListener("change",e=>current.automation=e.target.checked);
    $("[data-import-followup]",root)?.addEventListener("change",e=>current.followup=e.target.value);
  }
  return {view,bind,status};
}

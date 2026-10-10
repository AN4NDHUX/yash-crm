// Teamspaces views and event handlers extracted from the CRM entrypoint.
export function createTeamspacesFeature({ api, pageHeader, esc, emptyState, $, $$, readForm, toast, navigate }) {
async function teamspacesView() {
  const data = await api("/api/teamspaces");
  const items = data.items || [];
  return `${pageHeader("Workspace", "Teamspaces", "Organize modules, people, and work around the teams that use CONVOSIS CRM.")}
    <div class="teamspaces-layout">
      <section class="card settings-section"><div class="settings-section-head"><h2>Create a teamspace</h2><p>Give a group a focused workspace without changing the underlying CRM records.</p></div>
        <form data-teamspace-form class="settings-form"><div class="form-grid"><div class="field"><label>Name</label><input class="field-input" name="name" required placeholder="Revenue team" /></div><div class="field"><label>Icon</label><input class="field-input" name="icon" value="◈" maxlength="4" /></div><div class="field field-full"><label>Description</label><textarea class="field-input" name="description" rows="3" placeholder="What this teamspace is for"></textarea></div></div><div class="form-actions"><button class="button button-primary" type="submit">Create teamspace</button></div></form>
      </section>
      <section class="card settings-section"><div class="settings-section-head"><h2>Your teamspaces</h2><p>${items.length} active workspace${items.length === 1 ? "" : "s"} with shared module context.</p></div><div class="teamspace-list">${items.length ? items.map((item) => `<article class="teamspace-card"><div class="teamspace-icon">${esc(item.icon || "◈")}</div><div class="rule-info"><strong>${esc(item.name)}</strong><small>${esc(item.description || "No description yet")}</small><small>${item.members?.length || 0} member${item.members?.length === 1 ? "" : "s"} · ${(item.modules || []).length} module${(item.modules || []).length === 1 ? "" : "s"}</small></div><button class="button button-small button-ghost" data-teamspace-open="${item.id}">Open</button></article>`).join("") : emptyState("◈", "No teamspaces yet", "Create a workspace for a sales, support, or operations group.")}</div></section>
    </div>`;
}

function bindTeamspaces() {
  $("[data-teamspace-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await api("/api/teamspaces", { method: "POST", body: JSON.stringify(readForm(event.currentTarget)) }); toast("Teamspace created", "The new workspace is ready for your team."); await navigate("/teamspaces", true); }
    catch (error) { toast("Could not create teamspace", error.message, "error"); }
  });
  $$('[data-teamspace-open]').forEach((button) => button.addEventListener("click", async () => {
    const item = await api(`/api/teamspaces/${button.dataset.teamspaceOpen}`);
    toast(item.name, `${item.members.length} members · ${(item.modules || []).length} modules`, "success");
  }));
}



return { teamspacesView, bindTeamspaces };
}

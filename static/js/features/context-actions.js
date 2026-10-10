// Contextual CRM actions preserve the selected source record when opening a modal.
export function createContextActions({ api, openPlatformModal, openRecordModal, state, toast, selectAll }) {
  async function openQuoteForDeal(id) {
    try {
      const deal = await api(`/api/deals/${id}`);
      await openPlatformModal("quotes", null, {
        name: `${deal.name} - Quote`,
        deal_id: deal.id,
        account_id: deal.account_id ?? null,
        contact_id: deal.contact_id ?? null,
        amount: deal.amount ?? 0,
        status: "Draft",
      });
      state.modal.context = { kind: "deal-quote", sourceId: deal.id };
    } catch (error) {
      toast("Cannot create quote", error.message, "error");
    }
  }

  async function openDealForAccount(id) {
    try {
      const account = await api(`/api/accounts/${id}`);
      await openRecordModal("deals", null, {
        name: `${account.name} - Opportunity`,
        account_id: account.id,
        phone: account.phone || "",
        amount: 0,
        stage: "Qualification",
        status: "Open",
        type: "New business",
      });
      state.modal.context = { kind: "account-deal", sourceId: account.id };
    } catch (error) {
      toast("Cannot create deal", error.message, "error");
    }
  }

  function bindContextCreationActions() {
    selectAll("[data-create-deal-quote]").forEach(button =>
      button.addEventListener("click", () => openQuoteForDeal(Number(button.dataset.createDealQuote)))
    );
    selectAll("[data-create-account-deal]").forEach(button =>
      button.addEventListener("click", () => openDealForAccount(Number(button.dataset.createAccountDeal)))
    );
  }

  return { openQuoteForDeal, openDealForAccount, bindContextCreationActions };
}

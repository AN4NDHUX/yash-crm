export async function renderPricingView({ api, esc, pageHeader }) {
  const data = await api("/api/plans");
  const currentCode = data.current_subscription?.plan_code || "free";
  const pendingCode = data.current_subscription?.pending_upgrade?.plan_code || "";
  const currencySymbol = (currency) => currency === "INR" ? "₹" : currency === "USD" ? "$" : currency + " ";
  const orderedCodes = ["free", "bigin_express", "standard", "professional", "enterprise", "crm_plus"];
  const plans = [...(data.items || [])].sort((a, b) => orderedCodes.indexOf(a.code) - orderedCodes.indexOf(b.code));

  const cards = plans.map((plan) => {
    const features = plan.features || {};
    const included = Array.isArray(features.included_features) ? features.included_features : [];
    const current = plan.code === currentCode;
    const pending = plan.code === pendingCode;
    const popular = features.popular === true;
    const price = Number(plan.price_monthly || 0);
    const priceLabel = price === 0 ? `${currencySymbol(plan.currency)}0` : `${currencySymbol(plan.currency)}${price.toLocaleString("en-IN")}`;
    return `<article class="pricing-card selectable ${popular ? "popular" : ""} ${current ? "current" : ""} ${pending ? "pending-upgrade" : ""}" data-plan-card="${esc(plan.code)}" tabindex="0" role="button" aria-pressed="${current}">
      ${popular ? '<span class="pricing-popular">Most Popular</span>' : ""}
      <div class="pricing-card-head">
        <h2>${esc(plan.name)}</h2>
        <div class="pricing-price">${esc(priceLabel)}</div>
        <div class="pricing-cycle">${price === 0 ? "No credit card required" : "/user/month"}</div>
        <p>${esc(features.tagline || "")}</p>
        <span class="pricing-status ${current ? "is-current" : pending ? "is-pending" : ""}">${current ? "Current plan" : pending ? "Upgrade requested" : "Available plan"}</span>
      </div>
      <ul class="pricing-features">${included.map((item) => `<li><span>✓</span><span>${esc(item)}</span></li>`).join("")}</ul>
      <div class="pricing-limits">
        <span>${plan.max_records == null ? "Unlimited" : Number(plan.max_records).toLocaleString("en-IN")} records</span>
        <span>${plan.max_custom_modules == null ? "Unlimited" : Number(plan.max_custom_modules).toLocaleString("en-IN")} custom modules</span>
      </div>
      <div class="pricing-select-row">
        <button class="button ${current ? "button-ghost" : "button-primary"} pricing-select-button"
          type="button" data-select-plan="${esc(plan.code)}" ${current || pending ? "disabled" : ""}>
          ${current ? "Current plan" : pending ? "Upgrade requested" : "Select plan"}
        </button>
      </div>
    </article>`;
  }).join("");

  return `${pageHeader("Account", "Upgrade plan", "Choose the CONVOSIS CRM plan that best matches your team and feature requirements.")}
    <section class="pricing-grid">${cards}</section>
    <section class="pricing-note card">
      <strong>Subscription</strong>
      <p>Paid plans activate only after verified checkout. Prices are per user per month where applicable; taxes and external provider charges are separate.</p>
    </section>`;
}


export function bindPricingInteractions({
  api,
  toast,
  state,
  applyProfile,
  renderRoute,
  titleCase,
  queryOne,
  queryAll,
}) {
  const choose = async (planCode, button) => {
    if (!planCode || button?.disabled) return;
    const original = button?.textContent;
    try {
      if (button) {
        button.disabled = true;
        button.textContent = "Updating…";
      }
      const result = await api("/api/subscription", {
        method: "PATCH",
        body: JSON.stringify({ plan_code: planCode }),
      });
      if (result.requires_payment) {
        toast("Upgrade requested", "Opening secure checkout…");
        try {
          const checkout = await api("/api/billing/checkout", {
            method: "POST",
            body: JSON.stringify({ plan_code: planCode }),
          });
          if (checkout.checkout_url) {
            window.location.assign(checkout.checkout_url);
            return;
          }
          toast("Checkout unavailable", "The upgrade request is saved. Contact your administrator to complete payment.", "error");
        } catch (billingError) {
          toast("Checkout unavailable", billingError.message || "The upgrade request is saved, but billing is not configured yet.", "error");
        }
      } else {
        toast("Plan updated", `Your subscription is now ${result.subscription?.plan_name || titleCase(planCode)}.`);
      }
      try {
        state.profile = await api("/api/settings/profile");
        applyProfile();
      } catch {}
      await renderRoute();
    } catch (error) {
      if (button) {
        button.disabled = false;
        button.textContent = original || "Select plan";
      }
      toast("Could not update plan", error.message, "error");
    }
  };

  queryAll("[data-select-plan]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      choose(button.dataset.selectPlan, button);
    });
  });

  queryAll("[data-plan-card]").forEach((card) => {
    const trigger = () => {
      const button = queryOne("[data-select-plan]", card);
      if (button && !button.disabled) choose(button.dataset.selectPlan, button);
    };
    card.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      trigger();
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        trigger();
      }
    });
  });
}

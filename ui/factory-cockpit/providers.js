"use strict";
// Fournisseurs IA — which model provider keeps the factory running (ADR-0018).
// Self-contained: reads /api/providers, writes through /api/providers with the
// cockpit confirmation header. Every control is reversible and zero-token; the
// only thing it changes is which provider the next session starts on.
(() => {
  const HEADER = "human-provider-control";
  const STATE_LABEL = { available: "Disponible", low: "Bientôt épuisé", exhausted: "Épuisé", disabled: "Désactivé" };
  const STATE_CLASS = { available: "working", low: "attention", exhausted: "down", disabled: "idle" };
  const REASON = {
    preferred: "choix préféré",
    fallback: "repli automatique",
    forced: "forcé à la main",
    all_unavailable: "aucun fournisseur disponible",
  };
  const DURATIONS = [
    [60, "1 h"], [180, "3 h"], [300, "5 h"], [1440, "24 h"], [10080, "7 jours"], ["date", "jusqu’à une date…"],
  ];
  let data = null;
  let busy = false;

  const $ = (id) => document.getElementById(id);
  function el(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = text;
    return item;
  }
  function when(iso) {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return "";
    return date.toLocaleString("fr-FR", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }
  function pill(state) {
    const span = el("span", `status-pill ${STATE_CLASS[state] || "waiting"}`, STATE_LABEL[state] || state);
    return span;
  }
  function providerLabel(name) { return data?.providers?.[name]?.label || name || "—"; }
  function feedback(message, isError, compact) {
    for (const id of compact ? ["mobile-providers-feedback"] : ["providers-feedback", "mobile-providers-feedback"]) {
      const box = $(id);
      if (!box) continue;
      box.textContent = message;
      box.classList.toggle("error", Boolean(isError));
    }
  }

  async function load() {
    try {
      const response = await fetch("/api/providers", { cache: "no-store" });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      data = value;
      render();
    } catch (error) {
      const summary = $("providers-summary");
      if (summary) summary.textContent = `Lecture impossible : ${error.message}`;
      const mobile = $("mobile-providers-summary");
      if (mobile) mobile.textContent = "Lecture impossible";
    }
  }

  async function act(action, args, compact = false) {
    if (busy) return;
    busy = true;
    document.querySelectorAll("[data-provider-control]").forEach((b) => { b.disabled = true; });
    feedback("Application… (le rechargement de la cité peut prendre quelques secondes)", false, compact);
    try {
      const response = await fetch("/api/providers", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Factory-Cockpit": HEADER },
        body: JSON.stringify({ action, args }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      data = value.status || data;
      const moved = (value.switches || []).length ? ` · ${value.switches.join(" · ")}` : "";
      feedback(`${value.summary}${moved}`, false, compact);
      render();
    } catch (error) {
      feedback(error.message, true, compact);
    } finally {
      busy = false;
      // Redraw rather than blanket re-enable: the first "↑" must stay disabled.
      if (data) render();
      else document.querySelectorAll("[data-provider-control]").forEach((b) => { b.disabled = false; });
    }
  }

  function button(label, onClick, primary = false) {
    const item = el("button", primary ? "primary" : "", label);
    item.type = "button";
    item.dataset.providerControl = "1";
    item.addEventListener("click", onClick);
    return item;
  }

  function markControls(pool, compact) {
    const wrap = el("div", "provider-actions");
    const select = el("select");
    select.setAttribute("aria-label", "Durée de l’épuisement");
    for (const [value, label] of DURATIONS) {
      if (compact && value === "date") continue;
      const option = el("option", "", label);
      option.value = String(value);
      if (value === 300) option.selected = true;
      select.append(option);
    }
    const date = el("input");
    date.type = "datetime-local";
    date.className = "hidden";
    date.setAttribute("aria-label", "Reprise prévue");
    select.addEventListener("change", () => date.classList.toggle("hidden", select.value !== "date"));
    const go = button("Marquer épuisé", () => {
      if (select.value === "date") {
        const picked = date.value ? new Date(date.value) : null;
        if (!picked || Number.isNaN(picked.getTime())) { feedback("Choisis la date de reprise.", true, compact); return; }
        act("mark", { pool, until: picked.toISOString(), reason: "marqué depuis le cockpit" }, compact);
      } else {
        act("mark", { pool, minutes: Number(select.value), reason: "marqué depuis le cockpit" }, compact);
      }
    });
    wrap.append(select, date, go);
    return wrap;
  }

  function renderPools(container, compact) {
    if (!container) return;
    container.replaceChildren();
    // On the phone, a healthy pool is one line of noise above the questions
    // that matter. Only pools with a problem stay open; the rest fold away
    // behind the one action a phone user would want: report a quota wall.
    let fold = null;
    if (compact) {
      const healthy = Object.values(data.pools || {}).filter((p) => p.state === "available").length;
      if (healthy) {
        fold = el("details", "provider-fold");
        fold.append(el("summary", "", `Signaler un quota atteint (${healthy} disponible${healthy > 1 ? "s" : ""})`));
      }
    }
    for (const [name, pool] of Object.entries(data.pools || {})) {
      const row = el("div", `provider-row ${pool.state}`);
      const head = el("div", "provider-row-head");
      head.append(el("strong", "", pool.label), pill(pool.state));
      row.append(head);
      const facts = [];
      if (pool.until && pool.state !== "available") facts.push(`reprise prévue ${when(pool.until)}`);
      if (pool.source === "manual") facts.push(pool.by === "cockpit" ? "marqué depuis le cockpit" : `marqué à la main${pool.by ? ` (${pool.by})` : ""}`);
      else if (pool.state !== "available") facts.push("détecté automatiquement");
      if (pool.detected && pool.state === "available") facts.push(`détecté « ${pool.detected} » mais ignoré (mode manuel)`);
      if (facts.length) row.append(el("p", "muted", facts.join(" · ")));
      if (!compact && pool.evidence && pool.state !== "available") row.append(el("p", "provider-evidence", pool.evidence));
      if (pool.state === "exhausted" || pool.state === "low") {
        const actions = el("div", "provider-actions");
        actions.append(button("Rétablir", () => act("clear", { pool: name }, compact), true));
        row.append(actions);
      } else {
        row.append(markControls(name, compact));
      }
      if (fold && pool.state === "available") fold.append(row);
      else container.append(row);
    }
    if (fold) container.append(fold);
  }

  function renderTargets(container) {
    if (!container) return;
    container.replaceChildren();
    for (const [name, target] of Object.entries(data.targets || {})) {
      const card = el("article", "provider-target");
      const head = el("div", "provider-row-head");
      head.append(el("strong", "", target.label));
      head.append(el("span", target.provider ? "provider-effective" : "provider-effective none",
        target.provider ? `${providerLabel(target.provider)} · ${REASON[target.reason] || target.reason}`
          : `${REASON.all_unavailable}${target.next_reset ? ` · reprise ${when(target.next_reset)}` : ""}`));
      card.append(head);
      if (target.warning) card.append(el("p", "feedback error", target.warning));
      if (target.why) card.append(el("p", "muted", target.why));

      const chain = el("ol", "provider-chain");
      const order = target.chain.map((entry) => entry.provider);
      target.chain.forEach((entry, index) => {
        const item = el("li");
        item.append(el("span", "", providerLabel(entry.provider)), pill(entry.state));
        const up = button("↑", () => {
          const next = [...order]; [next[index - 1], next[index]] = [next[index], next[index - 1]];
          act("chain", { target: name, chain: next });
        });
        up.disabled = index === 0; up.setAttribute("aria-label", `Monter ${providerLabel(entry.provider)}`);
        const down = button("↓", () => {
          const next = [...order]; [next[index + 1], next[index]] = [next[index], next[index + 1]];
          act("chain", { target: name, chain: next });
        });
        down.disabled = index === order.length - 1; down.setAttribute("aria-label", `Descendre ${providerLabel(entry.provider)}`);
        const toggle = entry.state === "disabled"
          ? button("Réactiver", () => act("enable", { provider: entry.provider }))
          : button("Désactiver", () => {
            if (window.confirm(`Désactiver ${providerLabel(entry.provider)} pour toutes les cibles ? Réversible à tout moment.`)) {
              act("disable", { provider: entry.provider, reason: "désactivé depuis le cockpit" });
            }
          });
        const controls = el("span", "provider-chain-controls");
        controls.append(up, down, toggle);
        item.append(controls);
        chain.append(item);
      });
      card.append(chain);

      const tools = el("div", "provider-actions");
      const force = el("select");
      force.setAttribute("aria-label", `Fournisseur imposé pour ${target.label}`);
      const auto = el("option", "", "Choix automatique");
      auto.value = "auto";
      force.append(auto);
      for (const [provider, info] of Object.entries(data.providers || {})) {
        const option = el("option", "", `Forcer : ${info.label}`);
        option.value = provider;
        force.append(option);
      }
      force.value = target.forced || "auto";
      force.dataset.providerControl = "1";
      force.addEventListener("change", () => {
        const chosen = force.value;
        if (chosen !== "auto" && !window.confirm(`Imposer ${providerLabel(chosen)} à « ${target.label} », même s’il s’épuise ?`)) {
          force.value = target.forced || "auto";
          return;
        }
        act("force", { target: name, provider: chosen });
      });
      tools.append(force);
      if (target.chain_overridden) tools.append(button("Ordre par défaut", () => act("chain", { target: name, chain: "default" })));
      card.append(tools);
      container.append(card);
    }
  }

  function summary() {
    const targets = Object.values(data.targets || {});
    const stuck = targets.filter((t) => !t.provider);
    if (stuck.length) {
      return {
        level: "down",
        text: `Aucun fournisseur disponible pour : ${stuck.map((t) => t.label).join(", ")}. La campagne est mise en pause et reprendra seule.`,
      };
    }
    const workers = data.targets?.workspace;
    const mayor = data.targets?.mayor;
    const out = Object.values(data.pools || {}).filter((p) => p.state === "exhausted");
    const parts = [];
    if (workers) parts.push(`ouvriers sur ${providerLabel(workers.provider)}`);
    if (mayor) parts.push(`Mayor sur ${providerLabel(mayor.provider)}`);
    const tail = out.length ? ` · ${out.length} quota${out.length > 1 ? "s" : ""} épuisé${out.length > 1 ? "s" : ""}, repli en place` : "";
    return { level: out.length ? "attention" : "working", text: `Tout tourne : ${parts.join(", ")}${tail}.` };
  }

  function renderHistory() {
    const list = $("providers-history");
    if (!list) return;
    list.replaceChildren();
    for (const entry of data.history || []) {
      const who = entry.by === "cockpit" ? "depuis le cockpit" : entry.by && entry.by !== "system" ? entry.by : "";
      list.append(el("li", "", `${when(entry.at)} — ${entry.detail}${who ? ` (${who})` : ""}`));
    }
    if (!list.children.length) list.append(el("li", "muted", "Aucun changement enregistré."));
  }

  function render() {
    if (!data) return;
    const state = summary();
    const desktop = $("providers-summary");
    if (desktop) { desktop.textContent = state.text; desktop.className = `provider-summary ${state.level}`; }
    const navState = $("nav-providers-state");
    if (navState) navState.textContent = { working: "OK", attention: "Attention", down: "Panne" }[state.level] || "—";
    const mobile = $("mobile-providers-summary");
    if (mobile) mobile.textContent = state.text;
    const auto = $("providers-auto");
    if (auto) { auto.checked = Boolean(data.auto); auto.disabled = busy; }
    const overlay = $("providers-overlay-warning");
    if (overlay) overlay.classList.toggle("hidden", data.overlay_present !== false);
    renderPools($("providers-pools"), false);
    renderPools($("mobile-providers-pools"), true);
    renderTargets($("providers-targets"));
    renderHistory();
  }

  function init() {
    const auto = $("providers-auto");
    if (auto) {
      auto.dataset.providerControl = "1";
      auto.addEventListener("change", () => {
        if (!auto.checked && !window.confirm("Désactiver le repli automatique ? Les quotas détectés seront affichés mais plus appliqués ; seuls tes marquages manuels compteront.")) {
          auto.checked = true;
          return;
        }
        act("auto", { enabled: auto.checked });
      });
    }
    const refresh = $("providers-refresh");
    if (refresh) refresh.addEventListener("click", load);
    load();
    setInterval(() => { if (!document.hidden && !busy) load(); }, 30000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

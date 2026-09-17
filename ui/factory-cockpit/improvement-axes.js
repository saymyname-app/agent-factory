"use strict";
// Axes d'amélioration — the never-idle ladder's rung 5 content, and the
// maintain-alive master switch (docs/FACTORY_CONTINUITY.md sec1/sec4,
// ADR-0016 sec7). Self-contained: reads /api/improvement-axes, writes
// through /api/improvement-axes with the cockpit confirmation header. Every
// control is reversible and zero-token.
(() => {
  const HEADER = "human-improvement-axes-control";
  let data = null;
  let busy = false;

  const $ = (id) => document.getElementById(id);
  function el(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = text;
    return item;
  }
  function feedback(message, isError) {
    const box = $("axes-feedback");
    if (!box) return;
    box.textContent = message;
    box.classList.toggle("error", Boolean(isError));
  }

  async function load() {
    try {
      const response = await fetch("/api/improvement-axes", { cache: "no-store" });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      data = value;
      render();
    } catch (error) {
      const summary = $("axes-summary");
      if (summary) summary.textContent = `Lecture impossible : ${error.message}`;
    }
  }

  async function act(action, args) {
    if (busy) return;
    busy = true;
    document.querySelectorAll("[data-axes-control]").forEach((b) => { b.disabled = true; });
    feedback("Application…", false);
    try {
      const response = await fetch("/api/improvement-axes", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Factory-Cockpit": HEADER },
        body: JSON.stringify({ action, args }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      data = value.status || data;
      feedback(value.summary, false);
      render();
    } catch (error) {
      feedback(error.message, true);
      render();
    } finally {
      busy = false;
    }
  }

  function render() {
    if (!data) return;
    const summary = $("axes-summary");
    if (summary) {
      summary.textContent = data.maintain_alive
        ? "Actif : dès que la file de release est vide, l'usine avance sur un axe activé."
        : "Désactivé : l'usine reste au repos par ce réglage, pas par un blocage.";
    }
    const master = $("axes-maintain-alive");
    if (master) master.checked = Boolean(data.maintain_alive);

    const list = $("axes-list");
    if (list) {
      list.replaceChildren(...(data.axes || []).map((axis) => {
        const row = el("div", `axes-row ${axis.enabled ? "" : "off"}`.trim());
        const label = el("label");
        const input = el("input");
        input.type = "checkbox";
        input.checked = Boolean(axis.enabled);
        input.dataset.axesControl = "1";
        input.disabled = busy;
        input.addEventListener("change", () => act(input.checked ? "enable" : "disable", { axis: axis.name }));
        const body = el("div", "axes-row-body");
        const nameLine = el("div", "axes-row-name", axis.name);
        if (axis.draft_only) nameLine.append(el("span", "axes-badge draft", "proposition seulement"));
        if (axis.mechanism && axis.mechanism.status === "not_implemented") {
          nameLine.append(el("span", "axes-badge stub", "pas encore outillé"));
        }
        body.append(nameLine, el("div", "axes-row-scope", axis.scope_boundary));
        label.append(input, body);
        row.append(label);
        return row;
      }));
    }

    const next = $("axes-next");
    if (next) {
      next.textContent = data.next_selected
        ? `Prochain si la file de release est vide : ${data.next_selected.name} (${data.next_selected.action === "propose" ? "proposition à valider" : "travail normal"})`
        : "Rien à prendre pour l'instant sur cet échelon.";
    }
  }

  $("axes-refresh")?.addEventListener("click", load);
  $("axes-maintain-alive")?.addEventListener("change", (event) => {
    act("maintain-alive", { enabled: event.target.checked });
  });

  load();
  setInterval(load, 30000);
})();

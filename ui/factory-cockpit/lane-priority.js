"use strict";
// Lane priority switch (ADR-0023 amendment 2): which lane, Factory or
// product, is serviced first. Reversible at will; the other lane still
// materializes automatically the moment the priority lane has nothing
// eligible -- this switch only decides ORDER, never an exclusive pause.
// Self-contained: reads /api/lane-priority, writes through it with the
// cockpit confirmation header. Zero-token, same as the other switches.
(() => {
  const HEADER = "human-lane-priority";
  const LANE_LABEL = { factory: "Factory", product: "Produit" };
  const EXPLANATION = "Le travail en cours n’est pas interrompu ; seuls les prochains choix suivront cet ordre.";
  const CLEAR_AFTER_MS = 6000;
  let busy = false;
  let clearTimer = null;

  const $ = (id) => document.getElementById(id);

  function render(lane) {
    document.querySelectorAll(".lane-priority-btn").forEach((button) => {
      button.classList.toggle("primary", button.dataset.lane === lane);
      button.disabled = busy;
    });
  }

  function setStatus(kind, text) {
    const el = $("lane-priority-status");
    if (!el) return;
    if (clearTimer) {
      clearTimeout(clearTimer);
      clearTimer = null;
    }
    el.className = `lane-priority-status visible ${kind}`;
    el.textContent = text;
    if (kind === "success") {
      clearTimer = setTimeout(() => {
        el.className = "lane-priority-status";
        el.textContent = "";
      }, CLEAR_AFTER_MS);
    }
  }

  async function load() {
    try {
      const response = await fetch("/api/lane-priority", { cache: "no-store" });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      render(value.lane);
    } catch (error) {
      setStatus("error", `Lecture impossible : ${error.message}`);
    }
  }

  async function set(lane) {
    if (busy) return;
    busy = true;
    render(lane);
    setStatus("loading", `Changement vers ${LANE_LABEL[lane] || lane}…`);
    try {
      const response = await fetch("/api/lane-priority", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Factory-Cockpit": HEADER },
        body: JSON.stringify({ lane }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      busy = false;
      render(value.lane);
      const activeLabel = LANE_LABEL[value.lane] || value.lane;
      setStatus("success", `Priorité confirmée : ${activeLabel}. ${EXPLANATION}`);
    } catch (error) {
      busy = false;
      render(lane);
      setStatus("error", `Réglage refusé : ${error.message}`);
      load();
    }
  }

  document.querySelectorAll(".lane-priority-btn").forEach((button) => {
    button.addEventListener("click", () => set(button.dataset.lane));
  });

  load();
  setInterval(load, 30000);
})();

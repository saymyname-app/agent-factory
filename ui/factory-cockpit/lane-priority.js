"use strict";
// Lane priority switch (ADR-0023 amendment 2): which lane, Factory or
// product, is serviced first. Reversible at will; the other lane still
// materializes automatically the moment the priority lane has nothing
// eligible -- this switch only decides ORDER, never an exclusive pause.
// Self-contained: reads /api/lane-priority, writes through it with the
// cockpit confirmation header. Zero-token, same as the other switches.
(() => {
  const HEADER = "human-lane-priority";
  let busy = false;

  const $ = (id) => document.getElementById(id);

  function render(lane) {
    document.querySelectorAll(".lane-priority-btn").forEach((button) => {
      button.classList.toggle("primary", button.dataset.lane === lane);
      button.disabled = busy;
    });
  }

  async function load() {
    try {
      const response = await fetch("/api/lane-priority", { cache: "no-store" });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      render(value.lane);
    } catch (error) {
      const box = $("lane-priority");
      if (box) box.title = `Lecture impossible : ${error.message}`;
    }
  }

  async function set(lane) {
    if (busy) return;
    busy = true;
    render(lane);
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
    } catch (error) {
      busy = false;
      const box = $("lane-priority");
      if (box) box.title = `Réglage refusé : ${error.message}`;
      load();
    }
  }

  document.querySelectorAll(".lane-priority-btn").forEach((button) => {
    button.addEventListener("click", () => set(button.dataset.lane));
  });

  load();
  setInterval(load, 30000);
})();

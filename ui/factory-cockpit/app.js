const $ = (id) => document.getElementById(id);
let snapshot = null;
let loading = false;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function parseTime(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function durationSince(value) {
  const date = parseTime(value);
  if (!date) return "non disponible";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}min ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}min`;
}

function signalAge(value) {
  const date = parseTime(value);
  if (!date) return "inconnu";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 15) return "à l’instant";
  return `il y a ${durationSince(value)}`;
}

function statusClass(value) {
  return ["working", "waiting", "queued", "idle", "attention", "down"].includes(value)
    ? value
    : "waiting";
}

function setStatus(element, state, label) {
  element.className = `status-pill ${statusClass(state)}`;
  element.textContent = label;
}

function renderAgents(agents) {
  const container = $("agents");
  container.replaceChildren();
  $("agent-count").textContent = agents.length;
  agents.forEach((agent) => {
    const card = node("article", "agent-card");
    const top = node("div", "agent-top");
    const identity = node("div");
    identity.append(node("div", "agent-name", agent.name));
    identity.append(node("div", "agent-role", agent.role));
    const badge = node("span", `status-pill ${statusClass(agent.state)}`, agent.state_label);
    top.append(identity, badge);
    card.append(top);
    card.append(node("p", "agent-objective", agent.objective));
    card.append(node("div", "agent-meta", agent.phase));
    card.append(node("div", "agent-meta", `Signal ${signalAge(agent.last_signal_at)} · depuis ${durationSince(agent.started_at)}`));
    container.append(card);
  });
  if (agents.length === 1) {
    container.append(node("div", "empty", "Aucun autre agent produit actif."));
  }
}

function renderQueue(queue) {
  const container = $("queue");
  container.replaceChildren();
  $("queue-count").textContent = queue.length;
  queue.forEach((item) => {
    const row = node("li", "queue-item");
    const copy = node("div");
    copy.append(node("div", "queue-title", item.title));
    copy.append(node("div", "queue-meta", item.state === "paused" ? "En pause" : "Prêt pour plus tard"));
    row.append(copy);
    row.append(node("span", `status-pill ${item.state === "paused" ? "waiting" : "idle"}`, item.urgency));
    container.append(row);
  });
  if (!queue.length) container.append(node("li", "empty", "La file produit est vide."));
}

function renderFactoryWork(items) {
  const container = $("factory-work");
  container.replaceChildren();
  $("factory-work-count").textContent = items.length;
  items.forEach((item) => {
    const row = node("div", "compact-item");
    row.append(node("strong", null, item.title));
    row.append(node("span", "queue-meta", `En cours depuis ${durationSince(item.started_at)}`));
    container.append(row);
  });
  if (!items.length) container.append(node("div", "empty", "Aucun autre travail Factory suivi."));
}

function render(data) {
  snapshot = data;
  setStatus($("factory-state"), data.factory.state, data.factory.label);
  $("focus-title").textContent = data.focus.title;
  setStatus($("focus-state"), data.focus.state, data.focus.state_label);
  $("focus-phase").textContent = data.focus.phase;
  $("focus-elapsed").textContent = durationSince(data.focus.started_at);
  $("focus-signal").textContent = signalAge(data.focus.last_signal_at);
  const steps = data.focus.steps;
  $("focus-steps").textContent = steps.total ? `${steps.completed} / ${steps.total}` : "aucune étape exposée";
  $("step-fill").style.width = steps.total ? `${Math.round((steps.completed / steps.total) * 100)}%` : "0%";
  $("needs-benjamin").textContent = data.needs_benjamin || "Rien pour l’instant";
  const delivered = data.last_delivery;
  const deliveryProof = [delivered.pr ? `PR ${delivered.pr}` : null, delivered.ci === "success" ? "CI verte" : delivered.ci ? `CI ${delivered.ci}` : null].filter(Boolean).join(" · ");
  $("last-delivery").textContent = `Dernière livraison : ${delivered.title}${deliveryProof ? ` · ${deliveryProof}` : ""}`;
  renderAgents(data.agents);
  renderQueue(data.queue);
  renderFactoryWork(data.factory_work);

  const alert = $("alert");
  if (data.warnings.length) {
    alert.textContent = `Visibilité partielle : ${data.warnings.join(" · ")}`;
    alert.classList.remove("hidden");
  } else {
    alert.classList.add("hidden");
    alert.textContent = "";
  }
  $("technical").textContent = [
    `Sources : ${Object.entries(data.sources).map(([name, ok]) => `${name}=${ok ? "ok" : "erreur"}`).join(" · ")}`,
    `Infrastructure : ${data.infrastructure.length ? data.infrastructure.map((item) => `${item.name} (${item.state})`).join(", ") : "aucune"}`,
    `Identifiant courant : ${data.focus.id || "aucun"}`,
    data.zero_token_contract.description,
  ].join("\n");
  $("refreshed").textContent = `Actualisé ${signalAge(data.generated_at)}`;
}

async function refresh() {
  if (loading) return;
  loading = true;
  $("refresh").disabled = true;
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    const alert = $("alert");
    alert.textContent = `Cockpit indisponible : ${error.message}`;
    alert.classList.remove("hidden");
    setStatus($("factory-state"), "down", "Cockpit indisponible");
  } finally {
    loading = false;
    $("refresh").disabled = false;
  }
}

$("refresh").addEventListener("click", refresh);
refresh();
setInterval(refresh, 5000);
setInterval(() => { if (snapshot) render(snapshot); }, 1000);

const $ = (id) => document.getElementById(id);
let snapshot = null;
let loading = false;
let autoRefresh = true;
let workFilter = "active";
let conversationPoll = null;

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
  return seconds < 15 ? "à l’instant" : `il y a ${durationSince(value)}`;
}

function statusClass(value) {
  return ["working", "waiting", "queued", "idle", "attention", "down"].includes(value) ? value : "waiting";
}

function setStatus(element, state, label) {
  element.className = `status-pill ${statusClass(state)}`;
  element.textContent = label;
}

function timed(element, value, prefix = "") {
  element.dataset.time = value || "";
  element.dataset.timePrefix = prefix;
  element.textContent = value ? `${prefix}${durationSince(value)}` : `${prefix}non disponible`;
}

function updateClocks() {
  document.querySelectorAll("[data-time]").forEach((element) => {
    if (element.dataset.time) element.textContent = `${element.dataset.timePrefix || ""}${durationSince(element.dataset.time)}`;
  });
  document.querySelectorAll("[data-signal-time]").forEach((element) => {
    if (element.dataset.signalTime) element.textContent = `${element.dataset.signalPrefix || ""}${signalAge(element.dataset.signalTime)}`;
  });
  if (snapshot) $("refreshed").textContent = `Actualisé ${signalAge(snapshot.generated_at)}`;
}

function renderAgents(agents) {
  const container = $("agents");
  container.replaceChildren();
  $("agent-count").textContent = agents.length;
  agents.forEach((agent) => {
    const card = node("article", "agent-card");
    const top = node("div", "agent-top");
    const identity = node("div");
    identity.append(node("div", "agent-name", agent.name), node("div", "agent-role", agent.role));
    top.append(identity, node("span", `status-pill ${statusClass(agent.state)}`, agent.state_label));
    card.append(top, node("p", "agent-objective", agent.objective), node("div", "agent-meta", agent.phase));
    const timing = node("div", "agent-meta");
    const signal = node("span", null, `Signal ${signalAge(agent.last_signal_at)}`);
    signal.dataset.signalTime = agent.last_signal_at || "";
    signal.dataset.signalPrefix = "Signal ";
    const elapsed = node("span");
    timed(elapsed, agent.started_at, " · depuis ");
    timing.append(signal, elapsed);
    card.append(timing);
    container.append(card);
  });
  if (agents.length === 1) container.append(node("div", "empty", "Aucun autre agent produit actif."));
}

function renderQueue(queue) {
  const container = $("queue");
  container.replaceChildren();
  $("queue-count").textContent = queue.length;
  queue.forEach((item) => {
    const row = node("li", "queue-item");
    const copy = node("div");
    copy.append(node("div", "queue-title", item.title), node("div", "queue-meta", item.state === "paused" ? "En pause" : "Prêt pour plus tard"));
    row.append(copy, node("span", `status-pill ${item.state === "paused" ? "waiting" : "idle"}`, item.urgency));
    container.append(row);
  });
  if (!queue.length) container.append(node("li", "empty", "La file produit est vide : rien de nouveau ne démarrera après le travail courant."));
}

function renderFactoryWork(items) {
  const container = $("factory-work");
  container.replaceChildren();
  $("factory-work-count").textContent = items.length;
  items.forEach((item) => {
    const row = node("div", "compact-item");
    row.append(node("strong", null, item.title));
    const elapsed = node("span", "queue-meta");
    timed(elapsed, item.started_at, "En cours depuis ");
    row.append(elapsed);
    container.append(row);
  });
  if (!items.length) container.append(node("div", "empty", "Aucun autre travail Factory suivi."));
}

function workMatches(item) {
  const groups = { active: ["current", "active", "ready"], queued: ["queued", "paused", "planned"], blocked: ["blocked"], delivered: ["delivered"] };
  if (workFilter !== "all" && !groups[workFilter].includes(item.state)) return false;
  const query = $("work-search").value.trim().toLocaleLowerCase("fr");
  return !query || `${item.title} ${item.product} ${item.kind}`.toLocaleLowerCase("fr").includes(query);
}

function renderProductWork(items) {
  const container = $("product-work");
  const visible = items.filter(workMatches);
  container.replaceChildren();
  $("product-work-count").textContent = `${visible.length} / ${items.length}`;
  visible.forEach((item) => {
    const card = node("article", "work-card");
    const header = node("div", "work-card-header");
    const identity = node("div");
    identity.append(node("span", "work-kind", `${item.product} · ${item.kind}`), node("h3", null, item.title));
    header.append(identity, node("span", `work-state state-${item.state}`, item.state_label));
    card.append(header);
    const proof = [item.urgency ? `Priorité ${item.urgency}` : null, item.pr ? `PR ${item.pr}` : null, item.ci === "success" ? "CI verte" : item.ci ? `CI ${item.ci}` : null].filter(Boolean);
    if (proof.length) card.append(node("p", "work-proof", proof.join(" · ")));
    const details = node("details", "work-details");
    details.append(node("summary", null, "Preuve technique"), node("div", null, `Bead ${item.id} · magasin ${item.store}`));
    card.append(details);
    container.append(card);
  });
  if (!visible.length) container.append(node("div", "empty", items.length ? "Aucun travail ne correspond à ce filtre." : "Aucun Bead produit visible."));
}

function prefillMayor(prompt) {
  $("mayor-message").value = prompt;
  $("mayor-message").focus();
  $("mayor-message").scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderDecisionAids(items) {
  const container = $("decision-aids");
  container.replaceChildren();
  $("advice-count").textContent = items.length;
  items.forEach((item) => {
    const card = node("article", `advice-card severity-${item.severity}`);
    const copy = node("div");
    copy.append(node("h3", null, item.title), node("p", null, item.explanation), node("small", null, item.action));
    const ask = node("button", "ask-mayor", "Demander au Mayor");
    ask.type = "button";
    ask.addEventListener("click", () => prefillMayor(item.prompt));
    card.append(copy, ask);
    container.append(card);
  });
}

function render(data) {
  snapshot = data;
  setStatus($("factory-state"), data.factory.state, data.factory.label);
  $("focus-title").textContent = data.focus.title;
  setStatus($("focus-state"), data.focus.state, data.focus.state_label);
  $("focus-phase").textContent = data.focus.phase;
  timed($("focus-elapsed"), data.focus.started_at);
  $("focus-signal").dataset.signalTime = data.focus.last_signal_at || "";
  $("focus-signal").textContent = signalAge(data.focus.last_signal_at);
  const steps = data.focus.steps;
  $("focus-steps").textContent = steps.total ? `${steps.completed} / ${steps.total}` : "aucune étape exposée";
  $("step-fill").style.width = steps.total ? `${Math.round((steps.completed / steps.total) * 100)}%` : "0%";
  $("needs-benjamin").textContent = data.needs_benjamin || "Rien pour l’instant";
  const delivered = data.last_delivery;
  const proof = [delivered.pr ? `PR ${delivered.pr}` : null, delivered.ci === "success" ? "CI verte" : delivered.ci ? `CI ${delivered.ci}` : null].filter(Boolean).join(" · ");
  $("last-delivery").textContent = `Dernière livraison : ${delivered.title}${proof ? ` · ${proof}` : ""}`;
  renderDecisionAids(data.decision_aids || []);
  renderAgents(data.agents || []);
  renderProductWork(data.product_work || []);
  renderQueue(data.queue || []);
  renderFactoryWork(data.factory_work || []);
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
  updateClocks();
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

function renderConversation(data) {
  const container = $("mayor-conversation");
  container.replaceChildren();
  setStatus($("mayor-chat-state"), data.state === "active" ? "working" : "idle", data.state === "active" ? "En activité" : "Disponible");
  (data.messages || []).forEach((message) => {
    const bubble = node("article", `message ${message.role === "Benjamin" ? "from-human" : "from-mayor"}`);
    bubble.append(node("strong", null, message.role), node("p", null, `${message.text}${message.truncated ? "…" : ""}`));
    container.append(bubble);
  });
  if (!(data.messages || []).length) container.append(node("div", "empty", "Aucun échange envoyé depuis ce cockpit."));
}

async function loadConversation() {
  try {
    const response = await fetch("/api/mayor/conversation", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    renderConversation(data);
  } catch (error) {
    $("mayor-conversation").replaceChildren(node("div", "empty", `Conversation indisponible : ${error.message}`));
  }
}

function pollConversation() {
  if (conversationPoll) clearInterval(conversationPoll);
  let attempts = 0;
  loadConversation();
  conversationPoll = setInterval(() => {
    attempts += 1;
    loadConversation();
    if (attempts >= 24) {
      clearInterval(conversationPoll);
      conversationPoll = null;
    }
  }, 5000);
}

async function sendMayor() {
  const message = $("mayor-message").value.trim();
  if (!message) {
    $("mayor-feedback").textContent = "Écris un message avant l’envoi.";
    return;
  }
  $("send-mayor").disabled = true;
  $("mayor-feedback").textContent = "Transmission au Mayor… cela peut consommer des tokens.";
  try {
    const response = await fetch("/api/mayor/message", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-message" },
      body: JSON.stringify({ message, intent: $("mayor-intent").value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    $("mayor-message").value = "";
    $("mayor-feedback").textContent = "Message accepté. La réponse apparaîtra à droite sans interrompre le travail en cours.";
    pollConversation();
  } catch (error) {
    $("mayor-feedback").textContent = `Envoi impossible : ${error.message}`;
  } finally {
    $("send-mayor").disabled = false;
  }
}

function humanSummary(data) {
  const advice = (data.decision_aids || []).map((item) => `- ${item.title}: ${item.action}`).join("\n");
  const queue = (data.queue || []).slice(0, 5).map((item, index) => `${index + 1}. ${item.title}`).join("\n");
  return [
    `Agent Factory — ${data.factory.label}`,
    `Objectif actuel : ${data.focus.title}`,
    `État : ${data.focus.state_label} — ${data.focus.phase}`,
    `Benjamin doit agir : ${data.needs_benjamin || "non"}`,
    `Agents visibles : ${(data.agents || []).map((agent) => `${agent.name} (${agent.state_label})`).join(", ")}`,
    `Conseils :\n${advice || "- Aucun"}`,
    `Prochains sujets :\n${queue || "- File vide"}`,
  ].join("\n");
}

$("refresh").addEventListener("click", refresh);
$("pause-refresh").addEventListener("click", () => {
  autoRefresh = !autoRefresh;
  $("pause-refresh").textContent = autoRefresh ? "Pause" : "Reprendre";
  $("pause-refresh").classList.toggle("active", !autoRefresh);
  $("refresh-mode").textContent = autoRefresh ? "Actualisation automatique toutes les 5 secondes" : "Actualisation automatique en pause";
});
$("copy-summary").addEventListener("click", async () => {
  if (!snapshot) return;
  try {
    await navigator.clipboard.writeText(humanSummary(snapshot));
    $("copy-summary").textContent = "Résumé copié";
    setTimeout(() => { $("copy-summary").textContent = "Copier le résumé"; }, 1800);
  } catch (error) {
    $("copy-summary").textContent = "Copie impossible";
  }
});
$("work-filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  workFilter = button.dataset.filter;
  document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
  if (snapshot) renderProductWork(snapshot.product_work || []);
});
$("work-search").addEventListener("input", () => { if (snapshot) renderProductWork(snapshot.product_work || []); });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => prefillMayor(button.dataset.prompt)));
$("send-mayor").addEventListener("click", sendMayor);
$("refresh-conversation").addEventListener("click", loadConversation);

$("mayor-conversation").replaceChildren(node("div", "empty", "Aucun échange chargé. Clique sur « Relire » ou envoie un message."));
refresh();
setInterval(() => { if (autoRefresh) refresh(); }, 5000);
setInterval(updateClocks, 1000);

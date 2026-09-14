const $ = (id) => document.getElementById(id);
let snapshot = null;
let loading = false;
let tokenLoaded = false;
let visitCompared = false;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function parseTime(value) { const date = value ? new Date(value) : null; return date && !Number.isNaN(date.getTime()) ? date : null; }
function durationSince(value) {
  const date = parseTime(value); if (!date) return "non disponible";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60); if (minutes < 60) return `${minutes}min ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60); return `${hours}h ${minutes % 60}min`;
}
function signalAge(value) { const date = parseTime(value); if (!date) return "inconnu"; return Date.now() - date.getTime() < 15000 ? "à l’instant" : `il y a ${durationSince(value)}`; }
function statusClass(value) { return ["working", "waiting", "queued", "idle", "attention", "down"].includes(value) ? value : "waiting"; }
function setStatus(element, state, label) { element.className = `status-pill ${statusClass(state)}`; element.textContent = label; }
function timed(element, value, prefix = "") { element.dataset.time = value || ""; element.dataset.timePrefix = prefix; element.textContent = value ? `${prefix}${durationSince(value)}` : `${prefix}non disponible`; }
function formatTokens(value) { return new Intl.NumberFormat("fr-FR", { notation: value >= 1000000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value || 0); }
function toast(message) { const box = $("toast"); box.textContent = message; box.classList.remove("hidden"); setTimeout(() => box.classList.add("hidden"), 2200); }

function updateClocks() {
  document.querySelectorAll("[data-time]").forEach((el) => { if (el.dataset.time) el.textContent = `${el.dataset.timePrefix || ""}${durationSince(el.dataset.time)}`; });
  document.querySelectorAll("[data-signal-time]").forEach((el) => { if (el.dataset.signalTime) el.textContent = `${el.dataset.signalPrefix || ""}${signalAge(el.dataset.signalTime)}`; });
  if (snapshot) $("refreshed").textContent = `Actualisé ${signalAge(snapshot.generated_at)}`;
}

function showDrawer(title, eyebrow, tabs) {
  $("drawer-title").textContent = title || "Détail"; $("drawer-eyebrow").textContent = eyebrow;
  const tabBar = $("drawer-tabs"); tabBar.replaceChildren();
  const content = $("drawer-content"); content.replaceChildren();
  const activate = (name) => {
    tabBar.querySelectorAll("button").forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
    content.replaceChildren(); const value = tabs[name];
    if (typeof value === "string") { const pre = node("div", "prose"); pre.textContent = value || "Aucune information."; content.append(pre); }
    else if (value) content.append(value);
  };
  Object.keys(tabs).forEach((name, index) => { const button = node("button", index ? "" : "active", name); button.dataset.tab = name; button.addEventListener("click", () => activate(name)); tabBar.append(button); });
  activate(Object.keys(tabs)[0]); $("detail-drawer").showModal();
}

function definitionList(entries) {
  const list = node("dl", "definition-list");
  entries.filter(([, value]) => value !== undefined && value !== null && value !== "").forEach(([label, value]) => { list.append(node("dt", "", label), node("dd", "", Array.isArray(value) ? value.join(", ") : value)); });
  return list;
}

async function openItem(item) {
  showDrawer(item.title, `${item.product || "Produit"} · chargement`, { Résumé: "Lecture de la source de vérité…" });
  try {
    const response = await fetch(`/api/item?store=${encodeURIComponent(item.store || "city")}&id=${encodeURIComponent(item.id)}`, { cache: "no-store" });
    const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    const summary = node("div", "prose"); if (data.description) summary.append(node("p", "", data.description)); summary.append(definitionList([["État", data.status], ["Priorité", data.priority], ["Responsable", data.assignee], ["Labels", data.labels]]));
    const progress = node("div", "prose"); progress.append(definitionList([["Créé", data.created_at], ["Mis à jour", data.updated_at], ["Clos", data.closed_at], ["Critères d’acceptation", data.acceptance]]));
    const relations = node("div", "stack"); (data.relations || []).forEach((relation) => relations.append(node("article", "memory-card", `${relation.direction} · ${relation.id || "?"} · ${relation.title || relation.type || "relation"}`))); if (!relations.children.length) relations.append(node("p", "muted", "Aucune relation exposée par Beads."));
    const evidence = node("div", "prose"); evidence.append(definitionList(Object.entries(data.metadata || {}))); if (data.notes) evidence.append(node("pre", "activity-log", data.notes));
    showDrawer(data.title, `${data.id} · ${data.store}`, { Résumé: summary, Progression: progress, "Sous-travaux": relations, "Preuves & notes": evidence });
  } catch (error) { showDrawer(item.title, "DÉTAIL INDISPONIBLE", { Erreur: error.message }); }
}

async function openAgent(agent) {
  if (!agent.session_id) return;
  showDrawer(agent.name, `${agent.provider || "agent"} · chargement`, { Activité: "Lecture locale à la demande…" });
  try {
    const response = await fetch(`/api/agent?id=${encodeURIComponent(agent.session_id)}`, { cache: "no-store" });
    const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    const summary = node("div", "prose"); summary.append(node("p", "", agent.objective), definitionList([["Rôle", agent.role], ["Phase", agent.phase], ["État", agent.state_label], ["Dernier signal", data.session.last_active], ["Dossier", data.session.work_dir]]), node("p", "privacy-note", data.privacy));
    const messages = node("div", "conversation"); (data.messages || []).forEach((message) => { const card = node("article", `message ${message.role === "user" ? "from-human" : "from-mayor"}`); card.append(node("strong", "", message.role === "user" ? "Instruction" : agent.name), node("p", "", message.text)); messages.append(card); }); if (!messages.children.length) messages.append(node("p", "muted", "Aucun message conversationnel utile exposé."));
    const activity = node("pre", "activity-log", data.activity);
    showDrawer(agent.name, `${data.session.provider || "agent"} · ${data.session.id}`, { Résumé: summary, Messages: messages, "Journal d’activité": activity });
  } catch (error) { showDrawer(agent.name, "AGENT INDISPONIBLE", { Erreur: error.message }); }
}

function renderAgents(agents) {
  const container = $("agents"); container.replaceChildren(); $("agent-count").textContent = agents.length; $("nav-agent-count").textContent = `${agents.length} visibles`;
  agents.forEach((agent) => { const card = node("article", "agent-card clickable"); const top = node("div", "agent-top"); const identity = node("div"); identity.append(node("div", "agent-name", agent.name), node("div", "agent-role", `${agent.role}${agent.provider ? ` · ${agent.provider}` : ""}`)); top.append(identity, node("span", `status-pill ${statusClass(agent.state)}`, agent.state_label)); card.append(top, node("p", "agent-objective", agent.objective), node("div", "agent-meta", agent.phase)); const timing = node("div", "agent-meta"); const signal = node("span", "", `Signal ${signalAge(agent.last_signal_at)}`); signal.dataset.signalTime = agent.last_signal_at || ""; signal.dataset.signalPrefix = "Signal "; const elapsed = node("span"); timed(elapsed, agent.started_at, " · depuis "); timing.append(signal, elapsed); card.append(timing); card.addEventListener("click", () => openAgent(agent)); container.append(card); });
}

function renderQueue(queue) {
  const container = $("queue"); container.replaceChildren(); $("queue-count").textContent = queue.length;
  queue.slice(0, 6).forEach((item) => { const row = node("li", "queue-item"); const copy = node("div"); copy.append(node("div", "queue-title", item.title), node("div", "queue-meta", item.state === "paused" ? "En pause" : "Prêt pour plus tard")); row.append(copy, node("span", `status-pill ${item.state === "paused" ? "waiting" : "idle"}`, item.urgency)); if (item.id) { row.classList.add("clickable"); row.addEventListener("click", () => openItem({ ...item, store: "city", product: "SayMyName" })); } container.append(row); });
  if (!queue.length) container.append(node("li", "empty", "File vide : aucun nouveau résultat ne démarrera après le travail courant."));
}

function renderDecisionAids(items) {
  const container = $("decision-aids"); container.replaceChildren(); $("advice-count").textContent = items.length;
  items.forEach((item) => { const card = node("article", `advice-card severity-${item.severity}`); const copy = node("div"); copy.append(node("h3", "", item.title), node("p", "", item.explanation), node("small", "", item.action)); const ask = node("button", "ask-mayor", "Demander au Mayor"); ask.addEventListener("click", () => { $("mayor-message").value = item.prompt; $("mayor-message").focus(); }); card.append(copy, ask); container.append(card); });
}

const boardDefinitions = [
  ["active", "En livraison", ["current", "active"]], ["ready", "Prêt", ["ready"]], ["queued", "À venir", ["queued", "planned"]], ["paused", "En attente de preuve", ["paused"]], ["blocked", "Bloqué", ["blocked"]], ["delivered", "Livré", ["delivered"]],
];
function renderBoard(items) {
  const query = $("work-search").value.trim().toLocaleLowerCase("fr"); const board = $("work-board"); board.replaceChildren();
  boardDefinitions.forEach(([key, label, states]) => { const column = node("section", "board-column"); const filtered = items.filter((item) => states.includes(item.state) && (!query || `${item.title} ${item.product}`.toLocaleLowerCase("fr").includes(query))); const header = node("div", "column-title"); header.append(node("h2", "", label), node("span", "count", filtered.length)); column.append(header); const stack = node("div", "board-stack"); filtered.forEach((item) => { const card = node("article", `work-card clickable state-border-${item.state}`); card.append(node("span", "work-kind", `${item.product} · ${item.kind}`), node("h3", "", item.title)); const proof = [item.urgency && `Priorité ${item.urgency}`, item.pr && `PR ${item.pr}`, item.ci === "success" && "CI verte"].filter(Boolean); if (proof.length) card.append(node("p", "work-proof", proof.join(" · "))); card.addEventListener("click", () => openItem(item)); stack.append(card); }); if (!filtered.length) stack.append(node("div", "column-empty", "—")); column.append(stack); board.append(column); });
}

function renderMemory(memory) {
  $("product-thesis").textContent = memory.thesis; const roadmap = $("roadmap"); roadmap.replaceChildren();
  const stages = [["now", "Maintenant", "Résultat en livraison"], ["next", "Ensuite", "Les prochaines preuves utiles"], ["later", "Plus tard", "Direction acceptée, pas encore engagée"], ["evidence", "Après preuve", "Dépend d’un apprentissage client"]];
  stages.forEach(([key, title, subtitle]) => { const column = node("section", "roadmap-column"); column.append(node("p", "eyebrow", title.toUpperCase()), node("h2", "", subtitle)); memory.roadmap.filter((item) => item.stage === key).forEach((item) => { const card = node("article", "roadmap-card clickable"); card.append(node("span", "roadmap-number", String(item.order)), node("p", "", item.title)); card.addEventListener("click", () => showDrawer(item.title, `ROADMAP · ${title}`, { Résumé: item.title, Source: item.source })); column.append(card); }); roadmap.append(column); });
  const pending = memory.decisions.filter((item) => item.status === "pending"); const accepted = memory.decisions.filter((item) => item.status === "accepted"); $("pending-count").textContent = pending.length; $("accepted-count").textContent = accepted.length; $("nav-decision-count").textContent = `${pending.length} à trancher`; $("today-pending").textContent = pending.length;
  [["pending-decisions", pending], ["accepted-decisions", accepted]].forEach(([id, values]) => { const container = $(id); container.replaceChildren(); values.forEach((item) => { const card = node("article", `memory-card clickable ${item.status}`); card.append(node("h3", "", item.title), node("p", "", item.detail)); card.addEventListener("click", () => showDrawer(item.title, item.status === "pending" ? "DÉCISION À PRENDRE" : "DÉCISION ACQUISE", { Contexte: item.detail, Source: item.source })); container.append(card); }); });
}

function compareVisit(data) {
  if (visitCompared) return; visitCompared = true; const key = "factory-cockpit-last-visit-v2"; const current = { focus: data.focus.id, state: data.focus.state, delivery: data.last_delivery.id, pending: data.product_memory.decisions.filter((item) => item.status === "pending").length, at: data.generated_at }; let previous = null; try { previous = JSON.parse(localStorage.getItem(key)); } catch (_) {}
  const changes = []; if (previous) { if (previous.focus !== current.focus) changes.push("le résultat en cours a changé"); else if (previous.state !== current.state) changes.push("son état a évolué"); if (previous.delivery !== current.delivery) changes.push("une nouvelle livraison est enregistrée"); if (previous.pending !== current.pending) changes.push("la liste des décisions a changé"); }
  if (changes.length) { $("since-visit").textContent = `Depuis ta dernière visite : ${changes.join(" · ")}.`; $("since-visit").classList.remove("hidden"); } localStorage.setItem(key, JSON.stringify(current));
}

function render(data) {
  snapshot = data; setStatus($("factory-state"), data.factory.state, data.factory.label); $("focus-title").textContent = data.focus.title; setStatus($("focus-state"), data.focus.state, data.focus.state_label); $("focus-phase").textContent = data.focus.phase; timed($("focus-elapsed"), data.focus.started_at); $("focus-signal").dataset.signalTime = data.focus.last_signal_at || ""; $("focus-signal").textContent = signalAge(data.focus.last_signal_at); const steps = data.focus.steps; $("focus-steps").textContent = steps.total ? `${steps.completed} / ${steps.total}` : "aucune étape exposée"; $("step-fill").style.width = steps.total ? `${Math.round((steps.completed / steps.total) * 100)}%` : "0%"; $("needs-benjamin").textContent = data.needs_benjamin || "Rien pour l’instant"; const delivered = data.last_delivery; $("last-delivery").textContent = `Dernière livraison : ${delivered.title}${delivered.pr ? ` · PR ${delivered.pr}` : ""}${delivered.ci === "success" ? " · CI verte" : ""}`;
  renderDecisionAids(data.decision_aids || []); renderQueue(data.queue || []); renderMemory(data.product_memory); renderBoard(data.product_work || []); renderAgents(data.agents || []);
  const factoryWork = $("factory-work"); factoryWork.replaceChildren(); (data.factory_work || []).forEach((item) => factoryWork.append(node("div", "compact-item", item.title))); if (!factoryWork.children.length) factoryWork.append(node("p", "muted", "Aucun autre travail Factory.")); const infrastructure = $("infrastructure"); infrastructure.replaceChildren(); (data.infrastructure || []).forEach((item) => infrastructure.append(node("div", "compact-item", `${item.name} · ${item.state}`)));
  const alert = $("alert"); if (data.warnings.length) { alert.textContent = `Visibilité partielle : ${data.warnings.join(" · ")}`; alert.classList.remove("hidden"); } else alert.classList.add("hidden"); compareVisit(data); updateClocks();
}

async function refresh() { if (loading) return; loading = true; $("refresh").disabled = true; try { const response = await fetch("/api/snapshot", { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); render(await response.json()); } catch (error) { $("alert").textContent = `Cockpit indisponible : ${error.message}`; $("alert").classList.remove("hidden"); setStatus($("factory-state"), "down", "Cockpit indisponible"); } finally { loading = false; $("refresh").disabled = false; } }

async function loadTokens() {
  $("refresh-tokens").disabled = true; $("token-sessions").replaceChildren(node("div", "empty", "Lecture des compteurs locaux…"));
  try { const response = await fetch("/api/tokens", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); tokenLoaded = true; const cards = $("token-summary").children; cards[1].querySelector("strong").textContent = formatTokens(data.factory.known_total_tokens); cards[1].querySelector("small").textContent = data.factory.coverage; cards[2].querySelector("strong").textContent = formatTokens(data.host_codex_24h.total_tokens); cards[2].querySelector("small").textContent = `${data.host_codex_24h.sessions} sessions Codex locales`; const table = $("token-sessions"); table.replaceChildren(); (data.factory.sessions || []).forEach((entry) => { const row = node("article", "token-row"); const identity = node("div"); identity.append(node("strong", "", entry.name), node("small", "", `${entry.provider} · ${entry.confidence}`)); const total = node("strong", "token-total", formatTokens(entry.usage.total_tokens)); const breakdown = node("div", "token-breakdown", [entry.usage.input_tokens !== undefined && `entrée ${formatTokens(entry.usage.input_tokens)}`, entry.usage.cached_input_tokens !== undefined && `cache ${formatTokens(entry.usage.cached_input_tokens)}`, entry.usage.output_tokens !== undefined && `sortie ${formatTokens(entry.usage.output_tokens)}`, entry.usage.reasoning_output_tokens !== undefined && `raisonnement ${formatTokens(entry.usage.reasoning_output_tokens)}`].filter(Boolean).join(" · ") || "total estimé"); row.append(identity, total, breakdown); table.append(row); }); if (!table.children.length) table.append(node("div", "empty", "Aucun compteur Factory corrélé.")); const notes = $("token-notes"); notes.replaceChildren(); data.notes.forEach((note) => notes.append(node("p", "", note))); } catch (error) { $("token-sessions").replaceChildren(node("div", "empty", `Compteurs indisponibles : ${error.message}`)); } finally { $("refresh-tokens").disabled = false; }
}

function renderConversation(data) { const container = $("mayor-conversation"); container.replaceChildren(); setStatus($("mayor-chat-state"), data.state === "active" ? "working" : "idle", data.state === "active" ? "En activité" : "Disponible"); (data.messages || []).forEach((message) => { const bubble = node("article", `message ${message.role === "Benjamin" ? "from-human" : "from-mayor"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text)); container.append(bubble); }); if (!container.children.length) container.append(node("div", "empty", "Aucun échange récent depuis ce cockpit.")); }
async function loadConversation() { try { const response = await fetch("/api/mayor/conversation", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); renderConversation(data); } catch (error) { $("mayor-conversation").replaceChildren(node("div", "empty", `Conversation indisponible : ${error.message}`)); } }
async function sendMayor() { const message = $("mayor-message").value.trim(); if (!message) return; $("send-mayor").disabled = true; $("mayor-feedback").textContent = "Transmission au Mayor…"; try { const response = await fetch("/api/mayor/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-message" }, body: JSON.stringify({ message, intent: $("mayor-intent").value }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); $("mayor-message").value = ""; $("mayor-feedback").textContent = "Message accepté."; setTimeout(loadConversation, 3000); } catch (error) { $("mayor-feedback").textContent = `Envoi impossible : ${error.message}`; } finally { $("send-mayor").disabled = false; } }
function humanSummary(data) { return [`Agent Factory — ${data.factory.label}`, `Résultat : ${data.focus.title}`, `État : ${data.focus.state_label} — ${data.focus.phase}`, `Benjamin doit agir : ${data.needs_benjamin || "non"}`, `Agents : ${(data.agents || []).map((agent) => `${agent.name} (${agent.state_label})`).join(", ")}`, `Décisions produit ouvertes : ${data.product_memory.decisions.filter((item) => item.status === "pending").length}`, `Prochains sujets :\n${(data.queue || []).slice(0, 5).map((item, i) => `${i + 1}. ${item.title}`).join("\n") || "- File vide"}`].join("\n"); }

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button)); document.querySelectorAll(".view").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === button.dataset.view)); if (button.dataset.view === "tokens" && !tokenLoaded) loadTokens(); window.scrollTo({ top: 0, behavior: "smooth" }); }));
$("refresh").addEventListener("click", refresh); $("refresh-tokens").addEventListener("click", loadTokens); $("work-search").addEventListener("input", () => snapshot && renderBoard(snapshot.product_work || [])); $("focus-card").addEventListener("click", () => snapshot?.focus?.id && openItem({ ...snapshot.focus, store: "city" })); $("focus-card").addEventListener("keydown", (event) => { if (event.key === "Enter") $("focus-card").click(); }); $("close-drawer").addEventListener("click", () => $("detail-drawer").close()); $("detail-drawer").addEventListener("click", (event) => { if (event.target === $("detail-drawer")) $("detail-drawer").close(); });
$("copy-summary").addEventListener("click", async () => { if (snapshot) { await navigator.clipboard.writeText(humanSummary(snapshot)); toast("Point de situation copié"); } }); $("copy-po-prompt").addEventListener("click", async () => { if (!snapshot) return; const prompt = `Agis comme mon PO SayMyName. À partir de la mémoire produit durable et de l'état actuel, discutons du prochain choix sans lancer de travail. Résultat actuel : ${snapshot.focus.title}. Décisions ouvertes : ${snapshot.product_memory.decisions.filter((item) => item.status === "pending").map((item) => item.title).join("; ")}.`; await navigator.clipboard.writeText(prompt); toast("Prompt PO copié"); });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("mayor-message").value = button.dataset.prompt; $("mayor-message").focus(); })); $("send-mayor").addEventListener("click", sendMayor); $("refresh-conversation").addEventListener("click", loadConversation);
$("mayor-conversation").replaceChildren(node("div", "empty", "Clique sur « Relire » pour charger les échanges.")); refresh(); setInterval(refresh, 5000); setInterval(updateClocks, 1000);

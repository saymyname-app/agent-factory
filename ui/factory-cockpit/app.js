const $ = (id) => document.getElementById(id);
let snapshot = null;
let loading = false;
let tokenLoaded = false;
let visitCompared = false;
let poPoll = null;
let decisionPoll = null;
let currentDecision = null;
let currentPOKey = null;
let poIndex = [];
let knownUnreadReplies = null;

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
function seenDecisionAt(id) { return localStorage.getItem(`factory-cockpit-decision-seen:${id}`) || ""; }
function hasUnreadReply(item) { return item?.last_role === "PO" && Boolean(item.last_message_at) && item.last_message_at > seenDecisionAt(item.decision_id); }
function unreadReplyCount() { return poIndex.filter((item) => item.kind === "decision" && hasUnreadReply(item)).length; }
function updateDecisionNav(pendingCount = null) { const unread = unreadReplyCount(); const total = pendingCount ?? snapshot?.product_memory?.decisions.filter((item) => item.status === "pending").length ?? 0; $("nav-decision-count").textContent = unread ? `${unread} réponse${unread > 1 ? "s" : ""} PO` : `${total} à trancher`; }

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
  const pending = memory.decisions.filter((item) => item.status === "pending"); const accepted = memory.decisions.filter((item) => item.status === "accepted"); $("pending-count").textContent = `${pending.length} à décider`; $("accepted-count").textContent = accepted.length; updateDecisionNav(pending.length); $("today-pending").textContent = pending.length;
  const domainLabels = { enterprise: "Entreprise", product: "Produit", project: "Projet" };
  const decisionCard = (item) => { const card = node("article", `memory-card ${item.status}`); card.append(node("h3", "", item.title), node("p", "", item.detail)); if (item.status === "pending") { const open = node("button", "primary", "Ouvrir la décision"); open.addEventListener("click", () => openDecisionWorkspace(item)); card.append(open); } else { card.classList.add("clickable"); card.addEventListener("click", () => showDrawer(item.title, "DÉCISION ACQUISE", { Contexte: item.detail, Source: item.source })); } return card; };
  Object.entries(domainLabels).forEach(([domain]) => { const values = pending.filter((item) => item.domain === domain); $(`${domain}-decision-count`).textContent = values.length; const container = $(`${domain}-decisions`); container.replaceChildren(...values.map(decisionCard)); if (!values.length) container.append(node("p", "muted", "Aucune décision ouverte.")); });
  const businessOnly = $("business-decisions"); businessOnly.replaceChildren(...pending.filter((item) => item.domain === "enterprise").map(decisionCard)); $("business-decision-count").textContent = `${pending.filter((item) => item.domain === "enterprise").length} choix entreprise`;
  const acceptedContainer = $("accepted-decisions"); acceptedContainer.replaceChildren(...accepted.map(decisionCard));
}

function renderBusiness(memory) {
  $("business-north-star").textContent = memory.business?.north_star || "Objectif entreprise non documenté.";
  const labels = { now: "En validation", next: "Ensuite", later: "Planifié", evidence: "Après preuve" }; const flow = $("business-objectives"); flow.replaceChildren();
  (memory.business?.objectives || []).forEach((item, index, all) => { const objective = node("article", `business-objective status-${item.status}`); objective.append(node("small", "", labels[item.status] || item.status), node("h3", "", item.title), node("p", "", item.detail)); flow.append(objective); if (index < all.length - 1) flow.append(node("span", "flow-arrow", "→")); });
}

function renderProject(memory, data) {
  const legend = $("capability-legend"); legend.replaceChildren(); [["now", "En construction"], ["next", "Ensuite"], ["later", "Planifié"], ["evidence", "Après preuve"]].forEach(([status, label]) => legend.append(node("span", `legend-${status}`, label)));
  const graph = $("capability-graph"); graph.replaceChildren();
  const statusLabels = { now: "En construction", next: "Ensuite", later: "Planifié", evidence: "Après preuve" };
  (memory.project_graph?.nodes || []).forEach((item) => { const card = node("article", `capability-node status-${item.status}`); card.dataset.nodeId = item.id; card.append(node("span", "capability-area", item.area), node("strong", "", item.title), node("small", "", statusLabels[item.status] || item.status)); card.addEventListener("click", () => { const roadmap = memory.roadmap.find((entry) => entry.order === item.roadmap); showDrawer(item.title, `CAPACITÉ · ${item.area}`, { Résumé: roadmap?.title || item.title, Dépendances: (memory.project_graph.edges || []).filter((edge) => edge.includes(item.id)).map((edge) => edge.join(" → ")).join("\n") || "Aucune relation déclarée." }); }); graph.append(card); });
  const graphNodes = memory.project_graph?.nodes || [];
  const edges = node("div", "graph-edges"); (memory.project_graph?.edges || []).forEach(([from, to]) => { const source = graphNodes.find((item) => item.id === from); const target = graphNodes.find((item) => item.id === to); edges.append(node("span", "", `${source?.title || from} → ${target?.title || to}`)); }); graph.append(edges);
  const now = (memory.project_graph?.nodes || []).filter((item) => item.status === "now").length; $("project-progress").textContent = `${now} capacité${now > 1 ? "s" : ""} en construction`;

  const lifecycle = $("reference-lifecycle"); lifecycle.replaceChildren(); [["Parler", "Besoin avec le PO"], ["Structurer", "Carte et parcours"], ["Valider", "Choix humain"], ["Référencer", "Documentation qui fait foi"], ["Livrer", "Factory dans le bon ordre"]].forEach(([title, detail], index, all) => { const card = node("article", `workflow-node ${index < 3 ? "done" : "upcoming"}`); card.append(node("span", "workflow-index", String(index + 1)), node("strong", "", title), node("small", "", detail)); lifecycle.append(card); if (index < all.length - 1) lifecycle.append(node("span", "workflow-arrow", "→")); });
  const reference = $("product-reference"); reference.replaceChildren(); (memory.product_reference || []).forEach((item) => { const card = node("article", `reference-card status-${item.status}`); card.append(node("span", "inventory-status", item.status_label), node("h3", "", item.title), node("p", "", item.detail)); const open = node("button", "", "Consulter"); open.addEventListener("click", () => showDrawer(item.title, "RÉFÉRENCE PRODUIT", { Contenu: item.detail, État: item.status_label, Source: item.source })); card.append(open); reference.append(card); });
  const inventory = $("view-inventory"); inventory.replaceChildren(); const inventoryLabels = { existing: "Existe dans le code", building: "En construction", next: "Ensuite", planned: "Planifié", evidence: "Après preuve" }; (memory.view_inventory || []).forEach((item) => { const card = node("article", `inventory-item inventory-${item.status}`); card.append(node("span", "inventory-status", inventoryLabels[item.status] || item.status), node("h3", "", item.area), node("p", "", (item.views || []).join(" · "))); inventory.append(card); });
  const freshness = memory.inventory_freshness || {}; setStatus($("inventory-freshness"), freshness.state === "review_due" ? "attention" : "idle", freshness.label || "État inconnu");
  const remote = data.remote_access || {}; $("mobile-access-copy").textContent = remote.enabled ? `Disponible uniquement sur ton tailnet : ${remote.url}` : "Accès distant non activé; le cockpit reste limité à ce PC."; const link = $("mobile-access-link"); link.classList.toggle("hidden", !remote.enabled); if (remote.enabled) link.href = remote.url;
}

function renderWorkflow(memory, data) {
  const stages = memory.delivery_workflow || []; let active = 0;
  if (data.focus?.id) active = data.focus.state === "queued" ? 2 : data.focus.state === "working" ? (data.agents.length ? 4 : 3) : data.focus.steps?.complete ? 5 : 2;
  const flow = $("delivery-workflow"); flow.replaceChildren(); stages.forEach((item, index) => { const state = index < active ? "done" : index === active ? "active" : "upcoming"; const card = node("article", `workflow-node ${state}`); card.append(node("span", "workflow-index", String(index + 1)), node("strong", "", item.title), node("small", "", item.detail)); if (state === "active") card.append(node("span", "workflow-live", "Ici maintenant")); flow.append(card); if (index < stages.length - 1) flow.append(node("span", "workflow-arrow", "→")); });
  const context = $("context-graph"); context.replaceChildren(); [["Benjamin", "Intentions et décisions", "human"], ["PO GPT", "Vision, roadmap et mémoire", "po"], ["Mayor", "Résultat autorisé et livraison", "mayor"], ["Beads", "Travail et dépendances", "beads"], ["Agents", "Une tâche bornée", "agents"], ["GitHub", "Preuve livrée", "github"]].forEach(([title, detail, kind], index, all) => { const card = node("article", `context-node ${kind}`); card.append(node("strong", "", title), node("small", "", detail)); context.append(card); if (index < all.length - 1) context.append(node("span", "context-arrow", "→")); });
  $("upper-context").replaceChildren(node("span", "context-chip", "Thèse produit"), node("span", "context-chip", `${memory.roadmap.length} résultats roadmap`), node("span", "context-chip", `${memory.decisions.filter((item) => item.status === "pending").length} décisions ouvertes`), node("span", "context-chip", "Stratégie et règles d’accès"));
  $("execution-context").replaceChildren(node("span", "context-chip", data.focus.title), node("span", "context-chip", data.focus.phase), node("span", "context-chip", `${data.focus.steps.completed}/${data.focus.steps.total} étapes prouvées`), node("span", "context-chip", `${data.agents.length} agents visibles`));
}

function activateView(view) {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === view));
  if (view === "tokens" && !tokenLoaded) loadTokens();
  if (view === "po") loadPOConversation();
  if (view === "project") loadPreviewStatus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function decisionPrompt(decision) { return `Aide-moi à prendre cette décision : ${decision.title}\n\nReformule le choix, propose les options utiles, recommande-en une avec ses compromis, puis pose-moi la prochaine question nécessaire.`; }
async function openDecisionWorkspace(decision) { clearTimeout(decisionPoll); currentDecision = decision; $("decision-feedback").textContent = ""; $("decision-workspace-domain").textContent = `DÉCISION ${decision.domain.toUpperCase()}`; $("decision-workspace-title").textContent = decision.title; $("decision-workspace-detail").textContent = decision.detail; $("decision-message").value = decisionPrompt(decision); $("decision-workspace").classList.remove("hidden"); document.querySelector(".decision-domain-grid").classList.add("hidden"); document.querySelector(".accepted-archive").classList.add("hidden"); await loadDecisionConversation(); $("decision-workspace").scrollIntoView({ behavior: "smooth" }); }
function closeDecisionWorkspace() { clearTimeout(decisionPoll); currentDecision = null; $("decision-workspace").classList.add("hidden"); document.querySelector(".decision-domain-grid").classList.remove("hidden"); document.querySelector(".accepted-archive").classList.remove("hidden"); }

function renderPO(data) {
  currentPOKey = data.key || currentPOKey; const working = ["queued", "running"].includes(data.status); setStatus($("po-state"), working ? "working" : data.status === "error" ? "down" : "idle", working ? "Le PO réfléchit…" : data.status === "error" ? "Erreur" : "Prêt"); $("nav-po-state").textContent = (data.conversations || []).some((item) => ["queued", "running"].includes(item.status)) ? "GPT · répond…" : "GPT · prêt"; $("send-po").disabled = working;
  const messages = $("po-messages"); messages.replaceChildren(); (data.messages || []).forEach((message) => { const bubble = node("article", `po-message ${message.role === "Benjamin" ? "from-human" : "from-po"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text)); if (message.intent === "record") bubble.append(node("small", "", "Demande d’enregistrement")); messages.append(bubble); }); if (!messages.children.length) messages.append(node("div", "empty", "Commence une discussion générale ou ouvre une décision à trancher.")); if (working) messages.append(node("div", "po-thinking", "Le PO lit le contexte et prépare sa réponse…")); if (data.error) messages.append(node("div", "alert", data.error)); messages.scrollTop = messages.scrollHeight;
  $("copy-po-thread").disabled = !data.thread_id; $("copy-po-thread").dataset.threadId = data.thread_id || ""; $("po-token-usage").textContent = data.usage ? `${formatTokens(data.usage.total_tokens)} tokens · compteur local` : "Aucun token mesuré"; const codex = $("open-po-codex"); codex.classList.toggle("hidden", !data.codex_url); if (data.codex_url) codex.href = data.codex_url;
  const list = $("po-conversation-list"); list.replaceChildren(); (data.conversations || []).forEach((item) => { const card = node("button", `conversation-card ${item.key === data.key ? "active" : ""}`); card.append(node("strong", "", item.title), node("small", "", `${item.kind === "decision" ? "Décision" : "Général"} · ${item.status === "not_started" ? "pas démarrée" : item.status} · ${item.usage ? `${formatTokens(item.usage.total_tokens)} tokens` : "0 token mesuré"}`)); card.addEventListener("click", () => item.decision_id ? openDecisionById(item.decision_id) : loadPOConversation(item.key)); list.append(card); }); if (!list.children.length) list.append(node("p", "muted", "Aucune session. Les décisions en créent une seulement au premier envoi."));
  if (working) { clearTimeout(poPoll); poPoll = setTimeout(loadPOConversation, 2500); }
}

async function loadPOConversation(key = null) { try { const query = key ? `?key=${encodeURIComponent(key)}` : ""; const response = await fetch(`/api/po/conversation${query}`, { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); renderPO(data); } catch (error) { $("po-feedback").textContent = `PO indisponible : ${error.message}`; } }
async function sendPO() { const message = $("po-message").value.trim(); if (!message) { $("po-feedback").textContent = "Écris un message ou une réponse."; return; } $("send-po").disabled = true; $("po-feedback").textContent = "Message remis au PO…"; try { const response = await fetch("/api/po/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: JSON.stringify({ message, intent: $("po-intent").value, conversation_key: currentPOKey }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); currentPOKey = data.key; $("po-message").value = ""; $("po-feedback").textContent = "Le PO prépare sa réponse; tu peux ouvrir un autre sujet pendant ce temps."; loadPOConversation(currentPOKey); } catch (error) { $("po-feedback").textContent = `Envoi impossible : ${error.message}`; $("send-po").disabled = false; } }
async function newPOConversation() { try { const response = await fetch("/api/po/new", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: "{}" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); currentPOKey = data.key; $("po-feedback").textContent = "Espace prêt. Aucune session ni token avant ton premier envoi."; loadPOConversation(currentPOKey); } catch (error) { $("po-feedback").textContent = `Impossible : ${error.message}`; } }

function openDecisionById(id) { const decision = snapshot?.product_memory?.decisions.find((item) => item.id === id); if (decision) { activateView("decisions"); openDecisionWorkspace(decision); } }
function renderDecisionSwitcher(data) {
  poIndex = data.conversations || poIndex; const pending = snapshot?.product_memory?.decisions.filter((item) => item.status === "pending") || []; const switcher = $("decision-switcher"); switcher.replaceChildren(); let workingCount = 0;
  pending.forEach((decision) => { const conversation = poIndex.find((item) => item.decision_id === decision.id); const working = ["queued", "running"].includes(conversation?.status); const unread = decision.id !== currentDecision?.id && hasUnreadReply(conversation); if (working) workingCount += 1; const button = node("button", `decision-switch ${decision.id === currentDecision?.id ? "active" : ""} ${unread ? "unread" : ""}`); button.append(node("span", "decision-switch-domain", decision.domain), node("strong", "", decision.title), node("small", "", unread ? "Réponse du PO" : working ? "PO travaille…" : conversation ? "Conversation en cours" : "Pas lancée")); button.addEventListener("click", () => openDecisionWorkspace(decision)); switcher.append(button); });
  const unread = unreadReplyCount(); $("decision-switcher-summary").textContent = [workingCount && `${workingCount} en cours`, unread && `${unread} réponse${unread > 1 ? "s" : ""}`].filter(Boolean).join(" · ") || "Passe d’un sujet à l’autre en un clic"; updateDecisionNav(pending.length);
}
function renderDecisionConversation(data) {
  const working = ["queued", "running"].includes(data.status); const lastPO = [...(data.messages || [])].reverse().find((message) => message.role === "PO" && message.timestamp); if (lastPO && currentDecision) localStorage.setItem(`factory-cockpit-decision-seen:${currentDecision.id}`, lastPO.timestamp); renderDecisionSwitcher(data); const messages = $("decision-messages"); messages.replaceChildren();
  (data.messages || []).forEach((message) => { const bubble = node("article", `po-message ${message.role === "Benjamin" ? "from-human" : "from-po"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text)); messages.append(bubble); }); if (!messages.children.length) messages.append(node("div", "empty", "Cette décision n’a pas encore de session. Elle sera créée uniquement quand tu enverras le premier message.")); if (working) messages.append(node("div", "po-thinking", "Le PO travaille sur cette décision; ouvre un autre sujet avec la barre ci-dessus."));
  $("send-decision-po").disabled = working; $("send-decision-po").textContent = data.status === "not_started" ? "Commencer avec le PO" : "Envoyer au PO"; setStatus($("decision-current-state"), working ? "working" : data.status === "error" ? "down" : "idle", working ? "PO travaille" : data.status === "not_started" ? "Pas lancée" : data.status === "error" ? "Erreur" : "À toi"); $("decision-token-usage").textContent = data.usage ? `${formatTokens(data.usage.total_tokens)} tokens · compteur local` : "Aucun token consommé"; $("copy-decision-thread").disabled = !data.thread_id; $("copy-decision-thread").dataset.threadId = data.thread_id || ""; const link = $("open-decision-codex"); link.classList.toggle("hidden", !data.codex_url); if (data.codex_url) link.href = data.codex_url; if (data.error) $("decision-feedback").textContent = data.error;
  clearTimeout(decisionPoll); if (currentDecision) decisionPoll = setTimeout(loadDecisionConversation, 3000);
}
async function loadDecisionConversation() { if (!currentDecision) return; try { const expectedId = currentDecision.id; const response = await fetch(`/api/po/conversation?decision_id=${encodeURIComponent(expectedId)}`, { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); if (currentDecision?.id === expectedId) renderDecisionConversation(data); } catch (error) { $("decision-feedback").textContent = `PO indisponible : ${error.message}`; } }
async function loadPOIndex() { try { const response = await fetch("/api/po/index", { cache: "no-store" }); const data = await response.json(); if (!response.ok) return; poIndex = data.conversations || []; const unread = unreadReplyCount(); const added = knownUnreadReplies === null ? 0 : unread - knownUnreadReplies; if (added > 0) toast(`${added} nouvelle${added > 1 ? "s" : ""} réponse${added > 1 ? "s" : ""} du PO`); knownUnreadReplies = unread; updateDecisionNav(); if (currentDecision) renderDecisionSwitcher({ conversations: poIndex }); } catch (_) {} }
async function sendDecisionPO() { if (!currentDecision) return; const message = $("decision-message").value.trim(); if (!message) return; $("send-decision-po").disabled = true; $("decision-feedback").textContent = "Session dédiée remise au PO…"; try { const response = await fetch("/api/po/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: JSON.stringify({ message, intent: $("decision-intent").value, decision_id: currentDecision.id }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); $("decision-message").value = ""; $("decision-feedback").textContent = "Le PO répond ici; les autres décisions restent disponibles."; loadDecisionConversation(); } catch (error) { $("decision-feedback").textContent = `Envoi impossible : ${error.message}`; $("send-decision-po").disabled = false; } }

function renderPreview(data) { const busy = Boolean(data.action); setStatus($("preview-state"), busy ? "working" : data.state === "running" ? "idle" : data.error ? "down" : "waiting", busy ? `${data.action}…` : data.state === "running" ? "Disponible" : "Arrêtée"); $("preview-policy").textContent = data.version_policy; $("preview-frontend").textContent = `${data.frontend_health} · ${String(data.frontend_sha).slice(0, 8)}`; $("preview-backend").textContent = `${data.backend_health} · ${String(data.backend_sha).slice(0, 8)}`; [$("start-preview"), $("restart-preview"), $("stop-preview")].forEach((button) => { button.disabled = busy; }); const open = $("open-preview"); open.classList.toggle("hidden", data.state !== "running"); open.href = data.browser_url; $("preview-feedback").textContent = data.error || (busy ? "Le contrôle sécurisé prépare la bonne version…" : ""); if (busy) setTimeout(loadPreviewStatus, 2500); }
async function loadPreviewStatus() { try { const response = await fetch("/api/preview/status", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); renderPreview(data); } catch (error) { $("preview-feedback").textContent = `État indisponible : ${error.message}`; } }
async function previewAction(action) { $("preview-feedback").textContent = `Action ${action} demandée…`; try { const response = await fetch("/api/preview/action", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-preview-action" }, body: JSON.stringify({ action }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); loadPreviewStatus(); } catch (error) { $("preview-feedback").textContent = `Impossible : ${error.message}`; } }

function compareVisit(data) {
  if (visitCompared) return; visitCompared = true; const key = "factory-cockpit-last-visit-v2"; const current = { focus: data.focus.id, state: data.focus.state, delivery: data.last_delivery.id, pending: data.product_memory.decisions.filter((item) => item.status === "pending").length, at: data.generated_at }; let previous = null; try { previous = JSON.parse(localStorage.getItem(key)); } catch (_) {}
  const changes = []; if (previous) { if (previous.focus !== current.focus) changes.push("le résultat en cours a changé"); else if (previous.state !== current.state) changes.push("son état a évolué"); if (previous.delivery !== current.delivery) changes.push("une nouvelle livraison est enregistrée"); if (previous.pending !== current.pending) changes.push("la liste des décisions a changé"); }
  if (changes.length) { $("since-visit").textContent = `Depuis ta dernière visite : ${changes.join(" · ")}.`; $("since-visit").classList.remove("hidden"); } localStorage.setItem(key, JSON.stringify(current));
}

function render(data) {
  snapshot = data; setStatus($("factory-state"), data.factory.state, data.factory.label); $("focus-title").textContent = data.focus.title; setStatus($("focus-state"), data.focus.state, data.focus.state_label); $("focus-phase").textContent = data.focus.phase; timed($("focus-elapsed"), data.focus.started_at); $("focus-signal").dataset.signalTime = data.focus.last_signal_at || ""; $("focus-signal").textContent = signalAge(data.focus.last_signal_at); const steps = data.focus.steps; $("focus-steps").textContent = steps.total ? `${steps.completed} / ${steps.total}` : "aucune étape exposée"; $("step-fill").style.width = steps.total ? `${Math.round((steps.completed / steps.total) * 100)}%` : "0%"; $("needs-benjamin").textContent = data.needs_benjamin || "Rien pour l’instant"; const delivered = data.last_delivery; $("last-delivery").textContent = `Dernière livraison : ${delivered.title}${delivered.pr ? ` · PR ${delivered.pr}` : ""}${delivered.ci === "success" ? " · CI verte" : ""}`;
  renderDecisionAids(data.decision_aids || []); renderQueue(data.queue || []); renderMemory(data.product_memory); renderBusiness(data.product_memory); renderProject(data.product_memory, data); renderWorkflow(data.product_memory, data); renderBoard(data.product_work || []); renderAgents(data.agents || []);
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

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => activateView(button.dataset.view)));
$("refresh").addEventListener("click", refresh); $("refresh-tokens").addEventListener("click", loadTokens); $("work-search").addEventListener("input", () => snapshot && renderBoard(snapshot.product_work || [])); $("focus-card").addEventListener("click", () => snapshot?.focus?.id && openItem({ ...snapshot.focus, store: "city" })); $("focus-card").addEventListener("keydown", (event) => { if (event.key === "Enter") $("focus-card").click(); }); $("close-drawer").addEventListener("click", () => $("detail-drawer").close()); $("detail-drawer").addEventListener("click", (event) => { if (event.target === $("detail-drawer")) $("detail-drawer").close(); });
$("copy-summary").addEventListener("click", async () => { if (snapshot) { await navigator.clipboard.writeText(humanSummary(snapshot)); toast("Point de situation copié"); } }); $("copy-po-prompt").addEventListener("click", () => { activateView("po"); $("po-message").value = `Aide-moi à relire la roadmap et à choisir le prochain sujet produit utile, sans lancer de travail.`; $("po-message").focus(); });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("mayor-message").value = button.dataset.prompt; $("mayor-message").focus(); })); $("send-mayor").addEventListener("click", sendMayor); $("refresh-conversation").addEventListener("click", loadConversation);
$("send-po").addEventListener("click", sendPO); $("new-po-conversation").addEventListener("click", newPOConversation); $("copy-po-thread").addEventListener("click", async () => { const id = $("copy-po-thread").dataset.threadId; if (id) { await navigator.clipboard.writeText(id); toast("Identifiant de discussion copié"); } });
$("open-design-decision").addEventListener("click", () => { const decision = snapshot?.product_memory?.decisions.find((item) => item.domain === "project" && item.title === "Socle du workflow design"); if (decision) { activateView("decisions"); openDecisionWorkspace(decision); } }); $("close-decision-workspace").addEventListener("click", closeDecisionWorkspace); $("send-decision-po").addEventListener("click", sendDecisionPO); $("copy-decision-thread").addEventListener("click", async () => { const id = $("copy-decision-thread").dataset.threadId; if (id) { await navigator.clipboard.writeText(id); toast("Identifiant de discussion copié"); } });
$("build-reference-with-po").addEventListener("click", () => { activateView("po"); $("po-message").value = "Aide-moi à compléter la documentation produit de référence SayMyName. Identifie la section la plus importante encore à valider, propose une représentation visuelle simple et ne lance aucune exécution."; $("po-message").focus(); }); $("start-preview").addEventListener("click", () => previewAction("start")); $("restart-preview").addEventListener("click", () => previewAction("restart")); $("stop-preview").addEventListener("click", () => previewAction("stop"));
$("mayor-conversation").replaceChildren(node("div", "empty", "Clique sur « Relire » pour charger les échanges.")); refresh(); loadPOIndex(); setInterval(refresh, 5000); setInterval(loadPOIndex, 5000); setInterval(updateClocks, 1000);

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
let currentReference = null;
let queueCancelItem = null;
let deepLinkRestored = false;
const ENTERPRISE_IGNORE_KEY = "factory-cockpit-enterprise-ignore-v1";

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function enterpriseIgnored() {
  try { const value = JSON.parse(localStorage.getItem(ENTERPRISE_IGNORE_KEY) || "[]"); return new Set(Array.isArray(value) ? value : []); } catch (_) { return new Set(); }
}
function saveEnterpriseIgnored(values) { localStorage.setItem(ENTERPRISE_IGNORE_KEY, JSON.stringify([...values])); }
function visiblePending(memory) { const ignored = enterpriseIgnored(); return memory.decisions.filter((item) => item.status === "pending" && (item.domain !== "enterprise" || !ignored.has(item.id))); }
function deepLink(view, values = {}) { const params = new URLSearchParams({ view, ...values }); history.replaceState(null, "", `#${params}`); }
function relationChips(item) {
  const chips = node("div", "relation-chips");
  (item.capabilities || []).forEach((value) => chips.append(node("span", "context-chip", `Capacité · ${value.title}`)));
  (item.journeys || []).forEach((value) => chips.append(node("span", "context-chip", `Parcours · ${value.title}`)));
  const roadmap = Array.isArray(item.roadmap) ? item.roadmap : item.roadmap ? [item.roadmap] : [];
  roadmap.forEach((value) => chips.append(node("span", "context-chip", `Roadmap · ${value}`)));
  (item.sources || []).forEach((value) => { const button = node("button", "reference-chip", value.title); button.addEventListener("click", (event) => { event.stopPropagation(); activateView("project"); loadReference(value.id); }); chips.append(button); });
  return chips;
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
  stages.forEach(([key, title, subtitle]) => { const column = node("section", "roadmap-column"); column.append(node("p", "eyebrow", title.toUpperCase()), node("h2", "", subtitle)); memory.roadmap.filter((item) => item.stage === key).forEach((item) => { const card = node("article", "roadmap-card clickable"); const copy = node("div"); copy.append(node("p", "", item.title)); const related = [...(item.capabilities || []).map((value) => value.title), ...(item.journeys || []).map((value) => value.title)]; if (related.length) copy.append(node("small", "muted", related.join(" · "))); card.append(node("span", "roadmap-number", String(item.order)), copy); card.addEventListener("click", () => { const decisionList = (item.decisions || []).map((value) => `${value.status === "pending" ? "À décider" : "Acquis"} · ${value.title}`).join("\n") || "Aucune décision liée."; showDrawer(item.title, `ROADMAP · ${title}`, { Résumé: item.title, Capacités: related.join("\n") || "Aucune capacité liée.", Décisions: decisionList, Source: item.source }); }); column.append(card); }); roadmap.append(column); });
  const pending = memory.decisions.filter((item) => item.status === "pending"); const accepted = memory.decisions.filter((item) => item.status === "accepted"); $("pending-count").textContent = `${pending.length} à décider`; $("accepted-count").textContent = accepted.length; updateDecisionNav(pending.length); $("today-pending").textContent = pending.length;
  const ignored = enterpriseIgnored(); const visible = visiblePending(memory); $("pending-count").textContent = `${visible.length} à décider`; updateDecisionNav(visible.length); $("today-pending").textContent = visible.length;
  const decisionCard = (item) => { const isIgnored = item.domain === "enterprise" && ignored.has(item.id); const card = node("article", `memory-card ${item.status} ${isIgnored ? "ignored" : ""}`); card.append(node("h3", "", item.title), node("p", "", item.detail), relationChips(item)); if (item.status === "pending") { const actions = node("div", "decision-actions"); const open = node("button", "primary", "Ouvrir la décision"); open.addEventListener("click", () => openDecisionWorkspace(item)); actions.append(open); if (item.domain === "enterprise") { const toggle = node("button", "", isIgnored ? "Réafficher les rappels" : "Ignorer sur cet appareil"); toggle.addEventListener("click", () => { const values = enterpriseIgnored(); if (values.has(item.id)) values.delete(item.id); else values.add(item.id); saveEnterpriseIgnored(values); renderMemory(memory); renderBusiness(memory); if (snapshot) renderRoadmap(snapshot); }); actions.append(toggle); } card.append(actions); } else { card.classList.add("clickable"); card.addEventListener("click", () => showDrawer(item.title, "DÉCISION ACQUISE", { Contexte: item.detail, Relations: relationChips(item), Source: item.source })); } return card; };
  ["enterprise", "product", "project"].forEach((domain) => { const values = pending.filter((item) => item.domain === domain); $(`${domain}-decision-count`).textContent = values.length; const container = $(`${domain}-decisions`); container.replaceChildren(...values.map(decisionCard)); if (!values.length) container.append(node("p", "muted", "Aucune décision ouverte.")); });
  const ignoredCount = pending.filter((item) => item.domain === "enterprise" && ignored.has(item.id)).length; $("enterprise-ignore-summary").textContent = ignoredCount ? `· ${ignoredCount} ignorée${ignoredCount > 1 ? "s" : ""} localement` : "";
  const enterprise = pending.filter((item) => item.domain === "enterprise"); const businessOnly = $("business-decisions"); businessOnly.replaceChildren(...enterprise.map(decisionCard)); $("business-decision-count").textContent = `${enterprise.length - ignoredCount} visible${enterprise.length - ignoredCount > 1 ? "s" : ""} · ${ignoredCount} ignorée${ignoredCount > 1 ? "s" : ""}`;
  const toggle = $("toggle-enterprise-ignore"); const allIgnored = enterprise.length > 0 && enterprise.every((item) => ignored.has(item.id)); toggle.textContent = allIgnored ? "Réafficher tous les rappels Entreprise" : "Ignorer tous les rappels Entreprise";
  const acceptedContainer = $("accepted-decisions"); acceptedContainer.replaceChildren(...accepted.map(decisionCard));
}

function renderBusiness(memory) {
  $("business-north-star").textContent = memory.business?.north_star || "Objectif entreprise non documenté.";
  const labels = { now: "En validation", next: "Ensuite", later: "Planifié", evidence: "Après preuve" }; const flow = $("business-objectives"); flow.replaceChildren();
  (memory.business?.objectives || []).forEach((item, index, all) => { const objective = node("article", `business-objective status-${item.status}`); objective.append(node("small", "", labels[item.status] || item.status), node("h3", "", item.title), node("p", "", item.detail)); flow.append(objective); if (index < all.length - 1) flow.append(node("span", "flow-arrow", "→")); });
}

function appendInlines(container, inlines) {
  (inlines || []).forEach((part) => {
    if (part.type !== "link") { container.append(document.createTextNode(part.text || "")); return; }
    const link = node("a", "reference-inline-link", part.text);
    link.href = `#view=project&reference=${encodeURIComponent(part.reference_id)}&section=${encodeURIComponent(part.section_anchor)}`;
    link.addEventListener("click", (event) => { event.preventDefault(); loadReference(part.reference_id, part.section_anchor); });
    container.append(link);
  });
}

function renderMarkdownBlock(block) {
  let element;
  if (block.type === "heading") { element = node(`h${Math.min(6, Math.max(2, block.level || 2))}`, "reference-block", block.text); element.id = block.anchor; }
  else if (block.type === "paragraph") { element = node("p", "reference-block"); appendInlines(element, block.inlines); }
  else if (block.type === "list") { element = node(block.ordered ? "ol" : "ul", "reference-block"); (block.items || []).forEach((parts) => { const item = node("li"); appendInlines(item, parts); element.append(item); }); }
  else if (block.type === "table") { const wrapper = node("div", "reference-table-wrap reference-block"); const table = node("table"); const head = node("thead"); const headerRow = node("tr"); (block.headers || []).forEach((value) => headerRow.append(node("th", "", value))); head.append(headerRow); const body = node("tbody"); (block.rows || []).forEach((values) => { const row = node("tr"); values.forEach((value) => row.append(node("td", "", value))); body.append(row); }); table.append(head, body); wrapper.append(table); element = wrapper; }
  else if (block.type === "code") { element = node("pre", "reference-code reference-block"); element.append(node("code", "", block.text)); }
  else element = node("p", "reference-block", "Bloc non pris en charge.");
  return element;
}

function applyReferenceSearch() {
  const query = $("reference-search").value.trim().toLocaleLowerCase("fr");
  document.querySelectorAll("#product-reference .reference-card").forEach((card) => card.classList.toggle("search-hidden", Boolean(query) && !card.textContent.toLocaleLowerCase("fr").includes(query)));
  document.querySelectorAll("#reference-reader .reference-block").forEach((block) => block.classList.toggle("search-hidden", Boolean(query) && !block.textContent.toLocaleLowerCase("fr").includes(query)));
}

async function loadReference(referenceId, sectionAnchor = null) {
  currentReference = referenceId; activateView("project", false); deepLink("project", { reference: referenceId, ...(sectionAnchor ? { section: sectionAnchor } : {}) });
  document.querySelectorAll("#product-reference .reference-card").forEach((card) => card.classList.toggle("active", card.dataset.referenceId === referenceId));
  const reader = $("reference-reader"); reader.replaceChildren(node("div", "empty", "Lecture et validation de la source configurée…"));
  try {
    const response = await fetch(`/api/reference?id=${encodeURIComponent(referenceId)}`, { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    const heading = node("header", "reference-reader-heading"); heading.append(node("div", "", data.status_label), node("h2", "", data.title), node("p", "muted", data.summary));
    const toc = node("nav", "reference-toc"); toc.setAttribute("aria-label", "Sommaire du document"); toc.append(node("strong", "", "Sommaire"));
    const content = node("div", "reference-prose");
    data.documents.forEach((documentValue) => {
      const provenance = node("aside", "reference-provenance"); provenance.append(node("strong", "", documentValue.configured_path), node("span", "", `Fraîcheur fichier · ${new Date(documentValue.modified_at).toLocaleString("fr-FR")}`), node("code", "", `SHA-256 ${documentValue.sha256.slice(0, 16)}…`)); content.append(provenance);
      documentValue.sections.forEach((section) => {
        const tocButton = node("button", "", section.heading); tocButton.addEventListener("click", () => { const target = $(section.anchor); if (target) { target.scrollIntoView({ behavior: "smooth", block: "start" }); deepLink("project", { reference: referenceId, section: section.anchor }); } }); toc.append(tocButton);
        section.blocks.forEach((block) => content.append(renderMarkdownBlock(block)));
      });
    });
    reader.replaceChildren(heading, toc, content); applyReferenceSearch();
    const target = sectionAnchor && $(sectionAnchor); if (target) requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  } catch (error) { reader.replaceChildren(node("div", "reference-error", `Source indisponible : ${error.message}`), node("p", "muted", "Aucun résumé de remplacement n’est inventé. Vérifie le chemin et les sections configurés.")); }
}

function renderReferenceIndex(references) {
  const container = $("product-reference"); container.replaceChildren();
  references.forEach((item) => { const card = node("button", `reference-card status-${item.status} ${item.state === "source_error" ? "source-error" : ""}`); card.dataset.referenceId = item.id; card.append(node("span", "inventory-status", item.state === "source_error" ? "Source en erreur" : item.status_label), node("h3", "", item.title), node("p", "", item.summary), node("small", "", item.state === "source_error" ? item.error : `${item.configured_paths.join(" · ")} · ${new Date(item.freshness).toLocaleString("fr-FR")}`)); card.addEventListener("click", () => loadReference(item.id)); container.append(card); });
  applyReferenceSearch();
}

function renderProject(memory, data) {
  const legend = $("capability-legend"); legend.replaceChildren(); [["now", "En construction"], ["next", "Ensuite"], ["later", "Planifié"], ["evidence", "Après preuve"]].forEach(([status, label]) => legend.append(node("span", `legend-${status}`, label)));
  const graph = $("capability-graph"); graph.replaceChildren();
  const statusLabels = { now: "En construction", next: "Ensuite", later: "Planifié", evidence: "Après preuve" };
  (memory.project_graph?.nodes || []).forEach((item) => { const card = node("article", `capability-node status-${item.status}`); card.dataset.nodeId = item.id; card.append(node("span", "capability-area", item.area), node("strong", "", item.title), node("small", "", `${statusLabels[item.status] || item.status} · roadmap ${item.roadmap}`), relationChips(item)); card.addEventListener("click", () => { const roadmap = memory.roadmap.find((entry) => entry.order === item.roadmap); const dependencies = node("div", "stack"); (item.relations || []).forEach((relation) => dependencies.append(node("div", "compact-item", `${relation.direction === "requires" ? "Dépend de" : "Soutient"} · ${relation.title}`))); const decisions = node("div", "stack"); (item.decisions || []).forEach((decision) => { const button = node("button", "", `${decision.status === "pending" ? "À décider" : "Acquis"} · ${decision.title}`); if (decision.status === "pending") button.addEventListener("click", () => { $("detail-drawer").close(); activateView("decisions"); openDecisionWorkspace(decision); }); decisions.append(button); }); showDrawer(item.title, `CAPACITÉ · ${item.area}`, { Résumé: roadmap?.title || item.title, Dépendances: dependencies, Décisions: decisions, Sources: relationChips(item) }); }); graph.append(card); });
  const graphNodes = memory.project_graph?.nodes || [];
  const edges = node("div", "graph-edges"); (memory.project_graph?.edges || []).forEach(([from, to]) => { const source = graphNodes.find((item) => item.id === from); const target = graphNodes.find((item) => item.id === to); edges.append(node("span", "", `${source?.title || from} → ${target?.title || to}`)); }); graph.append(edges);
  const now = (memory.project_graph?.nodes || []).filter((item) => item.status === "now").length; const candidates = (data.queue || []).filter((item) => item.kind !== "factory_campaign").length; $("project-progress").textContent = `${now} capacité${now > 1 ? "s" : ""} en construction · ${candidates} candidats live`;

  const journeys = $("journey-graph"); journeys.replaceChildren(); (memory.journeys || []).forEach((item) => { const card = node("article", `journey-node status-${item.status}`); card.append(node("span", "inventory-status", `Roadmap ${item.roadmap}`), node("h3", "", item.title), node("p", "", item.detail), relationChips(item)); card.addEventListener("click", () => showDrawer(item.title, "PARCOURS PRODUIT", { Résumé: item.detail, Capacités: (item.capabilities || []).map((value) => value.title).join(" → "), Décisions: (item.decisions || []).map((value) => value.title).join("\n") || "Aucune décision liée.", Sources: relationChips(item) })); journeys.append(card); });

  const lifecycle = $("reference-lifecycle"); lifecycle.replaceChildren(); [["Parler", "Besoin avec le PO"], ["Structurer", "Carte et parcours"], ["Valider", "Choix humain"], ["Référencer", "Documentation qui fait foi"], ["Livrer", "Factory dans le bon ordre"]].forEach(([title, detail], index, all) => { const card = node("article", `workflow-node ${index < 3 ? "done" : "upcoming"}`); card.append(node("span", "workflow-index", String(index + 1)), node("strong", "", title), node("small", "", detail)); lifecycle.append(card); if (index < all.length - 1) lifecycle.append(node("span", "workflow-arrow", "→")); });
  renderReferenceIndex(memory.product_reference || []);
  const inventory = $("view-inventory"); inventory.replaceChildren(); const inventoryLabels = { existing: "Existe dans le code", building: "En construction", next: "Ensuite", planned: "Planifié", evidence: "Après preuve" }; (memory.view_inventory || []).forEach((item) => { const card = node("article", `inventory-item inventory-${item.status}`); card.append(node("span", "inventory-status", inventoryLabels[item.status] || item.status), node("h3", "", item.area), node("p", "", (item.views || []).join(" · "))); inventory.append(card); });
  const freshness = memory.inventory_freshness || {}; setStatus($("inventory-freshness"), freshness.state === "review_due" ? "attention" : "idle", freshness.label || "État inconnu");
  const remote = data.remote_access || {}; $("mobile-access-copy").textContent = remote.enabled ? `Disponible uniquement sur ton tailnet : ${remote.url}` : "Accès distant non activé; le cockpit reste limité à ce PC."; const link = $("mobile-access-link"); link.classList.toggle("hidden", !remote.enabled); if (remote.enabled) link.href = remote.url;
}

function setQueueFeedback(message, isError = false, undo = null) {
  const feedback = $("queue-feedback"); feedback.className = `feedback ${isError ? "queue-error" : "queue-success"}`; feedback.replaceChildren(document.createTextNode(message));
  if (undo) { const button = node("button", "queue-undo", "Annuler ce changement"); button.addEventListener("click", () => queueMutation(undo.action, undo.payload)); feedback.append(document.createTextNode(" "), button); }
}

async function queueMutation(action, payload, undo = null) {
  setQueueFeedback("Enregistrement dans la file Beads…"); document.querySelectorAll(".queue-action").forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch("/api/product-queue", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-queue-record" }, body: JSON.stringify({ action, payload }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    snapshot.queue = data.queue || []; renderQueue(snapshot.queue); renderRoadmap(snapshot); renderProject(snapshot.product_memory, snapshot); setQueueFeedback(`${data.message || "File mise à jour."} Projection rafraîchie sans appel modèle.`, false, undo);
  } catch (error) { setQueueFeedback(`Échec sans état inventé : ${error.message} La file affichée n’a pas été supposée modifiée; actualise ou réessaie.`, true); }
}

function queueCard(item, allItems) {
  const card = node("article", `queue-record ${item.state === "paused" ? "paused" : "queued"}`); const heading = node("div", "queue-record-heading"); const copy = node("div"); copy.append(node("span", "inventory-status", `Position ${item.position} · ${item.state === "paused" ? "En pause" : "Candidate"}`), node("h3", "", item.title)); heading.append(copy, node("span", `status-pill ${item.state === "paused" ? "waiting" : "idle"}`, item.urgency)); card.append(heading);
  const controls = node("div", "queue-controls"); const up = node("button", "queue-action", "Monter"); up.disabled = item.position <= 1; up.addEventListener("click", () => queueMutation("move", { id: item.id, position: item.position - 1 }, { action: "move", payload: { id: item.id, position: item.position } })); const down = node("button", "queue-action", "Descendre"); down.disabled = item.position >= allItems.length; down.addEventListener("click", () => queueMutation("move", { id: item.id, position: item.position + 1 }, { action: "move", payload: { id: item.id, position: item.position } })); controls.append(up, down);
  const urgencyLabel = node("label", "queue-field", "Urgence"); const urgency = node("select", "queue-action"); ["normal", "urgent", "critical"].forEach((value) => { const option = node("option", "", value === "normal" ? "Normale" : value === "urgent" ? "Urgente" : "Critique"); option.value = value; urgency.append(option); }); urgency.value = item.urgency; urgency.addEventListener("change", () => queueMutation("urgency", { id: item.id, urgency: urgency.value }, { action: "urgency", payload: { id: item.id, urgency: item.urgency } })); urgencyLabel.append(urgency); controls.append(urgencyLabel);
  if (item.state === "paused") { const resume = node("button", "queue-action", "Reprendre"); resume.addEventListener("click", () => queueMutation("resume", { id: item.id })); controls.append(resume); }
  else { const reason = node("input", "queue-pause-reason"); reason.placeholder = "Raison requise pour la pause"; reason.maxLength = 1000; const pause = node("button", "queue-action", "Mettre en pause"); pause.addEventListener("click", () => { if (!reason.value.trim()) { reason.focus(); setQueueFeedback("Une raison est requise pour mettre un candidat en pause.", true); return; } queueMutation("pause", { id: item.id, reason: reason.value.trim() }, { action: "resume", payload: { id: item.id } }); }); controls.append(reason, pause); }
  const cancel = node("button", "queue-action danger", "Annuler…"); cancel.addEventListener("click", () => { queueCancelItem = item; $("queue-cancel-title").textContent = item.title; $("queue-cancel-reason").value = ""; $("queue-cancel-confirmed").checked = false; $("queue-cancel-dialog").showModal(); $("queue-cancel-reason").focus(); }); controls.append(cancel); card.append(controls); return card;
}

function renderRoadmap(data) {
  const delivered = data.last_delivery || {}; $("roadmap-delivered-title").textContent = delivered.title || "Aucun résultat livré résolu"; $("roadmap-delivered-proof").textContent = [delivered.pr && `PR ${delivered.pr}`, delivered.ci ? `CI ${delivered.ci}` : "CI non prouvée", delivered.outcome && `résultat ${delivered.outcome}`, delivered.closed_at && new Date(delivered.closed_at).toLocaleString("fr-FR")].filter(Boolean).join(" · ");
  const active = data.focus || {}; $("roadmap-active-title").textContent = active.title || "Aucun résultat actif"; $("roadmap-active-state").textContent = `${active.state_label || "Au repos"} · ${active.phase || "Aucune phase"}. Les contrôles de file ne peuvent pas modifier ce résultat.`;
  const queue = data.queue || []; const candidates = queue.filter((item) => item.kind !== "factory_campaign"); const campaigns = queue.filter((item) => item.kind === "factory_campaign"); $("roadmap-queue-count").textContent = candidates.length; const container = $("roadmap-queue"); container.replaceChildren(...candidates.map((item) => queueCard(item, queue))); if (!candidates.length) container.append(node("div", "empty", "Aucun candidat produit. Le travail actif reste indépendant."));
  const decisions = $("roadmap-decisions"); decisions.replaceChildren(); visiblePending(data.product_memory).filter((item) => item.roadmap?.length).forEach((item) => { const button = node("button", "roadmap-decision", `${item.title} · roadmap ${item.roadmap.join(", ")}`); button.addEventListener("click", () => { activateView("decisions"); openDecisionWorkspace(item); }); decisions.append(button); }); if (!decisions.children.length) decisions.append(node("div", "empty", "Aucune porte de décision visible."));
  const campaign = $("factory-campaign"); campaign.replaceChildren(); campaigns.forEach((item) => { const card = node("article", "memory-card factory-campaign-card"); card.append(node("h3", "", item.title), node("p", "", `Position globale ${item.position} · ${item.state} · séparée de la roadmap produit.`)); campaign.append(card); }); if (!campaign.children.length) campaign.append(node("div", "empty", "Aucune campagne Factory dans la file."));
}

function renderWorkflow(memory, data) {
  const stages = memory.delivery_workflow || []; let active = 0;
  if (data.focus?.id) active = data.focus.state === "queued" ? 2 : data.focus.state === "working" ? (data.agents.length ? 4 : 3) : data.focus.steps?.complete ? 5 : 2;
  const flow = $("delivery-workflow"); flow.replaceChildren(); stages.forEach((item, index) => { const state = index < active ? "done" : index === active ? "active" : "upcoming"; const card = node("article", `workflow-node ${state}`); card.append(node("span", "workflow-index", String(index + 1)), node("strong", "", item.title), node("small", "", item.detail)); if (state === "active") card.append(node("span", "workflow-live", "Ici maintenant")); flow.append(card); if (index < stages.length - 1) flow.append(node("span", "workflow-arrow", "→")); });
  const context = $("context-graph"); context.replaceChildren(); [["Benjamin", "Intentions et décisions", "human"], ["PO GPT", "Vision, roadmap et mémoire", "po"], ["Mayor", "Résultat autorisé et livraison", "mayor"], ["Beads", "Travail et dépendances", "beads"], ["Agents", "Une tâche bornée", "agents"], ["GitHub", "Preuve livrée", "github"]].forEach(([title, detail, kind], index, all) => { const card = node("article", `context-node ${kind}`); card.append(node("strong", "", title), node("small", "", detail)); context.append(card); if (index < all.length - 1) context.append(node("span", "context-arrow", "→")); });
  $("upper-context").replaceChildren(node("span", "context-chip", "Thèse produit"), node("span", "context-chip", `${memory.roadmap.length} résultats roadmap`), node("span", "context-chip", `${memory.decisions.filter((item) => item.status === "pending").length} décisions ouvertes`), node("span", "context-chip", "Stratégie et règles d’accès"));
  $("execution-context").replaceChildren(node("span", "context-chip", data.focus.title), node("span", "context-chip", data.focus.phase), node("span", "context-chip", `${data.focus.steps.completed}/${data.focus.steps.total} étapes prouvées`), node("span", "context-chip", `${data.agents.length} agents visibles`));
}

function activateView(view, updateLocation = true) {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === view));
  const selected = document.querySelector(`.nav-item[data-view="${view}"]`); if (selected?.closest("details.nav-more")) selected.closest("details.nav-more").open = true;
  if (view === "tokens" && !tokenLoaded) loadTokens();
  if (view === "po") loadPOConversation();
  if (view === "project") loadPreviewStatus();
  if (updateLocation) deepLink(view);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function restoreDeepLink(force = false) {
  if (deepLinkRestored && !force) return; deepLinkRestored = true; const params = new URLSearchParams(location.hash.replace(/^#/, "")); const view = params.get("view") || "today"; const allowed = new Set([...document.querySelectorAll(".nav-item")].map((item) => item.dataset.view)); activateView(allowed.has(view) ? view : "today", false);
  const reference = params.get("reference"); if (reference && snapshot?.product_memory?.product_reference.some((item) => item.id === reference)) loadReference(reference, params.get("section"));
  const decision = params.get("decision"); if (decision) openDecisionById(decision);
}

function decisionPrompt(decision) { return `Aide-moi à prendre cette décision : ${decision.title}\n\nReformule le choix, propose les options utiles, recommande-en une avec ses compromis, puis pose-moi la prochaine question nécessaire.`; }
async function openDecisionWorkspace(decision) { clearTimeout(decisionPoll); currentDecision = decision; deepLink("decisions", { decision: decision.id }); $("decision-feedback").textContent = ""; $("decision-workspace-domain").textContent = `DÉCISION ${decision.domain.toUpperCase()}`; $("decision-workspace-title").textContent = decision.title; $("decision-workspace-detail").textContent = decision.detail; $("decision-message").value = decisionPrompt(decision); $("decision-workspace").classList.remove("hidden"); document.querySelector(".decision-domain-grid").classList.add("hidden"); document.querySelector(".secondary-decisions").classList.add("hidden"); document.querySelector(".accepted-archive").classList.add("hidden"); await loadDecisionConversation(); $("decision-workspace").scrollIntoView({ behavior: "smooth" }); }
function closeDecisionWorkspace() { clearTimeout(decisionPoll); currentDecision = null; deepLink("decisions"); $("decision-workspace").classList.add("hidden"); document.querySelector(".decision-domain-grid").classList.remove("hidden"); document.querySelector(".secondary-decisions").classList.remove("hidden"); document.querySelector(".accepted-archive").classList.remove("hidden"); }

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
  renderDecisionAids(data.decision_aids || []); renderQueue(data.queue || []); renderMemory(data.product_memory); renderBusiness(data.product_memory); renderProject(data.product_memory, data); renderRoadmap(data); renderWorkflow(data.product_memory, data); renderBoard(data.product_work || []); renderAgents(data.agents || []);
  const factoryWork = $("factory-work"); factoryWork.replaceChildren(); (data.factory_work || []).forEach((item) => factoryWork.append(node("div", "compact-item", item.title))); if (!factoryWork.children.length) factoryWork.append(node("p", "muted", "Aucun autre travail Factory.")); const infrastructure = $("infrastructure"); infrastructure.replaceChildren(); (data.infrastructure || []).forEach((item) => infrastructure.append(node("div", "compact-item", `${item.name} · ${item.state}`)));
  const alert = $("alert"); if (data.warnings.length) { alert.textContent = `Visibilité partielle : ${data.warnings.join(" · ")}`; alert.classList.remove("hidden"); } else alert.classList.add("hidden"); compareVisit(data); updateClocks(); restoreDeepLink();
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
$("refresh").addEventListener("click", refresh); $("refresh-tokens").addEventListener("click", loadTokens); $("work-search").addEventListener("input", () => snapshot && renderBoard(snapshot.product_work || [])); $("reference-search").addEventListener("input", applyReferenceSearch); $("focus-card").addEventListener("click", () => snapshot?.focus?.id && openItem({ ...snapshot.focus, store: "city" })); $("focus-card").addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); $("focus-card").click(); } }); $("close-drawer").addEventListener("click", () => $("detail-drawer").close()); $("detail-drawer").addEventListener("click", (event) => { if (event.target === $("detail-drawer")) $("detail-drawer").close(); });
$("copy-summary").addEventListener("click", async () => { if (snapshot) { await navigator.clipboard.writeText(humanSummary(snapshot)); toast("Point de situation copié"); } }); $("copy-po-prompt").addEventListener("click", () => { activateView("po"); $("po-message").value = `Aide-moi à relire la roadmap et à choisir le prochain sujet produit utile, sans lancer de travail.`; $("po-message").focus(); });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("mayor-message").value = button.dataset.prompt; $("mayor-message").focus(); })); $("send-mayor").addEventListener("click", sendMayor); $("refresh-conversation").addEventListener("click", loadConversation);
$("send-po").addEventListener("click", sendPO); $("new-po-conversation").addEventListener("click", newPOConversation); $("copy-po-thread").addEventListener("click", async () => { const id = $("copy-po-thread").dataset.threadId; if (id) { await navigator.clipboard.writeText(id); toast("Identifiant de discussion copié"); } });
$("open-design-decision").addEventListener("click", () => { const decision = snapshot?.product_memory?.decisions.find((item) => item.domain === "project" && item.title === "Socle du workflow design"); if (decision) { activateView("decisions"); openDecisionWorkspace(decision); } }); $("close-decision-workspace").addEventListener("click", closeDecisionWorkspace); $("send-decision-po").addEventListener("click", sendDecisionPO); $("copy-decision-thread").addEventListener("click", async () => { const id = $("copy-decision-thread").dataset.threadId; if (id) { await navigator.clipboard.writeText(id); toast("Identifiant de discussion copié"); } });
$("build-reference-with-po").addEventListener("click", () => { activateView("po"); $("po-message").value = "Aide-moi à compléter la documentation produit de référence SayMyName. Identifie la section la plus importante encore à valider, propose une représentation visuelle simple et ne lance aucune exécution."; $("po-message").focus(); }); $("start-preview").addEventListener("click", () => previewAction("start")); $("restart-preview").addEventListener("click", () => previewAction("restart")); $("stop-preview").addEventListener("click", () => previewAction("stop"));
$("toggle-enterprise-ignore").addEventListener("click", () => { if (!snapshot) return; const enterprise = snapshot.product_memory.decisions.filter((item) => item.status === "pending" && item.domain === "enterprise"); const ignored = enterpriseIgnored(); const allIgnored = enterprise.length > 0 && enterprise.every((item) => ignored.has(item.id)); enterprise.forEach((item) => allIgnored ? ignored.delete(item.id) : ignored.add(item.id)); saveEnterpriseIgnored(ignored); renderMemory(snapshot.product_memory); renderBusiness(snapshot.product_memory); renderRoadmap(snapshot); });
$("queue-add-form").addEventListener("submit", (event) => { event.preventDefault(); queueMutation("add", { title: $("queue-add-title").value.trim(), why: $("queue-add-why").value.trim(), acceptance: $("queue-add-acceptance").value.trim(), urgency: $("queue-add-urgency").value }); });
$("queue-cancel-submit").addEventListener("click", (event) => { event.preventDefault(); if (!queueCancelItem) return; const reason = $("queue-cancel-reason").value.trim(); const confirmed = $("queue-cancel-confirmed").checked; if (!reason || !confirmed) { setQueueFeedback("L’annulation exige une raison et une confirmation explicite.", true); return; } $("queue-cancel-dialog").close(); queueMutation("cancel", { id: queueCancelItem.id, reason, confirmed: true }); queueCancelItem = null; });
document.querySelectorAll("[data-reference]").forEach((button) => button.addEventListener("click", () => { activateView("project"); loadReference(button.dataset.reference); }));
window.addEventListener("hashchange", () => restoreDeepLink(true));
$("mayor-conversation").replaceChildren(node("div", "empty", "Clique sur « Relire » pour charger les échanges.")); refresh(); loadPOIndex(); setInterval(refresh, 5000); setInterval(loadPOIndex, 5000); setInterval(updateClocks, 1000);

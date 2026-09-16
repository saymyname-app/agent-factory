const $ = (id) => document.getElementById(id);
let snapshot = null;
let identity = { product: "", operator: "" };
function productName() { return identity.product || snapshot?.product_memory?.product || ""; }
function operatorName() { return identity.operator || snapshot?.operator || ""; }
function applyIdentity(product, operator) {
  const changed = (product && product !== identity.product) || (operator && operator !== identity.operator);
  if (!changed) return;
  identity = { product: product || identity.product, operator: operator || identity.operator };
  [["data-product-text", identity.product], ["data-operator-text", identity.operator]].forEach(([attribute, name]) => {
    if (!name) return;
    document.querySelectorAll(`[${attribute}]`).forEach((element) => {
      const value = element.getAttribute(attribute).replace("%s", name);
      element.textContent = element.dataset.identityCase === "upper" ? value.toUpperCase() : value;
    });
  });
}
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
let deliveryEvidence = null;
let deliveryEvidenceLoading = false;
let releaseDecision = null;
let releaseDecisionOpenedAt = Date.now();
const directDecisionKeys = new Map();
const ENTERPRISE_IGNORE_KEY = "factory-cockpit-enterprise-ignore-v1";

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}
function makeActivatable(element, action) { element.tabIndex = 0; element.setAttribute("role", "button"); element.addEventListener("click", action); element.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); action(); } }); }

function enterpriseIgnored() {
  try { const value = JSON.parse(localStorage.getItem(ENTERPRISE_IGNORE_KEY) || "[]"); return new Set(Array.isArray(value) ? value : []); } catch (_) { return new Set(); }
}
function saveEnterpriseIgnored(values) { localStorage.setItem(ENTERPRISE_IGNORE_KEY, JSON.stringify([...values])); }
function visiblePending(memory) { const ignored = enterpriseIgnored(); return memory.decisions.filter((item) => item.status === "pending" && (item.domain !== "enterprise" || !ignored.has(item.id))); }
function visibleGeneralDecisions(memory, today) { const pending = visiblePending(memory); if (!Array.isArray(today?.general_decisions)) return pending; const ids = new Set(today.general_decisions.map((item) => item.id)); return pending.filter((item) => ids.has(item.id)); }
function deepLink(view, values = {}) { const params = new URLSearchParams({ view, ...values }); history.replaceState(null, "", `#${params}`); }
function relationChips(item, interactive = true) {
  const chips = node("div", "relation-chips");
  (item.capabilities || []).forEach((value) => chips.append(node("span", "context-chip", `Capacité · ${value.title}`)));
  (item.journeys || []).forEach((value) => chips.append(node("span", "context-chip", `Parcours · ${value.title}`)));
  const roadmap = Array.isArray(item.roadmap) ? item.roadmap : item.roadmap ? [item.roadmap] : [];
  roadmap.forEach((value) => chips.append(node("span", "context-chip", `Roadmap · ${value}`)));
  (item.sources || []).forEach((value) => { if (!interactive) { chips.append(node("span", "context-chip", `Source · ${value.title}`)); return; } const button = node("button", "reference-chip", value.title); button.addEventListener("click", (event) => { event.stopPropagation(); activateView("project"); loadReference(value.id); }); chips.append(button); });
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
function unreadReplyCount() {
  const visibleIds = snapshot ? new Set(visiblePending(snapshot.product_memory).map((item) => item.id)) : null;
  return poIndex.filter((item) => item.kind === "decision" && (!visibleIds || visibleIds.has(item.decision_id)) && hasUnreadReply(item)).length;
}
function updateDecisionNav(pendingCount = null) { const unread = unreadReplyCount(); const total = pendingCount ?? (snapshot ? visiblePending(snapshot.product_memory).length : 0); $("nav-decision-count").textContent = unread ? `${unread} réponse${unread > 1 ? "s" : ""} PO` : `${total} à trancher`; }

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
  agents.forEach((agent) => { const card = node("article", "agent-card clickable"); const top = node("div", "agent-top"); const identity = node("div"); identity.append(node("div", "agent-name", agent.name), node("div", "agent-role", `${agent.role}${agent.provider ? ` · ${agent.provider}` : ""}`)); top.append(identity, node("span", `status-pill ${statusClass(agent.state)}`, agent.state_label)); card.append(top, node("p", "agent-objective", agent.objective), node("div", "agent-meta", agent.phase)); const timing = node("div", "agent-meta"); const signal = node("span", "", `Signal ${signalAge(agent.last_signal_at)}`); signal.dataset.signalTime = agent.last_signal_at || ""; signal.dataset.signalPrefix = "Signal "; const elapsed = node("span"); timed(elapsed, agent.started_at, " · depuis "); timing.append(signal, elapsed); card.append(timing); makeActivatable(card, () => openAgent(agent)); container.append(card); });
}

function renderQueue(queue) {
  const candidates = queue.filter((item) => item.kind === "product_candidate"); const container = $("queue"); container.replaceChildren(); $("queue-count").textContent = candidates.length;
  candidates.slice(0, 6).forEach((item) => { const row = node("li", "queue-item"); const copy = node("div"); copy.append(node("div", "queue-title", item.title), node("div", "queue-meta", `${item.state_label} · ${item.reason}`)); row.append(copy, node("span", `status-pill ${item.state === "paused" ? "waiting" : "idle"}`, item.urgency_label)); if (item.id) { row.classList.add("clickable"); row.addEventListener("click", () => openItem({ ...item, store: "city", product: productName() })); } container.append(row); });
  if (!candidates.length) container.append(node("li", "empty", "Aucun candidat produit éligible ou en pause."));
}

function renderOperationalState(data) {
  const health = data.human_state.health; const activity = data.human_state.activity; const resume = data.human_state.resume;
  $("health-label").textContent = health.label; $("health-detail").textContent = health.detail;
  $("activity-label").textContent = activity.label; $("activity-detail").textContent = activity.detail;
  $("resume-label").textContent = resume.automatic ? "Automatique" : resume.required ? "Action requise" : "Non automatique · action facultative";
  $("resume-condition").textContent = resume.condition || "Aucune"; $("resume-owner").textContent = resume.owner_label; $("resume-action-copy").textContent = resume.action;
  const action = $("resume-action"); action.dataset.prompt = resume.prompt || ""; action.classList.toggle("hidden", !resume.prompt);
}

function renderCampaignState(data) {
  const state = data.human_state; const campaign = state.campaign;
  const blockedModes = new Set(["fail_closed", "blocking_decision", "blocked", "campaign_blocked"]);
  const blocked = Boolean(campaign?.blocked || blockedModes.has(state.resume.mode));
  const global = $("campaign-block-global"); const today = $("campaign-block-today");
  global.classList.toggle("hidden", !blocked); today.classList.toggle("hidden", !blocked);
  if (!blocked) return;
  const cause = campaign.cause || state.resume.condition || state.activity.detail || "La livraison ne peut pas poursuivre.";
  const owner = campaign.blocked ? campaign.owner_label : state.resume.owner_label;
  const action = campaign.blocked ? campaign.action : state.resume.action;
  $("campaign-block-global-cause").textContent = cause;
  $("campaign-block-global-action").textContent = `Reprise : ${owner} · ${action}`;
  $("campaign-block-today-cause").textContent = cause;
  $("campaign-block-today-owner").textContent = owner;
  $("campaign-block-today-action").textContent = action;
}

function renderDecisionAids(items) {
  const container = $("decision-aids"); container.replaceChildren(); $("advice-count").textContent = items.length;
  items.forEach((item) => { const card = node("article", `advice-card severity-${item.severity}`); const copy = node("div"); copy.append(node("h3", "", item.title), node("p", "", item.explanation), node("small", "", item.action)); const ask = node("button", "ask-mayor", "Demander au Mayor"); ask.addEventListener("click", () => { $("mayor-message").value = item.prompt; $("mayor-message").focus(); }); card.append(copy, ask); container.append(card); });
}

function renderTodayAttention(today) {
  const blockers = Array.isArray(today?.effective_blockers) ? today.effective_blockers : [];
  const blocker = blockers[0]; const action = $("open-blocker-decision");
  $("needs-benjamin").textContent = blocker?.text || "Aucun blocage effectif."; $("today-blockers").textContent = blockers.length;
  action.dataset.decisionId = blocker?.decision_id || ""; action.classList.toggle("hidden", !blocker?.decision_id);
}

const boardDefinitions = [
  ["active", "En livraison", ["current", "active"]], ["materialized", "Matérialisé", ["materialized"]], ["ready", "Prêt", ["ready"]], ["eligible", "Éligible · non programmé", ["eligible", "planned"]], ["paused", "En pause", ["paused"]], ["blocked", "Bloqué", ["blocked"]], ["delivered", "Livré", ["delivered"]], ["cancelled", "Annulé", ["cancelled"]],
];
function renderBoard(items) {
  const query = $("work-search").value.trim().toLocaleLowerCase("fr"); const board = $("work-board"); board.replaceChildren();
  boardDefinitions.forEach(([key, label, states]) => { const column = node("section", "board-column"); const filtered = items.filter((item) => states.includes(item.state) && (!query || `${item.title} ${item.product}`.toLocaleLowerCase("fr").includes(query))); const header = node("div", "column-title"); header.append(node("h2", "", label), node("span", "count", filtered.length)); column.append(header); const stack = node("div", "board-stack"); filtered.forEach((item) => { const card = node("article", `work-card clickable state-border-${item.state}`); card.append(node("span", "work-kind", `${item.product} · ${item.kind}`), node("h3", "", item.title)); const proof = [item.urgency && `Priorité ${item.urgency}`, item.pr && `PR ${item.pr}`, item.ci === "success" && "CI verte"].filter(Boolean); if (proof.length) card.append(node("p", "work-proof", proof.join(" · "))); makeActivatable(card, () => openItem(item)); stack.append(card); }); if (!filtered.length) stack.append(node("div", "column-empty", "—")); column.append(stack); board.append(column); });
}

function renderMemory(memory, today = snapshot?.today) {
  $("product-thesis").textContent = memory.thesis; const roadmap = $("roadmap"); roadmap.replaceChildren();
  const stages = [["now", "Maintenant", "Résultat en livraison"], ["next", "Ensuite", "Les prochaines preuves utiles"], ["later", "Plus tard", "Direction acceptée, pas encore engagée"], ["evidence", "Après preuve", "Dépend d’un apprentissage client"]];
  stages.forEach(([key, title, subtitle]) => { const column = node("section", "roadmap-column"); column.append(node("p", "eyebrow", title.toUpperCase()), node("h2", "", subtitle)); memory.roadmap.filter((item) => item.stage === key).forEach((item) => { const card = node("article", "roadmap-card clickable"); const copy = node("div"); copy.append(node("p", "", item.title)); const related = [...(item.capabilities || []).map((value) => value.title), ...(item.journeys || []).map((value) => value.title)]; if (related.length) copy.append(node("small", "muted", related.join(" · "))); card.append(node("span", "roadmap-number", String(item.order)), copy); makeActivatable(card, () => { const decisionList = (item.decisions || []).map((value) => `${value.status === "pending" ? "À décider" : "Acquis"} · ${value.title}`).join("\n") || "Aucune décision liée."; showDrawer(item.title, `ROADMAP · ${title}`, { Résumé: item.title, Capacités: related.join("\n") || "Aucune capacité liée.", Décisions: decisionList, Source: item.source }); }); column.append(card); }); roadmap.append(column); });
  const pending = memory.decisions.filter((item) => item.status === "pending"); const accepted = memory.decisions.filter((item) => item.status === "accepted"); $("accepted-count").textContent = accepted.length;
  const ignored = enterpriseIgnored(); const visible = visiblePending(memory); $("pending-count").textContent = `${visible.length} à décider`; updateDecisionNav(visible.length); $("today-pending").textContent = visibleGeneralDecisions(memory, today).length;
  const decisionCard = (item) => { const isIgnored = item.domain === "enterprise" && ignored.has(item.id); const card = node("article", `memory-card ${item.status} ${isIgnored ? "ignored" : ""}`); card.append(node("h3", "", item.title), node("p", "", item.detail), relationChips(item, false)); if (item.status === "pending") { const actions = node("div", "decision-actions"); const open = node("button", "primary", "Ouvrir la décision"); open.addEventListener("click", () => openDecisionWorkspace(item)); actions.append(open); if (item.domain === "enterprise") { const toggle = node("button", "", isIgnored ? "Réafficher les rappels" : "Ignorer sur cet appareil"); toggle.addEventListener("click", () => { const values = enterpriseIgnored(); if (values.has(item.id)) values.delete(item.id); else values.add(item.id); saveEnterpriseIgnored(values); renderMemory(memory); renderBusiness(memory); if (snapshot) renderRoadmap(snapshot); }); actions.append(toggle); } card.append(actions); } else { card.classList.add("clickable"); makeActivatable(card, () => showDrawer(item.title, "DÉCISION ACQUISE", { Contexte: item.detail, Relations: relationChips(item), Source: item.source })); } return card; };
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
  references.forEach((item) => { const card = node("button", `reference-card status-${item.status} ${item.state === "source_error" ? "source-error" : ""} ${item.id === currentReference ? "active" : ""}`); card.dataset.referenceId = item.id; card.append(node("span", "inventory-status", item.state === "source_error" ? "Source en erreur" : item.status_label), node("h3", "", item.title), node("p", "", item.summary), node("small", "", item.state === "source_error" ? item.error : `${item.configured_paths.join(" · ")} · ${new Date(item.freshness).toLocaleString("fr-FR")}`)); card.addEventListener("click", () => loadReference(item.id)); container.append(card); });
  applyReferenceSearch();
}

function renderProject(memory, data) {
  renderRelease(data.release);
  const legend = $("capability-legend"); legend.replaceChildren(); [["now", "En construction"], ["next", "Ensuite"], ["later", "Planifié"], ["evidence", "Après preuve"]].forEach(([status, label]) => legend.append(node("span", `legend-${status}`, label)));
  const graph = $("capability-graph"); graph.replaceChildren();
  const statusLabels = { now: "En construction", next: "Ensuite", later: "Planifié", evidence: "Après preuve" };
  (memory.project_graph?.nodes || []).forEach((item) => { const card = node("article", `capability-node status-${item.status}`); card.dataset.nodeId = item.id; card.append(node("span", "capability-area", item.area), node("strong", "", item.title), node("small", "", `${statusLabels[item.status] || item.status} · roadmap ${item.roadmap}`), relationChips(item, false)); makeActivatable(card, () => { const roadmap = memory.roadmap.find((entry) => entry.order === item.roadmap); const dependencies = node("div", "stack"); (item.relations || []).forEach((relation) => dependencies.append(node("div", "compact-item", `${relation.direction === "requires" ? "Dépend de" : "Soutient"} · ${relation.title}`))); const decisions = node("div", "stack"); (item.decisions || []).forEach((decision) => { const button = node("button", "", `${decision.status === "pending" ? "À décider" : "Acquis"} · ${decision.title}`); if (decision.status === "pending") button.addEventListener("click", () => { $("detail-drawer").close(); activateView("decisions"); openDecisionWorkspace(decision); }); decisions.append(button); }); showDrawer(item.title, `CAPACITÉ · ${item.area}`, { Résumé: roadmap?.title || item.title, Dépendances: dependencies, Décisions: decisions, Sources: relationChips(item) }); }); graph.append(card); });
  const graphNodes = memory.project_graph?.nodes || [];
  const edges = node("div", "graph-edges"); (memory.project_graph?.edges || []).forEach(([from, to]) => { const source = graphNodes.find((item) => item.id === from); const target = graphNodes.find((item) => item.id === to); edges.append(node("span", "", `${source?.title || from} → ${target?.title || to}`)); }); graph.append(edges);
  const now = (memory.project_graph?.nodes || []).filter((item) => item.status === "now").length; const candidates = (data.queue || []).filter((item) => item.kind !== "factory_campaign").length; $("project-progress").textContent = `${now} capacité${now > 1 ? "s" : ""} en construction · ${candidates} candidats live`;

  const journeys = $("journey-graph"); journeys.replaceChildren(); (memory.journeys || []).forEach((item) => { const card = node("article", `journey-node status-${item.status}`); card.append(node("span", "inventory-status", `Roadmap ${item.roadmap}`), node("h3", "", item.title), node("p", "", item.detail), relationChips(item, false)); makeActivatable(card, () => showDrawer(item.title, "PARCOURS PRODUIT", { Résumé: item.detail, Capacités: (item.capabilities || []).map((value) => value.title).join(" → "), Décisions: (item.decisions || []).map((value) => value.title).join("\n") || "Aucune décision liée.", Sources: relationChips(item) })); journeys.append(card); });

  const lifecycle = $("reference-lifecycle"); lifecycle.replaceChildren(); [["Parler", "Besoin avec le PO"], ["Structurer", "Carte et parcours"], ["Valider", "Choix humain"], ["Référencer", "Documentation qui fait foi"], ["Livrer", "Factory dans le bon ordre"]].forEach(([title, detail], index, all) => { const card = node("article", `workflow-node ${index < 3 ? "done" : "upcoming"}`); card.append(node("span", "workflow-index", String(index + 1)), node("strong", "", title), node("small", "", detail)); lifecycle.append(card); if (index < all.length - 1) lifecycle.append(node("span", "workflow-arrow", "→")); });
  renderReferenceIndex(memory.product_reference || []);
  const inventory = $("view-inventory"); inventory.replaceChildren(); const inventoryLabels = { existing: "Existe dans le code", building: "En construction", next: "Ensuite", planned: "Planifié", evidence: "Après preuve" }; (memory.view_inventory || []).forEach((item) => { const card = node("article", `inventory-item inventory-${item.status}`); card.append(node("span", "inventory-status", inventoryLabels[item.status] || item.status), node("h3", "", item.area), node("p", "", (item.views || []).join(" · "))); inventory.append(card); });
  const freshness = memory.inventory_freshness || {}; setStatus($("inventory-freshness"), freshness.state === "review_due" ? "attention" : "idle", freshness.label || "État inconnu");
  const remote = data.remote_access || {}; $("mobile-access-copy").textContent = remote.enabled ? `Disponible uniquement sur ton tailnet : ${remote.url}` : "Accès distant non activé; le cockpit reste limité à ce PC."; const link = $("mobile-access-link"); link.classList.toggle("hidden", !remote.enabled); if (remote.enabled) link.href = remote.url;
}

function releaseItem(item, badge = "Produit") {
  const card = node("article", `release-card status-${item.status}`);
  card.append(node("span", `release-badge ${badge === "Factory" ? "factory" : "product"}`, `${badge} · V1`), node("h4", "", item.title), node("p", "", item.description), node("small", "", item.status_label || item.status));
  const refs = (item.evidence || []).map((entry) => `${entry.kind.toUpperCase()} · ${entry.ref} · ${entry.status}`).join("\n"); if (refs) card.append(node("small", "", refs));
  return card;
}

function renderRelease(release) {
  if (!release) return;
  $("release-title").textContent = `${release.version} · ${release.title}`; $("release-version").value = release.version;
  setStatus($("release-state"), release.operational_state === "executing" ? "working" : release.truth_state === "frozen" ? "idle" : "waiting", release.operational_state_label);
  $("release-maturity").textContent = release.maturity.label;
  $("release-state-detail").textContent = `Vérité Git : ${release.truth_state} · état opérationnel : ${release.operational_state}. Le refresh ne réécrit jamais Git.`;
  const renderList = (id, values) => { const container = $(id); container.replaceChildren(); (values || []).forEach((item) => { const row = node("div", "release-list-item"); row.append(node("strong", "", item.title), node("small", "", `${item.status_label} · ${item.description}`)); container.append(row); }); if (!container.children.length) container.append(node("div", "empty", "Aucun élément.")); };
  renderList("release-included", release.included); renderList("release-excluded", release.excluded); renderList("release-dependencies", release.dependencies);
  const capabilities = $("release-capabilities"); capabilities.replaceChildren(...(release.capabilities || []).map((item) => releaseItem(item))); (release.journeys || []).forEach((item) => capabilities.append(releaseItem(item)));
  const factory = $("release-factory"); factory.replaceChildren(...(release.factory_improvements || []).map((item) => releaseItem(item, "Factory")));
  releaseDecision = (release.decisions || []).find((item) => item.id === release.intervention?.decision_id) || null;
  const intervention = $("release-intervention"); intervention.classList.toggle("hidden", !releaseDecision);
  if (releaseDecision) {
    $("release-decision-title").textContent = releaseDecision.title; const options = $("release-option"); options.replaceChildren(node("option", "", "Choisir une option…")); options.firstChild.value = ""; releaseDecision.options.forEach((item) => { const option = node("option", "", item.label); option.value = item.id; options.append(option); }); releaseDecisionOpenedAt = Date.now();
  }
  const params = new URLSearchParams(location.hash.replace(/^#/, "")); if (releaseDecision && params.get("releaseDecision") === releaseDecision.id) requestAnimationFrame(() => { intervention.scrollIntoView({ block: "center" }); intervention.focus(); });
}

function directKey(decisionId, action) { const id = `${decisionId}:${action}`; if (!directDecisionKeys.has(id)) directDecisionKeys.set(id, `cockpit-${crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`}`); return directDecisionKeys.get(id); }
async function submitDirectDecision(decision, action, optionId = null, detail = null, feedbackId = "release-decision-feedback") {
  if (!decision) return; const feedback = $(feedbackId); feedback.textContent = "Enregistrement local sans modèle…";
  try {
    const response = await fetch("/api/direct-decision", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-direct-decision" }, body: JSON.stringify({ decision_id: decision.id, action, option_id: optionId, detail, expected_revision: decision.revision, confirmed: $("release-decision-confirm").checked, elapsed_ms: Math.max(0, Date.now() - releaseDecisionOpenedAt), idempotency_key: directKey(decision.id, action) }) });
    const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); feedback.textContent = data.state === "already_recorded" ? "Choix déjà enregistré : reprise idempotente, 0 appel modèle." : "Choix audité, 0 appel modèle. Le PO doit maintenant le traduire dans la vérité Git.";
  } catch (error) { feedback.textContent = `Choix non enregistré : ${error.message}`; }
}

function setQueueFeedback(message, isError = false, undo = null) {
  const feedback = $("queue-feedback"); feedback.className = `feedback ${isError ? "queue-error" : "queue-success"}`; feedback.replaceChildren(document.createTextNode(message));
  if (undo) { const button = node("button", "queue-undo", "Annuler ce changement"); button.addEventListener("click", () => queueMutation(undo.action, undo.payload)); feedback.append(document.createTextNode(" "), button); }
}

async function queueMutation(action, payload, undo = null) {
  setQueueFeedback("Enregistrement dans la file Beads…"); document.querySelectorAll(".queue-action").forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch("/api/product-queue", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-queue-record" }, body: JSON.stringify({ action, payload }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    snapshot.queue = data.queue || []; if (action === "add") $("queue-add-form").reset(); renderQueue(snapshot.queue); renderRoadmap(snapshot); renderProject(snapshot.product_memory, snapshot); setQueueFeedback(`${data.message || "File mise à jour."} Projection rafraîchie sans appel modèle.`, false, undo);
  } catch (error) { if (snapshot) renderRoadmap(snapshot); setQueueFeedback(`Échec sans état inventé : ${error.message} La file affichée n’a pas été supposée modifiée; actualise ou réessaie.`, true); }
}

function queueCard(item, allItems) {
  const card = node("article", `queue-record ${item.state === "paused" ? "paused" : "eligible"}`); const heading = node("div", "queue-record-heading"); const copy = node("div"); copy.append(node("span", "inventory-status", `Position ${item.position} · ${item.state_label}`), node("h3", "", item.title), node("p", "muted", item.reason)); heading.append(copy, node("span", `status-pill ${item.state === "paused" ? "waiting" : "idle"}`, item.urgency_label)); card.append(heading);
  const controls = node("div", "queue-controls"); const up = node("button", "queue-action", "Monter"); up.setAttribute("aria-label", `Monter ${item.title} d’une position`); up.disabled = item.position <= 1; up.addEventListener("click", () => queueMutation("move", { id: item.id, position: item.position - 1 }, { action: "move", payload: { id: item.id, position: item.position } })); const down = node("button", "queue-action", "Descendre"); down.setAttribute("aria-label", `Descendre ${item.title} d’une position`); down.disabled = item.position >= allItems.length; down.addEventListener("click", () => queueMutation("move", { id: item.id, position: item.position + 1 }, { action: "move", payload: { id: item.id, position: item.position } })); controls.append(up, down);
  const urgencyLabel = node("label", "queue-field", "Urgence"); const urgency = node("select", "queue-action"); ["normal", "urgent", "critical"].forEach((value) => { const option = node("option", "", value === "normal" ? "Normale" : value === "urgent" ? "Urgente" : "Critique"); option.value = value; urgency.append(option); }); urgency.value = item.urgency; urgency.addEventListener("change", () => queueMutation("urgency", { id: item.id, urgency: urgency.value }, { action: "urgency", payload: { id: item.id, urgency: item.urgency } })); urgencyLabel.append(urgency); controls.append(urgencyLabel);
  if (item.state === "paused") { const resume = node("button", "queue-action", "Reprendre"); resume.addEventListener("click", () => queueMutation("resume", { id: item.id })); controls.append(resume); }
  else { const reason = node("input", "queue-pause-reason"); reason.placeholder = "Raison requise pour la pause"; reason.setAttribute("aria-label", `Raison de pause pour ${item.title}`); reason.maxLength = 1000; const pause = node("button", "queue-action", "Mettre en pause"); pause.addEventListener("click", () => { if (!reason.value.trim()) { reason.focus(); setQueueFeedback("Une raison est requise pour mettre un candidat en pause.", true); return; } queueMutation("pause", { id: item.id, reason: reason.value.trim() }, { action: "resume", payload: { id: item.id } }); }); controls.append(reason, pause); }
  const cancel = node("button", "queue-action danger", "Annuler…"); cancel.addEventListener("click", () => { queueCancelItem = item; $("queue-cancel-title").textContent = item.title; $("queue-cancel-reason").value = ""; $("queue-cancel-confirmed").checked = false; $("queue-cancel-dialog").showModal(); $("queue-cancel-reason").focus(); }); controls.append(cancel); card.append(controls); return card;
}

function renderRoadmap(data) {
  const delivered = data.last_delivery || {}; $("roadmap-delivered-title").textContent = delivered.title || "Aucun résultat livré résolu"; $("roadmap-delivered-proof").textContent = [delivered.pr && `PR ${delivered.pr}`, delivered.ci ? `CI ${delivered.ci}` : "CI non prouvée", delivered.outcome && `résultat ${delivered.outcome}`, delivered.closed_at && new Date(delivered.closed_at).toLocaleString("fr-FR")].filter(Boolean).join(" · ");
  if (deliveryEvidence) renderDeliveryEvidence(deliveryEvidence);
  const active = data.focus || {}; $("roadmap-active-title").textContent = active.title || "Aucun résultat actif"; $("roadmap-active-state").textContent = `${active.state_label || "Au repos"} · ${active.phase || "Aucune phase"}. Les contrôles de file ne peuvent pas modifier ce résultat.`;
  const queue = data.queue || []; const candidates = queue.filter((item) => item.kind !== "factory_campaign"); const campaigns = queue.filter((item) => item.kind === "factory_campaign"); $("roadmap-queue-count").textContent = candidates.length; const container = $("roadmap-queue"); container.replaceChildren(...candidates.map((item) => queueCard(item, queue))); if (!candidates.length) container.append(node("div", "empty", "Aucun candidat produit. Le travail actif reste indépendant."));
  const decisions = $("roadmap-decisions"); decisions.replaceChildren(); visiblePending(data.product_memory).filter((item) => item.roadmap?.length).forEach((item) => { const button = node("button", "roadmap-decision", `${item.title} · roadmap ${item.roadmap.join(", ")}`); button.addEventListener("click", () => { activateView("decisions"); openDecisionWorkspace(item); }); decisions.append(button); }); if (!decisions.children.length) decisions.append(node("div", "empty", "Aucune porte de décision visible."));
  const campaign = $("factory-campaign"); campaign.replaceChildren(); campaigns.forEach((item) => { const card = node("article", "memory-card factory-campaign-card"); card.append(node("h3", "", item.title), node("p", "", `Position globale ${item.position} · ${item.state_label} · séparée de la roadmap produit.`)); campaign.append(card); }); if (!campaign.children.length) campaign.append(node("div", "empty", "Aucune campagne Factory dans la file."));
}

function renderDeliveryEvidence(data) {
  const parts = String(data.last_delivered || "").split(" — ");
  $("roadmap-delivered-title").textContent = parts.shift() || "Aucun résultat livré résolu";
  $("roadmap-delivered-proof").textContent = parts.join(" — ") || "Aucune preuve de livraison résolue.";
  $("roadmap-delivery-verification").textContent = `PROVEN · ${data.verified_by} · ${data.model_calls} appel modèle`;
}

async function loadDeliveryEvidence() {
  if (deliveryEvidenceLoading) return;
  deliveryEvidenceLoading = true; deliveryEvidence = null; if (snapshot) renderRoadmap(snapshot); $("roadmap-delivery-verification").textContent = "Vérification exacte via Beads, Gas City et GitHub…";
  try {
    const response = await fetch("/api/delivery-evidence", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    deliveryEvidence = data; renderDeliveryEvidence(data);
  } catch (error) { $("roadmap-delivery-verification").textContent = `Preuve GitHub indisponible : ${error.message}. Le relevé courant reste affiché sans être présenté comme vérifié.`; }
  finally { deliveryEvidenceLoading = false; }
}

function renderWorkflow(memory, data) {
  const stages = memory.delivery_workflow || []; let active = 0;
  if (data.focus?.id) active = data.focus.state === "queued" ? 2 : data.focus.state === "working" ? (data.agents.length ? 4 : 3) : data.focus.steps?.complete ? 5 : 2;
  const flow = $("delivery-workflow"); flow.replaceChildren(); stages.forEach((item, index) => { const state = index < active ? "done" : index === active ? "active" : "upcoming"; const card = node("article", `workflow-node ${state}`); card.append(node("span", "workflow-index", String(index + 1)), node("strong", "", item.title), node("small", "", item.detail)); if (state === "active") card.append(node("span", "workflow-live", "Ici maintenant")); flow.append(card); if (index < stages.length - 1) flow.append(node("span", "workflow-arrow", "→")); });
  const context = $("context-graph"); context.replaceChildren(); [[operatorName() || "Opérateur", "Intentions et décisions", "human"], ["PO GPT", "Vision, roadmap et mémoire", "po"], ["Mayor", "Résultat autorisé et livraison", "mayor"], ["Beads", "Travail et dépendances", "beads"], ["Agents", "Une tâche bornée", "agents"], ["GitHub", "Preuve livrée", "github"]].forEach(([title, detail, kind], index, all) => { const card = node("article", `context-node ${kind}`); card.append(node("strong", "", title), node("small", "", detail)); context.append(card); if (index < all.length - 1) context.append(node("span", "context-arrow", "→")); });
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
  if (view === "roadmap") loadDeliveryEvidence();
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
  const messages = $("po-messages"); messages.replaceChildren(); (data.messages || []).forEach((message) => { const bubble = node("article", `po-message ${["PO", "Mayor"].includes(message.role) ? "from-po" : "from-human"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text)); if (message.intent === "record") bubble.append(node("small", "", "Demande d’enregistrement")); messages.append(bubble); }); if (!messages.children.length) messages.append(node("div", "empty", "Commence une discussion générale ou ouvre une décision à trancher.")); if (working) messages.append(node("div", "po-thinking", "Le PO lit le contexte et prépare sa réponse…")); if (data.error) messages.append(node("div", "alert", data.error)); messages.scrollTop = messages.scrollHeight;
  $("copy-po-thread").disabled = !data.thread_id; $("copy-po-thread").dataset.threadId = data.thread_id || ""; $("po-token-usage").textContent = data.usage ? `${formatTokens(data.usage.total_tokens)} tokens · compteur local` : "Aucun token mesuré"; const codex = $("open-po-codex"); codex.classList.toggle("hidden", !data.codex_url); if (data.codex_url) codex.href = data.codex_url;
  const list = $("po-conversation-list"); list.replaceChildren(); (data.conversations || []).forEach((item) => { const card = node("button", `conversation-card ${item.key === data.key ? "active" : ""}`); card.append(node("strong", "", item.title), node("small", "", `${item.kind === "decision" ? "Décision" : "Général"} · ${item.status === "not_started" ? "pas démarrée" : item.status} · ${item.usage ? `${formatTokens(item.usage.total_tokens)} tokens` : "0 token mesuré"}`)); card.addEventListener("click", () => item.decision_id ? openDecisionById(item.decision_id) : loadPOConversation(item.key)); list.append(card); }); if (!list.children.length) list.append(node("p", "muted", "Aucune session. Les décisions en créent une seulement au premier envoi."));
  if (working) { clearTimeout(poPoll); poPoll = setTimeout(loadPOConversation, 2500); }
}

async function loadPOConversation(key = null) { try { const query = key ? `?key=${encodeURIComponent(key)}` : ""; const response = await fetch(`/api/po/conversation${query}`, { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); renderPO(data); } catch (error) { $("po-feedback").textContent = `PO indisponible : ${error.message}`; } }
async function sendPO() { const message = $("po-message").value.trim(); if (!message) { $("po-feedback").textContent = "Écris un message ou une réponse."; return; } $("send-po").disabled = true; $("po-feedback").textContent = "Message remis au PO…"; try { const response = await fetch("/api/po/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: JSON.stringify({ message, intent: $("po-intent").value, conversation_key: currentPOKey }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); currentPOKey = data.key; $("po-message").value = ""; $("po-feedback").textContent = "Le PO prépare sa réponse; tu peux ouvrir un autre sujet pendant ce temps."; loadPOConversation(currentPOKey); } catch (error) { $("po-feedback").textContent = `Envoi impossible : ${error.message}`; $("send-po").disabled = false; } }
async function newPOConversation() { try { const response = await fetch("/api/po/new", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: "{}" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); currentPOKey = data.key; $("po-feedback").textContent = "Espace prêt. Aucune session ni token avant ton premier envoi."; loadPOConversation(currentPOKey); } catch (error) { $("po-feedback").textContent = `Impossible : ${error.message}`; } }

function openDecisionById(id) { const decision = snapshot?.product_memory?.decisions.find((item) => item.id === id); if (decision) { activateView("decisions"); openDecisionWorkspace(decision); } }
function renderDecisionSwitcher(data) {
  poIndex = data.conversations || poIndex; const pending = snapshot ? visiblePending(snapshot.product_memory) : []; const switcher = $("decision-switcher"); switcher.replaceChildren(); let workingCount = 0;
  pending.forEach((decision) => { const conversation = poIndex.find((item) => item.decision_id === decision.id); const working = ["queued", "running"].includes(conversation?.status); const unread = decision.id !== currentDecision?.id && hasUnreadReply(conversation); if (working) workingCount += 1; const button = node("button", `decision-switch ${decision.id === currentDecision?.id ? "active" : ""} ${unread ? "unread" : ""}`); button.append(node("span", "decision-switch-domain", decision.domain), node("strong", "", decision.title), node("small", "", unread ? "Réponse du PO" : working ? "PO travaille…" : conversation ? "Conversation en cours" : "Pas lancée")); button.addEventListener("click", () => openDecisionWorkspace(decision)); switcher.append(button); });
  const unread = unreadReplyCount(); $("decision-switcher-summary").textContent = [workingCount && `${workingCount} en cours`, unread && `${unread} réponse${unread > 1 ? "s" : ""}`].filter(Boolean).join(" · ") || "Passe d’un sujet à l’autre en un clic"; updateDecisionNav(pending.length);
}
function renderDecisionConversation(data) {
  const working = ["queued", "running"].includes(data.status); const lastPO = [...(data.messages || [])].reverse().find((message) => message.role === "PO" && message.timestamp); if (lastPO && currentDecision) localStorage.setItem(`factory-cockpit-decision-seen:${currentDecision.id}`, lastPO.timestamp); renderDecisionSwitcher(data); const messages = $("decision-messages"); messages.replaceChildren();
  (data.messages || []).forEach((message) => { const bubble = node("article", `po-message ${["PO", "Mayor"].includes(message.role) ? "from-po" : "from-human"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text)); messages.append(bubble); }); if (!messages.children.length) messages.append(node("div", "empty", "Cette décision n’a pas encore de session. Elle sera créée uniquement quand tu enverras le premier message.")); if (working) messages.append(node("div", "po-thinking", "Le PO travaille sur cette décision; ouvre un autre sujet avec la barre ci-dessus."));
  $("send-decision-po").disabled = working; $("send-decision-po").textContent = data.status === "not_started" ? "Commencer avec le PO" : "Envoyer au PO"; setStatus($("decision-current-state"), working ? "working" : data.status === "error" ? "down" : "idle", working ? "PO travaille" : data.status === "not_started" ? "Pas lancée" : data.status === "error" ? "Erreur" : "À toi"); $("decision-token-usage").textContent = data.usage ? `${formatTokens(data.usage.total_tokens)} tokens · compteur local` : "Aucun token consommé"; $("copy-decision-thread").disabled = !data.thread_id; $("copy-decision-thread").dataset.threadId = data.thread_id || ""; const link = $("open-decision-codex"); link.classList.toggle("hidden", !data.codex_url); if (data.codex_url) link.href = data.codex_url; if (data.error) $("decision-feedback").textContent = data.error;
  renderMobileDecisionConversation(data);
  clearTimeout(decisionPoll); if (currentDecision) decisionPoll = setTimeout(loadDecisionConversation, 3000);
}
async function loadDecisionConversation() { if (!currentDecision) return; try { const expectedId = currentDecision.id; const response = await fetch(`/api/po/conversation?decision_id=${encodeURIComponent(expectedId)}`, { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); if (currentDecision?.id === expectedId) renderDecisionConversation(data); } catch (error) { $("decision-feedback").textContent = `PO indisponible : ${error.message}`; } }
async function loadPOIndex() { try { const response = await fetch("/api/po/index", { cache: "no-store" }); const data = await response.json(); if (!response.ok) return; poIndex = data.conversations || []; const unread = unreadReplyCount(); const added = knownUnreadReplies === null ? 0 : unread - knownUnreadReplies; if (added > 0) toast(`${added} nouvelle${added > 1 ? "s" : ""} réponse${added > 1 ? "s" : ""} du PO`); knownUnreadReplies = unread; updateDecisionNav(); if (currentDecision) renderDecisionSwitcher({ conversations: poIndex }); } catch (_) {} }
async function sendDecisionPO() { if (!currentDecision) return; const message = $("decision-message").value.trim(); if (!message) return; $("send-decision-po").disabled = true; $("decision-feedback").textContent = "Session dédiée remise au PO…"; try { const response = await fetch("/api/po/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: JSON.stringify({ message, intent: $("decision-intent").value, decision_id: currentDecision.id }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); $("decision-message").value = ""; $("decision-feedback").textContent = "Le PO répond ici; les autres décisions restent disponibles."; loadDecisionConversation(); } catch (error) { $("decision-feedback").textContent = `Envoi impossible : ${error.message}`; $("send-decision-po").disabled = false; } }

function renderPreview(data) { const panel = document.querySelector(".preview-panel"); if (panel) panel.classList.toggle("hidden", data.state === "unconfigured"); if (data.state === "unconfigured") return; const busy = Boolean(data.action); setStatus($("preview-state"), busy ? "working" : data.state === "running" ? "idle" : data.error ? "down" : "waiting", busy ? `${data.action}…` : data.state === "running" ? "Disponible" : "Arrêtée"); $("preview-policy").textContent = data.version_policy; $("preview-grid").replaceChildren(...(data.components || []).map((component) => { const cell = node("div"); cell.append(node("span", "", component.label), node("strong", "", `${component.health} · ${String(component.sha).slice(0, 8)}`), node("small", "", component.command)); return cell; })); [$("start-preview"), $("restart-preview"), $("stop-preview")].forEach((button) => { button.disabled = busy; }); const open = $("open-preview"); open.classList.toggle("hidden", data.state !== "running"); open.href = data.browser_url; $("preview-feedback").textContent = data.error || (busy ? "Le contrôle sécurisé prépare la bonne version…" : ""); if (busy) setTimeout(loadPreviewStatus, 2500); }
async function loadPreviewStatus() { try { const response = await fetch("/api/preview/status", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); renderPreview(data); } catch (error) { $("preview-feedback").textContent = `État indisponible : ${error.message}`; } }
async function previewAction(action) { $("preview-feedback").textContent = `Action ${action} demandée…`; try { const response = await fetch("/api/preview/action", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-preview-action" }, body: JSON.stringify({ action }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); loadPreviewStatus(); } catch (error) { $("preview-feedback").textContent = `Impossible : ${error.message}`; } }

function compareVisit(data) {
  if (visitCompared) return; visitCompared = true; const key = "factory-cockpit-last-visit-v2"; const current = { focus: data.focus.id, state: data.focus.state, delivery: data.last_delivery.id, pending: visiblePending(data.product_memory).length, at: data.generated_at }; let previous = null; try { previous = JSON.parse(localStorage.getItem(key)); } catch (_) {}
  const changes = []; if (previous) { if (previous.focus !== current.focus) changes.push("le résultat en cours a changé"); else if (previous.state !== current.state) changes.push("son état a évolué"); if (previous.delivery !== current.delivery) changes.push("une nouvelle livraison est enregistrée"); if (previous.pending !== current.pending) changes.push("la liste des décisions a changé"); }
  if (changes.length) { $("since-visit").textContent = `Depuis ta dernière visite : ${changes.join(" · ")}.`; $("since-visit").classList.remove("hidden"); } localStorage.setItem(key, JSON.stringify(current));
}

function render(data) {
  snapshot = data; applyIdentity(data.product_memory?.product, data.operator); setStatus($("factory-state"), data.factory.state, data.factory.label); renderOperationalState(data); renderCampaignState(data); $("focus-title").textContent = data.focus.title; setStatus($("focus-state"), data.focus.state, data.focus.state_label); $("focus-phase").textContent = data.focus.phase; timed($("focus-elapsed"), data.focus.started_at); $("focus-signal").dataset.signalTime = data.focus.last_signal_at || ""; $("focus-signal").textContent = signalAge(data.focus.last_signal_at); const steps = data.focus.steps; $("focus-steps").textContent = steps.total ? `${steps.completed} / ${steps.total}` : "aucune étape exposée"; $("step-fill").style.width = steps.total ? `${Math.round((steps.completed / steps.total) * 100)}%` : "0%"; renderTodayAttention(data.today); const delivered = data.last_delivery; $("last-delivery").textContent = `Dernière livraison : ${delivered.title}${delivered.pr ? ` · PR ${delivered.pr}` : ""}${delivered.ci === "success" ? " · CI verte" : ""}`;
  renderDecisionAids(data.decision_aids || []); renderQueue(data.queue || []); renderMemory(data.product_memory, data.today); renderBusiness(data.product_memory); renderProject(data.product_memory, data); renderRoadmap(data); renderWorkflow(data.product_memory, data); renderBoard(data.product_work || []); renderAgents(data.agents || []);
  const factoryWork = $("factory-work"); factoryWork.replaceChildren(); (data.factory_work || []).forEach((item) => factoryWork.append(node("div", "compact-item", item.title))); if (!factoryWork.children.length) factoryWork.append(node("p", "muted", "Aucun autre travail Factory.")); const infrastructure = $("infrastructure"); infrastructure.replaceChildren(); (data.infrastructure || []).forEach((item) => infrastructure.append(node("div", "compact-item", `${item.name} · ${item.state}`)));
  const alert = $("alert"); if (data.warnings.length) { alert.textContent = `Visibilité partielle : ${data.warnings.join(" · ")}`; alert.classList.remove("hidden"); } else alert.classList.add("hidden"); renderMobile(data); compareVisit(data); updateClocks(); restoreDeepLink();
}

async function refresh() { if (loading) return; loading = true; $("refresh").disabled = true; try { const response = await fetch("/api/snapshot", { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); render(await response.json()); } catch (error) { $("alert").textContent = `Cockpit indisponible : ${error.message}`; $("alert").classList.remove("hidden"); setStatus($("factory-state"), "down", "Cockpit indisponible"); setStatus($("mobile-factory-state"), "down", "Cockpit indisponible"); } finally { loading = false; $("refresh").disabled = false; } }

async function loadTokens() {
  $("refresh-tokens").disabled = true; $("token-sessions").replaceChildren(node("div", "empty", "Lecture des compteurs locaux…"));
  try { const response = await fetch("/api/tokens", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); tokenLoaded = true; const cards = $("token-summary").children; cards[1].querySelector("strong").textContent = formatTokens(data.factory.known_total_tokens); cards[1].querySelector("small").textContent = data.factory.coverage; cards[2].querySelector("strong").textContent = formatTokens(data.host_codex_24h.total_tokens); cards[2].querySelector("small").textContent = `${data.host_codex_24h.sessions} sessions Codex locales`; const table = $("token-sessions"); table.replaceChildren(); (data.factory.sessions || []).forEach((entry) => { const row = node("article", "token-row"); const identity = node("div"); identity.append(node("strong", "", entry.name), node("small", "", `${entry.provider} · ${entry.confidence}`)); const total = node("strong", "token-total", formatTokens(entry.usage.total_tokens)); const breakdown = node("div", "token-breakdown", [entry.usage.input_tokens !== undefined && `entrée ${formatTokens(entry.usage.input_tokens)}`, entry.usage.cached_input_tokens !== undefined && `cache ${formatTokens(entry.usage.cached_input_tokens)}`, entry.usage.output_tokens !== undefined && `sortie ${formatTokens(entry.usage.output_tokens)}`, entry.usage.reasoning_output_tokens !== undefined && `raisonnement ${formatTokens(entry.usage.reasoning_output_tokens)}`].filter(Boolean).join(" · ") || "total estimé"); row.append(identity, total, breakdown); table.append(row); }); if (!table.children.length) table.append(node("div", "empty", "Aucun compteur Factory corrélé.")); const notes = $("token-notes"); notes.replaceChildren(); data.notes.forEach((note) => notes.append(node("p", "", note))); } catch (error) { $("token-sessions").replaceChildren(node("div", "empty", `Compteurs indisponibles : ${error.message}`)); } finally { $("refresh-tokens").disabled = false; }
}

function renderConversation(data) { const container = $("mayor-conversation"); container.replaceChildren(); const channel = data.channel || { state: "idle", label: "Disponible" }; const visual = { transmitting: "working", delivered: "waiting", waiting: "waiting", responded: "idle", failed: "down", late_response: "attention", empty_response: "down", idle: "idle" }; setStatus($("mayor-chat-state"), visual[channel.state] || "waiting", channel.label); (data.messages || []).forEach((message) => { const bubble = node("article", `message ${message.role === "Mayor" ? "from-mayor" : "from-human"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text), node("small", "muted", message.delivery_state === "delivered" ? "Remis" : "Réponse observée")); container.append(bubble); }); if (!container.children.length) container.append(node("div", "empty", "Aucun échange récent depuis ce cockpit.")); if (channel.detail) $("mayor-feedback").textContent = channel.detail; if (["transmitting", "delivered", "waiting"].includes(channel.state)) setTimeout(loadConversation, 3000); renderMobileMayor(data); }
async function loadConversation() { try { const response = await fetch("/api/mayor/conversation", { cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); renderConversation(data); } catch (error) { $("mayor-conversation").replaceChildren(node("div", "empty", `Conversation indisponible : ${error.message}`)); setStatus($("mayor-chat-state"), "down", "Échec"); $("mobile-mayor-conversation").replaceChildren(node("div", "empty", `Canal indisponible : ${error.message}`)); setStatus($("mobile-mayor-state"), "down", "Échec"); $("mobile-tab-mayor-count").textContent = "échec"; } }
async function sendMayor() { const message = $("mayor-message").value.trim(); if (!message) return; $("send-mayor").disabled = true; setStatus($("mayor-chat-state"), "working", "Transmission"); $("mayor-feedback").textContent = "Transmission au Mayor…"; try { const response = await fetch("/api/mayor/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-message" }, body: JSON.stringify({ message, intent: $("mayor-intent").value }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); $("mayor-message").value = ""; $("mayor-feedback").textContent = `${data.channel?.label || "Remis"}; attente d’une réponse observée.`; setStatus($("mayor-chat-state"), "waiting", data.channel?.label || "Remis"); setTimeout(loadConversation, 1000); } catch (error) { $("mayor-feedback").textContent = `Envoi impossible : ${error.message}`; setStatus($("mayor-chat-state"), "down", "Échec"); } finally { $("send-mayor").disabled = false; } }
function humanSummary(data) { const state = data.human_state; return [`Agent Factory`, `Santé : ${state.health.label}`, `Activité : ${state.activity.label} — ${state.activity.detail}`, `Résultat : ${state.result.title} — ${state.result.state_label}`, `Campagne : ${state.campaign.state_label}${state.campaign.blocked ? ` — ${state.campaign.cause}` : ""}`, `Reprise automatique : ${state.resume.automatic ? "oui" : "non"}`, `Condition : ${state.resume.condition || "aucune"}`, `Responsable : ${state.resume.owner_label}`, `Action utile : ${state.resume.action}`, `Décision bloquante ${operatorName() || "opérateur"} : ${state.needs_benjamin || "aucune"}`, `Blocages effectifs : ${(data.today?.effective_blockers || []).length}`, `Décisions générales ouvertes : ${(data.today?.general_decisions || []).length}`, `Prochain candidat : ${state.next_candidate ? `${state.next_candidate.id} · ${state.next_candidate.title} · ${state.next_candidate.state_label}` : "aucun"}`].join("\n"); }

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => activateView(button.dataset.view)));
$("refresh").addEventListener("click", refresh); $("refresh-tokens").addEventListener("click", loadTokens); $("work-search").addEventListener("input", () => snapshot && renderBoard(snapshot.product_work || [])); $("reference-search").addEventListener("input", applyReferenceSearch); $("focus-card").addEventListener("click", () => snapshot?.focus?.id && openItem({ ...snapshot.focus, store: "city" })); $("focus-card").addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); $("focus-card").click(); } }); $("close-drawer").addEventListener("click", () => $("detail-drawer").close()); $("detail-drawer").addEventListener("click", (event) => { if (event.target === $("detail-drawer")) $("detail-drawer").close(); });
$("open-blocker-decision").addEventListener("click", () => { const id = $("open-blocker-decision").dataset.decisionId; if (id) openDecisionById(id); });
$("campaign-block-global").addEventListener("click", () => activateView("today"));
$("resume-action").addEventListener("click", () => { const prompt = $("resume-action").dataset.prompt; if (!prompt) return; $("mayor-message").value = prompt; $("mayor-message").focus(); $("mayor-message").scrollIntoView({ behavior: "smooth", block: "center" }); });
$("copy-summary").addEventListener("click", async () => { if (snapshot) { await navigator.clipboard.writeText(humanSummary(snapshot)); toast("Point de situation copié"); } }); $("copy-po-prompt").addEventListener("click", () => { activateView("po"); $("po-message").value = `Aide-moi à relire la roadmap et à choisir le prochain sujet produit utile, sans lancer de travail.`; $("po-message").focus(); });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("mayor-message").value = button.dataset.prompt; $("mayor-message").focus(); })); $("send-mayor").addEventListener("click", sendMayor); $("refresh-conversation").addEventListener("click", loadConversation);
$("send-po").addEventListener("click", sendPO); $("new-po-conversation").addEventListener("click", newPOConversation); $("copy-po-thread").addEventListener("click", async () => { const id = $("copy-po-thread").dataset.threadId; if (id) { await navigator.clipboard.writeText(id); toast("Identifiant de discussion copié"); } });
$("open-design-decision").addEventListener("click", () => { const decision = snapshot?.product_memory?.decisions.find((item) => item.domain === "project" && item.title === "Socle du workflow design"); if (decision) { activateView("decisions"); openDecisionWorkspace(decision); } }); $("close-decision-workspace").addEventListener("click", closeDecisionWorkspace); $("send-decision-po").addEventListener("click", sendDecisionPO); $("copy-decision-thread").addEventListener("click", async () => { const id = $("copy-decision-thread").dataset.threadId; if (id) { await navigator.clipboard.writeText(id); toast("Identifiant de discussion copié"); } });
$("build-reference-with-po").addEventListener("click", () => { activateView("po"); $("po-message").value = `Aide-moi à compléter la documentation produit de référence ${productName()}. Identifie la section la plus importante encore à valider, propose une représentation visuelle simple et ne lance aucune exécution.`; $("po-message").focus(); }); $("start-preview").addEventListener("click", () => previewAction("start")); $("restart-preview").addEventListener("click", () => previewAction("restart")); $("stop-preview").addEventListener("click", () => previewAction("stop"));
$("release-accept").addEventListener("click", () => submitDirectDecision(releaseDecision, "accept")); $("release-reject").addEventListener("click", () => submitDirectDecision(releaseDecision, "reject")); $("release-option-submit").addEventListener("click", () => { const option = $("release-option").value; if (!option) { $("release-decision-feedback").textContent = "Choisis une option structurée."; return; } submitDirectDecision(releaseDecision, "option", option); }); $("release-other-submit").addEventListener("click", () => submitDirectDecision(releaseDecision, "other", null, $("release-other").value));
$("release-propose").addEventListener("click", () => { const decision = snapshot?.release?.decisions.find((item) => item.id === "release-v1-contract"); submitDirectDecision(decision, "propose", null, null, "release-change-feedback"); }); $("release-validate").addEventListener("click", () => { const decision = snapshot?.release?.decisions.find((item) => item.id === "release-v1-contract"); submitDirectDecision(decision, "validate", null, null, "release-change-feedback"); });
$("release-talk").addEventListener("click", () => { activateView("po"); $("po-message").value = ""; $("po-feedback").textContent = "Champ volontairement vide. Écrire puis envoyer appellera le modèle PO."; $("po-message").focus(); });
$("toggle-enterprise-ignore").addEventListener("click", () => { if (!snapshot) return; const enterprise = snapshot.product_memory.decisions.filter((item) => item.status === "pending" && item.domain === "enterprise"); const ignored = enterpriseIgnored(); const allIgnored = enterprise.length > 0 && enterprise.every((item) => ignored.has(item.id)); enterprise.forEach((item) => allIgnored ? ignored.delete(item.id) : ignored.add(item.id)); saveEnterpriseIgnored(ignored); renderMemory(snapshot.product_memory); renderBusiness(snapshot.product_memory); renderRoadmap(snapshot); });
$("queue-add-form").addEventListener("submit", (event) => { event.preventDefault(); queueMutation("add", { title: $("queue-add-title").value.trim(), why: $("queue-add-why").value.trim(), acceptance: $("queue-add-acceptance").value.trim(), urgency: $("queue-add-urgency").value }); });
$("queue-cancel-submit").addEventListener("click", (event) => { event.preventDefault(); if (!queueCancelItem) return; const reason = $("queue-cancel-reason").value.trim(); const confirmed = $("queue-cancel-confirmed").checked; if (!reason || !confirmed) { setQueueFeedback("L’annulation exige une raison et une confirmation explicite.", true); return; } $("queue-cancel-dialog").close(); queueMutation("cancel", { id: queueCancelItem.id, reason, confirmed: true }); queueCancelItem = null; });
document.querySelectorAll("[data-reference]").forEach((button) => button.addEventListener("click", () => { activateView("project"); loadReference(button.dataset.reference); }));
window.addEventListener("hashchange", () => restoreDeepLink(true));
$("mayor-conversation").replaceChildren(node("div", "empty", "Clique sur « Relire » pour charger les échanges.")); refresh(); loadPOIndex(); setInterval(refresh, 5000); setInterval(loadPOIndex, 5000); setInterval(updateClocks, 1000);


/* ---- Profil mobile -------------------------------------------------------
   Trois écrans seulement : État · Décisions à prendre · Répondre au Mayor.
   Le cockpit complet reste le poste de travail; personne ne pilote une usine
   au téléphone. Tout est rendu depuis le snapshot déjà chargé, donc lire
   reste à 0 token; seuls les deux envois explicites en consomment. */
let mobileDecision = null;
let mobileMayorLoaded = false;
function mobilePendingDecisions() { const memory = snapshot?.product_memory; if (!memory) return []; return visiblePending(memory).filter((item) => item.domain !== "enterprise"); }
function activateMobileView(view) {
  document.querySelectorAll(".mobile-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.mobileView === view));
  document.querySelectorAll(".mobile-screen").forEach((panel) => panel.classList.toggle("active", panel.dataset.mobilePanel === view));
  if (view === "mayor" && !mobileMayorLoaded) { mobileMayorLoaded = true; loadConversation(); }
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function renderMobile(data) {
  const state = data.human_state; const resume = state.resume; const campaign = state.campaign || {};
  setStatus($("mobile-factory-state"), data.factory.state, data.factory.label);
  $("mobile-health").textContent = state.health.label; $("mobile-health-detail").textContent = state.health.detail;
  $("mobile-activity").textContent = state.activity.label; $("mobile-activity-detail").textContent = state.activity.detail;
  $("mobile-resume").textContent = resume.automatic ? "Automatique" : resume.required ? "Action requise" : "Non automatique \u00b7 action facultative";
  $("mobile-resume-condition").textContent = resume.condition || "Aucune"; $("mobile-resume-owner").textContent = resume.owner_label; $("mobile-resume-action").textContent = resume.action;
  const blockers = Array.isArray(data.today?.effective_blockers) ? data.today.effective_blockers : []; const blocker = blockers[0];
  $("mobile-blockers").textContent = blocker?.text || "Aucun blocage effectif.";
  $("mobile-tab-state-count").textContent = blockers.length ? `${blockers.length} blocage${blockers.length > 1 ? "s" : ""}` : "rien à lever";
  const unblock = $("mobile-open-blocker"); unblock.dataset.decisionId = blocker?.decision_id || ""; unblock.classList.toggle("hidden", !blocker?.decision_id);
  const blockedModes = new Set(["fail_closed", "blocking_decision", "blocked", "campaign_blocked"]);
  const blocked = Boolean(campaign.blocked || blockedModes.has(resume.mode));
  $("mobile-block").classList.toggle("hidden", !blocked);
  if (blocked) { $("mobile-block-cause").textContent = campaign.cause || resume.condition || state.activity.detail || "La livraison ne peut pas poursuivre."; $("mobile-block-action").textContent = `Reprise : ${campaign.blocked ? campaign.owner_label : resume.owner_label} \u00b7 ${campaign.blocked ? campaign.action : resume.action}`; }
  const delivered = data.last_delivery; $("mobile-last-delivery").textContent = `Derni\u00e8re livraison : ${delivered.title}${delivered.pr ? ` \u00b7 PR ${delivered.pr}` : ""}${delivered.ci === "success" ? " \u00b7 CI verte" : ""}`;
  renderMobileDecisionList();
}
function renderMobileDecisionList() {
  const items = mobilePendingDecisions(); const list = $("mobile-decision-list"); list.replaceChildren();
  $("mobile-tab-decisions-count").textContent = items.length ? `${items.length} \u00e0 trancher` : "rien";
  items.forEach((item) => { const card = node("button", "mobile-decision-card"); card.type = "button"; card.append(node("span", "eyebrow", `D\u00c9CISION ${item.domain.toUpperCase()}`), node("strong", "", item.title), node("small", "muted", item.detail)); card.addEventListener("click", () => openMobileDecision(item)); list.append(card); });
  if (!items.length) list.append(node("div", "empty", "Rien \u00e0 trancher. Tu peux poser le t\u00e9l\u00e9phone."));
  const enterprise = snapshot ? visiblePending(snapshot.product_memory).filter((item) => item.domain === "enterprise").length : 0;
  $("mobile-enterprise-note").textContent = enterprise ? `${enterprise} d\u00e9cision${enterprise > 1 ? "s" : ""} entreprise \u00b7 \u00e0 traiter sur ordinateur` : "";
}
async function openMobileDecision(decision) {
  mobileDecision = decision; currentDecision = decision;
  $("mobile-decision-domain").textContent = `D\u00c9CISION ${decision.domain.toUpperCase()}`; $("mobile-decision-title").textContent = decision.title; $("mobile-decision-detail-copy").textContent = decision.detail;
  $("mobile-decision-message").value = decisionPrompt(decision); $("mobile-decision-feedback").textContent = "";
  $("mobile-decision-messages").replaceChildren(node("div", "empty", "Lecture de la session\u2026"));
  $("mobile-decision-detail").classList.remove("hidden"); $("mobile-decision-browse").classList.add("hidden");
  await loadDecisionConversation();
}
function closeMobileDecision() { clearTimeout(decisionPoll); mobileDecision = null; currentDecision = null; $("mobile-decision-detail").classList.add("hidden"); $("mobile-decision-browse").classList.remove("hidden"); }
function renderMobileDecisionConversation(data) {
  if (!mobileDecision) return;
  const box = $("mobile-decision-messages"); box.replaceChildren();
  (data.messages || []).forEach((message) => { const bubble = node("article", `po-message ${["PO", "Mayor"].includes(message.role) ? "from-po" : "from-human"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text)); box.append(bubble); });
  if (!box.children.length) box.append(node("div", "empty", "Aucune session. Elle na\u00eet \u00e0 ton premier envoi."));
  const working = ["queued", "running"].includes(data.status);
  $("mobile-send-decision").disabled = working; $("mobile-send-decision").textContent = data.status === "not_started" ? "Commencer avec le PO" : "Envoyer au PO";
  if (working) $("mobile-decision-feedback").textContent = "Le PO pr\u00e9pare sa r\u00e9ponse\u2026";
  box.scrollTop = box.scrollHeight;
}
async function sendMobileDecision() {
  if (!mobileDecision) return; const message = $("mobile-decision-message").value.trim();
  if (!message) { $("mobile-decision-feedback").textContent = "\u00c9cris ta r\u00e9ponse."; return; }
  $("mobile-send-decision").disabled = true; $("mobile-decision-feedback").textContent = "Remis au PO\u2026";
  try { const response = await fetch("/api/po/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-po-message" }, body: JSON.stringify({ message, intent: $("mobile-decision-intent").value, decision_id: mobileDecision.id }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); $("mobile-decision-message").value = ""; $("mobile-decision-feedback").textContent = "Le PO r\u00e9pond ici."; loadDecisionConversation(); } catch (error) { $("mobile-decision-feedback").textContent = `Envoi impossible : ${error.message}`; $("mobile-send-decision").disabled = false; }
}
function renderMobileMayor(data) {
  const channel = data.channel || { state: "idle", label: "Disponible" };
  const visual = { transmitting: "working", delivered: "waiting", waiting: "waiting", responded: "idle", failed: "down", late_response: "attention", empty_response: "down", idle: "idle" };
  setStatus($("mobile-mayor-state"), visual[channel.state] || "waiting", channel.label);
  $("mobile-tab-mayor-count").textContent = channel.label;
  const box = $("mobile-mayor-conversation"); box.replaceChildren();
  (data.messages || []).forEach((message) => { const bubble = node("article", `message ${message.role === "Mayor" ? "from-mayor" : "from-human"}`); bubble.append(node("strong", "", message.role), node("p", "", message.text), node("small", "muted", message.delivery_state === "delivered" ? "Remis" : "R\u00e9ponse observ\u00e9e")); box.append(bubble); });
  if (!box.children.length) box.append(node("div", "empty", "Aucun \u00e9change r\u00e9cent depuis ce cockpit."));
  if (channel.detail) $("mobile-mayor-feedback").textContent = channel.detail;
  box.scrollTop = box.scrollHeight;
}
async function sendMobileMayor() {
  const message = $("mobile-mayor-message").value.trim();
  if (!message) { $("mobile-mayor-feedback").textContent = "\u00c9cris ton message."; return; }
  $("mobile-send-mayor").disabled = true; $("mobile-mayor-feedback").textContent = "Transmission au Mayor\u2026";
  try { const response = await fetch("/api/mayor/message", { method: "POST", headers: { "Content-Type": "application/json", "X-Factory-Cockpit": "human-message" }, body: JSON.stringify({ message, intent: $("mobile-mayor-intent").value }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`); $("mobile-mayor-message").value = ""; $("mobile-mayor-feedback").textContent = `${data.channel?.label || "Remis"}; attente d\u2019une r\u00e9ponse observ\u00e9e.`; setTimeout(loadConversation, 1000); } catch (error) { $("mobile-mayor-feedback").textContent = `Envoi impossible : ${error.message}`; } finally { $("mobile-send-mayor").disabled = false; }
}
document.querySelectorAll(".mobile-tab").forEach((tab) => tab.addEventListener("click", () => activateMobileView(tab.dataset.mobileView)));
document.querySelectorAll("[data-mobile-prompt]").forEach((button) => button.addEventListener("click", () => { $("mobile-mayor-message").value = button.dataset.mobilePrompt; $("mobile-mayor-message").focus(); }));
$("mobile-decision-back").addEventListener("click", closeMobileDecision);
$("mobile-send-decision").addEventListener("click", sendMobileDecision);
$("mobile-send-mayor").addEventListener("click", sendMobileMayor);
$("mobile-refresh").addEventListener("click", refresh);
$("mobile-open-blocker").addEventListener("click", () => { const id = $("mobile-open-blocker").dataset.decisionId; const decision = id ? snapshot?.product_memory?.decisions.find((item) => item.id === id) : null; if (decision) { activateMobileView("decisions"); openMobileDecision(decision); } });

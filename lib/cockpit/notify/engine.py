"""The notification policy engine (spec af-oohx2x §"Notifications";
ticket T17, af-9jrvmi). ``tick(requests, now)`` is the whole public
interface for the policy itself -- same shape as
:class:`~cockpit.heartbeat.emitter.HeartbeatEmitter`: a poller thread
ticks it periodically in production (wiring, a later ticket's job), a
test moves a fake clock and calls it directly.

One dedup entry per Operator Request id, persisted through ``state_store``
(:mod:`cockpit.notify.state_store`) so a cockpit restart never sends a
duplicate (spec .52). Each entry tracks two different things on purpose:
bookkeeping (``niveau_courant``, ``reportee``, ``projet``) is kept in sync
every tick regardless of anything being sent; the dedup-relevant fields
(``niveau_envoye``, ``envoye_a``, ``dernier_rappel_a``, ``pending_kind``)
only advance once a send actually *succeeds*. A failed send leaves
``pending_kind`` set, so next tick's outbox re-sends the exact same
content instead of silently dropping it or moving on to a newer state
(spec .59: "échec [...] réessayé").

Per tick, in order:

  1. an id known from last tick but absent from ``requests`` was Urgent ->
     one push de fin (.55), then its state is dropped; an À faire that
     disappears is dropped silently (no push);
  2. Quand tu veux requests are skipped outright -- never pushed (.51);
  3. an acquittee request fires nothing at all, ever, while acked (.21) --
     bookkeeping is not even touched, so un-acking resumes exactly where
     it left off;
  4. a still-deferred (reportee) Urgent gets no push while deferred (.23)
     -- pending_kind stays whatever it was, so nothing new accrues;
  5. everything else funnels through one pending_kind sentinel: first
     sighting -> "initial"; reappearance right after a defer deadline ->
     "echeance" (.54, same niveau it had before, since niveau never
     changes under Reporter); a niveau change on an existing id ->
     "escalade"; otherwise, Urgent only, a 2 h-cooldown "rappel" (.53).

All pending sends are collected as candidates before anything is sent,
sorted Urgent-first, then the hourly cap (.58) is applied globally:
whatever would exceed 5 sends in the trailing hour becomes one grouped
push instead, so Urgent is never swallowed by a storm of À faire.
"""
from cockpit.notify import content
from cockpit.notify.model import (
    HEALTH_FAILURE_SECONDS,
    HOURLY_CAP,
    PRIORITY_A_FAIRE,
    PRIORITY_URGENT,
    REMINDER_INTERVAL_SECONDS,
)
from cockpit.requests.model import A_FAIRE, DEFAULT_PROJECT, QUAND_TU_VEUX, URGENT

_PRIORITY_BY_NIVEAU = {URGENT: PRIORITY_URGENT, A_FAIRE: PRIORITY_A_FAIRE}

CHANNEL_DOWN_MESSAGE = "canal de notification en panne"


def _fresh_entry(request):
    return {
        "niveau_courant": request.niveau,
        "niveau_envoye": None,
        "envoye_a": None,
        "dernier_rappel_a": None,
        "reportee": request.reportee,
        "pending_kind": None,
        "projet": request.projet,
    }


class NotificationEngine:
    def __init__(self, adapter, state_store, clock, cockpit_url_builder, journal=None):
        self._adapter = adapter
        self._state_store = state_store
        self._clock = clock
        self._cockpit_url = cockpit_url_builder
        self._journal = journal if journal is not None else []
        self._sent_timestamps = []  # trailing-hour cap bookkeeping (spec .58)
        self._delivery_failed = set()  # ids whose last attempt failed (spec .59)
        self._first_failure_at = None

    # -- public: read side ----------------------------------------------
    def journal_entries(self):
        return list(self._journal)

    def undelivered(self):
        """Ids with "notification non livrée" pending (spec .59)."""
        return set(self._delivery_failed)

    def health_issues(self):
        if self._first_failure_at is None:
            return []
        if self._clock.now() - self._first_failure_at >= HEALTH_FAILURE_SECONDS:
            return [CHANNEL_DOWN_MESSAGE]
        return []

    # -- public: actions ---------------------------------------------------
    def send_test(self):
        """"Envoyer une notification de test" (spec .60) -- an explicit,
        single operator gesture. It bypasses dedup and the hourly cap
        entirely; it must never itself count against the cap, or a storm
        of real Urgents could be starved by Benjamin proving the channel
        works."""
        title, body = content.build_test_message()
        ok = self._attempt_send(title, body, PRIORITY_A_FAIRE)
        self._record_journal(None, "test", PRIORITY_A_FAIRE, ok)
        return ok

    def tick(self, requests, now=None):
        now = self._clock.now() if now is None else now
        state = self._state_store.load()
        requests_by_id = {r.id: r for r in requests}
        include_quoi = self._adapter.e2e_available()

        candidates = self._collect_resolved(state, requests_by_id)
        candidates += self._collect_visible(state, requests, now)
        candidates.sort(key=lambda c: 0 if c["niveau"] == URGENT else 1)

        sent_recent = len([t for t in self._sent_timestamps if now - t < 3600])
        budget = max(0, HOURLY_CAP - sent_recent)
        to_send, overflow = candidates[:budget], candidates[budget:]

        any_failed = False
        for cand in to_send:
            ok = self._deliver(cand, now, include_quoi)
            any_failed = any_failed or not ok
            if ok:
                self._sent_timestamps.append(now)
                self._commit(state, cand, now)

        if overflow:
            niveau_max = URGENT if any(c["niveau"] == URGENT for c in overflow) else A_FAIRE
            title, body = content.build_grouped_message(len(overflow), self._cockpit_url(None))
            priority = _PRIORITY_BY_NIVEAU[niveau_max]
            ok = self._attempt_send(title, body, priority)
            self._record_journal(None, "groupe", priority, ok, extra={"count": len(overflow)})
            any_failed = any_failed or not ok
            if ok:
                self._sent_timestamps.append(now)
                for cand in overflow:
                    self._commit(state, cand, now)
                    self._delivery_failed.discard(cand["req_id"])
            else:
                for cand in overflow:
                    self._delivery_failed.add(cand["req_id"])

        if any_failed:
            if self._first_failure_at is None:
                self._first_failure_at = now
        else:
            self._first_failure_at = None

        self._state_store.save(state)
        return {"sent": len(to_send), "grouped": len(overflow)}

    # -- candidate collection --------------------------------------------
    def _collect_resolved(self, state, requests_by_id):
        candidates = []
        for req_id in list(state.keys()):
            if req_id in requests_by_id:
                continue
            entry = state[req_id]
            was_urgent = entry.get("niveau_courant") == URGENT or entry.get("niveau_envoye") == URGENT
            if not was_urgent:
                state.pop(req_id, None)
                continue
            if entry.get("pending_kind") is None:
                entry["pending_kind"] = "resolu"
            candidates.append(
                {
                    "req_id": req_id,
                    "kind": "resolu",
                    "niveau": URGENT,
                    "request": None,
                    "projet": entry.get("projet", DEFAULT_PROJECT),
                }
            )
        return candidates

    def _collect_visible(self, state, requests, now):
        candidates = []
        for request in requests:
            if request.niveau == QUAND_TU_VEUX:
                continue
            entry = state.get(request.id)
            if entry is None:
                entry = _fresh_entry(request)
                state[request.id] = entry
            if request.acquittee:
                continue

            prev_reportee = entry["reportee"]
            entry["reportee"] = request.reportee
            entry["niveau_courant"] = request.niveau
            entry["projet"] = request.projet

            if request.reportee:
                continue

            if entry["pending_kind"] is None:
                if entry["envoye_a"] is None:
                    entry["pending_kind"] = "initial"
                elif prev_reportee:
                    entry["pending_kind"] = "echeance"
                elif entry["niveau_envoye"] != request.niveau:
                    entry["pending_kind"] = "escalade"
                elif request.niveau == URGENT:
                    last = entry["dernier_rappel_a"] or entry["envoye_a"]
                    if now - last >= REMINDER_INTERVAL_SECONDS:
                        entry["pending_kind"] = "rappel"

            if entry["pending_kind"] is not None:
                candidates.append(
                    {
                        "req_id": request.id,
                        "kind": entry["pending_kind"],
                        "niveau": request.niveau,
                        "request": request,
                    }
                )
        return candidates

    # -- delivery ----------------------------------------------------------
    def _deliver(self, cand, now, include_quoi):
        kind = cand["kind"]
        if kind == "resolu":
            title, body = content.build_resolved_message(cand["projet"], self._cockpit_url(cand["req_id"]))
            priority = PRIORITY_URGENT
        else:
            request = cand["request"]
            title, body = content.build_message(
                request, include_quoi, self._cockpit_url(request.id), is_reminder=(kind == "rappel")
            )
            priority = _PRIORITY_BY_NIVEAU.get(request.niveau, PRIORITY_A_FAIRE)
        ok = self._attempt_send(title, body, priority)
        request = cand.get("request")
        self._record_journal(
            cand["req_id"], kind, priority, ok, extra={"quoi": request.quoi} if request is not None else None
        )
        if ok:
            self._delivery_failed.discard(cand["req_id"])
        else:
            self._delivery_failed.add(cand["req_id"])
        return ok

    def _commit(self, state, cand, now):
        req_id = cand["req_id"]
        if cand["kind"] == "resolu":
            state.pop(req_id, None)
            return
        entry = state[req_id]
        entry["envoye_a"] = now
        entry["niveau_envoye"] = cand["niveau"]
        entry["pending_kind"] = None
        entry["dernier_rappel_a"] = now if cand["niveau"] == URGENT else None

    def _attempt_send(self, title, body, priority):
        try:
            self._adapter.send(title, body, priority)
        except Exception:
            return False
        return True

    def _record_journal(self, req_id, kind, priority, ok, extra=None):
        entry = {"req_id": req_id, "kind": kind, "priority": priority, "ok": ok, "quand": self._clock.now()}
        if extra:
            entry.update(extra)
        self._journal.append(entry)

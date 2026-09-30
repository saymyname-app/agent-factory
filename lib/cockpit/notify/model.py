"""Pushover push priorities and the notify policy's fixed intervals (spec
af-oohx2x §"Notifications"). Urgent is capped at Pushover's own
"high priority" (1) -- ``PRIORITY_URGENT``/``PRIORITY_A_FAIRE`` are the
*only* two priority values this whole module ever produces; "jamais 2 ni
« critical »" is enforced structurally (nothing here even defines a value
for 2), not by a runtime check alone.
"""

PRIORITY_URGENT = 1
PRIORITY_A_FAIRE = 0

REMINDER_INTERVAL_SECONDS = 2 * 60 * 60  # rappel toutes les 2 h (spec .53)
HOURLY_CAP = 5  # plafond 5 pushes/h (spec .58)
HEALTH_FAILURE_SECONDS = 15 * 60  # "canal de notification en panne" (spec .59)

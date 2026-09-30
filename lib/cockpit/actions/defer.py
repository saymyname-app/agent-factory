"""Reporter's defer-until computation (spec af-oohx2x §"Actions
opérateur": "Reporter (Urgent et À faire : 1 h, 4 h, demain 09:00, heure
libre)"; T13 AC3).

Pure function of the cockpit's own clock (never ``time.time()`` directly
-- same discipline as :mod:`cockpit.core.clock`) so a test can move time
forward deterministically to prove a deferred request returns exactly at
its deadline.
"""
from datetime import datetime, timedelta

from cockpit.core.readmodel import PARIS

ONE_HOUR = "1h"
FOUR_HOURS = "4h"
TOMORROW_09H = "demain_09h"
FREE_TIME = "libre"

OPTIONS = (ONE_HOUR, FOUR_HOURS, TOMORROW_09H, FREE_TIME)


def compute_defer_until(option, clock, custom_epoch=None):
    """Returns the epoch seconds a deferred request becomes due again.
    ``demain_09h`` is always the next calendar day at 09:00 Europe/Paris,
    regardless of how close to 09:00 "now" already is -- "demain" means
    tomorrow, not "the next occurrence of 09:00"."""
    now = clock.now()
    if option == ONE_HOUR:
        return now + 3600
    if option == FOUR_HOURS:
        return now + 4 * 3600
    if option == TOMORROW_09H:
        now_paris = datetime.fromtimestamp(now, tz=PARIS)
        target = (now_paris + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return target.timestamp()
    if option == FREE_TIME:
        if custom_epoch is None:
            raise ValueError("l'option « heure libre » demande une échéance")
        return float(custom_epoch)
    raise ValueError("option de report inconnue : %s" % option)

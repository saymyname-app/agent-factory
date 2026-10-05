#!/usr/bin/env python3
"""PROTOTYPE JETABLE (af-0sayxf.18) -- lance le cockpit d'origin/main sur de
fausses sources (faux gc, faux bd des tests) et sert le prototype a cote.

Usage : python3 prototypes/af-0sayxf-fidelity-proof/serve.py [--once]
  --once : ecrit out/delivered.html et out/prototype.html puis s'arrete.
Sans option : reste au premier plan (Ctrl-C pour arreter).
  cockpit livre  : http://127.0.0.1:18173/
  prototype      : http://127.0.0.1:18174/prototype.html#D
Donnees synthetiques uniquement. Ne touche ni gc ni bd reels.
"""
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
CORE_FIX = ROOT / "tests" / "fixtures" / "cockpit" / "core"
REQ_FIX = ROOT / "tests" / "fixtures" / "cockpit" / "requests"
COCKPIT_PORT, PROTO_PORT = 18173, 18174

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(CORE_FIX))
from fake_gc import FakeGc  # noqa: E402

spec = importlib.util.spec_from_file_location("rt", ROOT / "tests" / "cockpit-requests-test.py")
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

OPTIONS = [
    {"option": "Approuver", "consequence": "le graphe est publie et la livraison demarre", "recommande": True,
     "raison": "la Spec est approuvee et le graphe la couvre"},
    {"option": "Renvoyer en planification", "consequence": "rien ne demarre, la carte est rouverte"},
]
BEADS = [
    rt.escalation_bead("af-demo1", "l'usine est muette", "plus rien ne repond depuis 20 minutes",
                       OPTIONS, "2026-09-30T09:00:00Z", bloquant=True),
    rt.escalation_bead("af-demo2", "une Spec attend ton accord", "elle change la portee du travail livre",
                       OPTIONS, "2026-09-30T08:00:00Z", bloquant=False, project="agent-factory"),
    rt.escalation_bead("af-demo3", "un graphe de tickets attend ton accord", "12 tickets, 3 vagues",
                       OPTIONS, "2026-09-30T08:30:00Z", bloquant=False, project="saymyname"),
    rt.proposal_bead("af-demo4", "regrouper deux rituels", "ils se recoupent", OPTIONS, "2026-09-30T07:00:00Z"),
]


MUTATIONS = [
    ("--r:10px;", "--r:6px;"),                                      # M1 rayon des coins (token)
    ("--muted:#687286;", "--muted:#7C8598;"),                       # M2 gris attenue un peu plus clair (token, theme clair)
    ("background:transparent;padding:11px 14px;", "background:transparent;padding:8px 14px;"),  # M3 ligne de demande plus serree
    (".vc .li .q{font-weight:600;", ".vc .li .q{font-weight:500;"),  # M4 titre de demande moins gras
    ('<span class="who">usine + projets</span>', ""),               # M5 sous-titre de la marque retire
]


def get(port, path):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=3) as r:
        return r.read().decode("utf-8")


def main():
    once = "--once" in sys.argv
    OUT.mkdir(exist_ok=True)
    proto_html = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", "origin/prototype/c01-home-screen:prototypes/c01-home-screen/index.html"])
    # BOM : http.server n'annonce pas de charset et le prototype n'en declare pas.
    (OUT / "prototype.html").write_bytes(b"\xef\xbb\xbf" + proto_html)
    # Temoin "presque fidele" : le prototype avec 5 petits defauts semes.
    mutant = proto_html.decode("utf-8")
    for old, new in MUTATIONS:
        assert old in mutant, old
        mutant = mutant.replace(old, new)
    (OUT / "mutant.html").write_bytes(b"\xef\xbb\xbf" + mutant.encode("utf-8"))
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))

    tmp = tempfile.mkdtemp(prefix="fidelity-")
    state = os.path.join(tmp, "beads.json")
    with open(state, "w") as fh:
        json.dump(BEADS, fh)
    gc = FakeGc().start()
    env = dict(os.environ, COCKPIT_HOST="127.0.0.1", COCKPIT_PORT=str(COCKPIT_PORT),
               COCKPIT_GC_BASE_URL=gc.base_url, COCKPIT_BD_BIN=str(REQ_FIX / "fake-bd"),
               COCKPIT_PID_FILE=os.path.join(tmp, "cockpit.pid"), COCKPIT_BEADS_POLL_SECONDS="0.2",
               FAKE_BD_STATE_FILE=state)
    cockpit = subprocess.Popen([sys.executable, str(ROOT / "bin" / "cockpit"), "run"], env=env)
    static = subprocess.Popen([sys.executable, "-m", "http.server", str(PROTO_PORT), "--bind", "127.0.0.1",
                               "--directory", str(OUT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        rt.wait_for_port("127.0.0.1", COCKPIT_PORT)
        gc.push_event({"running": True, "partial": False})
        rt.wait_until(lambda: len(json.loads(get(COCKPIT_PORT, "/api/requests"))["requests"]) == len(BEADS), timeout=10)
        (OUT / "delivered.html").write_text(get(COCKPIT_PORT, "/"), encoding="utf-8")
        print("delivered: http://127.0.0.1:%d/   prototype: http://127.0.0.1:%d/prototype.html#D" % (COCKPIT_PORT, PROTO_PORT), flush=True)
        if not once:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (cockpit, static):
            p.terminate()
        gc.stop()


if __name__ == "__main__":
    main()

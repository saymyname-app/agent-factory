#!/usr/bin/env python3
"""Capacity baseline sampler for af-2se8y2 (read-only, one process, low cost).

Every TICK s: read /proc/<pid>/stat of all processes, attribute CPU deltas to
families, count new processes per family and per caller (parent family).
Every WINDOW s: append one JSON line with per-family CPU seconds, spawns,
/proc/stat, PSI totals, loadavg, meminfo, Dolt global status counters.
"""
import json, os, re, subprocess, sys, time

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/capacity-af-2se8y2/samples.jsonl")
TICK, WINDOW = 2.0, 30.0
HZ = os.sysconf("SC_CLK_TCK")
SELF = os.getpid()

FAMILIES = [
    ("sampler", re.compile(r"capacity-af-2se8y2")),
    ("dolt-server", re.compile(r"^dolt sql-server")),
    ("dolt-client", re.compile(r"^dolt ")),
    ("bd", re.compile(r"(^|/)bd( |$)")),
    ("gc-bd", re.compile(r"^(\S*/)?gc( --city \S+)? bd ")),
    ("gc-supervisor", re.compile(r"^(\S*/)?gc supervisor")),
    ("gc-dispatcher", re.compile(r"^(\S*/)?gc convoy control --serve")),
    ("gc-other", re.compile(r"^(\S*/)?gc ")),
    ("fake-bd", re.compile(r"fake-bd")),
    ("claude", re.compile(r"(^|/)claude( |$)")),
    ("cockpit-run", re.compile(r"cockpit run")),
    ("tests", re.compile(r"(tests/|harness\.py|pytest|ci-run-tests|tdd-step|unittest)")),
    ("factory-bin", re.compile(r"/bin/(convoy-|factory-|code-review|ticket-evaluation|test-review|project-launch|escalation-door|order|bd-patch)|bin/[a-z-]+")),
    ("git", re.compile(r"(^|/)git( |$)|git-remote|gh ")),
    ("node", re.compile(r"(^|/)node( |$)")),
    ("python", re.compile(r"python")),
    ("shell", re.compile(r"^(-?bash|sh|tmux|sleep)( |$)")),
]


def family(args):
    for name, rx in FAMILIES:
        if rx.search(args):
            return name
    return "other"


def read_proc():
    procs = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                st = f.read()
            with open(f"/proc/{d}/cmdline", "rb") as f:
                args = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        rp = st.rfind(")")
        fields = st[rp + 2:].split()
        ppid, start = int(fields[1]), int(fields[19])
        cpu = int(fields[11]) + int(fields[12])  # utime+stime of the process itself
        ccpu = int(fields[13]) + int(fields[14])  # cutime+cstime: reaped descendants
        if not args:
            args = "[" + st[st.find("(") + 1:rp] + "]"
        procs[(int(d), start)] = (ppid, cpu, args, ccpu)
    return procs


def caller_of(procs_by_pid, ppid):
    p = procs_by_pid.get(ppid)
    if not p:
        return "?"
    return label(p[2])


INTERP = re.compile(r"^(\S*/)?(python3?|bash|sh|node|timeout|nice|env|setsid|nohup)( -\S+)*\s+(\d+\S*\s+)?")


def label(args):
    # Name the script, not its interpreter: "/usr/bin/python3 /tmp/x/bin/cockpit run" -> cockpit-run.
    while True:
        m = INTERP.match(args)
        if not m or m.end() >= len(args):
            break
        args = args[m.end():]
    if args.startswith("source ") or "shell-snapshots" in args:
        return "claude-tool-shell"
    if "cockpit run" in args:
        return "cockpit-run"
    if "harness.py" in args:
        return "tests:harness"
    m = re.search(r"(tests/[A-Za-z0-9_./-]+)", args)
    if m:
        return "tests:" + m.group(1).split("/")[-1][:40]
    m = re.search(r"bin/([A-Za-z0-9_.-]+)", args)
    if m:
        return "bin/" + m.group(1)
    return family(args) + ":" + args.split(" ")[0].split("/")[-1][:30]


def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def psi():
    out = {}
    for r in ("cpu", "io", "memory"):
        for line in read_file(f"/proc/pressure/{r}").splitlines():
            kind, *kv = line.split()
            out[f"{r}_{kind}_total_us"] = int(dict(x.split("=") for x in kv)["total"])
    return out


def stat_cpu():
    line = read_file("/proc/stat").splitlines()[0].split()[1:]
    return [int(x) for x in line]


def meminfo():
    m = {}
    for line in read_file("/proc/meminfo").splitlines():
        k, v = line.split(":", 1)
        if k in ("MemTotal", "MemAvailable", "SwapFree", "SwapTotal", "Dirty"):
            m[k] = int(v.split()[0])
    return m


def dolt_status():
    keys = {"Questions", "Com_select", "Com_insert", "Com_update", "Com_delete",
            "Connections", "Slow_queries", "Threads_connected"}
    try:
        r = subprocess.run(
            ["dolt", "--host", "127.0.0.1", "--port", "44632", "--user", "root", "--password", "",
             "--no-tls", "sql", "-r", "csv", "-q", "show global status"],
            capture_output=True, text=True, timeout=20, cwd="/tmp")
        d = {}
        for line in r.stdout.splitlines():
            k, _, v = line.partition(",")
            if k in keys:
                d[k] = int(v)
        return d
    except Exception as e:  # noqa: BLE001 - record and keep sampling
        return {"error": str(e)[:200]}


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prev = read_proc()
    win = {"cpu": {}, "spawn": {}, "callers": {}, "reaped": {}, "unseen": {}}
    t_win = time.time()
    while not os.path.exists(os.path.join(os.path.dirname(OUT), "STOP")):
        time.sleep(TICK)
        cur = read_proc()
        by_pid = {k[0]: v for k, v in cur.items()}
        # Children seen last tick and gone now: what they had already been
        # counted for, by their parent, so a parent's cutime delta minus this
        # is CPU never seen (short processes, last-tick tail) — no overlap.
        gone = {}
        for key, (ppid, cpu, args, ccpu) in prev.items():
            if key not in cur:
                gone[ppid] = gone.get(ppid, 0) + cpu + ccpu
        for key, (ppid, cpu, args, ccpu) in cur.items():
            if key in prev:
                unseen = (ccpu - prev[key][3]) - gone.get(key[0], 0)
                if unseen > 0:
                    lab = label(args)
                    win["unseen"][lab] = win["unseen"].get(lab, 0) + unseen
        for key, (ppid, cpu, args, ccpu) in cur.items():
            fam = family(args)
            if key in prev:
                delta = cpu - prev[key][1]
                cdelta = ccpu - prev[key][3]
                if cdelta > 0:
                    # Indicator only: nested levels overlap (bash>gc bd>bd).
                    lab = caller_of(by_pid, key[0])
                    win["reaped"][lab] = win["reaped"].get(lab, 0) + cdelta
            else:
                delta = cpu
                win["spawn"][fam] = win["spawn"].get(fam, 0) + 1
                if fam in ("bd", "gc-bd", "gc-other", "dolt-client", "fake-bd", "factory-bin"):
                    c = caller_of(by_pid, ppid)
                    ck = (label(args) if fam == "factory-bin" else fam) + " <- " + c
                    win["callers"][ck] = win["callers"].get(ck, 0) + 1
            if delta > 0:
                win["cpu"][fam] = win["cpu"].get(fam, 0) + delta
        prev = cur
        now = time.time()
        if now - t_win >= WINDOW:
            rec = {
                "ts": round(now, 1),
                "window_s": round(now - t_win, 1),
                "cpu_s": {k: round(v / HZ, 2) for k, v in sorted(win["cpu"].items())},
                "spawn": win["spawn"],
                "callers": win["callers"],
                "reaped_cpu_s": {k: round(v / HZ, 2) for k, v in win["reaped"].items() if v >= HZ // 10},
                "unseen_cpu_s": {k: round(v / HZ, 2) for k, v in win["unseen"].items() if v >= HZ // 10},
                "stat_cpu": stat_cpu(),
                "psi": psi(),
                "loadavg": read_file("/proc/loadavg").split()[:4],
                "mem_kb": meminfo(),
                "dolt": dolt_status(),
                "nproc": len(cur),
            }
            with open(OUT, "a") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
            win = {"cpu": {}, "spawn": {}, "callers": {}, "reaped": {}, "unseen": {}}
            t_win = now


if __name__ == "__main__":
    main()

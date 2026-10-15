#!/usr/bin/env python3
"""Summarise ~/capacity-af-2se8y2/samples.jsonl (af-2se8y2). Read-only."""
import json, sys, time
from collections import Counter

path = sys.argv[1]
since = float(sys.argv[2]) if len(sys.argv) > 2 else 0
rows = [json.loads(l) for l in open(path) if l.strip()]
rows = [r for r in rows if r["ts"] >= since]
if len(rows) < 2:
    sys.exit("not enough rows")

first, last = rows[0], rows[-1]
dur = last["ts"] - first["ts"]
ncpu = 8
st0, st1 = first["stat_cpu"], last["stat_cpu"]
tot = sum(st1) - sum(st0)
idle = (st1[3] + st1[4]) - (st0[3] + st0[4])
iowait = st1[4] - st0[4]
hz = 100
busy_s = (tot - idle) / hz
print(f"window: {time.strftime('%H:%M', time.localtime(first['ts']))} -> "
      f"{time.strftime('%H:%M', time.localtime(last['ts']))} ({dur/60:.1f} min, {len(rows)} rows)")
print(f"CPU utilisation: {100*(tot-idle)/tot:.1f}% of {ncpu} cores; iowait {100*iowait/tot:.2f}%")

def psi_rate(key):
    return 100 * (last["psi"][key] - first["psi"][key]) / (dur * 1e6)

for k in ("cpu_some", "io_some", "io_full", "memory_some", "memory_full"):
    print(f"PSI {k}: {psi_rate(k + '_total_us'):.1f}%")
loads = [float(r["loadavg"][0]) for r in rows]
print(f"loadavg1 mean {sum(loads)/len(loads):.1f} max {max(loads):.1f}")
mem = [r["mem_kb"]["MemAvailable"] / 1048576 for r in rows]
print(f"MemAvailable GiB min {min(mem):.1f} mean {sum(mem)/len(mem):.1f}")

cpu, spawn, callers, reaped = Counter(), Counter(), Counter(), Counter()
for r in rows[1:]:
    cpu.update(r["cpu_s"]); spawn.update(r["spawn"]); callers.update(r["callers"])
    reaped.update(r.get("reaped_cpu_s", {}))
att = sum(cpu.values())
print(f"\nCPU by family (cores, mean) — attributed {att/dur:.2f} of busy {busy_s/dur:.2f} cores; "
      f"rest = processes shorter than 2 s")
for k, v in cpu.most_common():
    print(f"  {k:15s} {v/dur:5.2f} cores  {100*v/busy_s:5.1f}% of busy")
print("\nSpawns per minute by family")
for k, v in spawn.most_common(12):
    print(f"  {k:15s} {60*v/dur:7.1f}/min")
print("\nTracker-client spawns per minute by caller (family <- parent)")
for k, v in callers.most_common(25):
    print(f"  {60*v/dur:7.1f}/min  {k}")
print("\nReaped-descendant CPU by waiting parent (cores; nested levels overlap)")
for k, v in reaped.most_common(20):
    print(f"  {v/dur:5.2f}  {k}")

d0, d1 = first["dolt"], last["dolt"]
if "Questions" in d0 and "Questions" in d1:
    for k in ("Questions", "Com_select", "Com_insert", "Com_update", "Com_delete", "Connections", "Slow_queries"):
        print(f"Dolt {k}: {(d1[k]-d0[k])/dur:.1f}/s")
    th = [r["dolt"].get("Threads_connected", 0) for r in rows]
    print(f"Dolt Threads_connected mean {sum(th)/len(th):.1f} max {max(th)}")

print("\nTimeline (10-min buckets, cores)")
from collections import defaultdict
b = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0])
for p, r in zip(rows, rows[1:]):
    dt = r["ts"] - p["ts"]
    tot = sum(r["stat_cpu"]) - sum(p["stat_cpu"])
    idl = (r["stat_cpu"][3] + r["stat_cpu"][4]) - (p["stat_cpu"][3] + p["stat_cpu"][4])
    k = int(r["ts"] // 600)
    b[k][0] += (tot - idl) / hz
    b[k][1] += r.get("reaped_cpu_s", {}).get("cockpit-run", 0)
    b[k][2] += r["cpu_s"].get("dolt-server", 0)
    b[k][3] += (r["psi"]["cpu_some_total_us"] - p["psi"]["cpu_some_total_us"]) / 1e6
    b[k][4] += dt
for k in sorted(b):
    v = b[k]
    print(f"  {time.strftime('%H:%M', time.localtime(k*600))}  busy {v[0]/v[4]:.2f}  cockpit-run {v[1]/v[4]:.2f}"
          f"  dolt {v[2]/v[4]:.2f}  psi_cpu {100*v[3]/v[4]:.0f}%")

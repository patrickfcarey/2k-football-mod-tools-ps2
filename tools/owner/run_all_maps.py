#!/usr/bin/env python3
"""Map every football-family disc under ~/Games/ps2 read-only, three at a time (runs on the rig)."""
import concurrent.futures, os, re, subprocess, sys, time
HOME = os.path.expanduser("~"); REPO = os.path.join(HOME, "2k-football-mod-tools-ps2"); OUT = os.path.join(HOME, "ps2-maps", "out")
os.makedirs(OUT, exist_ok=True)
pattern = re.compile(r"NCAA Football (2004|06|09)|MVP Baseball 2005|Madden NFL (2004|06|08|09|12)|ESPN NFL 2K5")
discs = sorted(p for p in os.listdir(os.path.join(HOME, "Games", "ps2")) if p.endswith(".iso") and pattern.search(p) and "pt2test" not in p and "2K27" not in p)
log = open(os.path.join(HOME, "ps2-maps", "run.log"), "a", buffering=1)
def one(name):
    iso = os.path.join(HOME, "Games", "ps2", name); label = name[:-4]; start = time.time()
    with open(os.path.join(OUT, label + ".log"), "w") as lf:
        rc = subprocess.call([sys.executable, "tools/owner/ea_disc_map.py", "--iso", iso, "--out", OUT, "--label", label, "--hash-image", "--quiet"],
                             cwd=REPO, env={**os.environ, "PYTHONPATH": REPO}, stdout=lf, stderr=subprocess.STDOUT)
    tail = open(os.path.join(OUT, label + ".log")).read().strip().splitlines()[-1:] or [""]
    log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} rc={rc} {int(time.time()-start)}s {label} :: {tail[0][:160]}\n")
    return rc
log.write(f"START {len(discs)} discs: {discs}\n")
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rcs = list(pool.map(one, discs))
log.write(f"ALL_MAPS_DONE failures={sum(1 for r in rcs if r)} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")

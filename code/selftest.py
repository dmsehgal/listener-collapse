"""Check the value comparator on clean text before any audio exists.

Correct and equivalent spoken forms must agree with the printed reference.
Every mutant must disagree. Prints counts, then every failure.
"""
import csv
import sys

from frames import frame

rows = [r for r in csv.DictReader(open("data/items.csv")) if r["kind"] != "natural"]
bad = []
counts = {}
for r in rows:
    same = frame(r["reference"]) == frame(r["spoken"])
    ok = same if r["kind"] in ("correct", "equivalent") else not same
    counts.setdefault(r["kind"], [0, 0])
    counts[r["kind"]][0 if ok else 1] += 1
    if not ok:
        bad.append(r)
print("read", len(rows), "rows")
for k, (g, b) in counts.items():
    print(f"{k:11s} pass={g} fail={b}")
for r in bad:
    print("FAIL", r["item"], "|", r["reference"], dict(frame(r["reference"])), "|", r["spoken"], dict(frame(r["spoken"])))
sys.exit(1 if bad else 0)

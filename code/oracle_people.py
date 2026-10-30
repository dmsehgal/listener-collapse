"""People as the oracle: score task 3 answers (answers_rater_B2.csv, answers_rater_C2.csv)
the way the round-trip oracles are scored, and compare them on the same clips.

A mutant is caught when a person marks it wrong; a correct reading or variant marked
wrong is a false alarm. Unclear counts as not caught and as no false alarm, and is
reported separately. Output: results/oracle_people.json
"""
import csv
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, "code")
from agreement import cohen  # noqa: E402
from score import wilson  # noqa: E402

RATERS_DIR = os.environ.get("RATERS_DIR", "results/raters")
items = {r["item"]: r for r in csv.DictReader(open("data/items.csv"))}
clips = [(r["voice"], r["item"]) for r in csv.DictReader(open("rater_packets/oracle_clips.csv"))]
ver = {}
for path, voice in [("results/tables/clip_verdicts.csv", "piper"), ("results/gemini/tables/clip_verdicts.csv", "gemini")]:
    for r in csv.DictReader(open(path)):
        if r["voice"] == voice and r["listener"] == "whisper":
            ver[(voice, r["item"])] = r
people = {}
for path in sorted(glob.glob(os.path.join(RATERS_DIR, "answers_rater_*2.csv"))):
    for r in csv.DictReader(open(path)):
        people.setdefault(r["rater"], {})[(r["voice"], r["item"])] = r["label"].strip().lower()


def rates(fail):
    out = {}
    for kind in ["mutant", "correct", "equivalent"]:
        ks = [k for k in clips if items[k[1]]["kind"] == kind]
        k = sum(fail(x) for x in ks)
        out[kind] = {"k": k, "n": len(ks), "rate": k / len(ks), "ci": list(wilson(k, len(ks)))}
    return out


out = {"clips": len(clips), "people": {}, "oracles": {}}
oracles = {"standard check": lambda k: float(ver[k]["wer"]) > 0.10 + 1e-9,
           "value comparator": lambda k: ver[k]["value_pass"] == "False"}
for name, f in oracles.items():
    out["oracles"][name] = rates(f)
for rid, ans in sorted(people.items()):
    missing = [k for k in clips if k not in ans]
    res = rates(lambda k: ans.get(k) == "wrong")
    res["unclear"] = sum(v == "unclear" for v in ans.values())
    res["missing"] = len(missing)
    res["missed_mutants"] = sorted(f"{v}/{it}" for v, it in clips if items[it]["kind"] == "mutant" and ans.get((v, it)) != "wrong")
    res["missed_by_op"] = dict(Counter(items[it]["op"] for v, it in clips if items[it]["kind"] == "mutant" and ans.get((v, it)) != "wrong"))
    out["people"][rid] = res
if len(people) == 2:
    a, b = sorted(people)
    both = [k for k in clips if people[a].get(k) in ("correct", "wrong") and people[b].get(k) in ("correct", "wrong")]
    out["agreement"] = {"clips": len(both), "agree": sum(people[a][k] == people[b][k] for k in both),
                        "kappa": cohen([people[a][k] for k in both], [people[b][k] for k in both])}
    pooled = lambda k: people[a].get(k) == "wrong" or people[b].get(k) == "wrong"
    out["people"]["either"] = rates(pooled)
json.dump(out, open("results/oracle_people.json", "w"), indent=1)
for name, res in list(out["oracles"].items()) + list(out["people"].items()):
    print(f"{name:17s} caught {res['mutant']['k']}/{res['mutant']['n']} = {100 * res['mutant']['rate']:.1f}% "
          f"[{100 * res['mutant']['ci'][0]:.1f}, {100 * res['mutant']['ci'][1]:.1f}]  "
          f"false alarms correct {res['correct']['k']}/{res['correct']['n']}  variants {res['equivalent']['k']}/{res['equivalent']['n']}"
          + (f"  unclear {res['unclear']} missing {res['missing']} missed by op {res['missed_by_op']}" if "unclear" in res else ""))
if "agreement" in out:
    g = out["agreement"]
    print(f"agreement {g['agree']}/{g['clips']}, kappa {g['kappa']:.2f}")

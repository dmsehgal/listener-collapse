"""Print every number the paper uses, plus example transcripts, from score.py output.

Counts for the ideal listener are per reading (the four voice copies are identical).
"""
import csv
import json
import sys
from collections import defaultdict

import os
IN = os.environ.get("SCORE_OUT", "results")
S = json.load(open(f"{IN}/summary.json"))
O = S["oracles"]
rows = list(csv.DictReader(open(f"{IN}/tables/clip_verdicts.csv")))
LIS = ["ideal", "whisper", "whisper_anchored", "whisper_spelled", "vosk"]
VOICES = os.environ.get("SCORE_VOICES", "piper,Samantha,Daniel,Rishi").split(",")
NV = len(VOICES)


def fmt(g, ideal=False):
    k, n = g["k"], g["n"]
    if ideal:
        k, n = k // NV, n // NV
    lo, hi = g["ci"]
    return f"{k}/{n} = {100 * g['rate']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


print("== Main table (tau = 0.10 and value) ==")
names = [f"{l}|{c}" for l in LIS for c in ("wer@0.10", "value")] + \
        ["any(whisper,vosk)|value", "any(whisper,spelled)|value", "any(all four)|value"]
for name in names:
    if name not in O:
        continue
    ideal = name.startswith("ideal")
    g = O[name]
    print(f"{name:30s} MS {fmt(g['mutant'], ideal):32s} FAc {fmt(g['correct'], ideal):30s} FAe {fmt(g['equivalent'], ideal)}")

print("\n== WER at tau = 0 ==")
for l in LIS:
    n = f"{l}|wer@0.00"
    if n in O:
        g = O[n]
        print(f"{n:30s} MS {fmt(g['mutant'], l == 'ideal'):32s} FAc {fmt(g['correct'], l == 'ideal'):30s} FAe {fmt(g['equivalent'], l == 'ideal')}")

print("\n== Per voice, mutation score and correct false alarms ==")
for name in ["whisper|wer@0.10", "whisper|value", "vosk|value", "whisper_spelled|value", "any(whisper,vosk)|value"]:
    if name not in O:
        continue
    parts = []
    for v in VOICES:
        m = O[name].get(f"mutant|voice={v}")
        c = O[name].get(f"correct|voice={v}")
        e = O[name].get(f"equivalent|voice={v}")
        if m:
            parts.append(f"{v}: MS {100 * m['rate']:.0f} FAc {100 * c['rate']:.0f} FAe {100 * e['rate']:.0f}")
    print(f"{name:28s} " + " | ".join(parts))

print("\n== Per operator mutation score ==")
ops = ["DEC", "UNIT", "TEENTY", "CUR", "SCALE", "SIGN", "NUM", "SWAP", "AMPM", "NEG", "CMP"]
hdr = ["ideal|wer@0.10", "whisper|wer@0.10", "whisper_anchored|wer@0.10", "whisper|value", "whisper_anchored|value",
       "whisper_spelled|value", "vosk|value", "any(whisper,vosk)|value"]
hdr = [h for h in hdr if h in O]
print("op     " + " ".join(f"{h[:18]:>18s}" for h in hdr))
for op in ops:
    print(f"{op:6s} " + " ".join(f"{100 * O[h][f'mutant|op={op}']['rate']:18.0f}" for h in hdr))

print("\n== Per category false alarms on correct readings ==")
cats = ["dose", "fee", "bigmoney", "temp", "date", "time", "neg", "threshold", "limit", "percent", "distance", "duration"]
for h in hdr:
    print(f"{h:28s} " + " ".join(f"{c[:5]}={100 * O[h][f'correct|cat={c}']['rate']:.0f}" for c in cats))

print("\n== Collapse diagnosis (mutant clips) ==")
for l, d in S["collapse"].items():
    print(l, json.dumps(d))

print("\n== Separability (WER comparator, mutant vs its own correct reading, same voice) ==")
for l, d in S["separability"].items():
    tot = d.get("higher", 0) + d.get("tied", 0) + d.get("lower", 0)
    ins = d.get("tied", 0) + d.get("lower", 0)
    div = NV if l == "ideal" else 1
    print(f"{l:18s} inseparable {ins // div}/{tot // div} = {100 * ins / tot:.1f}% (tied {d.get('tied', 0) // div}, lower {d.get('lower', 0) // div})")

print("\n== Anchoring (value verdict moved by prompting, versus plain Whisper) ==")
print(json.dumps(S["anchoring"]))
for e in S["anchoring_examples"][:8]:
    print("  ", e["item"], e["voice"], "| said:", e["spoken"][:70], "| plain:", e["plain"][:70], "| prompted:", e["anchored"][:70])

print("\n== McNemar on mutant clips ==")
for k, v in S["mcnemar"].items():
    print(f"{k:60s} only first {v['only_first']:4d} only second {v['only_second']:4d} p={v['p']:.2g}")

print("\n== Listener collapse examples (mutant transcript equals correct transcript) ==")
idx = {(r["listener"], r["item"], r["voice"]): r for r in rows}
shown = defaultdict(int)
for r in rows:
    if r["kind"] != "mutant" or r["listener"] == "ideal":
        continue
    c = idx.get((r["listener"], r["seed"] + "_C", r["voice"]))
    if c and r["hyp"].lower().strip(" .?,") == c["hyp"].lower().strip(" .?,") and shown[r["listener"]] < 6:
        shown[r["listener"]] += 1
        print(f"  {r['listener']:16s} {r['item']:16s} {r['voice']:8s} said: {r['spoken'][:60]} | heard: {r['hyp'][:70]}")

print("\n== Value comparator false alarms on correct readings, examples ==")
shown = defaultdict(int)
for r in rows:
    if r["kind"] == "correct" and r["listener"] != "ideal" and r["value_pass"] == "False" and shown[r["listener"]] < 5:
        shown[r["listener"]] += 1
        print(f"  {r['listener']:16s} {r['item']:10s} {r['voice']:8s} ref: {r['reference'][:55]} | heard: {r['hyp'][:70]}")
sys.exit(0)

"""Model-size check: score a larger plain Whisper with both comparators on the same
clips as base.en (run listen.py with LISTEN_MODEL=small.en first).
CHECK_LISTENER=whisper_large-v3-turbo CHECK_VOICES=Samantha scores another run.
Output: results/small_en.json, or results/<listener>.json for another run
"""
import csv
import json
import os
import sys

sys.path.insert(0, "code")
from score import frame, mcnemar_exact, wer, wilson  # noqa: E402

NAME = os.environ.get("CHECK_LISTENER", "whisper_small")
VOICES = os.environ.get("CHECK_VOICES", "piper,Samantha,Daniel,Rishi").split(",")
TAU = 0.10
items = {r["item"]: r for r in csv.DictReader(open("data/items.csv"))}


def load(name):
    return {(j["item"], j["voice"]): j["text"] for j in map(json.loads, open(f"results/transcripts/{name}.jsonl"))
            if j["voice"] in VOICES and items[j["item"]]["kind"] != "natural"}


small, base = load(NAME), load("whisper")
keys = sorted(k for k in small if k in base)
out = {"clips": len(keys)}
fails = {}
for name, tr in [("small", small), ("base", base)]:
    for comp in ["wer", "value"]:
        f = {}
        for it, v in keys:
            r = items[it]
            f[(it, v)] = wer(r["reference"], tr[(it, v)]) > TAU + 1e-9 if comp == "wer" else frame(r["reference"]) != frame(tr[(it, v)])
        fails[(name, comp)] = f
        res = {}
        for kind in ["mutant", "correct", "equivalent"]:
            ks = [k for k in keys if items[k[0]]["kind"] == kind]
            n, k = len(ks), sum(f[x] for x in ks)
            lo, hi = wilson(k, n)
            res[kind] = {"k": k, "n": n, "rate": k / n, "ci": [lo, hi]}
        out[f"{name}|{comp}"] = res
        print(f"{name:5s} {comp:5s} MS {res['mutant']['k']}/{res['mutant']['n']} = {100 * res['mutant']['rate']:.1f}% "
              f"[{100 * res['mutant']['ci'][0]:.1f}, {100 * res['mutant']['ci'][1]:.1f}]  "
              f"FAc {100 * res['correct']['rate']:.1f}%  FAv {100 * res['equivalent']['rate']:.1f}%")
mut = [k for k in keys if items[k[0]]["kind"] == "mutant"]
for comp in ["wer", "value"]:
    a, b = fails[("small", comp)], fails[("base", comp)]
    only_small, only_base = sum(a[k] and not b[k] for k in mut), sum(b[k] and not a[k] for k in mut)
    out[f"mcnemar|{comp}"] = {"only_small": only_small, "only_base": only_base, "p": mcnemar_exact(only_small, only_base)}
    print(f"{comp}: mutants only small kills {only_small}, only base kills {only_base}, p={mcnemar_exact(only_small, only_base):.2g}")
json.dump(out, open("results/small_en.json" if NAME == "whisper_small" else f"results/{NAME}.json", "w"), indent=1)

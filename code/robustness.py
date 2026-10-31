"""Two checks made after the main analysis, from score.py output. No component is changed.

1. Text-only prediction: how often the ideal listener's verdict, which needs no audio,
   equals a real listener's verdict on the same clip (WER comparator, tau = 0.10).
2. Seed-level robustness: clips that share a seed are not independent, so resample the
   120 seeds (percentile bootstrap) and compare oracles seed by seed with a sign test.
Output: results/robustness.json
"""
import csv
import json
import math
import random
from collections import defaultdict

TAU = 0.10
B = 4000
rows = list(csv.DictReader(open("results/tables/clip_verdicts.csv")))
ideal = {r["item"]: r for r in rows if r["listener"] == "ideal" and r["voice"] == "piper"}


def fails(r, comp):
    return float(r["wer"]) > TAU + 1e-9 if comp == "wer" else r["value_pass"] == "False"


def sign_test(b, c):
    """Two sided exact sign test, the same computation as the exact McNemar test."""
    n, k = b + c, min(b, c)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def bootstrap(listener, comp, kind):
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["listener"] == listener and r["kind"] == kind:
            by[r["seed"]][0] += fails(r, comp)
            by[r["seed"]][1] += 1
    seeds = sorted(by)
    rng = random.Random(7)
    est = []
    for _ in range(B):
        s = [by[rng.choice(seeds)] for _ in seeds]
        est.append(sum(k for k, _ in s) / sum(n for _, n in s))
    est.sort()
    k, n = sum(v[0] for v in by.values()), sum(v[1] for v in by.values())
    return {"k": k, "n": n, "rate": k / n, "ci": [est[int(0.025 * B)], est[int(0.975 * B)]]}


def seed_compare(a, b):
    ka, kb = defaultdict(int), defaultdict(int)
    for r in rows:
        if r["kind"] == "mutant":
            if r["listener"] == a[0]:
                ka[r["seed"]] += fails(r, a[1])
            if r["listener"] == b[0]:
                kb[r["seed"]] += fails(r, b[1])
    more = sum(ka[s] > kb[s] for s in ka)
    fewer = sum(ka[s] < kb[s] for s in ka)
    return {"first_more": more, "second_more": fewer, "tied": len(ka) - more - fewer, "p": sign_test(more, fewer)}


def youden(listener):
    """Proposition 3: pair each mutant with its correct reading (same voice). rho is the
    share of separable pairs; the best threshold's Youden index (MS - FA, counted once
    per pair) cannot exceed it. The value comparator's index is reported beside it."""
    R = {(r["item"], r["voice"]): r for r in rows if r["listener"] == listener}
    voices = ["piper"] if listener == "ideal" else ["piper", "Samantha", "Daniel", "Rishi"]
    pairs = [(r, R[(r["seed"] + "_C", v)]) for (it, v), r in R.items() if v in voices and r["kind"] == "mutant"]
    d = [(float(m["wer"]), float(c["wer"])) for m, c in pairs]
    rho = sum(dm > dc + 1e-9 for dm, dc in d) / len(d)
    taus = sorted({x for pair in d for x in pair} | {0.0})
    best = max((sum(dm > t + 1e-9 for dm, _ in d) - sum(dc > t + 1e-9 for _, dc in d)) / len(d) for t in taus)
    value = sum((m["value_pass"] == "False") - (c["value_pass"] == "False") for m, c in pairs) / len(pairs)
    return {"pairs": len(d), "rho": rho, "best_threshold_youden": best, "value_comparator_youden": value}


out = {"text_only": {}, "bootstrap": {}, "seed_tests": {}, "youden": {}}
for lis in ["ideal", "whisper"]:
    y = youden(lis)
    out["youden"][lis] = y
    print(f"youden      {lis:8s} rho {100 * y['rho']:.1f}%  best threshold {100 * y['best_threshold_youden']:.1f}%  "
          f"value comparator {100 * y['value_comparator_youden']:.1f}%")
for lis in ["whisper", "whisper_spelled", "vosk"]:
    for kind in ["mutant", "correct", "equivalent"]:
        cl = [r for r in rows if r["listener"] == lis and r["kind"] == kind]
        same = sum(fails(ideal[r["item"]], "wer") == fails(r, "wer") for r in cl)
        out["text_only"][f"{lis}|{kind}"] = {"same": same, "n": len(cl)}
        print(f"text-only   {lis:16s} {kind:10s} same verdict {same}/{len(cl)} = {100 * same / len(cl):.1f}%")
for lis, comp in [("whisper", "wer"), ("whisper", "value"), ("whisper_anchored", "value"), ("vosk", "value")]:
    for kind in ["mutant", "correct"]:
        g = bootstrap(lis, comp, kind)
        out["bootstrap"][f"{lis}|{comp}|{kind}"] = g
        print(f"bootstrap   {lis}|{comp} {kind:8s} {g['k']}/{g['n']} = {100 * g['rate']:.1f}% "
              f"[{100 * g['ci'][0]:.1f}, {100 * g['ci'][1]:.1f}]")
for a, b in [(("whisper", "value"), ("whisper", "wer")), (("whisper", "value"), ("whisper_anchored", "value"))]:
    t = seed_compare(a, b)
    out["seed_tests"][f"{'|'.join(a)} vs {'|'.join(b)}"] = t
    print(f"seed test   {'|'.join(a)} vs {'|'.join(b)}: first kills more in {t['first_more']} seeds, "
          f"second in {t['second_more']}, tied {t['tied']}, p={t['p']:.2g}")
json.dump(out, open("results/robustness.json", "w"), indent=1)

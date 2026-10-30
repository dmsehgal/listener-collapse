"""Score every oracle on every clip. Writes tables, a summary and figures.

An oracle is a listener plus a comparator. The listener turns audio into text.
The comparator decides pass or fail against the printed reference.
  listeners:   ideal (the spoken text itself, no audio), whisper, whisper_anchored,
               whisper_spelled, vosk
  comparators: wer@tau  Whisper English normaliser on both sides, then word error
                        rate at most tau (the ASR-WER practice)
               value    fact frames must be equal (frames.py)
A mutant is killed when the oracle fails it. A false alarm is a fail on a
correct reading or a meaning preserving variant.
"""
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, "third_party")
from whisper_normalizer import EnglishTextNormalizer  # noqa: E402

from frames import frame  # noqa: E402

NORM = EnglishTextNormalizer()
VOICES = os.environ.get("SCORE_VOICES", "piper,Samantha,Daniel,Rishi").split(",")
OUT = os.environ.get("SCORE_OUT", "results")
LISTENERS = ["ideal", "whisper", "whisper_anchored", "whisper_spelled", "vosk"]
TAUS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]
MAIN_TAU = 0.10
OPS = ["DEC", "UNIT", "TEENTY", "CUR", "SCALE", "SIGN", "NUM", "SWAP", "AMPM", "NEG", "CMP"]


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(ref, hyp):
    r, h = NORM(ref).split(), NORM(hyp).split()
    return edit_distance(r, h) / max(1, len(r))


def plain(t):
    return re.sub(r"[^a-z0-9 ]", " ", t.lower()).split()


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def mcnemar_exact(b, c):
    """Two sided exact McNemar p value from the discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load():
    items = {r["item"]: r for r in csv.DictReader(open("data/items.csv"))}
    tr = {}
    for name in LISTENERS[1:]:
        path = f"results/transcripts/{name}.jsonl"
        if not os.path.exists(path):
            print("no transcripts yet for", name)
            continue
        for j in map(json.loads, open(path)):
            if j["voice"] in VOICES:
                tr[(name, j["item"], j["voice"])] = j["text"]
    for it, r in items.items():
        if r["kind"] != "natural":
            for v in VOICES:
                tr[("ideal", it, v)] = r["spoken"]
    return items, tr


def verdicts(items, tr):
    """rows: one per (listener, item, voice) with comparator verdicts."""
    out = []
    for (lis, it, v), hyp in tr.items():
        r = items[it]
        w = wer(r["reference"], hyp)
        row = dict(listener=lis, item=it, voice=v, seed=r["seed"], cat=r["cat"], kind=r["kind"],
                   op=r["op"], reference=r["reference"], spoken=r["spoken"], hyp=hyp, wer=round(w, 4),
                   value_pass=frame(r["reference"]) == frame(hyp),
                   nwords=len(NORM(r["reference"]).split()))
        out.append(row)
    return out


def oracle_fail(row, comp):
    if comp == "value":
        return not row["value_pass"]
    tau = float(comp.split("@")[1])
    return row["wer"] > tau + 1e-9


def summarise(rows):
    idx = {(r["listener"], r["item"], r["voice"]): r for r in rows}
    comps = [f"wer@{t:.2f}" for t in TAUS] + ["value"]
    have = {r["listener"] for r in rows}
    oracles = [(l, c) for l in LISTENERS if l in have for c in comps]
    ens = {
        "any(whisper,vosk)|value": [("whisper", "value"), ("vosk", "value")],
        "any(whisper,spelled)|value": [("whisper", "value"), ("whisper_spelled", "value")],
        "any(all four)|value": [(l, "value") for l in LISTENERS[1:]],
    }
    keys = sorted({(r["item"], r["voice"]) for r in rows if r["kind"] != "natural"})
    res = {}

    def fail_of(name, it, v):
        if name in ens:
            return any(oracle_fail(idx[(l, it, v)], c) for l, c in ens[name])
        l, c = name
        return oracle_fail(idx[(l, it, v)], c)

    ens = {k: v for k, v in ens.items() if all(l in have for l, _ in v)}
    names = oracles + list(ens)
    for name in names:
        tally = defaultdict(lambda: [0, 0])
        for it, v in keys:
            r = idx[("ideal", it, v)]
            f = fail_of(name, it, v)
            groups = [r["kind"], f"{r['kind']}|voice={v}", f"{r['kind']}|cat={r['cat']}"]
            if r["kind"] == "mutant":
                groups.append(f"mutant|op={r['op']}")
            for g in groups:
                tally[g][0] += f
                tally[g][1] += 1
        key = name if isinstance(name, str) else f"{name[0]}|{name[1]}"
        res[key] = {g: dict(k=k, n=n, rate=k / n, ci=wilson(k, n)) for g, (k, n) in tally.items()}
    return res, idx, keys, ens, fail_of


def collapse_diagnosis(rows, idx):
    """For each listener, why surviving mutants survived under wer@MAIN_TAU and value."""
    out = {}
    have = {r["listener"] for r in rows}
    for lis in [l for l in LISTENERS[1:] if l in have]:
        cnt = defaultdict(int)
        for r in rows:
            if r["listener"] != lis or r["kind"] != "mutant":
                continue
            correct = idx[(lis, f"{r['seed']}_C", r["voice"])]
            same_as_correct = plain(r["hyp"]) == plain(correct["hyp"])
            for comp in (f"wer@{MAIN_TAU:.2f}", "value"):
                if oracle_fail(r, comp):
                    cnt[f"{comp}|killed"] += 1
                    continue
                if same_as_correct:
                    cnt[f"{comp}|listener_collapse"] += 1
                elif comp == "value":
                    cnt[f"{comp}|comparator_collapse"] += 1
                elif r["wer"] == 0:
                    cnt[f"{comp}|normaliser_collapse"] += 1
                else:
                    cnt[f"{comp}|threshold_dilution"] += 1
        out[lis] = dict(cnt)
    return out


def anchoring(idx, keys, items):
    """Clips where the anchored listener moved the value verdict, versus plain Whisper."""
    moved = defaultdict(int)
    examples = []
    for it, v in keys:
        r0 = idx[("whisper", it, v)]
        r1 = idx[("whisper_anchored", it, v)]
        k = r0["kind"]
        a, b = r0["value_pass"], r1["value_pass"]
        if a != b:
            moved[f"{k}|{'fail->pass' if b else 'pass->fail'}"] += 1
            if k == "mutant" and b and len(examples) < 12:
                examples.append(dict(item=it, voice=v, spoken=r0["spoken"], plain=r0["hyp"], anchored=r1["hyp"]))
    return dict(moved), examples


def paired_tests(keys, idx, fail_of, pairs):
    out = {}
    mut = [(it, v) for it, v in keys if idx[("ideal", it, v)]["kind"] == "mutant"]
    for a, b in pairs:
        only_a = sum(1 for it, v in mut if fail_of(a, it, v) and not fail_of(b, it, v))
        only_b = sum(1 for it, v in mut if fail_of(b, it, v) and not fail_of(a, it, v))
        name = f"{a if isinstance(a, str) else '|'.join(a)} vs {b if isinstance(b, str) else '|'.join(b)}"
        out[name] = dict(only_first=only_a, only_second=only_b, p=mcnemar_exact(only_a, only_b))
    return out


def separability(idx, keys):
    """Threshold free test of the WER comparator. A mutant can be failed without
    failing its own correct reading only if its WER is strictly higher."""
    out = {}
    for lis in [l for l in LISTENERS if (l, keys[0][0], keys[0][1]) in idx]:
        cnt = defaultdict(int)
        for it, v in keys:
            r = idx[(lis, it, v)]
            if r["kind"] != "mutant":
                continue
            c = idx[(lis, f"{r['seed']}_C", v)]
            if r["wer"] > c["wer"] + 1e-9:
                cnt["higher"] += 1
            elif abs(r["wer"] - c["wer"]) <= 1e-9:
                cnt["tied"] += 1
            else:
                cnt["lower"] += 1
            cnt[f"op={r['op']}|{'higher' if r['wer'] > c['wer'] + 1e-9 else 'not'}"] += 1
        out[lis] = dict(cnt)
    return out


def dilution(rows):
    """Kill rate of wer@MAIN_TAU on mutants by reference length, ideal listener."""
    bins = [(0, 8), (8, 12), (12, 16), (16, 40)]
    out = {}
    for lo, hi in bins:
        sel = [r for r in rows if r["listener"] == "ideal" and r["kind"] == "mutant" and lo <= r["nwords"] < hi]
        k = sum(oracle_fail(r, f"wer@{MAIN_TAU:.2f}") for r in sel)
        out[f"{lo}-{hi}"] = dict(k=k, n=len(sel), rate=k / len(sel) if sel else float("nan"))
    return out


def natural_sheet(rows):
    """Write the listening sheets for natural clips. Never overwrites a sheet that
    already exists, because the author may be labelling it. Gemini clips get their
    own sheet."""
    nat = [r for r in rows if r["kind"] == "natural"]
    by = defaultdict(dict)
    for r in nat:
        by[(r["item"], r["voice"])][r["listener"]] = r
    fields = ["item", "voice", "audio", "reference", "author_label", "author_note"]
    for lis in LISTENERS[1:]:
        fields += [f"{lis}_text", f"{lis}_wer", f"{lis}_value_pass"]
    written = 0
    for path, keep in (("results/natural_listening_sheet.csv", lambda v: v != "gemini"),
                       ("results/natural_listening_sheet_gemini.csv", lambda v: v == "gemini")):
        keys = sorted(k for k in by if keep(k[1]))
        if not keys:
            continue
        if os.path.exists(path):
            print(f"kept existing {path} unchanged")
            continue
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for it, v in keys:
                d = by[(it, v)]
                row = dict(item=it, voice=v, audio=f"audio/{v}/{it}.wav", reference=d["whisper"]["reference"],
                           author_label="", author_note="")
                for lis in LISTENERS[1:]:
                    row[f"{lis}_text"] = d[lis]["hyp"]
                    row[f"{lis}_wer"] = d[lis]["wer"]
                    row[f"{lis}_value_pass"] = d[lis]["value_pass"]
                w.writerow(row)
            written += len(keys)
    return len(by), written


def main():
    items, tr = load()
    rows = verdicts(items, tr)
    print(f"items={len(items)} transcripts={len(tr)} rows={len(rows)}")
    counts = defaultdict(int)
    for r in rows:
        counts[r["listener"]] += 1
    print("rows per listener:", dict(counts))
    res, idx, keys, ens, fail_of = summarise(rows)
    diag = collapse_diagnosis(rows, idx)
    full = all((l, keys[0][0], keys[0][1]) in idx for l in LISTENERS)
    moved, anchor_examples = anchoring(idx, keys, items) if full else ({}, [])
    pairs = [(("whisper", f"wer@{MAIN_TAU:.2f}"), ("whisper", "value")),
             (("whisper", "value"), ("vosk", "value")),
             (("whisper", "value"), "any(whisper,vosk)|value"),
             (("whisper", "value"), ("whisper_anchored", "value")),
             (("whisper", f"wer@{MAIN_TAU:.2f}"), ("whisper_anchored", f"wer@{MAIN_TAU:.2f}"))]
    tests = paired_tests(keys, idx, fail_of, pairs) if full else {}
    dil = dilution(rows)
    sep = separability(idx, keys)
    n_nat, n_lab = natural_sheet(rows) if full else (0, 0)
    os.makedirs(f"{OUT}/tables", exist_ok=True)
    with open(f"{OUT}/tables/clip_verdicts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = dict(oracles=res, collapse=diag, anchoring=moved, anchoring_examples=anchor_examples,
                   mcnemar=tests, dilution=dil, separability=sep,
                   natural=dict(clips=n_nat, new_sheet_rows=n_lab))
    json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=1, default=str)
    # Console report.
    print(f"\n{'oracle':40s} {'MS':>6s} {'FA_c':>6s} {'FA_e':>6s}")
    for name, g in res.items():
        if "@" in name and not name.endswith(f"{MAIN_TAU:.2f}") and not name.endswith("0.00"):
            continue
        ms, fc, fe = g["mutant"]["rate"], g["correct"]["rate"], g["equivalent"]["rate"]
        print(f"{name:40s} {ms:6.3f} {fc:6.3f} {fe:6.3f}")
    print("\ncollapse diagnosis:", json.dumps(diag, indent=1))
    print("anchoring moves:", moved)
    print("mcnemar:", json.dumps(tests, indent=1))
    print("dilution (ideal listener, wer@0.10):", dil)
    print("separability:", json.dumps({k: {x: y for x, y in v.items() if "|" not in x} for k, v in sep.items()}))
    print(f"natural clips={n_nat}, rows written to new sheets={n_lab}")


if __name__ == "__main__":
    main()

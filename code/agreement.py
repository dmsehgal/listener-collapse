"""Agreement between the first rater (the author) and the independent second raters.

Reads the answer files the raters send back (results/raters/answers_rater_<id>.csv)
and the author's labels. Task 1: Cohen's kappa for each rater against the author and
between raters, and Fleiss' kappa for all raters, on clips every rater in the comparison
judged correct or wrong. Unclear answers are counted separately. Task 2: how many of
the author's spot-check clips each rater heard differently, and how many of the six
Gemini rewrites and 18 faithful Gemini clips each rater marked as not said as given.
Output: results/agreement.json
"""
import csv
import glob
import itertools
import json
import os

RATERS_DIR = os.environ.get("RATERS_DIR", "results/raters")
REWRITES = {("gemini", "S062_M_NEG"), ("gemini", "S063_M_NEG"), ("gemini", "S065_M_NEG"),
            ("gemini", "S116_M_UNIT"), ("gemini_lite", "S062_M_NEG"), ("gemini_lite", "S078_M_CMP")}


def cohen(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def fleiss(table):
    """table: list of label lists, one per clip, same number of raters each."""
    if not table:
        return None
    n, m = len(table), len(table[0])
    cats = sorted({x for row in table for x in row})
    p = {c: sum(row.count(c) for row in table) / (n * m) for c in cats}
    P = [(sum(row.count(c) ** 2 for c in cats) - m) / (m * (m - 1)) for row in table]
    pbar, pe = sum(P) / n, sum(v * v for v in p.values())
    return 1.0 if pe == 1 else (pbar - pe) / (1 - pe)


def main():
    author = {}
    for path in ["results/natural_listening_sheet.csv", "results/natural_listening_sheet_gemini.csv"]:
        for r in csv.DictReader(open(path)):
            author[(r["voice"], r["item"])] = r["author_label"].strip().lower()
    spot = {(r["voice"], r["item"]): r["author_said_exactly_these_words(yes/no)"].strip().lower()
            for r in csv.DictReader(open("results/spotcheck_sheet.csv"))}
    # EXCLUDE="B=Samantha,Daniel,Rishi" drops a rater's answers for voices whose rebuilt
    # audio did not match the originals (mac_check.txt), so every comparison uses identical audio.
    exclude = {}
    for part in filter(None, os.environ.get("EXCLUDE", "").split(";")):
        rid, voices = part.split("=")
        exclude[rid] = set(voices.split(","))
    raters = {}
    for path in sorted(glob.glob(os.path.join(RATERS_DIR, "answers_rater_*.csv"))):
        for r in csv.DictReader(open(path)):
            if r["voice"] in exclude.get(r["rater"], ()):
                continue
            raters.setdefault(r["rater"], {})[(r["task"], r["voice"], r["item"])] = r["label"].strip().lower()
    if not raters:
        print(f"no answer files in {RATERS_DIR}")
        return
    names = ["author"] + sorted(raters)
    nat = {"author": {k: v for k, v in author.items() if v}}
    for rid, ans in raters.items():
        nat[rid] = {(v, it): lab for (t, v, it), lab in ans.items() if t == "natural"}
    out = {"raters": sorted(raters), "natural": {}, "exact": {}}
    for rid in names:
        labs = list(nat[rid].values())
        out["natural"][f"{rid}_counts"] = {c: labs.count(c) for c in ("correct", "wrong", "unclear")}
    for x, y in itertools.combinations(names, 2):
        both = [k for k in nat[x] if k in nat[y] and nat[x][k] in ("correct", "wrong") and nat[y][k] in ("correct", "wrong")]
        a, b = [nat[x][k] for k in both], [nat[y][k] for k in both]
        agree = sum(p == q for p, q in zip(a, b))
        out["natural"][f"{x}_vs_{y}"] = {"clips": len(both), "agree": agree, "kappa": cohen(a, b),
                                         "disagreements": [f"{v}/{it} {nat[x][(v, it)]}/{nat[y][(v, it)]}"
                                                           for (v, it) in both if nat[x][(v, it)] != nat[y][(v, it)]]}
    if len(names) > 2:
        common = [k for k in nat["author"] if all(nat[r].get(k) in ("correct", "wrong") for r in names)]
        out["natural"]["fleiss_all"] = {"clips": len(common), "kappa": fleiss([[nat[r][k] for r in names] for k in common])}
    for rid, ans in raters.items():
        ex = {(v, it): lab for (t, v, it), lab in ans.items() if t == "exact"}
        sp = [k for k in ex if k in spot]
        rw = [k for k in ex if k in REWRITES]
        ctl = [k for k in ex if k not in spot and k not in REWRITES]
        out["exact"][rid] = {
            "spot_clips": len(sp), "spot_differ_from_author": [f"{v}/{it}: {ex[(v, it)]}" for v, it in sp if ex[(v, it)] != spot[(v, it)]],
            "rewrites_marked_no": sum(ex[k] == "no" for k in rw), "rewrites_heard": len(rw),
            "rewrites_not_marked_no": [f"{v}/{it}: {ex[(v, it)]}" for v, it in rw if ex[(v, it)] != "no"],
            "controls_marked_no": [f"{v}/{it}: {ex[(v, it)]}" for v, it in ctl if ex[(v, it)] != "yes"], "controls_heard": len(ctl),
        }
    json.dump(out, open("results/agreement.json", "w"), indent=1)
    for k, v in out["natural"].items():
        if isinstance(v, dict) and "kappa" in v:
            kap = "n/a" if v["kappa"] is None else f"{v['kappa']:.2f}"
            extra = f", agree {v['agree']}/{v['clips']}" if "agree" in v else f" on {v['clips']} clips"
            print(f"task 1 {k:22s} kappa {kap}{extra}")
    for rid, v in out["exact"].items():
        print(f"task 2 rater {rid}: rewrites marked no {v['rewrites_marked_no']}/{v['rewrites_heard']}, "
              f"faithful clips marked no or unclear {len(v['controls_marked_no'])}/{v['controls_heard']}, "
              f"spot clips differing from author {len(v['spot_differ_from_author'])}/{v['spot_clips']}")


if __name__ == "__main__":
    main()

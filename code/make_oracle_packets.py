"""Build the 'people as the oracle' packets: a person hears a reading and judges it
against the printed reply, the job the round-trip oracle does.

100 clips per rater, each from a different seed so no reply is heard twice:
55 mutants (5 per operator), 30 correct readings and 15 meaning-preserving variants,
half Piper and half Gemini 3.8 Flash TTS, whose audio can be shared privately.
Excluded: every mutant the raters already heard in task 2, the four Gemini rewrites
and Gemini S066_M_NEG. Both raters get the same clips in different orders.

Usage: python code/make_oracle_packets.py B2 C2     Output: rater_packets/oracle_<id>.zip
"""
import csv
import json
import os
import random
import re
import shutil
import zipfile
from collections import Counter

OUT = "rater_packets"
VOICES = ["piper", "gemini"]
OPS = ["DEC", "UNIT", "TEENTY", "CUR", "SCALE", "SIGN", "NUM", "SWAP", "AMPM", "NEG", "CMP"]
SEEDS = {"B2": 101, "C2": 102}

items = {r["item"]: r for r in csv.DictReader(open("data/items.csv"))}
page = open(f"{OUT}/rater_B/label.html").read()
heard = json.loads(re.search(r"const TASKS = (\{.*?\});\n", page, re.S).group(1).replace("<\\/", "</"))
heard = {c["i"] for c in heard["exact"]["clips"]}
skip = {("gemini", i) for i in ["S062_M_NEG", "S063_M_NEG", "S065_M_NEG", "S116_M_UNIT", "S066_M_NEG"]}


def ok(v, it):
    return it not in heard and (v, it) not in skip and os.path.exists(f"audio/{v}/{it}.wav")


def choose():
    rng = random.Random(30)
    seeds = sorted({r["seed"] for r in items.values() if r["kind"] != "natural"})
    rng.shuffle(seeds)
    used, picks, turn = set(), [], 0

    def take(kind, op, n):
        nonlocal turn
        got = 0
        for s in seeds:
            if got == n:
                break
            if s in used:
                continue
            cands = [it for it, r in items.items() if r["seed"] == s and r["kind"] == kind and (op is None or r["op"] == op)]
            for v in VOICES[turn % 2:] + VOICES[:turn % 2]:
                its = [it for it in cands if ok(v, it)]
                if its:
                    picks.append((v, rng.choice(its)))
                    used.add(s)
                    turn += 1
                    got += 1
                    break
        assert got == n, (kind, op, got)

    by_need = sorted(OPS, key=lambda op: sum(r["op"] == op and r["item"] not in heard for r in items.values()))
    for op in by_need:
        take("mutant", op, 5)
    take("correct", None, 30)
    take("equivalent", None, 15)
    return picks


README = """Listening task 3 for the paper "Listener Collapse"            Rater {rid}

Thank you again. This one takes about 15 minutes and needs no Terminal step.
Please do it before you read the paper draft, and do not discuss the clips with
anyone, including Deep, until you have sent your answers. Use headphones.

1. Unzip this folder.
2. Open label.html in Chrome. Read the first page, then do the task.
3. Click "Download my answers" and send the file answers_rater_{rid}.csv to Deep.

Please keep these files private. They are for this study only.
"""


def build(rid, picks):
    d = os.path.join(OUT, f"oracle_{rid}")
    if os.path.isdir(d):
        shutil.rmtree(d)
    clips = [{"i": it, "v": v, "p": f"audio/{v}/{it}.wav", "t": items[it]["reference"]} for v, it in picks]
    random.Random(SEEDS[rid]).shuffle(clips)
    for c in clips:
        os.makedirs(os.path.join(d, os.path.dirname(c["p"])), exist_ok=True)
        shutil.copyfile(c["p"], os.path.join(d, c["p"]))
    T = {"natural": {"name": "Task 3: printed reply against voice", "prompt": "Printed reply. Does the voice say these facts?", "clips": clips}}
    js = lambda x: json.dumps(x, ensure_ascii=False).replace("</", "<\\/")
    html = open("code/oracle_page.html").read()
    html = html.replace("__RATER__", js({"id": rid})).replace("__MAC_VOICES__", js([])).replace("__TASKS__", js(T))
    open(os.path.join(d, "label.html"), "w").write(html)
    open(os.path.join(d, "README.txt"), "w").write(README.format(rid=rid))
    z = os.path.join(OUT, f"oracle_{rid}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(d):
            for name in sorted(files):
                p = os.path.join(root, name)
                zf.write(p, os.path.relpath(p, OUT))
    print(f"rater {rid}: {len(clips)} clips, zip {os.path.getsize(z) / 1e6:.1f} MB")


if __name__ == "__main__":
    import sys
    picks = choose()
    kinds = Counter(items[it]["kind"] for _, it in picks)
    print("kinds", dict(kinds), "voices", dict(Counter(v for v, _ in picks)),
          "ops", dict(Counter(items[it]["op"] for _, it in picks if items[it]["kind"] == "mutant")),
          "distinct seeds", len({items[it]["seed"] for _, it in picks}))
    with open(f"{OUT}/oracle_clips.csv", "w") as f:
        w = csv.writer(f)
        w.writerow(["voice", "item", "kind", "op"])
        for v, it in sorted(picks):
            w.writerow([v, it, items[it]["kind"], items[it]["op"]])
    for rid in sys.argv[1:] or ["B2", "C2"]:
        build(rid, picks)

"""Did each voice say the facts it was given?

For every mutation-study clip, compare the fact frame of each listener's
transcript with the fact frame of the spoken form that was synthesised (not the
printed reply). A clip is "faithful" when at least two of the three unprompted listeners
recover the spoken form's facts. The prompted listener is left out, because it is
biased toward the printed reply by design. Clips where fewer agree are listed,
so they can be checked by ear. Output: results/fidelity.json.
"""
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, "code")
from frames import frame  # noqa: E402

LIS = ["whisper", "whisper_anchored", "whisper_spelled", "vosk"]
items = {r["item"]: r for r in csv.DictReader(open("data/items.csv")) if r["kind"] != "natural"}
T = defaultdict(dict)
for l in LIS:
    for line in open(f"results/transcripts/{l}.jsonl"):
        j = json.loads(line)
        if j["item"] in items:
            T[(j["item"], j["voice"])][l] = j["text"]
out = {}
for v in ["piper", "Samantha", "Daniel", "Rishi", "gemini"]:
    keys = [k for k in T if k[1] == v and len(T[k]) == len(LIS)]
    if not keys:
        continue
    faithful, doubtful = 0, []
    for it, _ in keys:
        want = frame(items[it]["spoken"])
        agree = sum(frame(T[(it, v)][l]) == want for l in LIS if l != "whisper_anchored")
        if agree >= 2:
            faithful += 1
        else:
            doubtful.append(dict(item=it, agree=agree, spoken=items[it]["spoken"],
                                 whisper=T[(it, v)]["whisper"], vosk=T[(it, v)]["vosk"]))
    out[v] = dict(clips=len(keys), faithful=faithful, doubtful=len(doubtful), examples=doubtful[:15])
    print(f"{v:9s} clips={len(keys)} faithful={faithful} ({100 * faithful / len(keys):.1f}%) doubtful={len(doubtful)}")
json.dump(out, open("results/fidelity.json", "w"), indent=1)

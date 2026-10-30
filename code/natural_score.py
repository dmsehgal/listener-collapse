"""Score the oracles on the natural readings once the author has labelled them.

Fill the author_label column of results/natural_listening_sheet.csv with
"correct" (the voice said what the printed reply means) or "wrong" (it did not),
then run this script. Rows without a label are skipped and counted.
"""
import csv
import sys

sys.path.insert(0, "third_party")
from whisper_normalizer import EnglishTextNormalizer  # noqa: E402

import os
rows = []
for sheet in ("results/natural_listening_sheet.csv", "results/natural_listening_sheet_gemini.csv"):
    if os.path.exists(sheet):
        rows += list(csv.DictReader(open(sheet)))
# Sheets without transcript columns (the Gemini sheet) take their verdicts from
# the per-clip table that score.py writes.
for vpath in ("results/tables/clip_verdicts.csv", "results/gemini/tables/clip_verdicts.csv"):
    if not os.path.exists(vpath):
        continue
    ver = {(v["listener"], v["item"], v["voice"]): v for v in csv.DictReader(open(vpath)) if v["kind"] == "natural"}
    for r in rows:
        for lis in ("whisper", "whisper_anchored", "whisper_spelled", "vosk"):
            v = ver.get((lis, r["item"], r["voice"]))
            if v and f"{lis}_value_pass" not in r:
                r[f"{lis}_value_pass"] = v["value_pass"]
                r[f"{lis}_wer"] = v["wer"]
rows = [r for r in rows if "whisper_value_pass" in r or not r["author_label"].strip()]
lab = [r for r in rows if r["author_label"].strip().lower() in ("correct", "wrong")]
print(f"read {len(rows)} clips, labelled {len(lab)}, skipped {len(rows) - len(lab)}")
if not lab:
    sys.exit(0)
wrong = [r for r in lab if r["author_label"].strip().lower() == "wrong"]
right = [r for r in lab if r["author_label"].strip().lower() == "correct"]
print(f"author heard {len(wrong)} wrong readings and {len(right)} correct ones")
if "--voice" in sys.argv:
    want = sys.argv[sys.argv.index("--voice") + 1]
    wrong = [r for r in wrong if r["voice"] == want]
    right = [r for r in right if r["voice"] == want]
    print(f"restricted to voice {want}: {len(wrong)} wrong, {len(right)} correct")
by_voice = {}
for r in wrong:
    by_voice[r["voice"]] = by_voice.get(r["voice"], 0) + 1
print("wrong readings by voice:", by_voice)

LIS = ["whisper", "whisper_anchored", "whisper_spelled", "vosk"]


def fails(r, lis, comp):
    if comp == "value":
        return r[f"{lis}_value_pass"] != "True"
    return float(r[f"{lis}_wer"]) > 0.10 + 1e-9


print(f"\n{'oracle':32s} {'caught wrong':>14s} {'false alarms':>14s}")
for lis in LIS:
    for comp in ("wer@0.10", "value"):
        k = sum(fails(r, lis, comp) for r in wrong)
        f = sum(fails(r, lis, comp) for r in right)
        print(f"{lis + '|' + comp:32s} {k:6d}/{len(wrong):<7d} {f:6d}/{len(right):<7d}")
for name, members in (("any(whisper,vosk)|value", ["whisper", "vosk"]),
                      ("any(all four)|value", LIS)):
    k = sum(any(fails(r, m, "value") for m in members) for r in wrong)
    f = sum(any(fails(r, m, "value") for m in members) for r in right)
    print(f"{name:32s} {k:6d}/{len(wrong):<7d} {f:6d}/{len(right):<7d}")

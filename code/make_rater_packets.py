"""Build the listening packets for independent second raters.

Each packet holds a labelling page that runs offline in any browser, the clips
that may be shared privately (Piper and Gemini), and a script that rebuilds the
macOS-voice clips on the rater's own Mac and checks them against the originals.
No first-rater labels, transcripts or oracle verdicts go into a packet.

Task 1 (natural): the 40 natural replies in all five voices, as the author labelled them.
Task 2 (exact):   the author's 60 spot-check clips, plus 24 Gemini mutant clips: the six
                  rewrites and 18 clips said as given, five of them the same sentences
                  read by Gemini 2.5 Pro.

Usage: python code/make_rater_packets.py B C     Output: rater_packets/<id>/ and rater_packets/rater_<id>.zip
"""
import csv
import hashlib
import json
import os
import random
import shutil
import sys
import zipfile

sys.path.insert(0, "code")
from frames import frame  # noqa: E402

MAC = ["Samantha", "Daniel", "Rishi"]
NATURAL_VOICES = ["piper", "Samantha", "Daniel", "Rishi", "gemini"]
REWRITES = [("gemini", "S062_M_NEG"), ("gemini", "S063_M_NEG"), ("gemini", "S065_M_NEG"),
            ("gemini", "S116_M_UNIT"), ("gemini_lite", "S062_M_NEG"), ("gemini_lite", "S078_M_CMP")]
MATCHED = [("gemini_pro", it) for it in ["S062_M_NEG", "S063_M_NEG", "S065_M_NEG", "S116_M_UNIT", "S078_M_CMP"]]
OUT = "rater_packets"

items = {r["item"]: r for r in csv.DictReader(open("data/items.csv"))}


def faithful_controls():
    """Gemini mutant clips that all three unprompted listeners heard as the given text."""
    T = {}
    for lis in ["whisper", "whisper_spelled", "vosk"]:
        for line in open(f"results/transcripts/{lis}.jsonl"):
            j = json.loads(line)
            if j["voice"].startswith("gemini") and items[j["item"]]["kind"] == "mutant":
                T.setdefault((j["voice"], j["item"]), {})[lis] = j["text"]
    skip = set(REWRITES) | set(MATCHED) | {("gemini", "S066_M_NEG")}
    pool = {v: [] for v in ["gemini", "gemini_lite", "gemini_pro"]}
    for (v, it), t in sorted(T.items()):
        want = frame(items[it]["spoken"])
        if (v, it) not in skip and len(t) == 3 and all(frame(x) == want for x in t.values()):
            pool[v].append((v, it))
    rng = random.Random(2026)
    picks = rng.sample(pool["gemini"], 5) + rng.sample(pool["gemini_lite"], 5) + rng.sample(pool["gemini_pro"], 3)
    return picks


def clip(v, it, text):
    return {"i": it, "v": v, "p": f"audio/{v}/{it}.wav", "t": text}


def tasks(seed):
    natural = [clip(v, it, r["reference"]) for it, r in items.items() if r["kind"] == "natural" for v in NATURAL_VOICES]
    spot = [clip(r["voice"], r["item"], r["words_given_to_synthesiser"]) for r in csv.DictReader(open("results/spotcheck_sheet.csv"))]
    gem = [clip(v, it, items[it]["spoken"]) for v, it in REWRITES + MATCHED + faithful_controls()]
    rng = random.Random(seed)
    rng.shuffle(natural)
    exact = spot + gem
    rng.shuffle(exact)
    return {
        "natural": {"name": "Task 1: facts", "prompt": "Printed reply. Did the voice get the facts right?", "clips": natural},
        "exact": {"name": "Task 2: exact words", "prompt": "Words given to the voice. Did it say exactly these words?", "clips": exact},
    }


MAC_SCRIPT = r"""#!/bin/bash
# Rebuilds the macOS-voice clips for the listening task on this Mac, with the same
# settings as the original study, and checks that they match the originals exactly.
# Run with:  bash make_mac_voices.sh
cd "$(dirname "$0")" || exit 1
if ! command -v say >/dev/null 2>&1; then echo "This script needs macOS."; exit 1; fi
for v in Samantha Daniel Rishi; do
  if ! say -v '?' | grep -q "^$v "; then
    echo "The voice $v is not installed. Add it in System Settings > Accessibility > Spoken Content > System voice > Manage Voices, then run this again."
    exit 1
  fi
  mkdir -p "audio/$v"
done
n=0
while IFS=$'\t' read -r v item text; do
  say -v "$v" -o "audio/$v/$item.wav" --data-format=LEI16@16000 "$text" && n=$((n+1))
done < mac_voices/clips.tsv
same=$(cd audio && shasum -a 256 -c ../mac_voices/SHA256SUMS.txt 2>/dev/null | grep -c ': OK$')
total=$(wc -l < mac_voices/SHA256SUMS.txt | tr -d ' ')
{
  echo "Made $n clips."
  echo "$same of $total clips are identical to the originals."
} | tee mac_check.txt
echo "Done. Now open label.html."
"""

README = """Listening task for the paper "Listener Collapse"            Rater {rid}

Thank you for helping. Please do both tasks before you read the paper draft,
and do not discuss the clips with anyone, including Deep, until you have sent
your answers.
Use headphones in a quiet room.

Time: about 75 minutes on a Mac. About 30 minutes on Windows or Linux,
where the clips of the three Mac voices are skipped.

1. Unzip this folder, for example into Downloads.

2. Mac only. Open the Terminal app, type   bash   and a space, drag the file
   make_mac_voices.sh from this folder into the Terminal window, and press Return.
   If you unzipped into Downloads, this line does the same:

       bash ~/Downloads/rater_{rid}/make_mac_voices.sh

   It makes {nmac} clips with three voices that come with macOS (about two minutes)
   and checks that they match the originals exactly. If it says a voice is not
   installed, add it in System Settings > Accessibility > Spoken Content >
   System voice > Manage Voices, then run it again.
   On Windows or Linux, skip this step.

3. Open label.html in Chrome, Edge, Firefox or Safari. Read the instructions on
   the page, then do Task 1 and Task 2. Answers are saved in the browser as you
   go, so you can stop and come back. Use the same browser each time.

4. Click "Download my answers" and send the file answers_rater_{rid}.csv back
   to Deep. On a Mac, also send the file mac_check.txt from this folder.

Please keep these files private. They are for this study only.
"""


def build(rid, seed):
    d = os.path.join(OUT, f"rater_{rid}")
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(os.path.join(d, "mac_voices"))
    T = tasks(seed)
    allclips = T["natural"]["clips"] + T["exact"]["clips"]
    for c in allclips:
        if c["v"] not in MAC:
            dst = os.path.join(d, c["p"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(c["p"], dst)
    texts = {(c["v"], c["i"]): items[c["i"]]["spoken"] for c in allclips if c["v"] in MAC}
    with open(os.path.join(d, "mac_voices", "clips.tsv"), "w") as f:
        for (v, it), text in sorted(texts.items()):
            assert "\t" not in text and "\n" not in text
            f.write(f"{v}\t{it}\t{text}\n")
    with open(os.path.join(d, "mac_voices", "SHA256SUMS.txt"), "w") as f:
        for v, it in sorted(texts):
            h = hashlib.sha256(open(f"audio/{v}/{it}.wav", "rb").read()).hexdigest()
            f.write(f"{h}  {v}/{it}.wav\n")
    with open(os.path.join(d, "make_mac_voices.sh"), "w") as f:
        f.write(MAC_SCRIPT)
    with open(os.path.join(d, "README.txt"), "w") as f:
        f.write(README.format(rid=rid, nmac=len(texts)))
    page = open("code/rater_page.html").read()
    js = lambda x: json.dumps(x, ensure_ascii=False).replace("</", "<\\/")
    page = page.replace("__RATER__", js({"id": rid})).replace("__MAC_VOICES__", js(MAC)).replace("__TASKS__", js(T))
    with open(os.path.join(d, "label.html"), "w") as f:
        f.write(page)
    z = os.path.join(OUT, f"rater_{rid}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(d):
            for name in sorted(files):
                p = os.path.join(root, name)
                zf.write(p, os.path.relpath(p, OUT))
    n_nat, n_ex = len(T["natural"]["clips"]), len(T["exact"]["clips"])
    no_mac = sum(c["v"] not in MAC for c in allclips)
    print(f"rater {rid}: task 1 {n_nat} clips, task 2 {n_ex} clips, {len(texts)} rebuilt on a Mac, "
          f"{no_mac} without a Mac; zip {os.path.getsize(z) / 1e6:.1f} MB")


SEEDS = {"B": 11, "C": 23, "D": 35, "E": 47}  # fixed per rater, so rebuilding one packet keeps its clip order

if __name__ == "__main__":
    for rid in sys.argv[1:] or ["B", "C"]:
        build(rid, seed=SEEDS[rid])

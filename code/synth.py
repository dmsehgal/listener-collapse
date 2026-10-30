"""Synthesise every item in four voices.

Piper (en_US lessac, open source) and three macOS system voices: Samantha (US),
Daniel (UK) and Rishi (Indian English). Aman was dropped: it is not deterministic
and sometimes produced broken audio (see lessons_learned.md). Mutation items are synthesised from their
spoken form, so the fault is the one we injected. Natural items are synthesised
from the printed text, so each synthesiser applies its own text handling.
Output: audio/<voice>/<item>.wav. Skips files that already exist.
"""
import csv
import os
import subprocess
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor

from piper import PiperVoice

PIPER_MODEL = "models/piper/en_US-lessac-medium.onnx"
SAY_VOICES = ["Samantha", "Daniel", "Rishi"]


def main():
    rows = list(csv.DictReader(open("data/items.csv")))
    print("read", len(rows), "items")
    voice = PiperVoice.load(PIPER_MODEL)
    made = skipped = 0
    t0 = time.time()
    for v in ["piper"] + SAY_VOICES:
        os.makedirs(f"audio/{v}", exist_ok=True)
    jobs = []
    for r in rows:
        text = r["spoken"]
        out = f"audio/piper/{r['item']}.wav"
        if os.path.exists(out):
            skipped += 1
        else:
            with wave.open(out, "wb") as wf:
                voice.synthesize_wav(text, wf)
            made += 1
        for v in SAY_VOICES:
            out = f"audio/{v}/{r['item']}.wav"
            if os.path.exists(out):
                skipped += 1
            else:
                jobs.append(["say", "-v", v, "-o", out, "--data-format=LEI16@16000", text])
    # The system voices run in parallel; each call is a separate process.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for _ in pool.map(lambda cmd: subprocess.run(cmd, check=True), jobs):
            made += 1
    print(f"made={made} skipped={skipped} seconds={time.time() - t0:.0f}")
    expected = len(rows) * (1 + len(SAY_VOICES))
    have = sum(len(os.listdir(f"audio/{v}")) for v in ["piper"] + SAY_VOICES)
    print(f"expected={expected} on_disk={have}")
    sys.exit(0 if have == expected else 1)


if __name__ == "__main__":
    main()

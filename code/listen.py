"""Transcribe every clip with each listener. One listener at a time.

Listeners:
  whisper           faster-whisper base.en, int8, beam 5, temperature 0
  whisper_anchored  the same model, prompted with the printed reference text
  whisper_spelled   the same model with every digit and symbol token suppressed,
                    so numbers must come out as words
  vosk              Vosk small English model (Kaldi), a different model family
Output: results/transcripts/<listener>.jsonl, one line per clip. Resumable.
"""
import csv
import json
import os
import sys
import time
import wave

VOICES = os.environ.get("LISTEN_VOICES", "piper,Samantha,Daniel,Rishi").split(",")
OUT = "results/transcripts"


def done_keys(path):
    if not os.path.exists(path):
        return set()
    return {(j["item"], j["voice"]) for j in map(json.loads, open(path))}


def run(name, rows, transcribe):
    os.makedirs(OUT, exist_ok=True)
    path = f"{OUT}/{name}.jsonl"
    done = done_keys(path)
    todo = [(r, v) for r in rows for v in VOICES if (r["item"], v) not in done]
    print(f"[{name}] clips={len(rows) * len(VOICES)} already={len(done)} todo={len(todo)}", flush=True)
    t0 = time.time()
    with open(path, "a") as f:
        for k, (r, v) in enumerate(todo):
            wav = f"audio/{v}/{r['item']}.wav"
            text = transcribe(wav, r)
            f.write(json.dumps({"item": r["item"], "voice": v, "text": text}) + "\n")
            if k % 200 == 0:
                f.flush()
                print(f"[{name}] {k}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    n = len(done_keys(path))
    print(f"[{name}] finished, lines={n} seconds={time.time() - t0:.0f}", flush=True)
    return n


def main():
    rows = list(csv.DictReader(open("data/items.csv")))
    want = sys.argv[1:] or ["whisper", "whisper_anchored", "whisper_spelled", "vosk"]
    print("read", len(rows), "items, listeners:", want, flush=True)
    missing = [(r["item"], v) for r in rows for v in VOICES if not os.path.exists(f"audio/{v}/{r['item']}.wav")]
    if missing and os.environ.get("LISTEN_PARTIAL"):
        # Partial mode: transcribe only the clips that exist so far.
        have = {(r["item"]) for r in rows if all(os.path.exists(f"audio/{v}/{r['item']}.wav") for v in VOICES)}
        rows = [r for r in rows if r["item"] in have]
        print(f"partial mode: {len(rows)} items have audio, {len(missing)} clips still missing", flush=True)
    elif missing:
        print("missing audio:", len(missing), missing[:5])
        sys.exit(1)

    if any(w.startswith("whisper") for w in want):
        from faster_whisper import WhisperModel
        model = WhisperModel("base.en", device="cpu", compute_type="int8",
                             cpu_threads=int(os.environ.get("LISTEN_THREADS", "8")))
        kw = dict(beam_size=5, language="en", temperature=0.0, vad_filter=False)

        def w_plain(wav, r):
            segs, _ = model.transcribe(wav, **kw)
            return " ".join(s.text.strip() for s in segs)

        def w_anchor(wav, r):
            segs, _ = model.transcribe(wav, initial_prompt=r["reference"], **kw)
            return " ".join(s.text.strip() for s in segs)

        tok = model.hf_tokenizer
        bad_chars = set("0123456789%$€£°")
        vocab = tok.get_vocab_size()
        suppress = [-1] + [i for i in range(vocab) if any(c in bad_chars for c in tok.decode([i]))]
        print(f"whisper_spelled suppresses {len(suppress) - 1} of {vocab} tokens", flush=True)

        def w_spelled(wav, r):
            segs, _ = model.transcribe(wav, suppress_tokens=suppress, **kw)
            return " ".join(s.text.strip() for s in segs)

        table = {"whisper": w_plain, "whisper_anchored": w_anchor, "whisper_spelled": w_spelled}
        for name in want:
            if name in table:
                run(name, rows, table[name])
        del model

    if "vosk" in want:
        from vosk import KaldiRecognizer, Model, SetLogLevel
        SetLogLevel(-1)
        vm = Model("models/vosk-model-small-en-us-0.15")

        def v_listen(wav, r):
            with wave.open(wav, "rb") as wf:
                rec = KaldiRecognizer(vm, wf.getframerate())
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)
                return json.loads(rec.FinalResult()).get("text", "")
        run("vosk", rows, v_listen)


if __name__ == "__main__":
    main()

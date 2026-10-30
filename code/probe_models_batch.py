"""Rewrite probe: do other Google voices say the mutant text they are given?

Synthesises the 230 mutants with two more Gemini TTS models through the Batch API
and writes audio/<name>/<item>.wav. A response without audio is logged as a
refusal. The dollar ceiling covers all Gemini spending in this project: the main
Gemini run (results/gemini_usage.jsonl) plus this probe. Prices are the published
batch rates per token, checked on 2026-10-29.
"""
import base64
import csv
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, "code")
from synth_gemini import DOLLAR_CAP, VOICE, load_key  # noqa: E402
from synth_gemini_batch import BASE, call, spent_so_far  # noqa: E402

MODELS = {  # name: (model id, batch price per text token in, per audio token out)
    "gemini_lite": ("gemini-3.8-flash-lite-tts", 0.25 / 1e6, 3.00 / 1e6),
    "gemini_pro": ("gemini-2.5-pro-preview-tts", 0.50 / 1e6, 10.00 / 1e6),
}
USAGE = "results/gemini_probe_usage.jsonl"
JOBS = "results/gemini_probe_jobs.json"
REFUSALS = "results/gemini_probe_refusals.jsonl"
CHUNK = 50


def probe_spent():
    total = 0.0
    if os.path.exists(USAGE):
        for line in open(USAGE):
            u = json.loads(line)
            _, pin, pout = MODELS[u["voice"]]
            total += u.get("promptTokenCount", 0) * pin + u.get("candidatesTokenCount", 0) * pout
    return total


def main():
    key = load_key()
    rows = [r for r in csv.DictReader(open("data/items.csv")) if r["kind"] == "mutant"]
    jobs = json.load(open(JOBS)) if os.path.exists(JOBS) else []
    spent = spent_so_far() + probe_spent()
    est = sum(len(rows) * 130 * pout for _, _, pout in MODELS.values())
    print(f"mutants={len(rows)}; Gemini spend so far ${spent:.3f}; estimate for probe ${est:.3f}; cap ${DOLLAR_CAP:.2f}", flush=True)
    if not jobs and spent + est > DOLLAR_CAP:
        sys.exit("estimate would exceed the dollar cap, not submitting")
    if not jobs:
        for name, (model, _, _) in MODELS.items():
            os.makedirs(f"audio/{name}", exist_ok=True)
            for i in range(0, len(rows), CHUNK):
                chunk = rows[i:i + CHUNK]
                reqs = [{"request": {"contents": [{"parts": [{"text": r["spoken"]}]}],
                                     "generationConfig": {"responseModalities": ["AUDIO"],
                                                          "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}},
                         "metadata": {"key": r["item"]}} for r in chunk]
                body = {"batch": {"display_name": f"probe-{name}-{i // CHUNK}",
                                  "input_config": {"requests": {"requests": reqs}}}}
                r = call(key, f"{BASE}/models/{model}:batchGenerateContent", body)
                jobs.append({"name": r["name"], "voice": name, "items": [x["item"] for x in chunk], "saved": False})
                json.dump(jobs, open(JOBS, "w"), indent=1)
                print(f"submitted {name} job with {len(chunk)} items", flush=True)
    t0 = time.time()
    while any(not j["saved"] for j in jobs):
        for j in jobs:
            if j["saved"]:
                continue
            try:
                r = call(key, f"{BASE}/{j['name']}")
            except Exception as e:  # keep polling through transient errors
                print("  poll error", type(e).__name__, flush=True)
                continue
            state = r.get("metadata", {}).get("state")
            if state == "BATCH_STATE_SUCCEEDED":
                got = 0
                for x in r.get("response", {}).get("inlinedResponses", {}).get("inlinedResponses", []):
                    item = x["metadata"]["key"]
                    try:
                        part = x["response"]["candidates"][0]["content"]["parts"][0]["inlineData"]
                        data = base64.b64decode(part["data"])
                        assert data[:4] == b"RIFF"
                    except Exception:
                        with open(REFUSALS, "a") as f:
                            f.write(json.dumps({"voice": j["voice"], "item": item, "response": json.dumps(x)[:600]}) + "\n")
                        continue
                    with open(f"audio/{j['voice']}/{item}.wav", "wb") as f:
                        f.write(data)
                    u = x["response"].get("usageMetadata", {})
                    with open(USAGE, "a") as f:
                        f.write(json.dumps({"voice": j["voice"], "item": item,
                                            **{k: v for k, v in u.items() if isinstance(v, (int, str))}}) + "\n")
                    got += 1
                j["saved"] = True
                json.dump(jobs, open(JOBS, "w"), indent=1)
                print(f"{j['voice']} job saved {got}/{len(j['items'])} after {time.time() - t0:.0f}s; "
                      f"total Gemini spend ${spent_so_far() + probe_spent():.3f}", flush=True)
            elif state in ("BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED", "BATCH_STATE_EXPIRED"):
                j["saved"] = True
                json.dump(jobs, open(JOBS, "w"), indent=1)
                print(f"{j['voice']} job {state}: {json.dumps(r.get('metadata', {}).get('batchStats'))}", flush=True)
        time.sleep(30)
    for name in MODELS:
        print(f"{name}: {len(os.listdir(f'audio/{name}'))} clips on disk", flush=True)
    print(f"done; total Gemini spend ${spent_so_far() + probe_spent():.3f}", flush=True)


if __name__ == "__main__":
    main()

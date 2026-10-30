"""Finish the Gemini clips with the Batch API (separate quota, half price).

Submits the remaining items in jobs of 50 inline requests, polls until each job
finishes, and writes audio/gemini/<item>.wav. Usage is logged to the same file as
synth_gemini.py, priced at batch rates, and the same dollar ceiling covers both.
Job names are saved so a restart resumes polling instead of resubmitting.
"""
import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "code")
from synth_gemini import DOLLAR_CAP, MODEL, PRICE_IN, PRICE_OUT, USAGE, VOICE, load_key  # noqa: E402

BASE = "https://generativelanguage.googleapis.com/v1beta"
JOBS = "results/gemini_batch_jobs.json"
CHUNK = 50


def call(key, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))


def spent_so_far():
    total = 0.0
    if os.path.exists(USAGE):
        for line in open(USAGE):
            u = json.loads(line)
            f = 0.5 if u.get("batch") else 1.0
            total += f * (u.get("promptTokenCount", 0) * PRICE_IN + u.get("candidatesTokenCount", 0) * PRICE_OUT)
    return total


def save(responses):
    n = 0
    for x in responses:
        item = x["metadata"]["key"]
        try:
            part = x["response"]["candidates"][0]["content"]["parts"][0]["inlineData"]
        except (KeyError, IndexError):
            print("  no audio for", item, json.dumps(x)[:200])
            continue
        data = base64.b64decode(part["data"])
        if data[:4] != b"RIFF":
            print("  not a WAV for", item)
            continue
        with open(f"audio/gemini/{item}.wav", "wb") as f:
            f.write(data)
        u = x["response"].get("usageMetadata", {})
        with open(USAGE, "a") as f:
            f.write(json.dumps({"item": item, "batch": True, **{k: v for k, v in u.items() if isinstance(v, (int, str))}}) + "\n")
        n += 1
    return n


def main():
    key = load_key()
    rows = list(csv.DictReader(open("data/items.csv")))
    jobs = json.load(open(JOBS)) if os.path.exists(JOBS) else []
    if os.path.exists("results/gemini_batch_test.json"):
        t = json.load(open("results/gemini_batch_test.json"))
        if not any(j["name"] == t["name"] for j in jobs):
            jobs.append({"name": t["name"], "items": t["items"], "saved": False})
    pending_items = {i for j in jobs if not j.get("saved") for i in j["items"]}
    todo = [r for r in rows if not os.path.exists(f"audio/gemini/{r['item']}.wav") and r["item"] not in pending_items]
    est = sum(len(r["spoken"]) for r in todo) / 13 * 0  # text cost is negligible
    est_audio = len(todo) * 130 * PRICE_OUT * 0.5
    spent = spent_so_far()
    print(f"spent so far ${spent:.3f}; {len(todo)} items to submit, estimated ${est_audio + est:.3f} more; cap ${DOLLAR_CAP:.2f}", flush=True)
    if spent + est_audio > DOLLAR_CAP:
        sys.exit("estimated total would exceed the dollar cap, not submitting")
    for i in range(0, len(todo), CHUNK):
        chunk = todo[i:i + CHUNK]
        reqs = [{"request": {"contents": [{"parts": [{"text": r["spoken"]}]}],
                             "generationConfig": {"responseModalities": ["AUDIO"],
                                                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}},
                 "metadata": {"key": r["item"]}} for r in chunk]
        body = {"batch": {"display_name": f"lc-{i // CHUNK}", "input_config": {"requests": {"requests": reqs}}}}
        r = call(key, f"{BASE}/models/{MODEL}:batchGenerateContent", body)
        jobs.append({"name": r["name"], "items": [x["item"] for x in chunk], "saved": False})
        json.dump(jobs, open(JOBS, "w"), indent=1)
        print(f"submitted {r['name']} with {len(chunk)} items", flush=True)
    t0 = time.time()
    while any(not j.get("saved") for j in jobs):
        for j in jobs:
            if j.get("saved"):
                continue
            try:
                r = call(key, f"{BASE}/{j['name']}")
            except urllib.error.HTTPError as e:
                print("  poll error", e.code, flush=True)
                continue
            md = r.get("metadata", {})
            state = md.get("state")
            if state == "BATCH_STATE_SUCCEEDED":
                n = save(r.get("response", {}).get("inlinedResponses", {}).get("inlinedResponses", []))
                j["saved"] = True
                json.dump(jobs, open(JOBS, "w"), indent=1)
                print(f"{j['name']}: saved {n}/{len(j['items'])} after {time.time() - t0:.0f}s; spent ${spent_so_far():.3f}", flush=True)
            elif state in ("BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED", "BATCH_STATE_EXPIRED"):
                j["saved"] = True
                json.dump(jobs, open(JOBS, "w"), indent=1)
                print(f"{j['name']}: {state}", json.dumps(md.get("batchStats")), flush=True)
        time.sleep(30)
    have = len(os.listdir("audio/gemini"))
    print(f"all jobs done: on_disk={have} of {len(rows)}, spent ${spent_so_far():.3f}", flush=True)


if __name__ == "__main__":
    main()

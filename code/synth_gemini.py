"""Synthesise every item with Gemini 3.8 Flash TTS, a current commercial voice.

Same rule as synth.py: mutation items from their spoken form, natural items from
the printed text. The API key is read from the GEMINI_API_KEY environment
variable or from a .env file given with --env, sent only in a request header,
and never printed. Every request's token usage is logged, and the run stops
before the dollar cap (DOLLAR_CAP) is exceeded. Output: audio/gemini/<item>.wav. Resumable.
"""
import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

MODEL = "gemini-3.8-flash-tts"
VOICE = "Kore"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
# Hard spending ceiling, at gemini-3.8-flash-tts prices valid through 2026-12-31:
# $0.50 per 1M text tokens in, $9.00 per 1M audio tokens out.
PRICE_IN, PRICE_OUT = 0.50 / 1e6, 9.00 / 1e6
DOLLAR_CAP = 1.00
USAGE = "results/gemini_usage.jsonl"


def load_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if "--env" in sys.argv:
        path = sys.argv[sys.argv.index("--env") + 1]
        for line in open(path):
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("GEMINI_API_KEY not set and no --env file given")


def tts(key, text):
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    wait = 10
    for attempt in range(10):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
            part = r["candidates"][0]["content"]["parts"][0]["inlineData"]
            return base64.b64decode(part["data"]), r.get("usageMetadata", {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503):
                print(f"  HTTP {e.code}, retry in {wait}s", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            raise
        except (KeyError, IndexError, urllib.error.URLError, TimeoutError) as e:
            print(f"  bad or no response ({type(e).__name__}), retry in {wait}s", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 120)
    raise RuntimeError("gave up after 10 attempts")


def main():
    key = load_key()
    rows = list(csv.DictReader(open("data/items.csv")))
    os.makedirs("audio/gemini", exist_ok=True)
    def cost(u):
        return u.get("promptTokenCount", 0) * PRICE_IN + u.get("candidatesTokenCount", 0) * PRICE_OUT
    spent = 0.0
    if os.path.exists(USAGE):
        spent = sum(cost(json.loads(l)) for l in open(USAGE))
    todo = [r for r in rows if not os.path.exists(f"audio/gemini/{r['item']}.wav")]
    # Natural replies first, so the author can label them while the rest runs.
    todo.sort(key=lambda r: r["kind"] != "natural")
    print(f"read {len(rows)} items, {len(rows) - len(todo)} done, {len(todo)} to do, spent so far ${spent:.3f}, cap ${DOLLAR_CAP:.2f}", flush=True)
    t0 = time.time()
    for k, r in enumerate(todo, 1):
        # Stop while there is still room for one more long clip under the cap.
        if spent + 300 * PRICE_OUT > DOLLAR_CAP:
            print(f"dollar cap ${DOLLAR_CAP:.2f} reached (spent ${spent:.3f}), stopping", flush=True)
            sys.exit(2)
        data, usage = tts(key, r["spoken"])
        if data[:4] != b"RIFF":
            raise RuntimeError(f"{r['item']}: response is not a WAV file")
        with open(f"audio/gemini/{r['item']}.wav", "wb") as f:
            f.write(data)
        spent += cost(usage)
        with open(USAGE, "a") as f:
            f.write(json.dumps({"item": r["item"], **{k2: v for k2, v in usage.items() if isinstance(v, (int, str))}}) + "\n")
        if k % 25 == 0:
            print(f"{k}/{len(todo)} spent=${spent:.3f} {time.time() - t0:.0f}s", flush=True)
    have = len(os.listdir("audio/gemini"))
    print(f"finished: on_disk={have} of {len(rows)}, spent ${spent:.3f}", flush=True)
    sys.exit(0 if have == len(rows) else 1)


if __name__ == "__main__":
    main()

# Listener Collapse: harness and data

Code, data and results for the paper "Listener Collapse: Mutation Analysis of What Round-Trip Speech Oracles Cannot Hear" by Deep Mohan Sehgal (CSCI 2026, under review).

## What it does

Spoken output from voice assistants is often checked by a round trip. A recogniser transcribes the audio, the transcript is normalised, and the result is compared with the printed reply. The harness treats this check as a test oracle and measures it with mutation analysis. It injects known faults into the spoken form, synthesises the audio, transcribes it with four listeners, and records which faults each oracle catches and which correct readings it wrongly fails.

## What is included

| Path | Contents |
|---|---|
| `code/` | Every script behind the numbers in the paper |
| `data/items.csv` | 510 items: 120 correct readings, 230 mutants, 120 meaning-preserving variants and 40 natural replies |
| `results/transcripts/` | Every transcript from the four listeners, for all voices |
| `results/tables/clip_verdicts.csv` | The verdict of every oracle on every clip |
| `results/report.txt`, `results/summary.json` | Every number reported for the four main voices |
| `results/gemini/` | The same for the Gemini 3.8 Flash TTS replication |
| `results/natural_listening_sheet*.csv` | The author's labels for the natural readings, made by ear |
| `results/spotcheck_sheet.csv` | The author's ear check of 60 mutant clips |
| `results/probe_rewrites.json`, `results/confident_deviations.json` | Clips in which a voice did not say the text it was given |
| `results/frozen_before_audio.txt` | Hashes of the value comparator and items, recorded before any audio existed |
| `third_party/whisper_normalizer/` | Whisper's English normaliser, copied from `openai/whisper` under its MIT licence |

## What is not included

1. **Audio.** The licence for the macOS system voices (Samantha, Daniel, Rishi) does not allow their output to be shared publicly, so no audio is released. The transcripts are enough to recompute every number in the paper. To regenerate the audio, run the synthesis step below on a Mac.
2. **Models.** Download them as described below.

## Reproduce the numbers from the released transcripts

Run every step from this folder. A CPU is enough.

1. Create the environment: `uv venv .venv --python 3.11`, then `uv pip install --python .venv/bin/python -r requirements.txt`.
2. `.venv/bin/python code/selftest.py` checks the value comparator on clean text. It should report 470 passes and 0 failures.
3. `.venv/bin/python code/score.py`, then `.venv/bin/python code/report.py`. Compare `results/report.txt` with the paper.
4. For the Gemini replication: `SCORE_VOICES=gemini SCORE_OUT=results/gemini .venv/bin/python code/score.py`, then `SCORE_VOICES=gemini SCORE_OUT=results/gemini .venv/bin/python code/report.py`.
5. `.venv/bin/python code/natural_score.py` scores the natural readings against the author's labels.
6. `.venv/bin/python code/figures.py` draws the heatmap.

## Rerun the whole pipeline

This needs macOS for the system voices.

1. Get the models:
   1. The Piper voice `en_US-lessac-medium.onnx` and its `.json`, into `models/piper/`.
   2. The Vosk model `vosk-model-small-en-us-0.15`, unzipped into `models/`.
   3. Whisper base.en, which faster-whisper downloads on first use.
2. `.venv/bin/python code/items.py` builds `data/items.csv`. Its hash should match `results/frozen_before_audio.txt`.
3. `.venv/bin/python code/synth.py` writes 2,040 clips to `audio/`.
4. `.venv/bin/python code/listen.py` writes the transcripts to `results/transcripts/`. It resumes if interrupted.
5. Score as above.

Piper samples noise, so its audio and transcripts will differ slightly from the released ones. The macOS voices were repeatable in our tests.

## Optional: Gemini voices

These steps call a paid API. They need a Gemini API key in the `GEMINI_API_KEY` environment variable, and they stop before total spending passes $1.00. Our full run cost $0.84.

1. `.venv/bin/python code/synth_gemini_batch.py` synthesises all 510 items with Gemini 3.8 Flash TTS at batch prices.
2. `LISTEN_VOICES=gemini .venv/bin/python code/listen.py` transcribes them.
3. `.venv/bin/python code/fidelity.py` checks whether each voice said the facts it was given.
4. `.venv/bin/python code/probe_models_batch.py` gives the 230 mutants to Gemini 3.8 Flash Lite TTS and Gemini 2.5 Pro TTS.

Gemini output is sampled, so a new run will not give the same audio.

## Integrity notes

1. `code/frames.py`, the value comparator, was frozen before any audio existed. Its hash is in `results/frozen_before_audio.txt`.
2. `code/frames_posthoc.py` is a later copy with three parsing fixes. It is used only for the post-hoc sensitivity analysis and is labelled as such in the paper.
3. The macOS Aman voice was dropped because it is not repeatable. The measurements are in `results/voice_determinism.json`.
4. Gemini 3.8 Flash TTS rewrote 4 of its 470 inputs. Those clips are excluded when its mutants are scored.

## Licence

Code: MIT (see `LICENSE`). Data and results: CC BY 4.0 (see `DATA_LICENSE`). The Whisper normaliser keeps its own MIT licence.

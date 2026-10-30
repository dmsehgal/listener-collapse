"""Label clips by ear in the terminal. Saves after every answer and resumes.

  natural mode: did the voice convey the printed reply's facts correctly?
  spot mode:    did the voice say the critical fact exactly as written?

Only the printed reply (or the words given to the synthesiser) is shown, never
the transcripts or oracle verdicts, so the labels stay blind to the oracles.

Keys:  c = correct / yes   w = wrong / no   u = unclear   r = replay
       n = add a note to the last answer   q = save and quit
"""
import csv
import random
import subprocess
import sys

MODES = {
    "natural": ("results/natural_listening_sheet.csv", "reference", "author_label",
                {"c": "correct", "w": "wrong", "u": "unclear"}),
    "gemini": ("results/natural_listening_sheet_gemini.csv", "reference", "author_label",
               {"c": "correct", "w": "wrong", "u": "unclear"}),
    "spot": ("results/spotcheck_sheet.csv", "words_given_to_synthesiser",
             "author_said_exactly_these_words(yes/no)", {"c": "yes", "w": "no", "u": "unclear"}),
}


def play(path, audio):
    if audio:
        subprocess.run(["afplay", path])


def save(path, fields, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "natural"
    audio = "--no-audio" not in sys.argv
    path, shown, label_col, keys = MODES[mode]
    with open(path) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    todo = [r for r in rows if not r[label_col].strip()]
    random.Random(2026).shuffle(todo)
    done = len(rows) - len(todo)
    print(f"{mode}: {len(rows)} clips, {done} already labelled, {len(todo)} to go.")
    print("Keys: c correct/yes, w wrong/no, u unclear, r replay, n note on last, q quit.\n")
    last = None
    for k, r in enumerate(todo, 1):
        print(f"[{done + k}/{len(rows)}]  {r[shown]}")
        play(r["audio"], audio)
        while True:
            a = input("  > ").strip().lower()
            if a == "r":
                play(r["audio"], audio)
            elif a == "n" and last is not None:
                last["author_note"] = input("  note for previous clip: ").strip()
                save(path, fields, rows)
            elif a == "q":
                save(path, fields, rows)
                print("Saved. Run the same command to continue.")
                return
            elif a in keys:
                r[label_col] = keys[a]
                save(path, fields, rows)
                last = r
                break
            else:
                print("  c, w, u, r, n or q")
    save(path, fields, rows)
    print(f"All {len(rows)} clips labelled and saved to {path}.")


if __name__ == "__main__":
    main()

# Annotation instructions

These are the instructions every rater saw, word for word, on an offline labelling page. Raters labelled before reading the paper, with headphones, and did not discuss the clips until they had sent their answers. Clips were shown in a random order per rater, and the voice name was hidden.

## Task 1: Did the voice get the facts right?

Used for the 40 natural replies in all five voices (200 clips).

A voice reads a short reply from a voice assistant. The printed reply is shown above the player. Judge only the critical facts: numbers, units, signs such as minus, currencies, dates, times, comparisons such as above, below, at least or at most, and negations such as not.

- **Correct**: a listener would come away with every critical fact of the printed reply, even if the wording is unusual.
- **Wrong**: a listener would come away with a different fact, or could not tell what the fact was.
- **Unclear**: you cannot decide.

Read numeric dates month first: 3/4/2026 means March 4, 2026. Words that carry no critical fact do not matter.

## Task 2: Did the voice say exactly these words?

Used for the 60 spot-check mutant clips and 24 Gemini clips (the six rewrites, five Gemini 2.5 Pro readings of the same sentences, and 13 clips that all three unprompted listeners heard as given).

This time the words given to the voice are shown. Ignore accent, speed and tone.

- **Yes**: the voice said these words.
- **No**: it said something different, such as a different number, an added or dropped word, or a changed meaning. Please write what it said in the note.
- **Unclear**: you cannot decide.

Many of these texts contain a deliberate error, such as a wrong unit or advice that is plainly unsafe. That is expected. Judge only whether the voice said the words shown.

## Task 3: Does the voice say what the printed reply says?

Used for 100 Piper and Gemini 3.8 Flash clips, one per seed: 55 mutants (five per operator), 30 correct readings and 15 meaning-preserving variants. No mutant from task 2 was reused. The clip list is `rater_packets/oracle_clips.csv` in the build, produced by `code/make_oracle_packets.py`.

A voice reads a reply from a voice assistant. The printed reply is shown above the player. Some readings say exactly what the reply means. Others change one critical fact: a number, unit, sign such as minus, currency, date, time, comparison such as above or at most, or a negation such as not. Judge only the critical facts.

- **Correct**: the voice says every critical fact of the printed reply, even if the wording differs.
- **Wrong**: the voice says a different fact, or you could not tell what the fact was.
- **Unclear**: you cannot decide.

Read numeric dates month first. Listen as a tester checking many replies would. Replay a clip only if you need to.

## How answers were used

1. **Same audio for everyone.** The macOS voices may not be redistributed, so raters rebuilt those clips on their own Mac with `say`, using the study's settings, and a script compared each file with the original by SHA-256. When a rater's Mac produced different audio (0 of 170 identical for one rater), that rater's answers on the macOS voices were left out, so every comparison uses identical audio.
2. **Agreement.** Cohen's kappa for each pair of raters and Fleiss' kappa for all raters, on clips every rater in the comparison judged correct or wrong. Unclear answers are counted separately (`code/agreement.py`).
3. **Task 3.** A mutant counts as caught when it is marked wrong. A correct reading or variant marked wrong is a false alarm. Unclear counts as neither (`code/oracle_people.py`).
4. **First author's labels.** The data sheets record every relabel with a note.

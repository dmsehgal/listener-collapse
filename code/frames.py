"""Value-level comparator: reduce a sentence to the critical facts it states.

A fact frame is a multiset of atoms: numbers (with sign and scale applied),
units, currencies, comparison operators, negations, months and a.m. or p.m.
Two texts agree when their frames are equal. Wording, filler and number format
do not matter. Works on printed text ("2.5 mg") and on spoken words
("two point five milligrams"), so the same comparator serves every listener.
"""
import re
from collections import Counter

ONES = {w: i for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
     "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
     "eighteen", "nineteen"])}
ONES["oh"] = 0
TENS = {w: 10 * i for i, w in enumerate(
    ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]) if w}
ORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
        "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
        "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
        "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
SCALE = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]

# Phrase rewrites applied before tokenising. Longest phrases first.
PHRASES = [
    (r"three quarters of an hour", " 45 minutes "),
    (r"a quarter of an hour", " 15 minutes "),
    (r"half an hour", " 30 minutes "),
    (r"an hour and a half", " 90 minutes "),
    (r"\ban hour\b", " 60 minutes "),
    (r"greater than or equal to", " CMP_GE "), (r"less than or equal to", " CMP_LE "),
    (r"no fewer than", " CMP_GE "), (r"no less than", " CMP_GE "), (r"at least", " CMP_GE "),
    (r"a minimum of", " CMP_GE "), (r"no more than", " CMP_LE "), (r"at most", " CMP_LE "),
    (r"a maximum of", " CMP_LE "), (r"\bup to\b", " CMP_LE "), (r"\bmax\.?\b", " CMP_LE "),
    (r"more than", " CMP_GT "), (r"greater than", " CMP_GT "), (r"\babove\b", " CMP_GT "),
    (r"\bover\b", " CMP_GT "), (r"\bexceeds?\b", " CMP_GT "),
    (r"less than", " CMP_LT "), (r"fewer than", " CMP_LT "), (r"\bbelow\b", " CMP_LT "),
    (r"\bunder\b", " CMP_LT "),
    (r"in the morning", " AMPM_AM "), (r"in the evening", " AMPM_PM "),
    (r"in the afternoon", " AMPM_PM "), (r"at night", " AMPM_PM "),
    (r"\ba\.\s?m\.?", " AMPM_AM "), (r"\bp\.\s?m\.?", " AMPM_PM "),
    (r"\b(?<=\d )am\b", " AMPM_AM "), (r"\b(?<=\d )pm\b", " AMPM_PM "),
    (r"\ba m\b", " AMPM_AM "), (r"\bp m\b", " AMPM_PM "),
    (r"(?<=\d)am\b", " AMPM_AM "), (r"(?<=\d)pm\b", " AMPM_PM "),
    (r"per cent", " percent "),
]

UNITS = [
    ("kilometers per hour", "kmh"), ("kilometres per hour", "kmh"), ("km/h", "kmh"), ("kph", "kmh"),
    ("miles per hour", "mph"), ("mph", "mph"), ("beats per minute", "bpm"), ("bpm", "bpm"),
    ("degrees celsius", "deg"), ("degrees fahrenheit", "degF"), ("°c", "deg"), ("°f", "degF"),
    ("celsius", "deg"), ("fahrenheit", "degF"), ("degrees", "deg"), ("degree", "deg"),
    ("milligrams", "mg"), ("milligram", "mg"), ("mg", "mg"),
    ("micrograms", "mcg"), ("microgram", "mcg"), ("mcg", "mcg"), ("µg", "mcg"),
    ("milliliters", "ml"), ("milliliter", "ml"), ("millilitres", "ml"), ("millilitre", "ml"), ("ml", "ml"),
    ("liters", "l"), ("liter", "l"), ("litres", "l"), ("litre", "l"), ("l", "l"),
    ("kilometers", "km"), ("kilometer", "km"), ("kilometres", "km"), ("kilometre", "km"), ("km", "km"),
    ("miles", "mi"), ("mile", "mi"), ("mi", "mi"),
    ("kilograms", "kg"), ("kilogram", "kg"), ("kilos", "kg"), ("kilo", "kg"), ("kg", "kg"),
    ("millimeters", "mm"), ("millimetres", "mm"), ("mm", "mm"), ("meters", "m"), ("metres", "m"),
    ("gigabytes", "gb"), ("gigabyte", "gb"), ("gb", "gb"), ("psi", "psi"),
    ("percent", "pct"), ("%", "pct"),
    ("minutes", "min"), ("minute", "min"), ("mins", "min"), ("min", "min"),
    ("hours", "hr"), ("hour", "hr"), ("hrs", "hr"), ("hr", "hr"),
    ("teaspoons", "tsp"), ("teaspoon", "tsp"), ("tsp", "tsp"),
    ("tablespoons", "tbsp"), ("tablespoon", "tbsp"), ("tbsp", "tbsp"),
    ("years", "yr"), ("year", "yr"), ("yrs", "yr"),
]
CURRENCY = {"dollars": "usd", "dollar": "usd", "bucks": "usd", "$": "usd", "usd": "usd",
            "pounds": "gbp", "pound": "gbp", "£": "gbp", "gbp": "gbp",
            "euros": "eur", "euro": "eur", "€": "eur", "eur": "eur"}
NEG_WORDS = {"not", "never"}
CONTRACTIONS = {"shouldn't": "should not", "don't": "do not", "doesn't": "does not",
                "can't": "can not", "cannot": "can not", "won't": "will not",
                "isn't": "is not", "aren't": "are not", "mustn't": "must not",
                "didn't": "did not", "wouldn't": "would not"}


def _prep(text):
    t = text.lower()
    t = t.replace("−", "-").replace("–", "-").replace("’", "'")
    t = t.replace("≥", " CMP_GE ").replace(">=", " CMP_GE ").replace("≤", " CMP_LE ")
    t = t.replace("<=", " CMP_LE ").replace(">", " CMP_GT ").replace("<", " CMP_LT ")
    for k, v in CONTRACTIONS.items():
        t = t.replace(k, v)
    # Clock times: 7:30, 7.30 pm, 8:00.
    t = re.sub(r"\b(\d{1,2})[:.]00(?=\s*(?:a\.?\s?m|p\.?\s?m|am|pm)\b)", r"\1", t)
    t = re.sub(r"\b(\d{1,2})[:.](\d{2})(?=\s*(?:a\.?\s?m|p\.?\s?m|am|pm)\b)", r"\1 \2", t)
    t = re.sub(r"\b(\d{1,2}):00\b", r"\1", t)
    t = re.sub(r"\b(\d{1,2}):(\d{2})\b", r"\1 \2", t)
    # Numeric dates, read month first.
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
               lambda m: f" {MONTHS[int(m.group(1)) - 1] if 1 <= int(m.group(1)) <= 12 else m.group(1)} {int(m.group(2))} {m.group(3)} ", t)
    t = re.sub(r"\b1/2\b", " 0.5 ", t)
    t = re.sub(r"\b1/4\b", " 0.25 ", t)
    t = re.sub(r"\b3/4\b", " 0.75 ", t)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    # Money with letter scales: $3.5b, $1.2m, 3.5bn.
    t = re.sub(r"(\d+(?:\.\d+)?)\s?(?:bn|b)\b", r"\1 billion", t)
    t = re.sub(r"(?<=\$)(\d+(?:\.\d+)?)\s?m\b", r"\1 million", t)
    for pat, rep in PHRASES:
        t = re.sub(pat, rep, t)
    # Minus sign directly before a number at word start, not a range like 2-8.
    t = re.sub(r"(^|[\s(~])-\s?(?=\$?\d)", r"\1 minus ", t)
    t = re.sub(r"(?<=\d)-(?=\d)", " to ", t)
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    t = re.sub(r"([$£€])", r" \1 ", t)
    t = re.sub(r"(?<=\d)(?=[a-z%°])", " ", t)
    t = re.sub(r"(?<=[a-z])(?=\d)", " ", t)
    t = t.replace("%", " % ")
    t = re.sub(r"[^\w\s$£€%°/._-]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    return t.lower().split()


def _match_unit(tokens, i):
    for phrase, canon in UNITS:
        p = phrase.split()
        if tokens[i:i + len(p)] == p:
            return canon, len(p)
    return None, 0


def frame(text):
    toks = _prep(text)
    atoms = []
    i = 0
    sign = 1
    cur = None          # number being built from words
    dec = None          # digits after "point"
    pending_cur = None  # currency symbol seen before the number

    def flush():
        nonlocal cur, dec, sign
        if cur is None:
            return None
        v = cur
        if dec:
            v = float(f"{int(cur)}.{dec}")
        v = sign * v
        cur, dec, sign = None, None, 1
        return v

    nums = []  # list of [value, unit]

    def emit(v):
        nums.append([v, None])

    while i < len(toks):
        w = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if w in ("minus", "negative"):
            v = flush()
            if v is not None:
                emit(v)
            sign = -1
            i += 1
            continue
        if re.fullmatch(r"\d+(\.\d+)?", w):
            v = flush()
            if v is not None:
                emit(v)
            if len(w) >= 4 and w.startswith("0"):
                for ch in w:
                    emit(sign * int(ch))
                sign = 1
            else:
                cur = float(w) if "." in w else int(w)
                v = flush()
                emit(v)
            i += 1
            continue
        if w in ONES or w in TENS:
            val = ONES.get(w, TENS.get(w))
            if dec is not None:
                if w in ONES and ONES[w] < 10:
                    dec += str(ONES[w])
                    i += 1
                    continue
                emit(flush())
            if cur is None:
                cur = val
            elif w in TENS:
                if cur % 100 != 0:
                    emit(flush())
                    cur = val
                else:
                    cur += val
            else:
                if val >= 10 or cur == 0 or cur % 10 != 0 or 10 <= cur % 100 <= 19:
                    emit(flush())
                    cur = val
                else:
                    cur += val
            i += 1
            continue
        if w in ORDS:
            val = ORDS[w]
            if cur is not None and cur % 100 in (20, 30) and val < 10:
                cur += val
            else:
                if cur is not None:
                    emit(flush())
                cur = val
            emit(flush())
            i += 1
            continue
        if w == "point" and cur is not None and dec is None:
            dec = ""
            i += 1
            continue
        if w in SCALE:
            if cur is None and nums and nums[-1][1] is None:
                nums[-1][0] = nums[-1][0] * SCALE[w]
            elif cur is not None:
                if dec:
                    cur = float(f"{int(cur)}.{dec}")
                    dec = None
                if SCALE[w] == 100:
                    cur = cur * 100
                else:
                    emit(flush() * SCALE[w])
            i += 1
            continue
        if w == "and" and nxt == "a" and i + 2 < len(toks) and toks[i + 2] == "half":
            if cur is not None:
                cur = cur + 0.5
            elif nums:
                nums[-1][0] = nums[-1][0] + 0.5
            i += 3
            continue
        if w == "half" and nxt == "a":
            emit(flush()) if cur is not None else None
            emit(0.5)
            i += 2
            continue
        if w == "half" and cur == 1:
            cur = 0.5
            i += 1
            continue
        # Anything else ends a number in progress.
        if cur is not None:
            emit(flush())
        if w in CURRENCY:
            atoms.append(("cur", CURRENCY[w]))
            i += 1
            continue
        unit, n = _match_unit(toks, i)
        if unit and nums:
            if unit == "hr":
                nums[-1][0] = nums[-1][0] * 60
                unit = "min"
            nums[-1][1] = unit
            atoms.append(("unit", unit))
            i += n
            continue
        if w.startswith("cmp_"):
            atoms.append(("cmp", w[4:]))
        elif w.startswith("ampm_"):
            atoms.append(("ampm", w[5:]))
        elif w in NEG_WORDS:
            atoms.append(("neg", 1))
        elif w in MONTHS:
            atoms.append(("month", MONTHS.index(w) + 1))
        i += 1
    if cur is not None:
        emit(flush())
    for v, _ in nums:
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        atoms.append(("num", round(v, 6) if isinstance(v, float) else v))
    return Counter(atoms)


def agree(reference, hypothesis):
    return frame(reference) == frame(hypothesis)


if __name__ == "__main__":
    import sys
    for line in sys.argv[1:]:
        print(line, "->", dict(frame(line)))

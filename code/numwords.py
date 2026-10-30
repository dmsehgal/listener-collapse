"""Spell numbers the way a speech synthesiser should say them."""

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]
SCALES = [(10**9, "billion"), (10**6, "million"), (1000, "thousand")]
ORD_SPECIAL = {"one": "first", "two": "second", "three": "third", "five": "fifth",
               "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Teen and tens pairs that sound alike, used by the TEENTY operator.
TEENTY = {13: 30, 14: 40, 15: 50, 16: 60, 17: 70, 18: 80, 19: 90}
TEENTY.update({v: k for k, v in list(TEENTY.items())})


def int_words(n):
    if n < 0:
        return "minus " + int_words(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t] + ("" if o == 0 else " " + ONES[o])
    if n < 1000:
        h, r = divmod(n, 100)
        return ONES[h] + " hundred" + ("" if r == 0 else " " + int_words(r))
    for div, name in SCALES:
        if n >= div:
            q, r = divmod(n, div)
            return int_words(q) + " " + name + ("" if r == 0 else " " + int_words(r))
    raise ValueError(n)


def dec_words(s):
    """'2.5' -> 'two point five'. Digits after the point are read one by one."""
    s = str(s)
    if "." in s:
        i, f = s.split(".")
        return int_words(int(i)) + " point " + " ".join(ONES[int(c)] for c in f)
    return int_words(int(s))


def half_words(s):
    """'2.5' -> 'two and a half'. Only for values ending in .5."""
    i = int(float(s))
    return "half a" if i == 0 else int_words(i) + " and a half"


def ord_words(n):
    w = int_words(n).split()
    last = w[-1]
    if last in ORD_SPECIAL:
        w[-1] = ORD_SPECIAL[last]
    elif last.endswith("y"):
        w[-1] = last[:-1] + "ieth"
    else:
        w[-1] = last + "th"
    return " ".join(w)

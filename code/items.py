"""Build the seed sentences, their spoken forms, mutants and equivalent variants.

Every seed is an assistant reply that carries one critical fact. For each seed we
write the text a model would print (the reference), the correct spoken form, one
or two meaning changing mutants of the spoken form, and one meaning preserving
variant. Output: data/items.csv. Run from the project root.
"""
import csv
import random

from numwords import (MONTHS, TEENTY, dec_words, half_words, int_words, ord_words)

LEADS = ["", "Sure. ", "Okay. ", "Good question. ", "Here is what I found. ",
         "Just to confirm, ", "Based on your plan, "]
TAILS = ["", " Let me know if you need anything else.",
         " I can set a reminder if you like.", " Is there anything else I can help with?"]


def cap(s):
    return s[:1].upper() + s[1:]


def seed(cat, written, spoken, mutants, equivs):
    return dict(cat=cat, written=written, spoken=spoken, mutants=mutants, equivs=equivs)


def teenty_or(n, fallback):
    return TEENTY.get(n, fallback)


# 1. Medication dose. Operators: DEC (drop the decimal point), UNIT.
def doses():
    rows = [("2.5", "mg", "twice a day"), ("0.5", "mg", "at bedtime"),
            ("1.5", "mcg", "once a day"), ("7.5", "mL", "every 8 hours"),
            ("12.5", "mg", "once a day"), ("5.5", "mL", "twice a day"),
            ("3.5", "mcg", "every 12 hours"), ("0.5", "mL", "every 8 hours"),
            ("1.5", "mg", "at bedtime"), ("2.5", "mL", "once a day")]
    unit_sp = {"mg": "milligrams", "mcg": "micrograms", "mL": "milliliters"}
    unit_sg = {"mg": "milligram", "mcg": "microgram", "mL": "milliliter"}
    unit_mut = {"mg": "micrograms", "mcg": "milligrams", "mL": "liters"}
    freq_sp = {"every 8 hours": "every eight hours", "every 12 hours": "every twelve hours"}
    verbs = ["Take", "Give", "Take", "Use", "Take", "Give", "Take", "Use", "Take", "Give"]
    out = []
    for (d, u, f), v in zip(rows, verbs):
        fs = freq_sp.get(f, f)
        w = f"{v} {d} {u} {f}."
        s = f"{v} {dec_words(d)} {unit_sp[u]} {fs}."
        dec = int_words(int(round(float(d) * 10)))
        m = [("DEC", f"{v} {dec} {unit_sp[u]} {fs}."),
             ("UNIT", f"{v} {dec_words(d)} {unit_mut[u]} {fs}.")]
        hw = half_words(d)
        eq = f"{v} {hw} {unit_sg[u]} {fs}." if hw == "half a" else f"{v} {hw} {unit_sp[u]} {fs}."
        out.append(seed("dose", w, s, m, [("EQ_HALF", eq)]))
    return out


# 2. Small money amounts. Operators: TEENTY, CUR.
def fees():
    ctx = ["The transfer fee is", "Your copay is", "The late fee is", "The ticket costs",
           "Shipping costs", "The deposit is", "The cancellation fee is",
           "Your monthly charge is", "The parking fine is", "The booking fee is"]
    amounts = [14, 40, 15, 50, 16, 60, 17, 70, 18, 80]
    out = []
    for c, a in zip(ctx, amounts):
        w = f"{c} ${a}."
        s = f"{c} {int_words(a)} dollars."
        m = [("TEENTY", f"{c} {int_words(TEENTY[a])} dollars."),
             ("CUR", f"{c} {int_words(a)} pounds.")]
        out.append(seed("fee", w, s, m, [("EQ_PHRASE", f"{c} {int_words(a)} dollars in total.")]))
    return out


# 3. Large money amounts. Operators: SCALE, DEC.
def bigmoney():
    ctx = ["Revenue last quarter was", "The project budget is", "The company raised",
           "Annual sales reached", "The contract is worth", "The city spent",
           "Total donations came to", "The merger is valued at", "Operating costs were",
           "The fund manages"]
    vals = [("3.5", "billion"), ("2.5", "million"), ("1.5", "billion"), ("4.5", "million"),
            ("7.5", "billion"), ("6.5", "million"), ("8.5", "billion"), ("9.5", "million"),
            ("2.5", "billion"), ("5.5", "million")]
    flip = {"billion": "million", "million": "billion"}
    out = []
    for c, (v, sc) in zip(ctx, vals):
        w = f"{c} ${v} {sc}."
        s = f"{c} {dec_words(v)} {sc} dollars."
        dec = int_words(int(round(float(v) * 10)))
        m = [("SCALE", f"{c} {dec_words(v)} {flip[sc]} dollars."),
             ("DEC", f"{c} {dec} {sc} dollars.")]
        out.append(seed("bigmoney", w, s, m, [("EQ_HALF", f"{c} {half_words(v)} {sc} dollars.")]))
    return out


# 4. Temperatures below zero. Operators: SIGN (drop minus), NUM.
def temps():
    ctx = ["Tonight's low will be", "Tomorrow morning it will be", "The freezer should be set to",
           "Overnight it will drop to", "With wind chill it will feel like", "Expect lows of",
           "The forecast low is", "At dawn it will be", "The temperature will fall to",
           "By midnight it will reach"]
    vals = [-5, -3, -18, -12, -15, -2, -7, -10, -4, -14]
    out = []
    for c, t in zip(ctx, vals):
        mag = -t
        w = f"{c} -{mag}°C."
        s = f"{c} minus {int_words(mag)} degrees Celsius."
        m = [("SIGN", f"{c} {int_words(mag)} degrees Celsius."),
             ("NUM", f"{c} minus {int_words(mag + 2)} degrees Celsius.")]
        out.append(seed("temp", w, s, m, [("EQ_NEG", f"{c} negative {int_words(mag)} degrees Celsius.")]))
    return out


# 5. Dates. Operators: SWAP (day and month order), NUM (day plus ten).
def dates():
    ctx = ["Your appointment is on", "The payment is due on", "Your flight departs on",
           "The package will arrive on", "Your lease ends on", "The meeting is scheduled for",
           "Your prescription expires on", "The event takes place on", "Your trial ends on",
           "The deadline is"]
    vals = [(3, 4), (5, 2), (6, 9), (8, 3), (10, 7), (11, 5), (1, 6), (9, 12), (4, 11), (12, 8)]
    out = []
    for c, (mo, d) in zip(ctx, vals):
        w = f"{c} {MONTHS[mo - 1]} {d}."
        s = f"{c} {MONTHS[mo - 1]} {ord_words(d)}."
        m = [("SWAP", f"{c} {MONTHS[d - 1]} {ord_words(mo)}."),
             ("NUM", f"{c} {MONTHS[mo - 1]} {ord_words(d + 10)}.")]
        out.append(seed("date", w, s, m, [("EQ_ORDER", f"{c} the {ord_words(d)} of {MONTHS[mo - 1]}.")]))
    return out


# 6. Clock times. Operators: AMPM, NUM (hour plus one).
def times():
    ctx = ["Your train leaves at", "The pharmacy opens at", "Check-in closes at",
           "Your call is booked for", "The store closes at", "Boarding starts at",
           "Your reminder is set for", "The class begins at", "Pickup is at", "The webinar starts at"]
    vals = [(7, 30, "pm"), (9, 15, "am"), (6, 45, "pm"), (10, 30, "am"), (8, 0, "pm"),
            (11, 15, "am"), (5, 30, "pm"), (4, 45, "pm"), (8, 30, "am"), (3, 15, "pm")]
    out = []
    for c, (h, mi, ap) in zip(ctx, vals):
        wt = f"{h}:{mi:02d} {ap}"
        def sp(hh, ampm):
            mins = "" if mi == 0 else " " + int_words(mi)
            return f"{int_words(hh)}{mins} {'a.m.' if ampm == 'am' else 'p.m.'}"
        other = "am" if ap == "pm" else "pm"
        if ap == "am":
            part = "in the morning"
        elif h >= 5:
            part = "in the evening"
        else:
            part = "in the afternoon"
        mins = "" if mi == 0 else " " + int_words(mi)
        out.append(seed("time", f"{c} {wt}.", f"{c} {sp(h, ap)}.",
                        [("AMPM", f"{c} {sp(h, other)}."), ("NUM", f"{c} {sp(h + 1, ap)}.")],
                        [("EQ_PART", f"{c} {int_words(h)}{mins} {part}.")]))
    return out


# 7. Negated instructions. Operator: NEG (drop the negation).
def negations():
    acts = ["drive after taking this medicine", "take this with alcohol",
            "leave the oven unattended", "share this code with anyone",
            "charge the battery overnight", "mix bleach with ammonia",
            "give this to children under six", "stop the course early",
            "store the vaccine in the freezer", "reply to that message"]
    out = []
    for a in acts:
        a_sp = a.replace("under six", "under six")
        out.append(seed("neg", f"You should not {a}.", f"You should not {a_sp}.",
                        [("NEG", f"You should {a_sp}.")],
                        [("EQ_CONTR", f"You shouldn't {a_sp}.")]))
    return out


# 8. Thresholds. Operators: CMP (above and below), TEENTY.
def thresholds():
    rows = [("Keep your blood sugar", "above", 70, ""),
            ("Keep the room humidity", "below", 40, " percent"),
            ("Call us if your heart rate stays", "above", 90, " beats per minute"),
            ("Keep your speed", "below", 15, " miles per hour"),
            ("Refill the tank when it falls", "below", 18, " liters"),
            ("Keep the water temperature", "above", 60, " degrees Celsius"),
            ("Sell if the share price drops", "below", 14, " dollars"),
            ("Alert me when the reading goes", "above", 50, ""),
            ("Keep the battery", "above", 16, " percent"),
            ("Slow down if the wind is", "above", 80, " kilometers per hour")]
    wunit = {"": "", " percent": "%", " beats per minute": " bpm", " miles per hour": " mph",
             " liters": " L", " degrees Celsius": "°C", " dollars": "", " kilometers per hour": " km/h"}
    flip = {"above": "below", "below": "above"}
    syn = {"above": "over", "below": "under"}
    out = []
    for c, d, v, u in rows:
        wv = f"${v}" if u == " dollars" else f"{v}{wunit[u]}"
        w = f"{c} {d} {wv}."
        s = f"{c} {d} {int_words(v)}{u}."
        m = [("CMP", f"{c} {flip[d]} {int_words(v)}{u}."),
             ("TEENTY", f"{c} {d} {int_words(TEENTY[v])}{u}.")]
        out.append(seed("threshold", w, s, m, [("EQ_SYN", f"{c} {syn[d]} {int_words(v)}{u}.")]))
    return out


# 9. Limits, half written with symbols. Operators: CMP (at most and at least), NUM.
def limits():
    rows = [("You can bring", "at most", 2, "bags", "words"),
            ("Your password needs", "at least", 8, "characters", "symbol"),
            ("Each guest may order", "at most", 3, "drinks", "words"),
            ("The team needs", "at least", 6, "players", "symbol"),
            ("You may take", "at most", 4, "tablets in a day", "symbol"),
            ("The form requires", "at least", 12, "digits", "words"),
            ("Each account allows", "at most", 5, "devices", "symbol"),
            ("The plan includes", "at least", 10, "gigabytes", "words"),
            ("The ride admits", "at most", 1, "child per adult", "symbol"),
            ("The class requires", "at least", 7, "students", "words")]
    flip = {"at most": "at least", "at least": "at most"}
    sym = {"at most": "≤", "at least": "≥"}
    eqp = {"at most": "no more than", "at least": "no fewer than"}
    out = []
    for c, d, v, noun, style in rows:
        w = f"{c} {sym[d] if style == 'symbol' else d} {v} {noun}."
        s = f"{c} {d} {int_words(v)} {noun}."
        m = [("CMP", f"{c} {flip[d]} {int_words(v)} {noun}."),
             ("NUM", f"{c} {d} {int_words(v + 1)} {noun}.")]
        out.append(seed("limit", w, s, m, [("EQ_SYN", f"{c} {eqp[d]} {int_words(v)} {noun}.")]))
    return out


# 10. Percentages. Operators: TEENTY, NUM (plus five).
def percents():
    ctx = ["About {} of patients improved.", "Roughly {} of users never log in.",
           "Your score was {}.", "The chance of rain is {}.", "Prices rose by {}.",
           "Around {} of the budget is unspent.", "The battery is at {}.",
           "Turnout reached {}.", "The discount is {}.", "Only {} of tickets remain."]
    vals = [40, 15, 60, 17, 80, 13, 30, 19, 50, 70]
    out = []
    for c, v in zip(ctx, vals):
        w = c.format(f"{v}%")
        s = c.format(f"{int_words(v)} percent")
        m = [("TEENTY", c.format(f"{int_words(TEENTY[v])} percent")),
             ("NUM", c.format(f"{int_words(v + 5)} percent"))]
        out.append(seed("percent", w, s, m, [("EQ_PERCENT", c.format(f"{int_words(v)} per cent"))]))
    return out


# 11. Distances. Operators: UNIT (miles and kilometers), NUM.
def distances():
    rows = [("Turn left in {}.", "In {}, turn left.", 2, "mi"),
            ("The station is {} away.", "The station is about {} from here.", 3, "km"),
            ("The nearest charger is {} north.", "Head north for {} to the nearest charger.", 5, "mi"),
            ("Your hotel is {} from the airport.", "From the airport, your hotel is {}.", 4, "km"),
            ("The trail is {} long.", "The whole trail runs {}.", 6, "mi"),
            ("Exit the highway in {}.", "In {}, exit the highway.", 8, "km"),
            ("The beach is {} from here.", "From here, the beach is {}.", 1, "mi"),
            ("The detour adds {}.", "The detour will add {}.", 7, "km"),
            ("Your run today was {}.", "Today you ran {}.", 9, "mi"),
            ("The bridge is {} ahead.", "In {}, you reach the bridge.", 12, "km")]
    sp = {"mi": "miles", "km": "kilometers"}
    sg = {"mi": "mile", "km": "kilometer"}
    other = {"mi": "kilometers", "km": "miles"}
    out = []
    for c, para, v, u in rows:
        unit = sg[u] if v == 1 else sp[u]
        oth = other[u][:-1] if v == 1 else other[u]
        w = c.format(f"{v} {u}")
        s = c.format(f"{int_words(v)} {unit}")
        m = [("UNIT", c.format(f"{int_words(v)} {oth}")),
             ("NUM", c.format(f"{int_words(v + 2)} {sp[u]}"))]
        out.append(seed("distance", w, s, m, [("EQ_REORDER", para.format(f"{int_words(v)} {unit}"))]))
    return out


# 12. Durations. Operators: UNIT (minutes to hours), TEENTY or NUM.
def durations():
    ctx = ["Bake for {}.", "Let it rest for {}.", "The battery lasts {}.", "Your parking expires in {}.",
           "Charge it for {}.", "The drive takes {}.", "Soak the beans for {}.",
           "Your session times out after {}.", "Wait {} before swimming.", "The tour lasts {}."]
    vals = [45, 30, 90, 15, 20, 40, 60, 25, 50, 120]
    idiom = {45: "three quarters of an hour", 30: "half an hour", 90: "an hour and a half",
             15: "a quarter of an hour", 60: "an hour", 120: "two hours"}
    out = []
    for c, v in zip(ctx, vals):
        wv = "2 hours" if v == 120 else f"{v} minutes"
        sv = "two hours" if v == 120 else f"{int_words(v)} minutes"
        w = c.format(wv)
        s = c.format(sv)
        if v == 120:
            m = [("UNIT", c.format("two minutes")), ("NUM", c.format("three hours"))]
        else:
            alt = TEENTY.get(v, v + 5)
            op = "TEENTY" if v in TEENTY else "NUM"
            m = [("UNIT", c.format(f"{int_words(v)} hours")), (op, c.format(f"{int_words(alt)} minutes"))]
        eq = idiom.get(v)
        if eq:
            out.append(seed("duration", w, s, m, [("EQ_IDIOM", c.format(eq))]))
        else:
            out.append(seed("duration", w, s, m, [("EQ_PHRASE", c.format(f"{int_words(v)} minutes in total"))]))
    return out


# Natural set: written text only, read by each synthesiser with its own text handling.
NATURAL = [
    "Take 2.5 mg twice a day.", "It will be -5°C tonight.", "Revenue was $3.5B last quarter.",
    "Your appointment is on 3/4/2026.", "The flight leaves at 7:30 pm.", "Choose x ≥ 5 and y < 3.",
    "It costs ~$40.", "Henry VIII had six wives.", "Mt. Everest is 8,849 m tall.",
    "Add 1/2 cup of sugar.", "The bag weighs 10 kg.", "Use a 5 mm drill bit.",
    "Sales rose 3% in Q2.", "Store it between 2-8°C.", "The dose is 10-15 mg.",
    "Call 1-800-555-0199.", "It's open 24/7.", "You are No. 5 in the queue.",
    "Your balance is -$42.17.", "Mix at a ratio of 3:1.", "Turn left in 0.5 mi.",
    "Save 20% on orders over £50.", "The meeting is at 12:00 pm.", "Take 500 mcg daily.",
    "The speed limit is 65 mph.", "Max 2 bags per person.", "Room 4B is on the 3rd floor.",
    "Pay €1,250.50 by Friday.", "Your temperature is 98.6°F.", "Invest $1.2M over 5 yrs.",
    "WWII ended in 1945.", "The file is 2.5 GB.", "Use 1 tsp of salt and 2 tbsp of oil.",
    "Your code is 0471.", "Approx. 1 in 4 adults.", "The deadline is 05/06/2027.",
    "Boil for 3-4 min.", "Pressure must stay ≤ 120 psi.", "Dr. Lee sees patients on Wed.",
    "The 1990s saw rapid growth.",
]


def main():
    rng = random.Random(2026)
    seeds = []
    for fn in [doses, fees, bigmoney, temps, dates, times, negations, thresholds, limits,
               percents, distances, durations]:
        seeds.extend(fn())
    rows = []
    for i, sd in enumerate(seeds):
        sid = f"S{i:03d}"
        lead = rng.choice(LEADS)
        tail = rng.choice(TAILS)

        def wrap(t, lead=lead):
            t = t if not lead or lead.endswith(". ") else t[:1].lower() + t[1:]
            return cap(lead + t + tail).replace("m..", "m.")
        rows.append(dict(item=f"{sid}_C", seed=sid, cat=sd["cat"], kind="correct", op="",
                         reference=wrap(sd["written"]), spoken=wrap(sd["spoken"])))
        for op, m in sd["mutants"]:
            rows.append(dict(item=f"{sid}_M_{op}", seed=sid, cat=sd["cat"], kind="mutant", op=op,
                             reference=wrap(sd["written"]), spoken=wrap(m)))
        for op, e in sd["equivs"]:
            rows.append(dict(item=f"{sid}_E_{op}", seed=sid, cat=sd["cat"], kind="equivalent", op=op,
                             reference=wrap(sd["written"]), spoken=wrap(e)))
    for j, t in enumerate(NATURAL):
        rows.append(dict(item=f"N{j:03d}", seed=f"N{j:03d}", cat="natural", kind="natural", op="",
                         reference=t, spoken=t))
    with open("data/items.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"seeds={len(seeds)} rows={len(rows)} by kind={kinds}")


if __name__ == "__main__":
    main()

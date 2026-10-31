"""Draw the result figures from results/summary.json into paper/figures/*.pdf."""
import csv
import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

INK, MUTED, GRID = "#1C2536", "#52514e", "#e4e4e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RAMP = LinearSegmentedColormap.from_list("blue", ["#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])

plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})

S = json.load(open("results/summary.json"))
O = S["oracles"]
LABEL = {"ideal": "ideal", "whisper": "Whisper", "whisper_anchored": "Whisper, prompted",
         "whisper_spelled": "Whisper, spelled", "vosk": "Vosk"}
OPS = ["DEC", "UNIT", "TEENTY", "CUR", "SCALE", "SIGN", "NUM", "SWAP", "AMPM", "NEG", "CMP"]


def rate(name, group):
    g = O[name].get(group)
    return g["rate"] if g else float("nan")


def fa(name):
    c, e = O[name]["correct"], O[name]["equivalent"]
    return (c["k"] + e["k"]) / (c["n"] + e["n"])


def hollow_shares():
    """Per oracle and operator: the share of caught mutants whose own correct reading,
    in the same voice, the oracle also failed. Such a catch separates nothing."""
    rows = list(csv.DictReader(open("results/tables/clip_verdicts.csv")))
    idx = {(r["listener"], r["item"], r["voice"]): r for r in rows}
    fails = lambda r, comp: float(r["wer"]) > 0.10 + 1e-9 if comp == "wer@0.10" else r["value_pass"] == "False"
    caught, hollow = defaultdict(int), defaultdict(int)
    for r in rows:
        if r["kind"] != "mutant":
            continue
        for comp in ("wer@0.10", "value"):
            if fails(r, comp):
                key = (f"{r['listener']}|{comp}", r["op"])
                caught[key] += 1
                hollow[key] += fails(idx[(r["listener"], f"{r['seed']}_C", r["voice"])], comp)
    return {k: hollow[k] / caught[k] for k in caught}


def heatmap():
    cols = [("ideal|wer@0.10", "ideal\nWER"), ("whisper|wer@0.10", "Whisper\nWER"),
            ("whisper_anchored|wer@0.10", "Whisper\nprompted\nWER"), ("whisper|value", "Whisper\nvalue"),
            ("whisper_anchored|value", "Whisper\nprompted\nvalue"), ("whisper_spelled|value", "Whisper\nspelled\nvalue"),
            ("vosk|value", "Vosk\nvalue")]
    cols = [c for c in cols if c[0] in O]
    data = [[rate(c, f"mutant|op={op}") for c, _ in cols] for op in OPS]
    fig, ax = plt.subplots(figsize=(4.8, 3.3))
    ax.imshow(data, cmap=RAMP, vmin=0, vmax=1, aspect="auto")
    hollow = hollow_shares()
    for i, op in enumerate(OPS):
        for j, (c, _) in enumerate(cols):
            if hollow.get((c, op), 0) >= 0.5:
                ax.add_patch(plt.Rectangle((j - 0.44, i - 0.42), 0.88, 0.84, fill=False, edgecolor=ORANGE, linewidth=1.6))
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > 0.6 else INK)
    ax.set_xticks(range(len(cols)), [c[1] for c in cols], fontsize=6.5)
    ax.set_yticks(range(len(OPS)), OPS, fontsize=7)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, len(cols))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(OPS))], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", length=0)
    ax.xaxis.tick_top()
    fig.tight_layout()
    fig.savefig("paper/figures/heatmap.pdf")


def tradeoff():
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    pts = []
    for lis in LABEL:
        for comp, color, marker in (("wer@0.10", BLUE, "o"), ("value", ORANGE, "s")):
            name = f"{lis}|{comp}"
            if name in O:
                pts.append((fa(name), rate(name, "mutant"), color, marker, LABEL[lis]))
    for name, lab in (("any(whisper,vosk)|value", "Whisper or Vosk"),
                      ("any(all four)|value", "any of four")):
        if name in O:
            pts.append((fa(name), rate(name, "mutant"), AQUA, "D", lab))
    for x, y, c, m, lab in pts:
        ax.scatter(100 * x, 100 * y, s=36, color=c, marker=m, edgecolor="white", linewidth=1.2, zorder=3)
        ax.annotate(lab, (100 * x, 100 * y), xytext=(5, 2), textcoords="offset points", fontsize=6.5, color=INK)
    ax.set_xlabel("false alarm rate on correct and equivalent readings (%)")
    ax.set_ylabel("mutation score (%)")
    ax.set_xlim(-3, 100)
    ax.set_ylim(0, 105)
    ax.grid(color=GRID, linewidth=0.6)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], color=BLUE, marker="o", ls="", label="WER at most 0.10"),
         Line2D([], [], color=ORANGE, marker="s", ls="", label="value comparator"),
         Line2D([], [], color=AQUA, marker="D", ls="", label="any-fail ensemble")]
    ax.legend(handles=h, loc="lower right", frameon=False, fontsize=6.5)
    fig.tight_layout()
    fig.savefig("paper/figures/tradeoff.pdf")


def tau_curve():
    taus = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    for lis, ls in (("ideal", "--"), ("whisper", "-")):
        if f"{lis}|wer@0.00" not in O:
            continue
        ms = [100 * rate(f"{lis}|wer@{t:.2f}", "mutant") for t in taus]
        fr = [100 * fa(f"{lis}|wer@{t:.2f}") for t in taus]
        ax.plot(taus, ms, ls, color=BLUE, marker="o", markersize=4, linewidth=1.6)
        ax.plot(taus, fr, ls, color=ORANGE, marker="s", markersize=4, linewidth=1.6)
        ax.lines[-2].set_label(f"mutation score, {LABEL[lis]}")
        ax.lines[-1].set_label(f"false alarms, {LABEL[lis]}")
    ax.set_xlabel("WER threshold $\\tau$")
    ax.set_ylabel("rate (%)")
    ax.set_xlim(-0.01, 0.31)
    ax.legend(frameon=False, fontsize=6.5, loc="upper right")
    ax.set_ylim(0, 105)
    ax.grid(color=GRID, linewidth=0.6)
    fig.tight_layout()
    fig.savefig("paper/figures/tau.pdf")


if __name__ == "__main__":
    heatmap()
    tau_curve()
    print("figures written")

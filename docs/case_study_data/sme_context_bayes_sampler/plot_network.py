#!/usr/bin/env python3
"""Draw the structure of net_local_02 for the case study.

Nodes are placed in columns by distance to the nearest exit node (entry rung on
the left, exits on the right). Edges are parent -> child.

Usage:
    python plot_network.py [--out network_structure.png]
"""
import argparse
import json
from collections import deque
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
NETWORK = HERE.parents[2] / "tools" / "bayes_sampler" / "nets" / "net_local_02.json"

RUNG_LABELS = {
    4: "Entry rung\n(1–9)",
    3: "Mid-ladder rung\n(10–13)",
    2: "Rung 2\n(14–22)",
    1: "Near-exit rung\n(23–32)",
    0: "Exits\n(33, 34)",
}
RUNG_COLORS = {
    4: "#9ecae1",
    3: "#f28e2b",
    2: "#c7c7c7",
    1: "#8c6bb1",
    0: "#d62728",
}


def load_parents(path):
    net = json.loads(Path(path).read_text())
    parents = {str(node["id"]): [] for node in net["nodes"]}
    for edge in net["edges"]:
        parents[str(edge["target"]["id"])].append(str(edge["source"]["id"]))
    return parents


def distance_to_exit(parents):
    children = {n: [] for n in parents}
    for n, ps in parents.items():
        for p in ps:
            children[p].append(n)
    exits = [n for n, c in children.items() if not c]
    dist = {n: 0 for n in exits}
    q = deque(exits)
    while q:
        n = q.popleft()
        for p in parents[n]:
            if p not in dist:
                dist[p] = dist[n] + 1
                q.append(p)
    return dist, exits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", default=str(NETWORK))
    ap.add_argument("--out", default=str(HERE / "network_structure.png"))
    args = ap.parse_args()

    parents = load_parents(args.network)
    dist, exits = distance_to_exit(parents)
    entries = {n for n, ps in parents.items() if not ps}
    max_d = max(dist.values())

    # Position: column by distance, rows spread evenly and centred
    pos = {}
    for d in range(max_d + 1):
        rung = sorted((n for n in dist if dist[n] == d), key=int)
        for i, n in enumerate(rung):
            pos[n] = (max_d - d, (len(rung) - 1) / 2 - i)

    fig, ax = plt.subplots(figsize=(11, 6.5))

    for child, ps in parents.items():
        for p in ps:
            bypass = p in entries and dist[p] < max_d
            ax.add_patch(FancyArrowPatch(
                pos[p], pos[child],
                arrowstyle="-|>", mutation_scale=7,
                shrinkA=11, shrinkB=11,
                color="#d62728" if bypass else "#888888",
                alpha=0.9 if bypass else 0.22,
                lw=1.6 if bypass else 0.7,
                linestyle="--" if bypass else "-",
                zorder=1,
            ))

    for n, (x, y) in pos.items():
        d = dist[n]
        off_rung_entry = n in entries and d < max_d
        ax.scatter(x, y, s=420, color=RUNG_COLORS[d], zorder=2,
                   edgecolors="black" if off_rung_entry else "white",
                   linewidths=2.0 if off_rung_entry else 1.0)
        ax.text(x, y, n, ha="center", va="center", fontsize=8,
                color="white" if d in (0, 1) else "black",
                fontweight="bold", zorder=3)

    top = max(y for _, y in pos.values()) + 1.0
    for d, label in RUNG_LABELS.items():
        ax.text(max_d - d, top, label, ha="center", va="bottom", fontsize=9)

    n_edges = sum(len(ps) for ps in parents.values())
    ax.set_title(f"net_local_02: {len(parents)} nodes, {n_edges} directed edges "
                 "(attack flows left to right)", fontsize=11)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", markersize=11, color=RUNG_COLORS[1],
               markeredgecolor="black", markeredgewidth=2,
               label="Entry node outside the entry rung (32)"),
        Line2D([], [], color="#d62728", ls="--", lw=1.6,
               label="Edge from node 32 (bypasses the mid-ladder rung)"),
    ], loc="lower center", bbox_to_anchor=(0.5, -0.1), ncol=2,
        frameon=False, fontsize=9)

    ax.set_xlim(-0.6, max_d + 0.6)
    ax.set_ylim(min(y for _, y in pos.values()) - 0.8, top + 1.0)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

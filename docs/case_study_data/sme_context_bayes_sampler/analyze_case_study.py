#!/usr/bin/env python3
"""
Reproduce the tables in docs/case_study_sme_context_bayes_sampler.md.

Reads scenarios.csv (exported from the campaign DB) from this directory and
the network from tools/bayes_sampler/nets/net_local_02.json. To analyze a fresh campaign instead, pass its DB:

    python analyze_case_study.py                 # archived scenarios.csv
    python analyze_case_study.py --db db/x.db    # a new harness run

Requires numpy and networkx (already in requirements.txt).
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

import networkx as nx
import numpy as np

HERE = Path(__file__).parent
NETWORK = HERE.parents[2] / "tools" / "bayes_sampler" / "nets" / "net_local_02.json"
THRESHOLD = 25.5          # resilience <= this is critical (q0.5 of sweep 1)
EXITS = ["33", "34"]


def load_csv():
    data = {}
    with open(HERE / "scenarios.csv") as f:
        for row in csv.DictReader(f):
            sw = int(row["sweep_id"])
            w = {k[1:]: float(v) for k, v in row.items() if k.startswith("w")}
            data.setdefault(sw, []).append((w, float(row["overall_system_resilience"])))
    return data


def load_db(path):
    c = sqlite3.connect(path)
    rows = c.execute("SELECT s.sweep_id, s.scenario_id, i.parameter, i.value FROM scenarios s "
                     "JOIN inputs i USING (scenario_id) WHERE s.status='complete'").fetchall()
    out = dict(c.execute("SELECT scenario_id, value FROM outputs "
                         "WHERE metric='overall_system_resilience'").fetchall())
    X, sw = {}, {}
    for s, sid, p, v in rows:
        X.setdefault(sid, {})[p] = v
        sw[sid] = s
    data = {}
    for sid in sorted(X):
        data.setdefault(sw[sid], []).append((X[sid], out[sid]))
    return data


def rungs():
    net = json.load(open(NETWORK))
    G = nx.DiGraph()
    G.add_nodes_from(str(n["id"]) for n in net["nodes"])
    G.add_edges_from((str(e["source"]["id"]), str(e["target"]["id"])) for e in net["edges"])
    dist = {n: min(nx.shortest_path_length(G, n, x) for x in EXITS if nx.has_path(G, n, x))
            for n in G}
    by = {}
    for n, d in dist.items():
        by.setdefault(d, []).append(n)
    return {d: sorted(v, key=int) for d, v in sorted(by.items())}


def r2(W, y, cols):
    A = np.column_stack([W[c] for c in cols] + [np.ones(len(y))])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    return 1 - (y - A @ b).var() / y.var()


def summarize(name, rows, by):
    W = {k: np.array([r[0][k] for r in rows]) for k in rows[0][0]}
    y = np.array([r[1] for r in rows])
    crit = y <= THRESHOLD
    floor = 100 * (1 - W["33"]) * (1 - W["34"])
    print(f"\n=== {name}: n={len(y)}  resilience min {y.min():.1f} / median {np.median(y):.1f} "
          f"/ max {y.max():.1f}  critical {crit.sum()} ({crit.mean():.0%})")
    print(f"  median (observed - exit-only floor): {np.median(y - floor):.1f} pts")
    base = r2(W, y, EXITS)
    print(f"  R2 exits only {base:.3f} | all nodes {r2(W, y, list(W)):.3f}")
    for d, nodes in by.items():
        if d == 0:
            continue
        mean_corr = np.mean([np.corrcoef(W[n], y)[0, 1] for n in nodes])
        grp = np.mean([W[n] for n in nodes], axis=0)
        lo, hi = grp < np.median(grp), grp >= np.median(grp)
        rate = (f"critical rate low->high {crit[lo].mean():.0%} -> {crit[hi].mean():.0%}"
                if crit.any() else "no critical scenarios")
        print(f"  dist {d} nodes {nodes[0]}-{nodes[-1]} ({len(nodes)}): R2 gain {r2(W, y, EXITS + nodes) - base:+.3f}"
              f" | mean corr {mean_corr:+.3f} | {rate}")
    if crit.any():
        both_low = sum(1 for i in np.where(crit)[0]
                       if W["33"][i] <= W["33"].mean() and W["34"][i] <= W["34"].mean())
        print(f"  critical with both exits <= sweep mean: {both_low} of {crit.sum()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="analyze a harness DB instead of the archived CSV")
    args = ap.parse_args()
    data = load_db(args.db) if args.db else load_csv()
    by = rungs()
    print("Rungs by distance to exit:", {d: f"{v[0]}-{v[-1]}" if len(v) > 2 else v for d, v in by.items()})
    labels = {1: "Sweep 1 (LHS, all free)", 2: "Sweep 2 (exits 0.45-0.60)",
              3: "Sweep 3 (exits 0.45-0.60, near-exit rung <= 0.30)"}
    for sw in sorted(data):
        summarize(labels.get(sw, f"Sweep {sw}"), data[sw], by)


if __name__ == "__main__":
    main()

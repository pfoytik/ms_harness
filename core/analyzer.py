"""
Samples analyzer — PRIM with surprise scoring adapted to the harness DB schema.
Produces a structured findings report from any completed sweep.
"""

import importlib.util
import json
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.stats import chi2_contingency

from .store import load_sweep_data, load_all_data, first_lhs_sweep_id


# ── Element potentials ────────────────────────────────────────────────────────

def _load_network(network_path: str):
    import json as _json
    with open(network_path) as f:
        net = _json.load(f)
    G = nx.DiGraph()
    for e in net["edges"]:
        G.add_edge(e["source"]["id"], e["target"]["id"])
    return net, G


def _betweenness_potential(G, node_ids):
    bc = nx.betweenness_centrality(G, normalized=True)
    vals = {nid: bc.get(int(nid), 0.0) for nid in node_ids}
    return vals


def _paths_to_exit_potential(G, node_ids):
    try:
        topo = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        return {nid: 1.0 / len(node_ids) for nid in node_ids}

    paths_from = {}
    for v in topo:
        preds = list(G.predecessors(v))
        paths_from[v] = 1 if not preds else sum(paths_from.get(p, 0) for p in preds)

    paths_to_exit = {}
    for v in reversed(topo):
        succs = list(G.successors(v))
        paths_to_exit[v] = 1 if not succs else sum(paths_to_exit.get(c, 0) for c in succs)

    through = {v: paths_from.get(v, 0) * paths_to_exit.get(v, 0) for v in G.nodes}
    total   = max(sum(through.values()), 1)
    return {nid: through.get(int(nid), 0) / total for nid in node_ids}


def _likelihood_potential(X: np.ndarray, node_ids: list[str]) -> dict:
    means = X.mean(axis=0)
    total = means.sum() or 1.0
    return {nid: float(means[j] / total) for j, nid in enumerate(node_ids)}


def _sme_drivers(config: dict) -> dict:
    """objective.sme_expected_drivers as {node_id: importance}; a list means equal weights."""
    raw = config["objective"].get("sme_expected_drivers") or {}
    if isinstance(raw, list):
        raw = {str(k): 1.0 for k in raw}
    return {str(k): float(v) for k, v in raw.items()}


def _sme_potential(config: dict, node_ids: list[str]) -> dict:
    """
    Potential = the SME's stated expectation of which nodes drive the critical
    outcome. Low SP then means "the SME's expected drivers are NOT elevated",
    so critical + low SP = a critical scenario that contradicts the SME.
    """
    drivers = _sme_drivers(config)
    if not drivers:
        raise ValueError("element_potential 'sme' requires objective.sme_expected_drivers")
    unknown = set(drivers) - set(node_ids)
    if unknown:
        raise ValueError(f"sme_expected_drivers not among inputs: {sorted(unknown)}")
    return {nid: drivers.get(nid, 0.0) for nid in node_ids}


def _compute_potentials(potential_type: str, node_ids: list[str],
                         X: np.ndarray, config: dict) -> dict:
    if potential_type in ("betweenness", "paths_to_exit"):
        network_path = config["tool"]["adapter_config"]["network_template"]
        _, G = _load_network(network_path)
        if potential_type == "betweenness":
            return _betweenness_potential(G, node_ids)
        return _paths_to_exit_potential(G, node_ids)
    if potential_type == "likelihood":
        return _likelihood_potential(X, node_ids)
    if potential_type == "sme":
        return _sme_potential(config, node_ids)
    raise ValueError(f"Unknown potential_type: {potential_type!r}")


# ── Scenario potential SP(x) ──────────────────────────────────────────────────

def _scenario_potential(weights_row: dict, potentials: dict,
                         nominal: dict, potential_type: str) -> float:
    if potential_type == "likelihood":
        vals = list(weights_row.values())
        return np.mean(vals) / 0.99 if vals else 0.0
    total_p = sum(potentials.values()) or 1.0
    degraded = sum(
        potentials.get(nid, 0.0)
        for nid, w in weights_row.items()
        if w > nominal.get(nid, 0.5)
    )
    return degraded / total_p


# ── Surprise score Z(x) ───────────────────────────────────────────────────────

def _surprise_scores(y: np.ndarray, sp: np.ndarray,
                      lambda1=0.5, lambda2=1.0):
    y_min, y_max   = y.min(), y.max()
    sp_min, sp_max = sp.min(), sp.max()
    t_norm  = (y  - y_min)  / (y_max  - y_min)  if y_max  > y_min  else np.zeros_like(y)
    sp_norm = (sp - sp_min) / (sp_max - sp_min)  if sp_max > sp_min else np.zeros_like(sp)
    Z = lambda1 * t_norm - lambda2 * sp_norm + lambda2
    return Z, t_norm, sp_norm


# ── PRIM ─────────────────────────────────────────────────────────────────────

def _chi2_select(X: np.ndarray, z_high: np.ndarray, K: int) -> np.ndarray:
    n_feat = X.shape[1]
    stats  = np.zeros(n_feat)
    for j in range(n_feat):
        col = X[:, j]
        if col.std() < 1e-10:
            continue
        q = np.percentile(col, [25, 50, 75])
        binned = np.digitize(col, q)
        try:
            ct = np.zeros((4, 2), dtype=int)
            for b, z in zip(binned, z_high):
                ct[b, z] += 1
            stat, _, _, _ = chi2_contingency(ct + 1)
            stats[j] = stat
        except Exception:
            pass
    ranked = np.argsort(stats)[::-1]
    active = ranked[stats[ranked] > 0]
    return active[:min(K, len(active))]


def _prim(X: np.ndarray, Z: np.ndarray, feature_names: list[str],
            alpha=0.05, n_min=50, K=200):
    N, D = X.shape
    z_high      = (Z >= np.median(Z)).astype(int)
    active_feat = _chi2_select(X, z_high, K)
    if len(active_feat) == 0:
        active_feat = np.arange(D)

    in_box = np.ones(N, dtype=bool)
    z_star = Z[in_box].mean()
    box_lo = {j: None for j in range(D)}
    box_hi = {j: None for j in range(D)}

    while True:
        if in_box.sum() < n_min:
            break
        best_mask, best_z = None, z_star
        best_side = best_j = best_thresh = None

        for j in active_feat:
            col = X[:, j]
            lo_thresh = np.percentile(col[in_box], alpha * 100)
            mask_lo   = in_box & (col >= lo_thresh)
            if mask_lo.sum() >= n_min and Z[mask_lo].mean() > best_z:
                best_z, best_mask = Z[mask_lo].mean(), mask_lo.copy()
                best_side, best_j, best_thresh = "lo", j, lo_thresh

            hi_thresh = np.percentile(col[in_box], (1 - alpha) * 100)
            mask_hi   = in_box & (col <= hi_thresh)
            if mask_hi.sum() >= n_min and Z[mask_hi].mean() > best_z:
                best_z, best_mask = Z[mask_hi].mean(), mask_hi.copy()
                best_side, best_j, best_thresh = "hi", j, hi_thresh

        if best_mask is None:
            break
        in_box = best_mask
        z_star = best_z
        if best_side == "lo":
            box_lo[best_j] = best_thresh
        else:
            box_hi[best_j] = best_thresh

    box = {}
    for j in range(D):
        lo, hi = box_lo[j], box_hi[j]
        if lo is not None or hi is not None:
            box[feature_names[j]] = (lo, hi)

    return box, {"z_bar": float(z_star), "n_in_box": int(in_box.sum()), "in_box": in_box}


# ── Metrics ───────────────────────────────────────────────────────────────────

def _quintile_bins(sp: np.ndarray, n_bins=5) -> np.ndarray:
    edges = np.percentile(sp, np.linspace(0, 100, n_bins + 1))
    edges[-1] += 1e-10
    return np.digitize(sp, edges[1:])


def _bias_ratio(disc: np.ndarray, crit: np.ndarray, sp: np.ndarray, n_bins=5) -> float:
    bins = _quintile_bins(sp, n_bins)

    def recall(bin_set):
        mask  = np.isin(bins, bin_set)
        denom = (crit & mask).sum()
        return (disc & crit & mask).sum() / denom if denom else 0.0

    hi = recall(list(range(n_bins - 2, n_bins)))
    lo = recall(list(range(0, 2)))
    if lo == 0:
        return float("inf") if hi > 0 else 1.0
    return float(hi / lo)


def _completeness_index(disc: np.ndarray, crit: np.ndarray,
                         sp: np.ndarray, n_bins=5) -> float:
    bins   = _quintile_bins(sp, n_bins)
    counts = np.array(
        [(disc & crit & (bins == b)).sum() for b in range(n_bins)], dtype=float
    )
    coverage = (counts > 0).sum() / n_bins
    total    = counts.sum()
    if total == 0:
        return 0.0
    p      = counts[counts > 0] / total
    h_norm = -np.sum(p * np.log2(p)) / np.log2(n_bins)
    return float(0.5 * coverage + 0.5 * h_norm)


# ── Main analysis entry point ─────────────────────────────────────────────────

def analyze(sweep_id: int, db_path: str, config: dict,
             use_all_data: bool = False) -> dict:
    """
    Run PRIM analysis with surprise scoring on a completed sweep.

    Returns a findings report dict suitable for display and DB storage.
    """
    potential_type = config["objective"]["element_potential"]
    tau_q          = config["objective"]["critical_threshold_quantile"]
    metric         = config["objective"]["critical_metric"]
    direction      = config["objective"]["critical_direction"]  # 'below' or 'above'
    n_min          = config["sampling"].get("min_box_support", 30)
    alpha          = config["sampling"].get("alpha", 0.05)

    # Load data
    if use_all_data:
        input_rows, output_rows = load_all_data(db_path)
    else:
        input_rows, output_rows = load_sweep_data(db_path, sweep_id)

    if not input_rows:
        return {"error": "No data found for this sweep"}

    # Pivot into matrices
    scenario_ids = sorted({r["scenario_id"] for r in input_rows})
    params_set   = sorted({r["parameter"] for r in input_rows})

    inp_map = {r["scenario_id"]: {} for r in input_rows}
    for r in input_rows:
        inp_map[r["scenario_id"]][r["parameter"]] = r["value"]

    out_map = {}
    for r in output_rows:
        out_map[r["scenario_id"]] = out_map.get(r["scenario_id"], {})
        out_map[r["scenario_id"]][r["metric"]] = r["value"]

    valid = [sid for sid in scenario_ids if sid in out_map]
    if len(valid) < n_min:
        return {"error": f"Only {len(valid)} complete scenarios; need ≥ {n_min}"}

    X = np.array([[inp_map[sid].get(p, 0.5) for p in params_set] for sid in valid])
    y_raw = np.array([out_map[sid].get(metric, 0.0) for sid in valid])

    # For 'below' direction, attacker success = 100 - resilience
    y = (100.0 - y_raw) if direction == "below" else y_raw

    # Potentials, nominal, SP
    potentials = _compute_potentials(potential_type, params_set, X, config)
    nominal    = {p: X[:, j].mean() for j, p in enumerate(params_set)}

    sp_vals = np.array([
        _scenario_potential(inp_map[sid], potentials, nominal, potential_type)
        for sid in valid
    ])

    # Critical label. tau is on the internal "higher = worse" scale y.
    # It is frozen so targeted (deliberately biased) sweeps can't move it:
    #   1. objective.critical_threshold (metric units), if set
    #   2. else the tau_q quantile of the first completed LHS sweep
    #   3. else (no LHS sweep yet) the quantile of the data being analyzed
    explicit = config["objective"].get("critical_threshold")
    if explicit is not None:
        tau = (100.0 - float(explicit)) if direction == "below" else float(explicit)
        tau_source = "config critical_threshold"
    else:
        base_id = first_lhs_sweep_id(db_path)
        base_y  = None
        if base_id is not None:
            _, base_out = load_sweep_data(db_path, base_id)
            vals = [r["value"] for r in base_out if r["metric"] == metric]
            if vals:
                base_raw = np.array(vals)
                base_y   = (100.0 - base_raw) if direction == "below" else base_raw
        if base_y is not None:
            tau = float(np.quantile(base_y, tau_q))
            tau_source = f"q{tau_q:g} of initial LHS sweep {base_id}"
        else:
            tau = float(np.quantile(y, tau_q))
            tau_source = f"q{tau_q:g} of analyzed data"
    tau_raw       = (100.0 - tau) if direction == "below" else tau
    critical_mask = y >= tau

    # Z scores
    Z, t_norm, sp_norm = _surprise_scores(y, sp_vals)

    # PRIM
    box, meta = _prim(X, Z, params_set, alpha=alpha, n_min=n_min)
    disc_mask = meta["in_box"]

    # Metrics
    br = _bias_ratio(disc_mask, critical_mask, sp_vals)
    ci = _completeness_index(disc_mask, critical_mask, sp_vals)
    n_crit_in_box = int((disc_mask & critical_mask).sum())
    precision     = n_crit_in_box / disc_mask.sum() if disc_mask.sum() > 0 else 0.0

    # Build human-readable box description
    box_description = []
    for pid, (lo, hi) in box.items():
        # Find node title if possible
        lo_s = f"{lo:.3f}" if lo is not None else "—"
        hi_s = f"{hi:.3f}" if hi is not None else "—"
        box_description.append({"parameter": pid, "lower": lo, "upper": hi,
                                  "lower_str": lo_s, "upper_str": hi_s})

    # Top surprising critical scenarios (highest Z, inside box, critical)
    top_indices = np.where(disc_mask & critical_mask)[0]
    top_z       = Z[top_indices]
    top_order   = top_indices[np.argsort(top_z)[::-1][:5]]
    top_scenarios = []
    for idx in top_order:
        sid = valid[idx]
        drivers = _sme_drivers(config)
        extra = {}
        if drivers:
            extra["sme_drivers_elevated"] = sorted(
                (d for d in drivers if inp_map[sid].get(d, 0.0) > nominal.get(d, 0.5)), key=str)
        top_scenarios.append({
            **extra,
            "scenario_id": sid,
            "z_score":     float(Z[idx]),
            "sp":          float(sp_vals[idx]),
            "y_raw":       float(y_raw[idx]),
            "inputs":      inp_map[sid],
        })

    return {
        "sweep_id":           sweep_id,
        "n_scenarios":        len(valid),
        "n_critical":         int(critical_mask.sum()),
        "tau":                float(tau),
        "tau_quantile":       tau_q,
        "tau_raw":            float(tau_raw),
        "tau_source":         tau_source,
        "potential_type":     potential_type,
        "z_bar":              float(meta["z_bar"]),
        "n_in_box":           int(meta["n_in_box"]),
        "precision":          float(precision),
        "bias_ratio":         br,
        "completeness_index": ci,
        "box":                box_description,
        "potentials":         {k: round(float(v), 4) for k, v in potentials.items()},
        "top_surprising":     top_scenarios,
        "metric":             metric,
        "direction":          direction,
    }

"""
Sweep planner — designs LHS and targeted scenario batches.
"""

import numpy as np
from scipy.stats.qmc import LatinHypercube


def lhs_sweep(input_specs: list[dict], n: int, seed: int = None) -> list[dict]:
    """
    Generate n LHS scenarios over the input parameter space.

    input_specs : list of {"id": str, "range": [lo, hi], "nominal": float, ...}
    Returns     : list of {param_id: weight} dicts
    """
    D = len(input_specs)
    sampler = LatinHypercube(d=D, seed=seed)
    unit = sampler.random(n)  # (n, D) in [0,1]

    scenarios = []
    for row in unit:
        s = {}
        for j, spec in enumerate(input_specs):
            lo, hi = spec["range"]
            s[spec["id"]] = float(lo + row[j] * (hi - lo))
        scenarios.append(s)
    return scenarios


def targeted_sweep(input_specs: list[dict], box: dict, n: int, seed: int = None) -> list[dict]:
    """
    Generate n scenarios focused inside a PRIM box.

    box : {param_id: (lower_bound, upper_bound)}  — None bound = use spec range
    Params outside the box are drawn from their full range (LHS).
    Params inside the box are drawn uniformly within the box bounds.
    """
    D = len(input_specs)
    rng = np.random.default_rng(seed)

    scenarios = []
    for _ in range(n):
        s = {}
        for spec in input_specs:
            pid = spec["id"]
            full_lo, full_hi = spec["range"]
            if pid in box:
                lo_b, hi_b = box[pid]
                lo = lo_b if lo_b is not None else full_lo
                hi = hi_b if hi_b is not None else full_hi
                lo = max(lo, full_lo)
                hi = min(hi, full_hi)
            else:
                lo, hi = full_lo, full_hi
            s[pid] = float(rng.uniform(lo, hi))
        scenarios.append(s)
    return scenarios


def followup_budget(config: dict, sweep_number: int) -> int:
    """Calculate follow-up sweep size from config budget and fraction."""
    budget    = config["sampling"]["sweep_budget"]
    initial_n = config["sampling"]["initial_n"]
    frac      = config["sampling"].get("followup_fraction", 0.4)
    remaining = budget - initial_n - (sweep_number - 1) * int(budget * frac)
    return max(int(budget * frac), min(50, remaining))

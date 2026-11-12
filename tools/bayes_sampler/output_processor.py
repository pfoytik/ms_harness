"""
Bayesian attack network output processor.

Reads summary_<scenario_id>.json written by headless_sampler.js and
returns a standardised metrics dict for the harness DB.
"""

import json
import os


def process(output_dir: str, scenario_id: str) -> dict:
    """
    Parse sampler summary output.

    summary.json structure:
        {"1": 53, "2": 48, ..., "Overall System Resilience": 73}

    Node values are raw compromise counts out of n_samples_per_run.
    "Overall System Resilience" is a percentage (0-100).

    Returns:
        {"overall_system_resilience": float}
    """
    summary_path = os.path.join(output_dir, f"summary_{scenario_id}.json")
    with open(summary_path) as f:
        summary = json.load(f)

    resilience = float(summary.get("Overall System Resilience", 0.0))
    return {"overall_system_resilience": resilience}

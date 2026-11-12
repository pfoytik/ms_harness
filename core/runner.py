"""
Batch runner — executes scenarios via the tool adapter's run_model.sh.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .store import create_scenario, write_scenario_result


def _load_adapter(adapter_name: str):
    """Dynamically load input_processor and output_processor for a named adapter."""
    tools_dir = Path(__file__).parent.parent / "tools" / adapter_name
    mods = {}
    for name in ("input_processor", "output_processor"):
        spec = importlib.util.spec_from_file_location(name, tools_dir / f"{name}.py")
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods["input_processor"], mods["output_processor"]


def run_batch(config: dict, scenarios: list[dict], sweep_id: int, db_path: str) -> int:
    """
    Execute a batch of scenarios against the M&S tool.

    Returns number of successfully completed scenarios.
    """
    adapter_name   = config["tool"]["adapter"]
    adapter_config = config["tool"]["adapter_config"]
    sampler_path   = adapter_config.get("sampler_path", "")  # "" = adapter default
    n_samples      = adapter_config.get("n_samples_per_run", 1000)

    tools_dir  = Path(__file__).parent.parent / "tools" / adapter_name
    runner_sh  = str(tools_dir / "run_model.sh")

    input_proc, output_proc = _load_adapter(adapter_name)

    n_ok = 0
    with tempfile.TemporaryDirectory(prefix="harness_run_") as output_dir:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Running scenarios", total=len(scenarios))

            for i, scenario in enumerate(scenarios):
                scenario_id = create_scenario(db_path, sweep_id)
                input_path  = None
                try:
                    input_path = input_proc.process(scenario, adapter_config)
                    result = subprocess.run(
                        ["bash", runner_sh, input_path, str(scenario_id),
                         output_dir, sampler_path, str(n_samples)],
                        capture_output=True, text=True, timeout=120,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip())

                    outputs = output_proc.process(output_dir, str(scenario_id))
                    write_scenario_result(db_path, scenario_id, scenario, outputs)
                    n_ok += 1

                except Exception as exc:
                    sys.stderr.write(f"  [warn] scenario {scenario_id} failed: {exc}\n")
                finally:
                    if input_path and os.path.exists(input_path):
                        os.unlink(input_path)
                    progress.advance(task)

    return n_ok


def smoke_test(config: dict) -> dict:
    """
    Run one scenario at nominal input values to verify the adapter works.
    Returns {"ok": bool, "resilience": float, "error": str}.
    """
    adapter_name   = config["tool"]["adapter"]
    adapter_config = config["tool"]["adapter_config"]
    sampler_path   = adapter_config.get("sampler_path", "")  # "" = adapter default
    n_samples      = adapter_config.get("n_samples_per_run", 1000)

    tools_dir  = Path(__file__).parent.parent / "tools" / adapter_name
    runner_sh  = str(tools_dir / "run_model.sh")
    input_proc, output_proc = _load_adapter(adapter_name)

    input_specs = input_proc.discover_inputs(adapter_config)
    nominal     = {s["id"]: s["nominal"] for s in input_specs}

    with tempfile.TemporaryDirectory(prefix="harness_smoke_") as output_dir:
        input_path = None
        try:
            input_path = input_proc.process(nominal, adapter_config)
            result = subprocess.run(
                ["bash", runner_sh, input_path, "smoke", output_dir,
                 sampler_path, str(n_samples)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return {"ok": False, "error": result.stderr.strip()}

            outputs = output_proc.process(output_dir, "smoke")
            metric  = list(outputs.values())[0]
            return {"ok": True, "outputs": outputs, "n_inputs": len(input_specs)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)

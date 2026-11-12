#!/usr/bin/env python3
"""
MS Harness — AI-assisted critical scenario discovery for M&S tools.

Commands:
  run     Run a sweep campaign (LHS → analyze → targeted follow-up loop)
  status  Show DB summary for a project
  chat    Open a conversation about current findings
  new     Start onboarding conversation to generate a new config (requires API key)

Usage:
  python harness.py run   --config tools/bayes_sampler/harness_config.json --db demo.db
  python harness.py status --config tools/bayes_sampler/harness_config.json --db demo.db
  python harness.py chat   --config tools/bayes_sampler/harness_config.json --db demo.db
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import click
from rich import box as rbox
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

# Ensure core/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from core import store, planner, runner, analyzer
from core.conversation import (
    OnboardingSession,
    interpret_findings, propose_next_sweep,
    ai_available, build_preamble, _report_block,
)

console = Console()

BANNER = """[bold cyan]
╔══════════════════════════════════════════════════╗
║          M&S AI Harness  —  v0.1 POC             ║
║  Surprise-Driven Critical Scenario Discovery     ║
╚══════════════════════════════════════════════════╝[/bold cyan]"""


REPO_ROOT = Path(__file__).parent


def _load_config(config_path: str) -> dict:
    """Load a config; relative paths in adapter_config that exist under the
    repo root are made absolute, so runs don't depend on the current directory."""
    with open(config_path) as f:
        cfg = json.load(f)
    ac = cfg.get("tool", {}).get("adapter_config", {})
    for key, val in ac.items():
        if isinstance(val, str) and val and not os.path.isabs(val) and (REPO_ROOT / val).exists():
            ac[key] = str(REPO_ROOT / val)
    return cfg


DB_DIR = Path(__file__).parent / "db"


def _resolve_db(db: str) -> str:
    """A bare filename (e.g. 'demo.db') lives in db/; any path with a directory is used as given."""
    if "/" not in db and os.sep not in db:
        DB_DIR.mkdir(exist_ok=True)
        return str(DB_DIR / db)
    return db


def _load_input_specs(config: dict) -> list[dict]:
    adapter_name   = config["tool"]["adapter"]
    adapter_config = config["tool"]["adapter_config"]
    tools_dir = Path(__file__).parent / "tools" / adapter_name
    spec = importlib.util.spec_from_file_location(
        "input_processor", tools_dir / "input_processor.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.discover_inputs(adapter_config)


def _print_findings(report: dict) -> None:
    console.print()
    console.print(Panel(
        f"[bold]Sweep {report['sweep_id']} — Analysis Complete[/bold]",
        style="cyan", box=rbox.ROUNDED,
    ))

    t = Table(show_header=True, header_style="bold magenta", box=rbox.SIMPLE)
    t.add_column("Metric", style="dim")
    t.add_column("Value")
    t.add_row("Scenarios analyzed",  str(report["n_scenarios"]))
    if "tau_raw" in report:
        op = "≤" if report.get("direction") == "below" else "≥"
        t.add_row("Critical",        f"{report['n_critical']}  ({report['metric']} {op} "
                                     f"{report['tau_raw']:.1f}; {report['tau_source']})")
    else:  # findings saved before tau_raw existed
        t.add_row("Critical (τ)",    f"{report['n_critical']}  (τ = {report['tau']:.1f})")
    t.add_row("Z̄ (mean surprise)",   f"{report['z_bar']:.3f}")
    t.add_row("Box size",            str(report["n_in_box"]))
    t.add_row("Precision",           f"{report['precision']:.1%}")
    br = report["bias_ratio"]
    br_str = f"{br:.3f}×" if br != float("inf") else "∞"
    t.add_row("Bias Ratio",          f"[green]{br_str}[/green]")
    t.add_row("Completeness Index",  f"{report['completeness_index']:.3f}")
    console.print(t)

    if report["box"]:
        console.print("\n[bold yellow]Surprising region (PRIM box):[/bold yellow]")
        bt = Table(show_header=True, header_style="bold", box=rbox.SIMPLE)
        bt.add_column("Parameter")
        bt.add_column("Lower bound")
        bt.add_column("Upper bound")
        for item in report["box"]:
            bt.add_row(
                item["parameter"],
                item["lower_str"] if item["lower"] is not None else "[dim]none[/dim]",
                item["upper_str"] if item["upper"] is not None else "[dim]none[/dim]",
            )
        console.print(bt)

    if report.get("top_surprising"):
        console.print("\n[bold yellow]Top surprising critical scenarios:[/bold yellow]")
        st = Table(show_header=True, header_style="bold", box=rbox.SIMPLE)
        st.add_column("Scenario ID")
        st.add_column("Z score")
        st.add_column("SP")
        st.add_column("Resilience")
        for s in report["top_surprising"]:
            st.add_row(
                str(s["scenario_id"]),
                f"{s['z_score']:.3f}",
                f"{s['sp']:.3f}",
                f"{s['y_raw']:.1f}%",
            )
        console.print(st)


def _ai_interpret(report: dict, config: dict, db: str, final: bool) -> dict | None:
    """Call Claude for findings interpretation (+ next-sweep proposal unless final).
    Both outputs are stored in the DB. Returns the proposal or None."""
    if not ai_available():
        console.print("[dim]  (ANTHROPIC_API_KEY not set and HARNESS_AI_MODE != manual — skipping AI interpretation)[/dim]")
        return None
    try:
        console.print("[dim]  Asking AI for interpretation...[/dim]")
        interpretation = interpret_findings(report, config)
        store.save_ai_output(db, report["sweep_id"], "interpretation", interpretation)
        console.print(Panel(interpretation, title="[bold cyan]AI Interpretation[/bold cyan]",
                             border_style="cyan", box=rbox.ROUNDED))
        if final:
            return None
        proposal = propose_next_sweep(report, config, interpretation)
        store.save_ai_output(db, report["sweep_id"], "proposal", json.dumps(proposal))
        if proposal.get("rationale"):
            console.print(f"[dim]  AI proposal: {proposal['rationale']}[/dim]")
        return proposal
    except Exception as exc:
        console.print(f"[yellow]  AI interpretation failed: {exc}[/yellow]")
        return None


# ── Commands ──────────────────────────────────────────────────────────────────

@click.group()
def cli():
    pass


@cli.command()
@click.option("--config", required=True, help="Path to harness_config.json")
@click.option("--db",     required=True, help="SQLite samples DB; a bare filename is stored in db/ (created if absent)")
@click.option("--sweeps", default=3,     show_default=True,
              help="Maximum number of sweeps to run")
@click.option("--no-ai",  is_flag=True,  help="Skip AI interpretation (run analysis only)")
def run(config, db, sweeps, no_ai):
    """Run a sweep campaign: LHS → analyze → targeted follow-up loop."""
    db = _resolve_db(db)
    console.print(BANNER)
    cfg = _load_config(config)
    store.init_db(db)

    console.print(f"\n[bold]Project:[/bold] {cfg['project']['name']}")
    console.print(f"[bold]Tool:[/bold]    {cfg['tool']['name']}")
    console.print(f"[bold]DB:[/bold]      {db}\n")

    # Smoke test
    console.print("[cyan]Running smoke test...[/cyan]")
    result = runner.smoke_test(cfg)
    if not result["ok"]:
        console.print(f"[red]✗ Smoke test failed:[/red] {result['error']}")
        sys.exit(1)
    console.print(f"[green]✓ Smoke test passed[/green]  "
                  f"({result['n_inputs']} inputs discovered, "
                  f"output: {result['outputs']})\n")

    input_specs = _load_input_specs(cfg)
    box_constraints = {}  # grows with each targeted sweep

    for sweep_num in range(1, sweeps + 1):
        # Design sweep
        if sweep_num == 1:
            n = cfg["sampling"]["initial_n"]
            sweep_type = "lhs"
            scenarios  = planner.lhs_sweep(input_specs, n)
            console.print(Panel(
                f"[bold]Sweep {sweep_num} of {sweeps}[/bold]  —  Initial LHS  (N={n})\n"
                f"Purpose: establish baseline distribution and element potentials",
                style="blue",
            ))
        else:
            n = planner.followup_budget(cfg, sweep_num)
            sweep_type = "targeted"
            scenarios  = planner.targeted_sweep(input_specs, box_constraints, n)
            console.print(Panel(
                f"[bold]Sweep {sweep_num} of {sweeps}[/bold]  —  Targeted follow-up  (N={n})\n"
                f"Focus: {len(box_constraints)} constrained parameter(s)",
                style="blue",
            ))

        if not Confirm.ask("Proceed?", default=True):
            console.print("[yellow]Sweep skipped.[/yellow]")
            continue

        # Execute
        sweep_id = store.create_sweep(db, sweep_type, n,
                                       notes=f"Sweep {sweep_num}")
        n_ok = runner.run_batch(cfg, scenarios, sweep_id, db)
        store.complete_sweep(db, sweep_id, n_ok)
        console.print(f"\n[green]✓ {n_ok}/{n} scenarios complete[/green]")

        # Analyze
        console.print("\n[cyan]Analyzing...[/cyan]")
        report = analyzer.analyze(sweep_id, db, cfg,
                                   use_all_data=(sweep_num > 1))
        if "error" in report:
            console.print(f"[red]Analysis error:[/red] {report['error']}")
            continue

        store.save_finding(db, sweep_id, report)
        _print_findings(report)

        # AI interpretation
        proposal = None
        if not no_ai:
            proposal = _ai_interpret(report, cfg, db, final=(sweep_num == sweeps))

        # Update box for next targeted sweep
        if report["box"]:
            if proposal and "focus_parameters" in proposal:
                box_constraints = {
                    pid: (v.get("lower"), v.get("upper"))
                    for pid, v in proposal["focus_parameters"].items()
                }
            else:
                box_constraints = {
                    item["parameter"]: (item["lower"], item["upper"])
                    for item in report["box"]
                }

        if sweep_num < sweeps:
            console.print()
            if not Confirm.ask("Continue to next sweep?", default=True):
                break

    console.print("\n[bold green]Campaign complete.[/bold green]  "
                  f"Results stored in [cyan]{db}[/cyan]")


@cli.command()
@click.option("--config", required=True, help="Path to harness_config.json")
@click.option("--db",     required=True, help="SQLite samples DB; a bare filename is looked up in db/")
def status(config, db):
    """Show DB summary for a project."""
    db = _resolve_db(db)
    console.print(BANNER)
    cfg = _load_config(config)
    if not os.path.exists(db):
        console.print("[red]DB not found.[/red] Run 'harness.py run' first.")
        sys.exit(1)

    summary = store.db_summary(db)
    sweeps  = store.list_sweeps(db)

    console.print(f"\n[bold]Project:[/bold] {cfg['project']['name']}")
    console.print(f"[bold]DB:[/bold]      {db}\n")

    t = Table(show_header=True, header_style="bold magenta", box=rbox.SIMPLE)
    t.add_column("Metric")
    t.add_column("Value")
    t.add_row("Sweeps completed",    str(summary["sweeps"]))
    t.add_row("Scenarios complete",  str(summary["scenarios_complete"]))
    t.add_row("Scenarios pending",   str(summary["scenarios_pending"]))
    t.add_row("Findings stored",     str(summary["findings"]))
    console.print(t)

    if sweeps:
        console.print("\n[bold]Sweep history:[/bold]")
        st = Table(show_header=True, header_style="bold", box=rbox.SIMPLE)
        st.add_column("ID")
        st.add_column("Type")
        st.add_column("Planned")
        st.add_column("Complete")
        st.add_column("Status")
        st.add_column("Created")
        for sw in sweeps:
            st.add_row(
                str(sw["sweep_id"]), sw["sweep_type"],
                str(sw["n_planned"]), str(sw["n_complete"]),
                sw["status"], sw["created_at"][:19],
            )
        console.print(st)

    finding = store.load_latest_finding(db)
    if finding:
        console.print("\n[bold]Latest findings:[/bold]")
        _print_findings(finding)


@cli.command()
@click.option("--config", required=True, help="Path to harness_config.json")
@click.option("--db",     required=True, help="SQLite samples DB; a bare filename is looked up in db/")
def chat(config, db):
    """Open a conversation about current findings with the AI."""
    db = _resolve_db(db)
    if not ai_available():
        console.print("[red]ANTHROPIC_API_KEY not set (or use HARNESS_AI_MODE=manual).[/red]")
        sys.exit(1)

    cfg     = _load_config(config)
    finding = store.load_latest_finding(db) if os.path.exists(db) else None
    console.print(BANNER)
    console.print(f"\n[bold]Chatting about:[/bold] {cfg['project']['name']}\n")

    from core.conversation import _call_claude

    system = build_preamble(cfg, finding) + "\n\n" + (
        "LATEST FINDINGS:\n" + _report_block(finding) if finding else "No runs yet."
    ) + "\n\nAnswer the modeler's questions about these results."
    history = []

    console.print("[dim]Type your question. Enter 'quit' to exit.[/dim]\n")
    while True:
        user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        if user_input.lower() in ("quit", "exit", "q"):
            break
        history.append({"role": "user", "content": user_input})
        reply = _call_claude(history, system=system)
        history.append({"role": "assistant", "content": reply})
        console.print(Panel(reply, title="[bold cyan]AI[/bold cyan]",
                             border_style="cyan", box=rbox.ROUNDED))


@cli.command()
@click.option("--output", default="harness_config.json",
              help="Output path for generated config")
def new(output):
    """Start onboarding conversation to generate a new harness_config.json."""
    if not ai_available():
        console.print("[red]ANTHROPIC_API_KEY required for onboarding (or HARNESS_AI_MODE=manual).[/red]")
        console.print("Copy and edit tools/bayes_sampler/harness_config.json as a template.")
        sys.exit(1)

    console.print(BANNER)
    console.print("\n[bold cyan]New project onboarding[/bold cyan]\n")

    session = OnboardingSession()
    console.print(Panel(session.start(), title="AI", border_style="cyan",
                         box=rbox.ROUNDED))

    while True:
        user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        reply, cfg = session.respond(user_input)
        console.print(Panel(reply, title="AI", border_style="cyan", box=rbox.ROUNDED))
        if cfg:
            console.print("\n[green]Config generated:[/green]")
            console.print_json(json.dumps(cfg, indent=2))
            if Confirm.ask(f"Save to {output}?", default=True):
                with open(output, "w") as f:
                    json.dump(cfg, f, indent=2)
                console.print(f"[green]✓ Saved to {output}[/green]")
            break


if __name__ == "__main__":
    cli()

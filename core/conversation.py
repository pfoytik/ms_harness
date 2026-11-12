"""
AI conversation layer — Claude API via httpx (avoids pydantic SDK conflict).

Three modes:
  OnboardingSession  — SME interview → harness_config.json
  FindingsSession    — interpret analysis report + propose next sweep
  AdapterGenerator   — generate input_processor.py, output_processor.py, run_model.sh
"""

import json
import os
import textwrap
import time
from pathlib import Path

import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL     = "claude-sonnet-4-6"


def _manual_mode() -> bool:
    """HARNESS_AI_MODE=manual → prompts go to files and a human/agent writes replies."""
    return os.environ.get("HARNESS_AI_MODE", "api").lower() == "manual"


def ai_available() -> bool:
    return _manual_mode() or bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_manual(messages: list, system: str = None) -> str:
    """
    Write the request to <exchange>/request_NNN.md and block until
    <exchange>/response_NNN.md appears (and stops growing). Returns its text.
    """
    exchange = Path(os.environ.get("HARNESS_AI_EXCHANGE_DIR", "ai_exchange"))
    exchange.mkdir(parents=True, exist_ok=True)
    n = len(list(exchange.glob("request_*.md"))) + 1
    req  = exchange / f"request_{n:03d}.md"
    resp = exchange / f"response_{n:03d}.md"

    parts = [f"# Request {n:03d}\n"]
    if system:
        parts.append(f"## System\n\n{system}\n")
    for m in messages:
        parts.append(f"## {m['role'].capitalize()}\n\n{m['content']}\n")
    parts.append(f"---\nWrite the reply to: {resp}\n")
    req.write_text("\n".join(parts))

    print(f"\n[manual AI] Prompt written to {req}")
    print(f"[manual AI] Waiting for {resp} ... (Ctrl+C to abort)")
    while not resp.exists():
        time.sleep(2)
    # Wait until the file stops changing so we don't read a partial write
    last, size = -1, resp.stat().st_size
    while size != last or size == 0:
        last = size
        time.sleep(1)
        size = resp.stat().st_size
    return resp.read_text().strip()


def _call_claude(messages: list, system: str = None, model: str = DEFAULT_MODEL) -> str:
    if _manual_mode():
        return _call_manual(messages, system)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": messages,
    }
    if system:
        payload["system"] = system

    resp = httpx.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


# ── Onboarding ────────────────────────────────────────────────────────────────

ONBOARDING_SYSTEM = """You are an AI assistant helping configure a modeling and simulation analysis harness.
Your job is to conduct a brief, focused interview with a subject matter expert (SME) and produce
a valid harness_config.json from their answers.

Ask ONE question at a time. Keep questions short and conversational.
After ~6-8 exchanges you have enough to generate the config.
When ready, output ONLY valid JSON inside <config> tags — nothing else outside them."""

ONBOARDING_QUESTIONS = [
    "What does your modeling tool simulate, and what real-world system does it represent?",
    "How do you currently run a simulation? Describe the command or process briefly.",
    "What are the inputs — the parameters you vary between runs? For each, what range of values is realistic?",
    "What does the output look like, and what metric tells you a run went 'badly'?",
    "Is there a threshold for 'bad', or is it relative to other runs?",
    "What do you already know about which inputs tend to drive bad outcomes?",
    "What scenario worries you most that you haven't been able to characterize yet?",
]


class OnboardingSession:
    def __init__(self):
        self.history = []
        self.step    = 0

    def start(self) -> str:
        return (
            "I'll ask you a few questions to configure the harness for your tool.\n"
            "Answer in plain language — I'll handle the technical details.\n\n"
            + ONBOARDING_QUESTIONS[0]
        )

    def respond(self, user_input: str) -> tuple[str, dict | None]:
        """
        Process user input, return (next_message, config_or_None).
        config is returned (non-None) when the AI is ready to generate it.
        """
        self.history.append({"role": "user", "content": user_input})
        self.step += 1

        # After ~6 exchanges, ask Claude to generate the config
        if self.step >= len(ONBOARDING_QUESTIONS):
            self.history.append({
                "role": "user",
                "content": (
                    "That's all I need. Please generate the harness_config.json now. "
                    "Output ONLY valid JSON inside <config> tags."
                ),
            })
            reply = _call_claude(self.history, system=ONBOARDING_SYSTEM)
            config = _extract_config(reply)
            return reply, config

        # Continue the interview
        next_q = ONBOARDING_QUESTIONS[self.step]
        self.history.append({"role": "assistant", "content": next_q})
        return next_q, None

    def generate_config(self) -> dict:
        """Force config generation from accumulated history."""
        self.history.append({
            "role": "user",
            "content": "Please generate the harness_config.json now. Output ONLY valid JSON inside <config> tags.",
        })
        reply = _call_claude(self.history, system=ONBOARDING_SYSTEM)
        return _extract_config(reply)


def _extract_config(text: str) -> dict | None:
    start = text.find("<config>")
    end   = text.find("</config>")
    if start == -1 or end == -1:
        # Try bare JSON
        try:
            return json.loads(text.strip())
        except Exception:
            return None
    raw = text[start + 8:end].strip()
    try:
        return json.loads(raw)
    except Exception:
        return None


# ── Shared preamble ───────────────────────────────────────────────────────────

def _load_model_description(config: dict) -> dict | None:
    """Call the adapter's optional describe_model(adapter_config) hook."""
    try:
        import importlib.util
        adapter = config["tool"]["adapter"]
        path = Path(__file__).parent.parent / "tools" / adapter / "input_processor.py"
        spec = importlib.util.spec_from_file_location(f"{adapter}_input_processor", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "describe_model"):
            return mod.describe_model(config["tool"]["adapter_config"])
    except Exception:
        pass
    return None


def _model_section(config: dict, report: dict | None) -> str:
    desc = _load_model_description(config)
    if not desc:
        return ""
    lines = ["MODEL STRUCTURE (derived from the model itself, not from the SME):",
             f"- {desc.get('summary', '')}"]
    if desc.get("entry_nodes"):
        lines.append(f"- Entry nodes (no parents): {', '.join(desc['entry_nodes'])}")
    if desc.get("exit_nodes"):
        lines.append(f"- Exit nodes (reaching any of these = attacker success): {', '.join(desc['exit_nodes'])}")
    if desc.get("input_semantics"):
        lines.append(f"- Input semantics: {desc['input_semantics']}")
    pots = (report or {}).get("potentials") or {}
    nodes = desc.get("nodes") or {}
    if nodes:
        lines.append("- Nodes (id: title | parents" + (" | element potential" if pots else "") + "):")
        for nid, n in nodes.items():
            pot = f" | {pots[nid]:.3f}" if nid in pots else ""
            par = ",".join(n.get("parents", [])) or "-"
            lines.append(f"    {nid}: {n.get('title', '')} | {par}{pot}")
    return "\n".join(lines)


def _sme_section(config: dict) -> str:
    obj, inp = config.get("objective", {}), config.get("inputs", {})
    parts = []
    if obj.get("sme_context"):
        parts.append(f"- Context: {obj['sme_context']}")
    if inp.get("sme_notes"):
        parts.append(f"- Notes on inputs: {inp['sme_notes']}")
    if obj.get("surprise_definition"):
        parts.append(f"- What the SME would find surprising: {obj['surprise_definition']}")
    drivers = obj.get("sme_expected_drivers")
    if drivers:
        ids = drivers if isinstance(drivers, list) else list(drivers)
        parts.append(f"- Nodes the SME expects to drive critical outcomes: {', '.join(map(str, ids))}")
    if not parts:
        return ""
    return ("SME PRIOR UNDERSTANDING (the subject-matter expert's expectations — treat as "
            "hypotheses, not facts):\n" + "\n".join(parts))


def build_preamble(config: dict, report: dict | None = None) -> str:
    """System-prompt preamble shared by every findings / proposal / chat call."""
    outputs = config.get("outputs") or []
    metric_desc = outputs[0]["description"] if outputs else config["objective"]["critical_metric"]
    sections = [
        "You are an AI analyst working with a modeling and simulation expert on "
        "surprise-driven critical scenario discovery. The harness samples the input space, "
        "labels scenarios critical by a threshold on the output metric, scores them for "
        "surprise, and uses PRIM to find input regions rich in surprising critical scenarios.",
        f"TOOL: {config['tool'].get('name', '')} — {config['tool'].get('description', '')}",
        f"CRITICAL METRIC: {config['objective']['critical_metric']} — {metric_desc} "
        f"(critical direction: {config['objective']['critical_direction']}).",
        _model_section(config, report),
        _sme_section(config),
        "HOW TO USE THE SME CONTEXT:\n"
        "- Use it to interpret findings in domain terms, but do not force results to fit it.\n"
        "- For each critical scenario you discuss, say whether it is CONSISTENT WITH or "
        "CONTRADICTS the SME's expectations, and why, citing node IDs and values.\n"
        "- Critical scenarios that contradict the SME's expectations are SURPRISING and are "
        "the most important findings: lead with them.\n"
        "- If the data contradicts the SME context as a whole, say so plainly.\n"
        "- Distinguish effects from Monte Carlo noise and from analysis artifacts.",
    ]
    return "\n\n".join(s for s in sections if s)


# ── Findings interpreter ──────────────────────────────────────────────────────

FINDINGS_TASK = """TASK: Interpret the findings report in the user message for the modeler:
1. What the discovered region and the top critical scenarios mean operationally
2. Which critical scenarios contradict the SME's expectations (surprising) vs. confirm them
3. The most actionable insight for the modeler
4. A concrete recommendation for the next sweep

Be specific and concise: 3-5 short paragraphs. End with a clearly labelled RECOMMENDATION section."""


def _critical_rule(report: dict) -> str:
    """Human-readable critical rule in the metric's own units."""
    if "tau_raw" not in report:
        return f"tau={report['tau']:.1f} on internal scale"
    op = "<=" if report.get("direction") == "below" else ">="
    return (f"{report['metric']} {op} {report['tau_raw']:.1f}; "
            f"threshold fixed from {report['tau_source']}")


def _report_block(report: dict, n_top: int = 5) -> str:
    """Per-sweep findings, compact enough for a prompt."""
    tops = []
    for s in report.get("top_surprising", [])[:n_top]:
        t = {k: v for k, v in s.items() if k != "inputs"}
        for k in ("z_score", "sp", "y_raw"):
            if k in t:
                t[k] = round(float(t[k]), 3)
        t["inputs"] = {k: round(float(v), 3) for k, v in s.get("inputs", {}).items()}
        tops.append(t)
    box = [{"parameter": b["parameter"],
            "lower": None if b["lower"] is None else round(b["lower"], 3),
            "upper": None if b["upper"] is None else round(b["upper"], 3)}
           for b in report.get("box", [])]
    br  = report["bias_ratio"]
    l1  = report.get("lambda1", 0.5)
    l2  = report.get("lambda2", 1.0)
    mode = ("pure severity — PRIM maximised bad outcomes regardless of SP" if l2 == 0.0
            else "emphasise surprise — PRIM strongly penalised high-SP scenarios" if l1 < 0.4
            else "balanced severity + surprise")
    return f"""FINDINGS REPORT (sweep {report.get('sweep_id')})
- Scenarios analyzed: {report['n_scenarios']}
- Critical scenarios: {report['n_critical']} ({_critical_rule(report)})
- Element potential used for surprise scoring: {report.get('potential_type')}
- Z objective: λ₁={l1}, λ₂={l2} ({mode})
- Bias ratio: {br if br == float('inf') else round(br, 3)} (< 1 = discovered critical scenarios skew toward low-potential, i.e. surprising, ones)
- Completeness index: {report['completeness_index']:.3f}
- PRIM box: {report['n_in_box']} scenarios, precision {report['precision']:.1%} (fraction critical inside the box)

PRIM box constraints (input bounds of the surprising region; null = unbounded):
{json.dumps(box)}

Top surprising critical scenarios (highest surprise score Z; sp = scenario potential, y_raw = metric value):
{json.dumps(tops, indent=1)}"""


def interpret_findings(report: dict, config: dict) -> str:
    """Generate a natural language interpretation of a findings report."""
    return _call_claude(
        [{"role": "user", "content": _report_block(report) +
          "\n\nPlease interpret these findings for the modeler."}],
        system=build_preamble(config, report) + "\n\n" + FINDINGS_TASK,
    )


PROPOSAL_TASK = """TASK: Propose the next targeted sweep. The harness will sample the parameters
you constrain uniformly within your bounds and all other parameters over their full range.
Prefer regions likely to contain critical scenarios that contradict the SME's expectations,
or that test whether an apparent finding is real.

Output ONLY valid JSON (no prose, no code fences) with this structure:
{"sweep_type": "targeted",
 "focus_parameters": {"<param_id>": {"lower": <float or null>, "upper": <float or null>}},
 "n": <integer>,
 "rationale": "<one sentence>"}"""


def propose_next_sweep(report: dict, config: dict, interpretation: str | None = None) -> dict:
    """
    Ask Claude to propose the targeted follow-up sweep specification.
    Returns {"sweep_type": "targeted", "focus_parameters": {...}, "n": int, "rationale": str}
    """
    budget = config['sampling'].get('followup_fraction', 0.4) * config['sampling']['sweep_budget']
    prompt = _report_block(report)
    if interpretation:
        prompt += f"\n\nYOUR INTERPRETATION OF THESE FINDINGS:\n{interpretation}"
    prompt += f"\n\nFollow-up budget: about {budget:.0f} scenarios.\nPropose the next sweep."

    reply = _call_claude(
        [{"role": "user", "content": prompt}],
        system=build_preamble(config, report) + "\n\n" + PROPOSAL_TASK,
    )
    try:
        text = reply.strip()
        if text.startswith("```"):          # tolerate fenced JSON
            text = text.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        # Fallback: return the full current box as the targeted region
        return {
            "sweep_type": "targeted",
            "focus_parameters": {item["parameter"]: {"lower": item["lower"], "upper": item["upper"]}
                                  for item in report["box"]},
            "n": int(budget),
            "rationale": "Densify within current PRIM box (AI proposal was not valid JSON)",
        }


# ── Adapter generator ─────────────────────────────────────────────────────────

ADAPTER_SYSTEM = """You are an expert Python and bash developer generating adapter code
for a modeling and simulation harness. Generate clean, working code with no extra prose.
Output code inside the requested tags exactly."""


def generate_adapters(tool_description: str, command_example: str,
                       input_example: str, output_example: str,
                       critical_field: str) -> dict:
    """
    Generate input_processor.py, output_processor.py, and run_model.sh
    from natural language descriptions.

    Returns {"input_processor": str, "output_processor": str, "run_model_sh": str}
    """
    prompt = f"""Generate three adapter files for this M&S tool.

Tool description: {tool_description}
Run command example: {command_example}
Input file example:
{input_example}

Output file example:
{output_example}

Critical output field: {critical_field}

Generate:
1. input_processor.py with functions:
   - discover_inputs(adapter_config) -> list of input specs
   - process(scenario: dict, adapter_config: dict) -> str (path to temp input file)

2. output_processor.py with function:
   - process(output_dir: str, scenario_id: str) -> dict of metric name -> float

3. run_model.sh that accepts: <input_file> <scenario_id> <output_dir> <extra_args...>

Output each file inside tags: <input_processor>...</input_processor>,
<output_processor>...</output_processor>, <run_model_sh>...</run_model_sh>"""

    reply = _call_claude([{"role": "user", "content": prompt}], system=ADAPTER_SYSTEM)

    return {
        "input_processor":  _extract_tagged(reply, "input_processor"),
        "output_processor": _extract_tagged(reply, "output_processor"),
        "run_model_sh":     _extract_tagged(reply, "run_model_sh"),
    }


def _extract_tagged(text: str, tag: str) -> str:
    start = text.find(f"<{tag}>")
    end   = text.find(f"</{tag}>")
    if start == -1 or end == -1:
        return ""
    return text[start + len(tag) + 2:end].strip()

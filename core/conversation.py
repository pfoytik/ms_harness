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

import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL     = "claude-sonnet-4-6"


def _call_claude(messages: list, system: str = None, model: str = DEFAULT_MODEL) -> str:
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


# ── Findings interpreter ──────────────────────────────────────────────────────

FINDINGS_SYSTEM = """You are an AI assistant helping a modeling and simulation expert
understand surprising critical scenarios discovered by PRIM analysis.

Given a findings report and the tool's config, provide:
1. A plain-language interpretation of the discovered scenario region
2. What the box constraints mean operationally
3. The most actionable insight for the modeler
4. A concrete recommendation for the next sweep (targeted region or new question to explore)

Be specific, concise, and grounded in the SME context from the config.
Write 3-4 short paragraphs. End with a clearly labelled RECOMMENDATION section."""


def interpret_findings(report: dict, config: dict) -> str:
    """Generate a natural language interpretation of a findings report."""
    sme_context    = config["objective"].get("sme_context", "")
    surprise_defn  = config["objective"].get("surprise_definition", "")
    tool_desc      = config["tool"]["description"]
    metric         = config["outputs"][0]["description"] if config.get("outputs") else report["metric"]

    prompt = f"""Tool: {tool_desc}

SME context: {sme_context}

Surprise definition: {surprise_defn}

Critical metric: {metric}

Analysis results:
- Scenarios analyzed: {report['n_scenarios']}
- Critical scenarios (τ={report['tau']:.1f}): {report['n_critical']}
- Bias ratio: {report['bias_ratio']:.3f}× (< 1 = correctly steering toward low-potential surprising scenarios)
- Completeness index: {report['completeness_index']:.3f}
- PRIM box contains: {report['n_in_box']} scenarios, precision {report['precision']:.1%}

Discovered box constraints (parameter bounds for the surprising region):
{json.dumps(report['box'], indent=2)}

Top surprising critical scenarios (highest Z score):
{json.dumps(report['top_surprising'][:3], indent=2)}

Please interpret these findings for the modeler."""

    return _call_claude(
        [{"role": "user", "content": prompt}],
        system=FINDINGS_SYSTEM,
    )


def propose_next_sweep(report: dict, config: dict) -> dict:
    """
    Ask Claude to propose the targeted follow-up sweep specification.
    Returns {"sweep_type": "targeted", "box": {param: (lo, hi)}, "n": int, "rationale": str}
    """
    prompt = f"""Given this PRIM findings report, propose a targeted follow-up sweep.

Current box constraints:
{json.dumps(report['box'], indent=2)}

Bias ratio: {report['bias_ratio']:.3f}
Completeness index: {report['completeness_index']:.3f}
Precision: {report['precision']:.1%}

SME context: {config['objective'].get('sme_context', '')}
Follow-up budget: {config['sampling'].get('followup_fraction', 0.4) * config['sampling']['sweep_budget']:.0f} scenarios

Output ONLY valid JSON with this structure:
{{
  "sweep_type": "targeted",
  "focus_parameters": {{"param_id": {{"lower": float_or_null, "upper": float_or_null}}}},
  "n": integer,
  "rationale": "one sentence"
}}"""

    reply = _call_claude(
        [{"role": "user", "content": prompt}],
        system="You are a precise JSON generator. Output only valid JSON, no prose.",
    )
    try:
        return json.loads(reply.strip())
    except Exception:
        # Fallback: return the full current box as the targeted region
        return {
            "sweep_type": "targeted",
            "focus_parameters": {item["parameter"]: {"lower": item["lower"], "upper": item["upper"]}
                                  for item in report["box"]},
            "n": int(config["sampling"]["sweep_budget"] * config["sampling"].get("followup_fraction", 0.4)),
            "rationale": "Densify within current PRIM box",
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

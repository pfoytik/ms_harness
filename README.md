# MS Harness

**AI-assisted critical scenario discovery for modeling and simulation tools.**

MS Harness wraps any file-based M&S tool with an AI-driven sampling campaign that finds *surprising* critical scenarios — situations where bad outcomes occur despite inputs that look safe. It uses PRIM with surprise scoring (Foytik et al., "Discovering More Critical Scenarios in Critical Infrastructure Simulations Using Scenario Potential") as its core analysis method and Claude as the AI reasoning layer.

---

## Motivation

Standard sensitivity analysis and Monte Carlo sweeps find the obvious critical scenarios: push the high-impact inputs up, bad things happen. MS Harness is designed to find the *non-obvious* ones — where the attacker succeeds, the system fails, or the outcome degrades through a combination of low-importance inputs that standard methods never explore.

The modeler defines what "surprising" means for their domain. The harness runs the experiments, scores every scenario for surprise, and uses the AI to interpret findings and direct the next sampling campaign.

---

## Architecture

```
harness_config.json          ← describes the tool, inputs, outputs, and objective
        │
        ▼
   AI Harness (harness.py)
        │
        ├── Planner       — designs LHS and targeted sweep batches
        ├── Runner        — executes scenarios via run_model.sh
        ├── Analyzer      — PRIM: finds surprising critical region
        └── Conversation  — Claude interprets findings, proposes next sweep
        │
        ▼
   Samples DB (SQLite)      ← all inputs, outputs, and findings stored here
        │
        ▼
   Tool Adapters (tools/<name>/)
        ├── input_processor.py   — translate scenario dict → tool input format
        ├── output_processor.py  — parse tool output → metrics dict
        └── run_model.sh         — shell wrapper to execute one scenario
```

The harness never touches the M&S tool directly. All tool-specific logic lives in the adapter. Connecting a new tool means writing those three files — the harness core stays unchanged.

---

## Quick Start

### 1. Install dependencies

```bash
cd ms_harness
pip install -r requirements.txt
```

### 2. Set your API key (optional — required only for AI interpretation)

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Without the key the harness still runs the full sampling and PRIM analysis — it just skips the natural language interpretation step.

### 3. Run a campaign

```bash
python harness.py run \
  --config tools/bayes_sampler/harness_config.json \
  --db results/demo.db \
  --sweeps 3
```

The harness will:
1. Run a smoke test to verify the adapter works
2. Execute an initial LHS sweep (N from config)
3. Analyze with PRIM and display the surprising region
4. Ask the AI to interpret and propose a targeted follow-up
5. Repeat for `--sweeps` iterations, each focused on the discovered region

### 4. Check results at any time

```bash
python harness.py status \
  --config tools/bayes_sampler/harness_config.json \
  --db results/demo.db
```

### 5. Chat about the findings

```bash
python harness.py chat \
  --config tools/bayes_sampler/harness_config.json \
  --db results/demo.db
```

Opens a free-form conversation with Claude about the latest analysis results, using your SME context from the config.

---

## Commands

| Command | Purpose |
|---|---|
| `run`    | Run a sweep campaign: LHS → analyze → targeted follow-up loop |
| `status` | Show DB summary and latest findings |
| `chat`   | Open AI conversation about current results |
| `new`    | Onboarding conversation to generate a new config (requires API key) |

### `run` options

| Flag | Default | Description |
|---|---|---|
| `--config` | required | Path to `harness_config.json` |
| `--db`     | required | SQLite DB path (created if absent) |
| `--sweeps` | 3 | Maximum number of sweeps |
| `--no-ai`  | false | Skip AI interpretation, run analysis only |

---

## Configuration (`harness_config.json`)

The config describes everything the harness needs to know about the tool and the analysis objective. It has four sections.

### `project`

```json
"project": {
  "name": "My Analysis",
  "created": "2026-11-11",
  "description": "Optional description"
}
```

### `tool`

```json
"tool": {
  "name": "My Tool Name",
  "version": "1.0",
  "domain": "domain description",
  "description": "Plain language: what does this tool simulate?",
  "adapter": "my_tool",
  "adapter_config": {
    "any_key": "any_value"
  }
}
```

`adapter` must match a subdirectory under `tools/`. The `adapter_config` block is passed as-is to the input processor and runner — put any tool-specific paths or settings here.

### `objective`

```json
"objective": {
  "critical_metric": "my_output_metric",
  "critical_direction": "below",
  "critical_threshold_quantile": 0.5,
  "surprise_definition": "Plain language: what makes a scenario surprising?",
  "element_potential": "paths_to_exit",
  "sme_context": "What you already know about this system."
}
```

| Field | Options | Meaning |
|---|---|---|
| `critical_direction` | `"below"` / `"above"` | Which direction of the metric is bad |
| `critical_threshold_quantile` | 0.0–1.0 | Q50 = bottom half of outcomes is "critical" |
| `element_potential` | `betweenness`, `paths_to_exit`, `likelihood` | How node importance is defined (see below) |
| `sme_context` | string | Expert knowledge — fed to Claude for interpretation |

**Element potential options:**

| Potential | Description | Best for |
|---|---|---|
| `paths_to_exit` | Fraction of all source→exit paths through each input node | Most robust default |
| `likelihood` | Mean LHS weight of each input across all runs | Systems with no clear topology |
| `betweenness` | Betweenness centrality of each node in the input graph | Confirming peripheral-node failures |

### `sampling`

```json
"sampling": {
  "initial_n": 200,
  "sweep_budget": 1000,
  "min_box_support": 30,
  "alpha": 0.05,
  "followup_fraction": 0.4
}
```

| Field | Description |
|---|---|
| `initial_n` | Scenarios in the first LHS sweep |
| `sweep_budget` | Total scenario budget across all sweeps |
| `min_box_support` | Minimum scenarios in a box (stops peeling if below this) |
| `alpha` | PRIM peeling fraction — proportion removed per step |
| `followup_fraction` | Fraction of budget used for each targeted follow-up sweep |

---

## Connecting a New Tool

To wire in a new M&S tool, create a directory under `tools/` and write three files.

```
tools/
└── my_tool/
    ├── input_processor.py
    ├── output_processor.py
    └── run_model.sh
```

### `input_processor.py`

Must implement two functions:

```python
def discover_inputs(adapter_config: dict) -> list[dict]:
    """
    Return the input parameter schema for this tool.
    Each dict: {"id": str, "description": str, "type": "float",
                "range": [lo, hi], "nominal": float}
    """
    ...

def process(scenario: dict, adapter_config: dict) -> str:
    """
    Translate a scenario dict {param_id: value} into the tool's
    native input format. Return path to the prepared input file.
    The caller will delete this file after the run.
    """
    ...
```

### `output_processor.py`

Must implement one function:

```python
def process(output_dir: str, scenario_id: str) -> dict:
    """
    Parse the tool's output files from output_dir.
    Return a dict of {metric_name: float_value}.
    The metric names must match those in harness_config outputs[].id.
    """
    ...
```

### `run_model.sh`

Receives five positional arguments:

```bash
#!/usr/bin/env bash
INPUT_FILE="$1"      # path to prepared input file
SCENARIO_ID="$2"     # unique ID string for this run
OUTPUT_DIR="$3"      # directory to write output files into
SAMPLER_PATH="$4"    # from adapter_config (tool executable path)
N_SAMPLES="$5"       # from adapter_config

# Run your tool here, writing outputs to $OUTPUT_DIR
my_tool "$INPUT_FILE" --output "$OUTPUT_DIR/result_${SCENARIO_ID}.json"
```

The harness calls this script via `bash run_model.sh ...` and expects exit code 0 on success.

### Add a `harness_config.json`

Copy `tools/bayes_sampler/harness_config.json` as a template, update the `tool`, `objective`, and `sampling` sections for your domain, and set `"adapter": "my_tool"`.

---

## Database Schema

All results are stored in a tool-agnostic SQLite database.

| Table | Contents |
|---|---|
| `sweeps` | Each sampling campaign sweep (type, size, status, timestamps) |
| `scenarios` | Each individual simulation run |
| `inputs` | Parameter values for each scenario (one row per parameter) |
| `outputs` | Metric values for each scenario (one row per metric) |
| `findings` | PRIM analysis reports stored as JSON (one per sweep) |

You can query the DB directly with any SQLite tool. Example:

```sql
-- Worst-performing scenarios
SELECT s.scenario_id, o.value AS resilience
FROM scenarios s
JOIN outputs o USING (scenario_id)
WHERE o.metric = 'overall_system_resilience'
ORDER BY o.value ASC
LIMIT 10;

-- Input weights for a specific scenario
SELECT parameter, value
FROM inputs
WHERE scenario_id = 42
ORDER BY CAST(parameter AS INTEGER);
```

---

## Demo: Attack Ladder Bayesian Network

The included `tools/bayes_sampler/` adapter connects to the attack ladder Bayesian network sampler from the `bayes_sampler` project. It was used to validate the PRIM methodology across 30 randomly generated attack networks.

**What it simulates:** Monte Carlo sampling of a Bayesian network where each node is an attack step and edge probabilities govern how likely an attacker traverses each path. `Overall System Resilience` measures the fraction of runs where no exit node was reached.

**Pre-configured for:** `net_28` — the richest network in the test set, with baseline resilience ~26% and the highest completeness index (CI=0.903) under the likelihood potential.

**Run the demo:**

```bash
python harness.py run \
  --config tools/bayes_sampler/harness_config.json \
  --db results/net28_demo.db \
  --sweeps 3
```

Expected output from a 200-scenario initial sweep: BR < 0.15×, CI > 0.70, a 4–8 parameter box identifying the surprising failure region.

---

## How the AI Helps

| Phase | What Claude does |
|---|---|
| Onboarding (`new`) | Interviews the SME, generates `harness_config.json` from conversation |
| After each sweep | Interprets PRIM findings in plain language grounded in `sme_context` |
| Follow-up planning | Proposes targeted sweep bounds based on current box and remaining budget |
| Chat (`chat`) | Answers free-form questions about results using latest findings as context |

The AI never modifies the tool, the adapter, or the DB directly. Its role is reasoning and communication — the structural pipeline runs with or without it.

---

## Project Structure

```
ms_harness/
├── harness.py              Entry point — Click CLI
├── requirements.txt
├── core/
│   ├── store.py            Tool-agnostic SQLite interface
│   ├── planner.py          LHS and targeted sweep design
│   ├── runner.py           Batch execution with progress display
│   ├── analyzer.py         PRIM analysis and metrics
│   └── conversation.py     Claude API via httpx
├── db/
│   └── schema.sql          Database schema
└── tools/
    └── bayes_sampler/      Demo adapter — Bayesian network sampler
        ├── harness_config.json
        ├── input_processor.py
        ├── output_processor.py
        └── run_model.sh
```

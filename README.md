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

Requires Python 3.10+.

```bash
cd ms_harness
pip install -r requirements.txt
```

### 2. Set up the AI layer (optional)

**With an API key:**

```bash
export ANTHROPIC_API_KEY=your_key_here
```

**Without an API key (manual mode):** you or an assistant can play the AI role by hand:

```bash
export HARNESS_AI_MODE=manual
```

Each AI call then writes its full prompt (system preamble + user message) to `ai_exchange/request_NNN.md` and waits until `ai_exchange/response_NNN.md` appears. The harness uses that file's contents as the AI reply. Proposal replies must be plain JSON (code fences are tolerated). Numbering continues from existing files, so clear `ai_exchange/` between campaigns if you want it to restart at 001. The exchange directory can be changed with `HARNESS_AI_EXCHANGE_DIR`.

With neither, the harness still runs the full sampling and PRIM analysis. It just skips interpretation, and follow-up sweeps target the raw PRIM box.

### 3. Run a campaign

```bash
python harness.py run \
  --config tools/bayes_sampler/harness_config.json \
  --db demo.db \
  --sweeps 3
```

A bare `--db` filename is stored in `db/` (here `db/demo.db`). A path containing a directory (`./demo.db`, `results/demo.db`) is used as given. DB files are git-ignored.

The harness will:
1. Run a smoke test to verify the adapter works
2. Execute an initial LHS sweep (N from config)
3. Analyze with PRIM and display the surprising region
4. Ask the AI to interpret the findings and propose a targeted follow-up (no proposal after the final sweep)
5. Repeat for `--sweeps` iterations, each focused on the region the AI (or PRIM) selects

### 4. Check results at any time

```bash
python harness.py status \
  --config tools/bayes_sampler/harness_config.json \
  --db demo.db
```

### 5. Chat about the findings

```bash
python harness.py chat \
  --config tools/bayes_sampler/harness_config.json \
  --db demo.db
```

Opens a free-form conversation with Claude about the latest analysis results, using the same SME and model-structure preamble as the sweep interpretations.

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
| `--db`     | required | SQLite DB (created if absent); a bare filename is stored in `db/` |
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
  "critical_threshold": null,
  "surprise_definition": "Plain language: what makes a scenario surprising?",
  "element_potential": "paths_to_exit",
  "sme_expected_drivers": [],
  "sme_context": "What you already know about this system."
}
```

| Field | Options | Meaning |
|---|---|---|
| `critical_direction` | `"below"` / `"above"` | Which direction of the metric is bad |
| `critical_threshold_quantile` | 0.0–1.0 | Q50 = bottom half of outcomes is "critical" |
| `critical_threshold` | number or `null` | Optional fixed threshold in the metric's own units (e.g. `20` = resilience ≤ 20% is critical) |
| `element_potential` | `betweenness`, `paths_to_exit`, `likelihood`, `sme` | How node importance is defined (see below) |
| `sme_expected_drivers` | list of input ids, or `{id: importance}` | Optional: inputs the SME expects to drive critical outcomes. Required for `sme`; otherwise shown to the AI, and each top scenario lists which of them were elevated |
| `sme_context` | string | Expert knowledge, placed in the AI's system preamble (see [How the AI Helps](#how-the-ai-helps)) |

**The critical threshold is fixed for the whole campaign.** If `critical_threshold` is set, it is used directly. Otherwise the threshold is `critical_threshold_quantile` of the **first LHS sweep**, and later targeted sweeps cannot move it. Targeted sweeps sample deliberately unrepresentative regions; recomputing the quantile from pooled data would make the definition of "critical" drift from sweep to sweep. The results table states the rule in metric units, e.g. `overall_system_resilience ≤ 25.5; q0.5 of initial LHS sweep 1`.

**Element potential options:**

| Potential | Description | Best for |
|---|---|---|
| `paths_to_exit` | Fraction of all source→exit paths through each input node | Most robust default |
| `likelihood` | Mean LHS weight of each input across all runs | Systems with no clear topology |
| `betweenness` | Betweenness centrality of each node in the input graph | Confirming peripheral-node failures |
| `sme` | The inputs listed in `sme_expected_drivers` | Treating critical scenarios that **contradict the SME** as surprising |

With `sme`, a critical scenario scores as surprising when the SME's expected drivers are *not* elevated, so PRIM searches directly for critical regions the expert did not anticipate. This matters when the SME's expectations and the network topology disagree about which nodes matter: the topological potentials treat structurally central nodes as "expected", even if the SME would be surprised by them.

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

It may also implement an optional hook that gives the AI structural facts about the model, so the AI does not depend on the SME having typed node IDs into the free-text context:

```python
def describe_model(adapter_config: dict) -> dict:
    """
    Optional. All keys optional:
    {"summary": str, "entry_nodes": [id], "exit_nodes": [id],
     "input_semantics": str,                      # what an input value means
     "nodes": {id: {"title": str, "parents": [id]}}}
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

Start from `config/harness_config.template.json`, which documents every field, or copy `tools/bayes_sampler/harness_config.json`. Update the `tool`, `objective`, and `sampling` sections for your domain, and set `"adapter": "my_tool"`.

**Machine-specific configs:** name them `*.local.json` (e.g. `harness_config.local.json`). That pattern is git-ignored, so local tool and data paths stay out of the repository.

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
| `ai_outputs` | AI interpretations and proposals (`kind` = `interpretation` / `proposal`), one row per call |

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

## Demo: Bayesian Attack Network

The included `tools/bayes_sampler/` adapter connects to the Bayesian attack network sampler from the `bayes_sampler` project. It was used to validate the PRIM methodology across 30 randomly generated attack networks.

**What it simulates:** Monte Carlo sampling of a Bayesian network where each node is an attack step and edge probabilities govern how likely an attacker traverses each path. `Overall System Resilience` measures the fraction of runs where no exit node was reached.

**Input semantics (foothold-gated):** each input is a node ID, and its value `w` is written into that node's conditional probability table as follows:

| Parent state | P(node compromised) |
|---|---|
| Entry node (no parents) | `w` |
| At least one parent compromised | `w` |
| No parent compromised | `leak` (`adapter_config.leak`, default 0) |

An attacker therefore needs a foothold before progressing, and the network topology shapes the outcome. Earlier versions wrote `w` into every row regardless of parent state. That removed all parent dependence, and resilience depended only on the exit-node weights. Results produced before this change may not reproduce.

A useful consequence: an exit can never be compromised with probability above its own weight, so resilience is bounded below by `100 × Π(1 − w_exit)`. A scenario can only be critical if that floor is below the threshold. To study upstream effects, hold the exit weights in a band where the floor straddles the threshold.

**Bundled sampler:** the adapter includes the Bayesian attack network sampler and network generator in `tools/bayes_sampler/sampler/`, developed by Ross Gore (see [Acknowledgments](#acknowledgments) and the README in that folder). If `adapter_config.sampler_path` is omitted or empty, `run_model.sh` uses the bundled `headless_sampler.js`. Set it only to use a different sampler build. Node.js is required. `run_model.sh` also detects whether a sampler takes the extra MITRE attack-group argument (newer versions) and passes the right number of placeholder arguments.

**Paths in `adapter_config`:** relative paths that exist under the repository root (e.g. `tools/bayes_sampler/nets/net_local_02.json`) are resolved against it, so configs work from any working directory.

**Pre-configured for:** `net_28` (baseline resilience ~26%). net_28 itself is not included: point `network_template` at your copy, ideally in a `harness_config.local.json`. A bundled example network, `tools/bayes_sampler/nets/net_local_02.json`, is the one used in [the SME-context case study](docs/case_study_sme_context_bayes_sampler.md). New test networks can be generated with the bundled `sampler/netGen.py --function createRandAG`. Its exit count is random, so screen generated networks for a small number of exits: a network with many exits gives near-0% resilience almost everywhere and leaves nothing to analyze.

**Run the demo:**

```bash
python harness.py run \
  --config tools/bayes_sampler/harness_config.json \
  --db net28_demo.db \
  --sweeps 3
```

---

## How the AI Helps

| Phase | What Claude does |
|---|---|
| Onboarding (`new`) | Interviews the SME, generates `harness_config.json` from conversation |
| After each sweep | Interprets PRIM findings, labelling critical scenarios as consistent with or contradicting the SME's expectations |
| Follow-up planning | Proposes targeted sweep bounds, given its own interpretation, the top scenarios and the budget (not after the final sweep) |
| Chat (`chat`) | Answers free-form questions about results using the latest findings as context |

**Shared preamble.** Every interpretation, proposal and chat call uses the same system preamble:

1. **Role and tool:** what the harness does, the tool description and the critical metric.
2. **Model structure:** taken from the adapter's `describe_model()` hook when present. This covers entry and exit nodes, node titles and parents, input semantics and each node's element potential. It comes from the model itself, not from the SME.
3. **SME prior understanding:** `sme_context`, `inputs.sme_notes`, `surprise_definition` and `sme_expected_drivers`, labelled as **hypotheses to test, not facts**.
4. **How to use the SME context:** label each critical scenario CONSISTENT WITH or CONTRADICTS the SME's expectations, lead with the contradicting ones (they are the surprising findings), say plainly when the data contradicts the SME overall, and separate real effects from noise and artifacts.

The per-sweep findings (threshold rule, metrics, box, top scenarios) go in the user message. Both AI outputs are saved in the `ai_outputs` table.

The SME context never enters the PRIM math directly. Only the structured fields (`critical_*`, `element_potential`, `sme_expected_drivers`) affect the analysis.

The AI never modifies the tool, the adapter, or the DB directly. Its role is reasoning and communication — the structural pipeline runs with or without it.

---

## Project Structure

```
ms_harness/
├── harness.py              Entry point — Click CLI
├── requirements.txt
├── config/
│   └── harness_config.template.json   Documented config template
├── core/
│   ├── store.py            Tool-agnostic SQLite interface
│   ├── planner.py          LHS and targeted sweep design
│   ├── runner.py           Batch execution with progress display
│   ├── analyzer.py         PRIM analysis and metrics
│   └── conversation.py     Claude API via httpx, AI preamble, manual mode
├── docs/
│   ├── related_work_and_gap.md
│   ├── case_study_sme_context_bayes_sampler.md   SME-context case study
│   └── case_study_data/    Case-study config, scenario CSV, AI prompts, analysis script
├── db/
│   ├── schema.sql          Database schema
│   └── *.db                Campaign DBs (git-ignored)
├── ai_exchange/            Manual-mode prompts/replies (git-ignored)
└── tools/
    └── bayes_sampler/      Demo adapter — Bayesian network sampler
        ├── sampler/            Bundled sampler (headless_sampler.js) and netGen.py
        ├── nets/               Example networks (net_local_02.json)
        ├── harness_config.json
        ├── harness_config.local.json   Machine-specific copy (git-ignored)
        ├── input_processor.py
        ├── output_processor.py
        └── run_model.sh
```

---

## Acknowledgments

The Bayesian attack network sampler (`headless_sampler.js`) and network generator (`netGen.py`) bundled in `tools/bayes_sampler/sampler/` were developed by **Ross Gore**, co-author and colleague on this work.

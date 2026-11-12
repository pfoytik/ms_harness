# Case Study: Testing an SME Expectation on a Bayesian Attack Network

## Overview

This case study follows one three-sweep MS Harness campaign on a generated Bayesian attack network. Its subject-matter expert (SME) context stated an expectation about which parts of the network drive attacker success. The campaign used targeted follow-up sweeps to test that expectation directly. It **partly confirmed and partly contradicted** it, and the contradicting part is the surprising finding:

1. **Confirmed:** the rung of nodes immediately before the exits acts as a *collective gate*. With that rung suppressed, no scenario was critical.
2. **Contradicted:** once that gate is open, whether a scenario becomes critical is decided mainly by a **mid-ladder chokepoint** (nodes 10–13), far from the end nodes. No individual near-exit node mattered much.

The campaign also showed where the harness itself fell short, which is documented in [Lessons for the Harness](#lessons-for-the-harness).

Date: 2026-11-11. AI layer: manual mode (`HARNESS_AI_MODE=manual`). The AI role was played by an assistant answering each `ai_exchange/request_NNN.md` prompt, exactly as an API model would receive it.

---

## Background: Why an Earlier Campaign Was Discarded

An earlier campaign on the same network gave findings that looked plausible but turned out to be artifacts. The bayes_sampler input processor wrote each node's sampled weight into **every row** of its conditional probability table (CPT), whatever its parents' states. That removed all parent dependence: the network behaved as 34 independent nodes, and resilience was explained almost perfectly by the two exit nodes alone:

```
resilience ≈ 100 × (1 − w33) × (1 − w34)      r = 0.998, mean error 0.9 pts (n = 200)
```

Two diagnostic sweeps confirmed it. With both exits held at or below 0.30, resilience never fell below 49.0%, the exact predicted floor. With both exits held at about 0.5 and all 32 other nodes free, resilience was 25.0% ± 1.4, which is pure Monte Carlo noise. The PRIM "surprising regions" from that campaign were artifacts of the surprise score, not attack paths.

The campaign also showed that the critical threshold drifted. It was recomputed as the median of all pooled data after every sweep, so it moved from resilience ≤ 19.5% to ≤ 64.8% to ≤ 27.2% as targeted sweeps sampled unrepresentative regions.

Both problems were fixed before the campaign described here:

| Fix | Change |
|---|---|
| Foothold-gated input mapping | P(compromise) = `w` if at least one parent is compromised (or the node is an entry node), otherwise `leak` (default 0) |
| Fixed critical threshold | Taken from the first LHS sweep (or set explicitly in `objective.critical_threshold`), never recomputed from targeted data |
| SME preamble | SME context placed in the AI system prompt as *hypotheses to test*; the AI labels each critical scenario as consistent with or contradicting it |

After the mapping fix, the exits-at-nominal control varied from 23% to 57% (sd 6.4) instead of a flat 25%, so the network structure now affects the outcome.

---

## Setup

### Network: `net_local_02`

The network was generated with Ross Gore's `netGen.py --function createRandAG` (bundled with the adapter at `tools/bayes_sampler/sampler/netGen.py`) (5 rungs; netGen is unseeded, so this exact network is not reproducible from the command alone). It was chosen from 40 generated candidates for having two exit nodes and a baseline resilience similar to the reference network net_28.

| Property | Value |
|---|---|
| Nodes / edges | 34 / 134 |
| Entry nodes (no parents) | 1–9, 32 |
| Exit nodes | 33, 34 |
| Baseline resilience (generated CPTs) | ~25% |

Rung structure, by distance to the nearest exit:

| Distance to exit | Nodes | Width |
|---|---|---|
| 0 (exits) | 33, 34 | 2 |
| 1 (near-exit rung) | 23–32 | 10 |
| 2 | 14–22 | 9 |
| 3 (mid-ladder rung) | 10–13 | **4** |
| 4 (entry rung) | 1–9 | 9 |

Every attack path crosses the 4-node mid-ladder rung. The `paths_to_exit` element potential ranks nodes 10 (0.068) and 12 (0.062) as the most important nodes after the exits.

### SME context

The SME supplied a single expectation (quoted verbatim from the config):

> "Large degredation or high probability of failure of segments that are closer to end nodes are more likely to cause critical scenarios."

No `sme_expected_drivers` were set. Surprise scoring used the default `paths_to_exit` potential.

### Campaign

```bash
HARNESS_AI_MODE=manual python harness.py run \
  --config tools/bayes_sampler/harness_config.local.json --db fixed_run.db --sweeps 3
```

Critical threshold: resilience ≤ **25.5%** (median of sweep 1), fixed for all three sweeps.

---

## Results

### Sweep 1: Initial LHS (200 scenarios, all inputs free)

| Harness metric | Value |
|---|---|
| Critical | 100 of 200 |
| PRIM box | 30 scenarios, precision 43.3% |
| Bias ratio / completeness | 0.037 / 0.691 |

**The exits dominate.** Exit weights alone explain 85% of the variance in resilience (linear R²). Adding the near-exit rung brings this to only 86%, and all 34 nodes reach 90%.

| Distance to exit | Mean correlation of node weight with resilience |
|---|---|
| 0 (exits) | −0.67 |
| 1 (23–32) | −0.03 |
| 2 (14–22) | +0.02 |
| 3 (10–13) | −0.10 |
| 4 (1–9) | −0.02 |

None of the 100 critical scenarios had both exits at or below their nominal weight. All five "top surprising" scenarios had one exit at 0.90 or above. The AI labelled them **consistent with** the SME.

**Why this is structural, not a finding.** Under foothold-gated semantics, an exit can never be compromised with probability above its own weight. Resilience is therefore bounded below:

```
resilience ≥ 100 × (1 − w33) × (1 − w34)
```

A scenario can be critical only if that floor is below 25.5%, which requires at least one exit weight well above 0.5. With this metric, "high exit compromise → critical" cannot be contradicted. The open question is which **upstream** segments supply the foothold.

**Proposal:** hold both exits at 0.45–0.60, where the exit-only floor (about 16–30%) straddles the threshold, so upstream structure decides criticality.

### Sweep 2: Exits held at 0.45–0.60 (400 scenarios)

Resilience ranged from 17.4% to 63.3% (median 26.6%), and 168 of 400 (42%) were critical. With the exits nearly fixed, they explain only 27% of the variance, and the upstream rungs can be compared directly:

| Added to exits | R² gain | Critical rate, rung low → high |
|---|---|---|
| **Mid-ladder rung (10–13)** | **+0.361** | **28% → 56%** |
| Near-exit rung (23–32) | +0.059 | 38% → 46% |
| Entry rung (1–9) | +0.020 | — |
| Rung 14–22 | +0.003 | — |

The nodes that most lower resilience are 10 (r = −0.35), 12 (−0.30), 11 (−0.26) and 13 (−0.24), all mid-ladder. This **contradicts** the SME expectation that segments closer to the end nodes drive critical outcomes.

Why: the near-exit rung is 10 nodes wide, and an exit needs only one compromised parent, so any single near-exit node is redundant. The mid-ladder rung is only 4 nodes wide and every path must cross it, so it is a genuine chokepoint.

**The harness's own metrics missed this.** The PRIM box had 20% precision, bias ratio 0, and completeness 0.398. Under `paths_to_exit`, nodes 10–13 have the highest potentials after the exits. Elevating them raises a scenario's potential and *lowers* its surprise score, so the surprise score treated mid-ladder-driven failures as expected and steered PRIM away from them. The topology-based potential and the SME's text disagreed about which nodes were the expected drivers, and the analysis followed the topology.

**Proposal:** keep the exit band and hold the whole near-exit rung (23–32) at or below 0.30. Any critical scenario that remains is critical without the segments closest to the end nodes.

### Sweep 3: Exits at 0.45–0.60, near-exit rung ≤ 0.30 (400 scenarios)

**No scenario was critical.** Resilience ranged from 30.8% to 82.3% (median 48.0%). Even the scenarios with the mid-ladder rung in its top decile stayed at or above 31.2%. Observed resilience sat a median 25.2 points above the exit-only floor, against 3.7 points in sweep 2: with the near-exit rung suppressed, the attacker rarely reached an exit at all. The mid-ladder rung still modulated resilience (r = −0.49), but it could not push any scenario below the threshold.

The harness reported 268 critical of 1000 pooled scenarios (unchanged from sweep 2), with a box of 0% precision.

Within this sweep, how low the near-exit rung was held explained much of the remaining variance (R² gain +0.435, against +0.268 for the mid-ladder rung). This is consistent with the gate interpretation: when the gate is mostly closed, small differences in how closed it is decide how often the attacker gets through.

---

## Conclusion: A Two-Stage Picture

| Stage | Role | Relation to SME context |
|---|---|---|
| Near-exit rung (23–32) | **Collective gate.** It must be broadly compromised for the attacker to reach the exits. No single node in it matters, because the exits have redundant parents. | **Confirms** the SME, at the level of the rung as a whole |
| Mid-ladder rung (10–13) | **Decider.** Given an open gate, it governs which scenarios become critical (R² +0.36; critical rate doubles). | **Contradicts** the SME, which looked toward the end nodes. This is the surprising finding. |

Suggested refinement of the SME context for future campaigns:

> Attacker success requires broad compromise of the segments adjacent to the end nodes, but no single such segment is decisive. Given that access, critical outcomes are driven by the narrow mid-ladder chokepoint (nodes 10–13) that every attack path must cross.

### Limitations

- One randomly generated network and one campaign. The two-stage pattern follows from the rung widths (wide and redundant near the exits, narrow in the middle) and may differ on networks with other shapes.
- Rung effects were measured with linear R² gains and median splits on 400 scenarios per sweep. Each scenario's resilience carries roughly ±1.4 points of Monte Carlo noise (1000 samples per run).
- The mid-ladder conclusion came from analysis of the full scenario DB, not from the harness's PRIM metrics or the AI prompts (see below).

---

## Lessons for the Harness

| Observation | Consequence | Status |
|---|---|---|
| The surprise score used topology (`paths_to_exit`), which rated the mid-ladder rung as *expected* | PRIM was steered away from the SME-contradicting finding | Mitigation exists: `element_potential: "sme"` with `sme_expected_drivers` = near-exit nodes 23–32 makes critical scenarios *without* those drivers score as surprising |
| The findings report has no per-input sensitivity summary | The AI could not see the mid-ladder effect from its prompt; it was established only by querying the DB | Open: add per-input / per-group sensitivity (e.g. critical rate low vs high) to the report |
| The interpretation prompt has no sweep history | The AI had to infer what the final sweep had sampled | Open: include each sweep's constraints and number of new critical scenarios |
| A box with no critical scenarios reports bias ratio 1.000 and completeness 0 | Default values read like results | Open: report "no critical scenarios in box" explicitly |
| A resilience floor of `100 × Π(1 − w_exit)` makes exit-driven criticality guaranteed | Unconstrained sweeps put most variance on the exits and hide upstream effects | Practice: hold exits in a band where the floor straddles the threshold when studying upstream structure |

The SME preamble did work as intended. Framing the SME context as hypotheses led the AI to design sweeps 2 and 3 as direct tests of the expectation, rather than densifying PRIM boxes. The labels it produced (consistent in sweep 1, undetermined from the prompt in sweep 2, and a collective gate in sweep 3) traced the two-stage conclusion as it emerged.

---

## Reproducing This Case Study

Case-study material is in [`case_study_data/sme_context_bayes_sampler/`](case_study_data/sme_context_bayes_sampler/). The network and simulation code ship with the `bayes_sampler` adapter:

| File | Contents |
|---|---|
| `tools/bayes_sampler/nets/net_local_02.json` | The exact network used (2.4 MB; CPTs of nodes with 9 parents have 1,024 rows) |
| `tools/bayes_sampler/sampler/` | The bundled sampler (`headless_sampler.js`) and network generator (`netGen.py`), developed by Ross Gore; see its README |
| `harness_config.case_study.json` | The campaign config. It uses the bundled sampler and a repo-relative network path, so it runs as-is |
| `scenarios.csv` | All 1000 scenarios: sweep, scenario ID, 34 input weights, resilience |
| `ai_prompts/` | The five AI exchanges: each `request_NNN.md` (full system preamble and user message) and the reply `response_NNN.md` |
| `analyze_case_study.py` | Recomputes every table in this document |

### Re-run the analysis (no simulation needed)

From the repository root:

```bash
python docs/case_study_data/sme_context_bayes_sampler/analyze_case_study.py
```

This reads `scenarios.csv` and the network, and prints, per sweep, the resilience range, the critical count, the exit-only R², each rung's R² gain and its critical rate when low versus high. Pass `--db db/<name>.db` to apply the same analysis to a new campaign.

### Re-run the campaign

Requires Node.js (v19.3 was used) for the bundled sampler. No other checkout is needed.

1. From the repository root, clear any earlier manual exchanges (so requests start at `request_001`) and run in manual mode:

   ```bash
   rm -f ai_exchange/*
   HARNESS_AI_MODE=manual python harness.py run \
     --config docs/case_study_data/sme_context_bayes_sampler/harness_config.case_study.json \
     --db case_study_rerun.db --sweeps 3
   ```

2. Replay the archived sweep proposals.

   The harness asks for, in order: interpretation, proposal, interpretation, proposal, interpretation. To reproduce the sweep design exactly, answer the two proposal requests with the archived replies: copy `ai_prompts/response_008.md` (exits 0.45–0.60) to `ai_exchange/response_002.md`, and `ai_prompts/response_010.md` (adds near-exit rung ≤ 0.30) to `ai_exchange/response_004.md`. Interpretation replies do not affect sampling, so any text works. Alternatively, write your own replies to the requests your run produces.

3. Analyze the new run:

   ```bash
   python docs/case_study_data/sme_context_bayes_sampler/analyze_case_study.py --db db/case_study_rerun.db
   ```

**Expect statistical, not exact, reproduction.** The LHS and targeted sweeps are unseeded and the sampler is stochastic (about ±1.4 points of resilience noise at 1000 samples per run). Individual scenario values will differ. The rung-level results (exit-only floor, the mid-ladder R² gain in sweep 2 and no critical scenarios in sweep 3) should hold.

---

## Recommended Next Campaign

1. Update `sme_context` to the refined statement above.
2. Set `element_potential: "sme"` and `sme_expected_drivers: ["23", …, "32"]`.
3. Hold the exits at 0.45–0.60 and leave the near-exit rung free, so the gate is usually open, and let PRIM search for critical regions in which the near-exit nodes are only moderately compromised.

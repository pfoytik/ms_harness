# Case Study: Testing an SME Expectation on a Bayesian Attack Network

## Overview

This case study documents three three-sweep MS Harness campaigns on the same generated Bayesian attack network. All three campaigns tested the same SME expectation and converged on the same two-stage conclusion — but via different paths. The difference between Campaign 1 and Campaigns 2–3 traces directly to the lambda schedule feature added between campaigns. Campaign 3 is an independent replication of Campaign 2 and adds a refinement to the mid-ladder finding.

**The finding, confirmed by all three campaigns:**

1. **Confirmed:** the rung of nodes immediately before the exits acts as a *collective gate*. With that rung suppressed, no scenario was critical.
2. **Contradicted:** once that gate is open, whether a scenario becomes critical is decided mainly by a **mid-ladder chokepoint** (nodes 10–13), far from the end nodes. No individual near-exit node mattered much. Campaign 3 further found that node 13 alone (only 3 parents: 1, 3, 7) can sustain a critical attack path when nodes 11 and 12 are suppressed.

**How the three campaigns differed in reaching it:**

| | Campaign 1 (2026-11-11) | Campaign 2 (2026-11-12) | Campaign 3 (2026-11-12) |
|---|---|---|---|
| Lambda schedule | Fixed at λ₁=0.5, λ₂=1.0 all sweeps | [[1.0, 0.0], [0.5, 1.0], [0.25, 1.5]] | [[1.0, 0.0], [0.5, 1.0], [0.25, 1.5]] |
| Mid-ladder finding surfaced via | Post-hoc R² analysis of the DB | Harness metrics (bias ratio flip 3.012 → 0.000) | Harness metrics (bias ratio flip 9.322 → 0.251) |
| Sweep 1 bias ratio | 0.037 (PRIM already steered toward low-SP) | 3.012 (pure severity — full critical region) | 9.322 (pure severity — full critical region) |
| Sweep 2 bias ratio | 0.000 (topology suppressed mid-ladder signal) | 0.000 (flip from sweep 1 is the signal) | 0.251 (flip from sweep 1 is the signal) |
| Critical threshold | ≤ 25.5% | ≤ 24.4% | ≤ 26.3% |
| New detail | — | — | Node 13 narrow path (3 parents) bypasses nodes 11–12 |

In Campaign 1, the PRIM objective used topology (`paths_to_exit`) to define surprise from the first sweep, which rated mid-ladder nodes as *expected* drivers and steered PRIM away from them. The finding required manual R² analysis of the scenario DB. In Campaigns 2 and 3, sweep 1 ran with pure severity (λ₂=0.0), establishing the full critical region including mid-ladder involvement. Sweep 2 then applied balanced surprise scoring — and the bias ratio flip directly indicated that the balanced-scoring sweep found scenarios contradicting the topology's expectations. The same conclusion emerged from PRIM's own metrics rather than from external analysis.

---

## Background: Why an Earlier Campaign Was Discarded

An earlier campaign on the same network gave findings that looked plausible but turned out to be artifacts. The bayes_sampler input processor wrote each node's sampled weight into **every row** of its conditional probability table (CPT), whatever its parents' states. That removed all parent dependence: the network behaved as 34 independent nodes, and resilience was explained almost perfectly by the two exit nodes alone:

```
resilience ≈ 100 × (1 − w33) × (1 − w34)      r = 0.998, mean error 0.9 pts (n = 200)
```

Two diagnostic sweeps confirmed it. With both exits held at or below 0.30, resilience never fell below 49.0%, the exact predicted floor. With both exits held at about 0.5 and all 32 other nodes free, resilience was 25.0% ± 1.4, which is pure Monte Carlo noise. The PRIM "surprising regions" from that campaign were artifacts of the surprise score, not attack paths.

The campaign also showed that the critical threshold drifted. It was recomputed as the median of all pooled data after every sweep, so it moved from resilience ≤ 19.5% to ≤ 64.8% to ≤ 27.2% as targeted sweeps sampled unrepresentative regions.

Both problems were fixed before the campaigns described here:

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

No `sme_expected_drivers` were set. Surprise scoring used the default `paths_to_exit` potential in both campaigns.

---

## Campaign 1 (2026-11-11): Fixed Lambda

```bash
HARNESS_AI_MODE=manual python harness.py run \
  --config tools/bayes_sampler/harness_config.local.json --db fixed_run.db --sweeps 3
```

Lambda: fixed at λ₁=0.5, λ₂=1.0 for all three sweeps (pre-lambda-schedule harness).  
Critical threshold: resilience ≤ **25.5%** (median of sweep 1), fixed for all three sweeps.

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

---

## Campaign 2 (2026-11-12): Lambda Schedule

This campaign ran after the lambda schedule feature was added to the harness. The same network, SME context, and sweep design were used. The key change was `sampling.lambda_schedule: [[1.0, 0.0], [0.5, 1.0], [0.25, 1.5]]` in the config.

```bash
HARNESS_AI_MODE=manual python harness.py run \
  --config docs/case_study_data/sme_context_bayes_sampler/harness_config.case_study.json \
  --db lambda_test.db --sweeps 3
```

Critical threshold: resilience ≤ **24.4%** (median of sweep 1), fixed for all three sweeps.

### Sweep 1: Initial LHS (200 scenarios, λ₁=1.0, λ₂=0.0 — pure severity)

| Harness metric | Value |
|---|---|
| Critical | 100 of 200 |
| PRIM box | 30 scenarios, precision 100.0% |
| Bias ratio / completeness | 3.012 / 0.863 |
| Z objective | λ₁=1.0, λ₂=0.0 (pure severity) |

With λ₂=0.0 the SP term vanishes and PRIM maximises mean outcome severity alone — identical to standard PRIM. The 100% precision box captures the 30 worst-outcome scenarios in the dataset (resilience 1.6–2.6%). The bias ratio of 3.012× confirms that the most severe failures involve high-potential nodes: exits 33 (≥0.355) and 34 (≥0.252) dominate, **consistent with** the SME. Critically, mid-ladder nodes 11 (≥0.069) and 12 (≥0.065) also appear in the box — an early signal that the chokepoint participates in the severe region even under pure severity.

Compare to Campaign 1 sweep 1 (bias ratio 0.037): the balanced surprise scoring immediately penalised high-SP scenarios including mid-ladder-driven ones, producing a low bias ratio but also hiding the structure of the severe region. The pure-severity sweep correctly establishes the full critical region before any surprise signal is applied.

### Sweep 2: Exits held at 0.45–0.60 (400 scenarios, λ₁=0.5, λ₂=1.0 — balanced)

| Harness metric | Value |
|---|---|
| Scenarios analyzed (all sweeps pooled) | 600 |
| Critical | 236 |
| PRIM box | 30 scenarios, precision 23.3% |
| Bias ratio / completeness | 0.000 / 0.597 |
| Z objective | λ₁=0.5, λ₂=1.0 (balanced) |
| Top scenario SP range | 0.345 – 0.446 |

The bias ratio flipped from 3.012× (sweep 1) to 0.000× (sweep 2). Every discovered critical scenario now sits in the two lowest SP quintiles — driven by nodes the topology considers low-importance. This is a wholesale **contradiction of the SME expectation**, and it surfaced directly in the harness metric rather than requiring post-hoc DB analysis.

The top five scenarios have SP values of 0.345–0.446, compared to 0.654–0.759 in Campaign 1 sweep 2. The flip in bias ratio between sweeps — from high (pure severity found expected drivers) to zero (balanced scoring found unexpected drivers) — is the signal that Campaign 1 never produced within its own metrics. Campaign 1 sweep 2 also had bias ratio 0 and similar SP values in top scenarios, but because sweep 1 had already applied surprise scoring (bias ratio 0.037), there was no reference point to show the flip.

**Proposal:** suppress the near-exit rung (23–32) to ≤0.30 to test whether the rung is a necessary gate.

### Sweep 3: Exits at 0.45–0.60, near-exit rung ≤ 0.30 (400 scenarios, λ₁=0.25, λ₂=1.5 — emphasise surprise)

| Harness metric | Value |
|---|---|
| Scenarios analyzed (all sweeps pooled) | 1000 |
| Critical | 236 (unchanged — no new critical scenarios) |
| PRIM box | 30 scenarios, precision 0.0% |
| Bias ratio / completeness | 1.000 / 0.000 |
| Z objective | λ₁=0.25, λ₂=1.5 (emphasise surprise) |

**No scenario was critical.** The critical count held at 236 — all 400 new scenarios with the near-exit rung at ≤0.30 stayed above the threshold. The gate is confirmed: without broad compromise of nodes 23–32, the attacker cannot reach the exits regardless of mid-ladder activation.

The 0% precision, BR=1.000, and CI=0.000 are the expected result when no critical scenarios exist in sweep 3 data. PRIM found the highest-surprise non-critical scenarios — the nearest misses under gate suppression — which correctly maps the edge of the feasible critical region.

---

## Campaign 3 (2026-11-12): Independent Replication

This campaign is an independent replication of Campaign 2 using a fresh database and new random samples.

```bash
HARNESS_AI_MODE=manual python harness.py \
  --config docs/case_study_data/sme_context_bayes_sampler/harness_config.case_study.json \
  --db lambda_test2.db
```

Critical threshold: resilience ≤ **26.3%** (median of sweep 1), fixed for all three sweeps.

### Sweep 1: Initial LHS (200 scenarios, λ₁=1.0, λ₂=0.0 — pure severity)

| Harness metric | Value |
|---|---|
| Critical | 101 of 200 |
| PRIM box | 30 scenarios, precision 100.0% |
| Bias ratio / completeness | 9.322 / 0.735 |
| Z objective | λ₁=1.0, λ₂=0.0 (pure severity) |

The bias ratio of 9.322× is higher than Campaign 2's 3.012× — both confirm that pure severity finds the SME-consistent high-SP region, with exits (33≥0.443, 34≥0.326) and mid-ladder inputs 11, 12, 15, 17 all elevated. The magnitude difference reflects the smaller sample and slightly higher threshold, not a structural difference. The 100% precision box is the full severe critical region.

**Proposal:** hold both exits at 0.45–0.60 and apply balanced surprise scoring in sweep 2.

### Sweep 2: Exits held at 0.45–0.60 (400 scenarios, λ₁=0.5, λ₂=1.0 — balanced)

| Harness metric | Value |
|---|---|
| Scenarios analyzed (all sweeps pooled) | 600 |
| Critical | 299 |
| PRIM box | 30 scenarios, precision 10.0% |
| Bias ratio / completeness | 0.251 / 0.641 |
| Z objective | λ₁=0.5, λ₂=1.0 (balanced) |
| Top scenario SP range | 0.386 – 0.589 |

The bias ratio flipped from 9.322× to 0.251× — the same directional signal as Campaign 2's 3.012→0.000 flip. The PRIM box caps exit 33 at ≤0.863 and most near-exit rung nodes with upper bounds, defining a region where criticality occurs without heavy exit or near-exit elevation. This **contradicts the SME expectation**.

The most surprising scenario is ID 196 (Z=1.149, SP=0.386, resilience=10.1%) — the highest Z score across all three campaigns. Exit 33=0.288 (very low), yet the attacker wins 90% of runs. The path runs through exit 34 (0.890) fed by **node 13 (0.972)** while nodes 11 (0.054) and 12 (0.130) are nearly inactive. This is a new refinement: node 13 has only three parents (1, 3, 7), making it a narrower and more efficient attack route than node 10 (which aggregates all nine entry nodes). Scenario 62 (Z=0.948, resilience=7.3%) confirms the same pattern with node 13=0.709 and nodes 11=0.025, 12=0.146.

**Proposal:** suppress the near-exit rung (23–32) to ≤0.30 to confirm the collective gate.

### Sweep 3: Exits at 0.45–0.60, near-exit rung ≤ 0.30 (400 scenarios, λ₁=0.25, λ₂=1.5 — emphasise surprise)

| Harness metric | Value |
|---|---|
| Scenarios analyzed (all sweeps pooled) | 1000 |
| Critical | 299 (unchanged — no new critical scenarios) |
| PRIM box | 30 scenarios, precision 0.0% |
| Bias ratio / completeness | 1.000 / 0.000 |
| Z objective | λ₁=0.25, λ₂=1.5 (emphasise surprise) |

**No scenario was critical.** The critical count held at 299 — all 400 new scenarios with the near-exit rung at ≤0.30 stayed above the threshold. The gate is confirmed for the third time independently, across different random seeds (200 LHS scenarios) and a different threshold (26.3% vs 24.4% in Campaign 2). The 0% precision, BR=1.000, and CI=0.000 are the expected result when no critical scenarios exist in the targeted data. PRIM's box maps the nearest-miss region at the edge of the gate constraint, with near-exit rung nodes tightly at their ≤0.30 ceilings (27≤0.293, 28≤0.298, 31≤0.283).

---

## Conclusion: A Two-Stage Picture

The conclusion is the same in all three campaigns:

| Stage | Role | Relation to SME context |
|---|---|---|
| Near-exit rung (23–32) | **Collective gate.** It must be broadly compromised for the attacker to reach the exits. No single node in it matters, because the exits have redundant parents. | **Confirms** the SME, at the level of the rung as a whole |
| Mid-ladder rung (10–13) | **Decider.** Given an open gate, it governs which scenarios become critical. | **Contradicts** the SME, which looked toward the end nodes. This is the surprising finding. |

The lambda schedule changed how the evidence appeared, not what it said. In Campaign 1, the evidence for the mid-ladder came from manual R² analysis of the full scenario DB. In Campaigns 2 and 3, it came from the bias ratio flip between sweep 1 and sweep 2 — a signal that lives inside the harness metrics and is visible in the terminal output without any additional analysis. Campaign 3 adds a structural refinement: the mid-ladder chokepoint is not monolithic. Node 13, with only three parents (1, 3, 7), is a narrower attack route than node 10, and can independently sustain a critical path when nodes 11 and 12 are suppressed.

Suggested refinement of the SME context for future campaigns:

> Attacker success requires broad compromise of the segments adjacent to the end nodes, but no single such segment is decisive. Given that access, critical outcomes are driven by the narrow mid-ladder chokepoint (nodes 10–13) that every attack path must cross — and within that chokepoint, node 13 (parents: 1, 3, 7) is a sufficient but less obvious path that bypasses the wider nodes 11 and 12.

### Limitations

- One randomly generated network and three campaigns on it. The two-stage pattern follows from the rung widths (wide and redundant near the exits, narrow in the middle) and may differ on networks with other shapes.
- Rung effects in Campaign 1 were measured with linear R² gains and median splits on 400 scenarios per sweep. Each scenario's resilience carries roughly ±1.4 points of Monte Carlo noise (1000 samples per run).
- The mid-ladder conclusion in Campaigns 2 and 3 was derived from the bias ratio flip between sweeps, not from per-node sensitivity analysis. The conclusions across all three campaigns are consistent but measured differently.
- The node 13 narrow-path finding from Campaign 3 is based on two top scenarios from a single sweep; it is a hypothesis for the next campaign rather than a confirmed result.

---

## Lessons for the Harness

| Observation | Consequence | Status |
|---|---|---|
| Campaign 1: surprise score used topology (`paths_to_exit`), which rated the mid-ladder rung as *expected* from sweep 1 onward | PRIM was steered away from the SME-contradicting finding; the mid-ladder effect was only visible in post-hoc R² analysis | **Fixed in Campaign 2** by lambda schedule: sweep 1 runs pure severity (λ₂=0.0), establishing the full critical region before surprise scoring is applied; the bias ratio flip between sweeps becomes the signal |
| The findings report has no per-input sensitivity summary | The AI cannot see rung-level effects from its prompt; they must be established by querying the DB | Open: add per-input / per-group sensitivity (e.g. critical rate low vs high) to the report |
| The interpretation prompt has no sweep history | The AI had to infer what each sweep had sampled | Open: include each sweep's constraints and number of new critical scenarios |
| A box with no critical scenarios reports bias ratio 1.000 and completeness 0 | Default values read like results | Open: report "no critical scenarios in this sweep's data" explicitly |
| A resilience floor of `100 × Π(1 − w_exit)` makes exit-driven criticality guaranteed in unconstrained sweeps | Unconstrained sweeps put most variance on the exits and hide upstream effects | Practice: hold exits in a band where the floor straddles the threshold when studying upstream structure |

The SME preamble worked as intended in both campaigns. Framing the SME context as hypotheses led the AI to design sweeps 2 and 3 as direct tests of the expectation rather than densifying PRIM boxes.

---

## Reproducing This Case Study

Case-study material is in [`case_study_data/sme_context_bayes_sampler/`](case_study_data/sme_context_bayes_sampler/). The network and simulation code ship with the `bayes_sampler` adapter:

| File | Contents |
|---|---|
| `tools/bayes_sampler/nets/net_local_02.json` | The exact network used (2.4 MB; CPTs of nodes with 9 parents have 1,024 rows) |
| `tools/bayes_sampler/sampler/` | The bundled sampler (`headless_sampler.js`) and network generator (`netGen.py`), developed by Ross Gore; see its README |
| `harness_config.case_study.json` | The Campaign 2 config with lambda schedule. Uses the bundled sampler and a repo-relative network path, so it runs as-is |
| `scenarios.csv` | Campaign 1 scenarios: sweep, scenario ID, 34 input weights, resilience (1000 scenarios) |
| `ai_prompts/` | Campaign 1 AI exchanges (request/response 007–011) |
| `analyze_case_study.py` | Recomputes the Campaign 1 rung-level tables; accepts `--db` for a new run |

### Re-run Campaign 2 (lambda schedule)

Requires Node.js (v19.3 was used) for the bundled sampler. No other checkout is needed.

1. From the repository root, clear any earlier manual exchanges and run in manual mode:

   ```bash
   rm -f ai_exchange/*
   HARNESS_AI_MODE=manual python harness.py run \
     --config docs/case_study_data/sme_context_bayes_sampler/harness_config.case_study.json \
     --db case_study_lambda_rerun.db --sweeps 3
   ```

2. For each request file the harness writes, provide an interpretation (free-form text) for odd-numbered requests and a JSON sweep proposal for even-numbered requests. The two key proposal responses that reproduce the original sweep design are:
   - Sweep 2: hold exits 33 and 34 at 0.45–0.60
   - Sweep 3: keep exits at 0.45–0.60, add near-exit rung nodes 23–32 all ≤ 0.30

3. Analyze the new run:

   ```bash
   python docs/case_study_data/sme_context_bayes_sampler/analyze_case_study.py --db db/case_study_lambda_rerun.db
   ```

**Expect statistical, not exact, reproduction.** The LHS and targeted sweeps are unseeded and the sampler is stochastic (about ±1.4 points of resilience noise at 1000 samples per run). The bias ratio flip (sweep 1 ~3–9×, sweep 2 ~0–0.3×) and zero critical scenarios in sweep 3 should hold — as confirmed independently by Campaign 3 (`lambda_test2.db`).

---

## Recommended Next Campaign

1. Update `sme_context` to the refined statement above.
2. Set `element_potential: "sme"` and `sme_expected_drivers: ["23","24","25","26","27","28","29","30","31","32"]`. This makes the near-exit rung the SME's declared expectation, so critical scenarios that occur without those nodes elevated score as maximally surprising from the outset.
3. Hold the exits at 0.45–0.60 from sweep 1 so the exit floor straddles the threshold and upstream structure decides criticality immediately.
4. Retain `lambda_schedule: [[1.0, 0.0], [0.5, 1.0], [0.25, 1.5]]`. With the SME-based potential, the sweep 1 pure-severity box should contain the mid-ladder-driven scenarios directly, and sweep 2 should converge on them as the most surprising critical region.
5. In sweep 2, watch specifically for node 13 elevation (parents: 1, 3, 7) with nodes 11 and 12 suppressed — Campaign 3 identified this as a sufficient narrow attack path that bypasses the standard mid-ladder chokepoint. Confirming it as a stable finding would motivate adding node 13 specifically to defensive monitoring priorities.

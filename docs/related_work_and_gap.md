# Related Work and Research Gap

## Overview

MS Harness wraps file-based modeling and simulation (M&S) tools in a sequential sampling campaign. Each round runs scenarios, finds critical regions with PRIM, and proposes the next sampling batch. An optional LLM layer interprets the results and proposes those batches. The harness takes the subject-matter expert's (SME's) stated expectations as hypotheses, and looks for critical scenarios that contradict them.

This document places the harness among existing work and states the gap it addresses. It follows the project's literature review, so every claim about prior work traces to a source with a recorded access level (see [References](#references)). Where a source was read only as an abstract, the text says so.

**Positioning in one sentence.** Scenario discovery already finds high-density critical regions, adaptive methods already sample near the boundary of a discovered region, and LLM agents already run simulation experiments. What has not been done is to direct the simulation budget at critical scenarios that the modeler's *stated assumptions* and the first-pass rules leave unexplained, and to measure how much an AI agent adds to that search.

---

## 1. Scenario discovery and exploratory modeling

**Foundations.** Exploratory modeling runs a model across many combinations of assumptions instead of predicting with one (Bankes 1993, *not yet verified*). Scenario discovery formalizes this: run a simulation ensemble, label the policy-relevant (critical) cases with a threshold, and describe them with interpretable rules, usually PRIM boxes (Friedman & Fisher 1999 [SD3]) or CART (Lempert et al. 2006 [SD4]; Groves & Lempert 2007 [SD5]; Lempert, Bryant & Bankes 2008 [SD1]; Bryant & Lempert 2010 [SD2]).

**Evaluation criteria are established.** Box sets are judged by coverage, density and interpretability. SD1 measures interpretability as the number of boxes and the maximum number of restricted dimensions, and recommends about three or four boxes with two or three restricted dimensions each. SD1 also reports that no single objective function reproduced every desired box set, and recommends choosing interactively along an efficient frontier. Kwakkel (2019) [SD9] treats scenario discovery as a many-objective problem over coverage, density and interpretability, and names consistency and diversity as further objectives that could be added.

**Extensions.**
- Oblique boxes (PCA-PRIM) [SD6].
- Bagged random boxes [SD7, abstract].
- Lenient and Gini objectives for heterogeneous uncertainties [SD8, abstract].
- Time-series and behavior-based scenario discovery [SD10, SD11, SD12].
- Multidimensional scenario discovery [SD18, abstract].
- Scenario sets selected for diversity across scenarios or outcomes [SD13, SD14, abstracts].
- An evaluation workflow for rule-induction algorithms [SD20, preview only].
- A taxonomy of vulnerability-analysis purposes and methods [SD24, abstract].

**Adaptive and simulation-in-the-loop scenario discovery.**
- SD1 noted that PRIM and CART work on fixed datasets and so cannot ask the simulator for new data. It proposed active learning as the remedy.
- REDS trains a surrogate to label many points for PRIM, which cuts the number of simulation runs needed [SD19].
- A KIT bachelor thesis adds active learning to REDS [SD23, abstract only].
- Adaptive sampling has been used to find new model behaviors [SD21, conference abstract].
- Torres Lahoz et al. (2025) [SD22, preprint] alternate between PRIM on surrogate-labeled points and new simulations sampled inside and on the borders of the current box. This is the closest prior work to the harness's follow-up sweeps.

**Implication for the harness.** Finding the most critical region first and then sampling for more is not new in itself: sequential PRIM covering, multi-box methods [SD7] and adaptive refinement of a box's boundary [SD22] already do it. Coverage, density and interpretability are the evaluation criteria, and the harness should report them in those terms (SD1, SD9). What the harness can add is a different *target* for the later sweeps: the part of the critical class that is not explained by the first-pass rules or by the modeler's stated expectations.

---

## 2. Modeler and analyst choices

**Choices made inside scenario discovery.**
- Hadjimichael et al. (2020) [SD15] read one fixed ensemble under 100 definitions of acceptable performance per water user. The drivers of consequential scenarios changed with the definition. This is an *outcome-side* choice.
- Quinn et al. (2020) [SD17] show that sensitivities, factor maps and robustness rankings change across four experimental designs for sampling hydrologic inputs. They argue that "scenario-neutral" sampling carries implicit assumptions. This is an *input-sampling* choice.
- Both use logistic-regression factor maps, not PRIM boxes.
- Steinmann et al. (2024) [SD12] acknowledge that the number of clusters, the PRIM density threshold and the choice of outcomes are analyst choices, but do not test their effect.

**Modeler choices in neighboring fields.**
- In hydrology, modelers given the same data produced widely different predictions [M2, M3], and four configuration decisions significantly changed simulated floods and droughts (Melsen et al. 2019) [M1].
- Many analysts working on one dataset reach different statistical conclusions [M4].
- Simulation credibility guidance says assumptions should be documented, reviewed and tested, but does not measure their effect [M6, M9].
- Sensitivity auditing and assumption-based planning make the same argument for policy models [M7, M8].
- Recent evacuation modeling separates measured inputs from expert-assigned assumptions, then perturbs one assumption once [E4].

**Implication for the harness.** The field acknowledges modeler choices, and has measured them on the output side and in input sampling, but scenario discovery tools do not take the modeler's expectations as an explicit input and test them. The harness does: `sme_expected_drivers` and `element_potential: "sme"` turn the SME's expectation into a structured hypothesis, and the AI preamble labels it a hypothesis to test, not a fact. "Surprise" in this document therefore means *discordant with a stated assumption*. It is relative to that assumption, not an absolute property of a scenario. Prefer "subjective modeling decisions" [M1] or "assumption dependence" over "modeler bias": there is no ground truth to be biased against.

---

## 3. Subgroup discovery

Subgroup discovery is the data-mining counterpart of scenario discovery. Subgroup *set* discovery penalizes redundancy among rules [SG1, abstract], and skyline methods trade off subgroup-set quality criteria [SG2, abstract]. Lijffijt et al. (2018) [SG3, abstract] look for subgroups that are interesting *given what the analyst already knows*, and support iterative mining. SG3 is the closest conceptual precedent for scoring findings against a prior. Its prior is statistical rather than a domain assumption, and it is not applied to simulation ensembles.

---

## 4. Critical-infrastructure vulnerability, importance and interdiction

**Multi-component failure is well established.**
- Importance measures extend to pairs and groups of components [CI14].
- Interdiction models choose the set of facilities whose joint loss does the most damage [CI13].
- Power-system screening searches for multiple contingencies that single-outage analysis misses [CI15, CI16].
- In road networks:
  - the critical combination of links is not the union of the individually critical ones [CI8, abstract];
  - optimization bounds performance under multi-link disruptions [CI9, CI10, abstracts];
  - simultaneous failures interact non-additively [CI12, abstract];
  - concurrent blockages and area-wide disruptions change the picture [CI7, CI11, abstracts].
- Topological and flow-based vulnerability measures often disagree [CI17, CI18, CI5].
- Reviews cover interdependent-infrastructure modeling, resilience definitions and sources of uncertainty [CI1–CI4].

**Implication for the harness.** Do not claim that combination failures, or failures driven by "low-importance" components, are an unrecognized problem. Structural methods (cut sets, interdiction, n−k screening) can also find chokepoints straight from topology, without simulation. Any benchmark must include such a structural baseline. Otherwise a reviewer can argue that a finding like "the 4-node mid-ladder rung decides criticality" ([case study](case_study_sme_context_bayes_sampler.md)) needed no simulation. The harness's value lies where structure alone is not enough: failures caused by stochastic dynamics, conditional probabilities or behavior, which a graph does not determine.

---

## 5. Reliability engineering and simulation-based testing

**Adaptive sampling toward failure.**
- Active-learning Kriging [R1, R3] and subset simulation [R2] sample adaptively toward the failure boundary in order to *estimate a failure probability*.
- Bryan et al. (2005) [R6] use active learning to find threshold boundaries of a function, as cited in SD1.
- In autonomous-vehicle testing, adaptive sampling toward performance boundaries, followed by clustering, produces diverse challenging scenarios [R4, R5, abstracts].
- Adaptive stress testing uses reinforcement learning to find likely failure trajectories (Lee et al. 2019, *not yet in the verified bibliography*).
- Falsification tools search for inputs that violate a temporal-logic specification (S-TaLiRo, Breach; *not yet verified*).

**Implication for the harness.** These methods aim at the failure boundary, a failure probability or a formally specified violation. The harness aims at *interpretable rules* for critical regions and at the part of the critical class its current rules do not cover. That difference must be shown empirically against at least one adaptive baseline, not just asserted.

---

## 6. LLM agents in simulation-based scenario generation and experiment design

*Added 2026-11-22 from a web search. All entries are preprints or papers read only as search snippets; read them before citing.*

**Safety-critical scenario generation.** LLMs now generate safety-critical driving scenarios for simulation testing:
- ChatScene turns language descriptions into executable CARLA scenarios [L1].
- Gao et al. (2025) use LLMs both to evaluate driving scenarios and to generate adversarial ones [L2].
- Tian et al. (2025) generate scenarios online with retrieval-augmented LLM agents [L3].

**Agentic experiment design with simulators.** LLM agents now design and run controlled experiments with simulation models:
- pharmaceutical process design [L4];
- particle-physics experiment design (GRACE) [L5];
- free-form exploration of unknown physical systems (SciExplorer) [L6];
- simulation-grounded decision support, where the simulator, not the LLM, is treated as the source of truth [L7].

**Evaluating the agent.** Recent work argues for evaluating an AI agent as a stochastic operator across many controlled runs, with cost and process treated as outcomes [L8]. This is the template the harness's own evaluation should follow.

**Implication for the harness.** An LLM proposing follow-up simulations is not novel in itself. Two things are not covered by the work above:
1. using the LLM inside scenario discovery under deep uncertainty, where the output is interpretable rules and the modeler's assumptions are explicit inputs;
2. measuring how much the LLM adds over a non-LLM acquisition rule at the same simulation budget.

---

## 7. Software tools

| Tool | What it provides | Relation to MS Harness |
|---|---|---|
| **EMA Workbench** (Kwakkel 2017) | The most complete open toolkit for exploratory modeling and scenario discovery. It offers sampling designs (LHS, full factorial, Sobol and others), PRIM (including multiple boxes) and CART, feature scoring and dimensional stacking, and robust decision making. Non-Python models connect through connectors (e.g. NetLogo, Vensim, Excel) and a file-model base class for wrapping external tools. | Builds on the same ideas. **Do not claim EMA Workbench cannot couple to file-based tools.** The harness's three-file adapter is a convenience, not a capability EMA lacks. EMA does not provide an assumption-conditioned objective, LLM interpretation or an LLM-proposed follow-up sweep. *Check the current connector list against the EMA documentation before publishing.* |
| **SALib** (Herman & Usher 2017) | Global sensitivity analysis: Sobol, Morris, FAST, delta moment-independent measure and others. | Complementary. Variance-based indices rank inputs but do not describe critical regions; an input with a low first-order index can still matter through interactions (visible in total-order indices). |
| **Dakota** (Sandia) | UQ, sensitivity analysis and optimization with a file-based interface to external simulators, including surrogate-based and adaptive reliability methods. | Closest precedent for file-based coupling and adaptive sampling. It has no scenario-discovery (PRIM-style) rule induction and no SME-assumption input. |
| **OpenMDAO** (NASA) | Multidisciplinary design analysis and optimization. | Different purpose (design optimization); listed for completeness. |

*The descriptions of Dakota and OpenMDAO are from general knowledge and have not been checked in the literature review.*

---

## 8. Capability comparison

"Partial" means the capability exists in a narrower form. The MS Harness column describes what the code does, not what has been shown to work. Rows marked † are open research questions (Section 9).

| Capability | EMA Workbench | SALib | Dakota | Adaptive SD (SD19, SD22) | LLM scenario agents (L1–L5) | MS Harness |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Coupling to non-Python / file-based tools | Yes | — | Yes | — | Tool-specific | Yes (three-file adapter) |
| Space-filling sampling (LHS etc.) | Yes | Yes | Yes | Yes | — | Yes |
| Interpretable critical regions (PRIM/CART) | Yes | — | — | Yes | — | Yes |
| Adaptive follow-up sampling | — | — | Yes (reliability/surrogate) | Yes (inside/near box) | Yes | Yes |
| Modeler's assumptions as explicit, testable input | — | — | — | — | Partial (prompted intent) | Yes (`sme_expected_drivers`, `element_potential`) |
| Objective targeting critical scenarios discordant with those assumptions | — | — | — | — | — | Partial † |
| LLM interpretation of findings | — | — | — | — | Yes | Yes |
| LLM-proposed next experiment | — | — | — | — | Yes | Yes † |
| Measured added value of the LLM | — | — | — | — | Rare | Not yet † |

---

## 9. The gap MS Harness addresses

**G1 — Assumption-conditioned residual search (primary).** Existing scenario discovery spends its budget on density: it finds the regions where critical cases are most concentrated, then refines or adds boxes. The harness separates two phases:
1. **Phase 1** finds the high-density critical regions with standard PRIM (λ₂ = 0, pure severity).
2. **Phase 2** spends the remaining simulation budget on critical scenarios that the Phase 1 rules *and* the modeler's stated assumptions leave unexplained.

"Unexplained" needs an operational definition. Candidates:
- **Discordant:** critical while the expected drivers are not elevated.
- **Residual:** not covered by a fixed budget of Phase 1 rules.
- **Interaction-driven:** misclassified by an additive model, or needing a box that restricts at least k inputs.

No work found in the review targets this set. The nearest are diversity-based selection [SD13, SD14], subgroups interesting relative to a prior [SG3] and box-boundary refinement [SD22].

**G2 — Measured contribution of an AI agent to scenario discovery.** LLM agents now generate scenarios and design simulation experiments (Section 6). The review found no study that measures, at equal simulation budget and with replication, whether an LLM finds more distinct critical mechanisms than non-LLM alternatives in scenario discovery. Those alternatives are random sampling, sequential PRIM covering, target-label PRIM, boundary-adaptive sampling and a rule-based acquisition policy. Treating the agent as a stochastic operator [L8] means replicating each campaign and reporting the spread.

**G3 — Loose coupling to file-based simulators (engineering, not a research claim).** The three-file adapter lowers the cost of connecting an existing simulator. EMA Workbench and Dakota already connect to external tools, so present this as a design choice that makes the harness practical, not as a gap in the literature.

**Claims this document does not make:**
- that multi-component or low-importance-component failures are unrecognized (Section 4);
- that coverage per interpretable rule is a new metric (SD1, SD9);
- that adaptive or simulation-in-the-loop scenario discovery is new (SD1, SD19, SD22);
- that the scenario-potential objective is the only way to separate expected from unexpected critical scenarios (target-label PRIM reproduces the effect; SG3 is a related idea);
- that the harness finds scenarios that are hard for *humans* to identify. That needs evidence from SMEs, such as predictions elicited before a campaign.

---

## 10. Open issues in the current implementation

These affect whether G1 and G2 can be demonstrated, and should be resolved before a benchmark study.

| Issue | Where | Consequence | Proposed fix |
|---|---|---|---|
| The surprise score Z = λ₁·t_norm − λ₂·SP_norm + λ₂ is computed for all scenarios, critical or not | `core/analyzer.py`, `_surprise_scores` | With λ = (0.5, 1.0), a harmless scenario with SP = 0 scores 1.0 and the most severe, highest-potential scenario scores 0.5. PRIM is drawn to quiet regions, so box precision drops (10–23% in the case study's balanced sweeps). | Condition on criticality: maximize coverage of low-SP critical scenarios subject to a density floor (τ-constrained frontier), or use target-label PRIM with label = critical ∧ low SP |
| SP counts inputs above their mean, and PRIM can cap those inputs | `_scenario_potential` | A low bias ratio follows mechanically whenever λ₂ > 0, so a "bias ratio flip" is not by itself evidence of a finding | Report the flip alongside a fixed-λ control on the same sample, and keep SP fixed per scenario rather than re-deriving it from the box |
| `nominal` is the column mean of the pooled data | `analyze` | The meaning of "elevated" drifts as targeted sweeps add data (the same drift already fixed for the threshold) | Freeze nominal values from the input schema or the first LHS sweep |
| The default threshold is the median (q0.5) | config | Half of all scenarios count as critical, which leaves no rare regime to study | Use a tail quantile (q0.1 or q0.05) or a threshold in metric units with operational meaning |
| Sampling is unseeded and netGen is unseeded | `core/planner.py`, `netGen.py` | Campaigns are reproducible only statistically | Seed and log all random number generators |

---

## 11. Planned evaluation

The evaluation design is still to be written up separately. It should include:
- **A benchmark with planted mechanisms.** Generated attack networks containing known critical mechanisms (a narrow chokepoint, a k-way interaction, and a decoy that matches the SME's expectation), so that recall can be measured against ground truth.
- **A second domain** for external validity: the evacuation simulation from the TRB paper.
- **Baselines at equal simulation budget:**
  - random LHS;
  - sequential PRIM covering;
  - target-label PRIM;
  - SD22-style boundary sampling;
  - a structural (cut-set) baseline;
  - rule-based acquisition without an LLM.
- **LLM conditions:** with and without the SME context, with node labels shuffled, and across models.
- **Replication:** at least 10 replicate campaigns per condition.
- **Metrics:**
  - recall of planted mechanisms per simulation run;
  - runs needed to first discovery;
  - false discoveries, checked by re-simulating each rule on fresh runs;
  - rule complexity (number of boxes and restricted dimensions).
- **Human-difficulty check:** SME predictions elicited blind, before each campaign.

---

## References

Keys match the project's `verified_bibliography.md`. Access levels: **Full** (full text read), **Partial** (parts read), **Abstract**, **Secondary** (confirmed through another paper's reference list), **Snippet** (search result only). Entries without a key have not been checked in the literature review.

### Scenario discovery and exploratory modeling
- [SD1] Lempert, R.J., Bryant, B.P., Bankes, S.C. (2008). *Comparing Algorithms for Scenario Discovery.* RAND WR-557-NSF. https://www.rand.org/pubs/working_papers/WR557.html — Full
- [SD2] Bryant, B.P., Lempert, R.J. (2010). Thinking inside the box: A participatory, computer-assisted approach to scenario discovery. *Technological Forecasting and Social Change* 77(1), 34–49. — Secondary
- [SD3] Friedman, J.H., Fisher, N.I. (1999). Bump hunting in high-dimensional data. *Statistics and Computing* 9, 123–143. https://doi.org/10.1023/A:1008894516817 — Secondary
- [SD4] Lempert, R.J., Groves, D.G., Popper, S.W., Bankes, S.C. (2006). A general, analytic method for generating robust strategies and narrative scenarios. *Management Science* 52(4), 514–528. — Secondary
- [SD5] Groves, D.G., Lempert, R.J. (2007). A new analytic method for finding policy-relevant scenarios. *Global Environmental Change* 17, 73–85. https://doi.org/10.1016/j.gloenvcha.2006.11.006 — Secondary
- [SD6] Dalal, S., Han, B., Lempert, R., Jaycocks, A., Hackbarth, A. (2013). Improving scenario discovery using orthogonal rotations. *Environmental Modelling & Software* 48, 49–64. https://doi.org/10.1016/j.envsoft.2013.05.013 — Secondary
- [SD7] Kwakkel, J.H., Cunningham, S.C. (2016). Improving scenario discovery by bagging random boxes. *Technological Forecasting and Social Change* 111, 124–134. https://doi.org/10.1016/j.techfore.2016.06.014 — Abstract
- [SD8] Kwakkel, J.H., Jaxa-Rozen, M. (2016). Improving scenario discovery for handling heterogeneous uncertainties and multinomial classified outcomes. *Environmental Modelling & Software* 79, 311–321. https://doi.org/10.1016/j.envsoft.2015.11.020 — Abstract
- [SD9] Kwakkel, J.H. (2019). A generalized many-objective optimization approach for scenario discovery. *Futures & Foresight Science* 1(2), e8. https://doi.org/10.1002/ffo2.8 — Full
- [SD10] Kwakkel, J.H., Auping, W.L., Pruyt, E. (2013). Dynamic scenario discovery under deep uncertainty: The future of copper. *Technological Forecasting and Social Change* 80(4), 789–800. https://doi.org/10.1016/j.techfore.2012.09.012 — Abstract
- [SD11] Steinmann, P., Auping, W.L., Kwakkel, J.H. (2020). Behavior-based scenario discovery using time series clustering. *Technological Forecasting and Social Change* 156, 120052. https://doi.org/10.1016/j.techfore.2020.120052 — Abstract
- [SD12] Steinmann, P., van der Zwet, K., Keijser, B. (2024). Simulation-based generation and analysis of multidimensional future scenarios with time series clustering. *Futures & Foresight Science* 6(4), e194. https://doi.org/10.1002/ffo2.194 — Partial
- [SD13] Guivarch, C., Rozenberg, J., Schweizer, V. (2016). The diversity of socio-economic pathways and CO2 emissions scenarios. *Environmental Modelling & Software* 80, 336–353. — Abstract
- [SD14] Carlsen, H., Lempert, R., Wikman-Svahn, P., Schweizer, V. (2016). Choosing small sets of policy-relevant scenarios by combining vulnerability and diversity approaches. *Environmental Modelling & Software* 84, 155–164. https://doi.org/10.1016/j.envsoft.2016.06.011 — Abstract
- [SD15] Hadjimichael, A., Quinn, J., Wilson, E., Reed, P., Basdekas, L., Yates, D., Garrison, M. (2020). Defining robustness, vulnerabilities, and consequential scenarios for diverse stakeholder interests in institutionally complex river basins. *Earth's Future* 8(7), e2020EF001503. https://doi.org/10.1029/2020EF001503 — Full
- [SD17] Quinn, J.D., Hadjimichael, A., Reed, P.M., Steinschneider, S. (2020). Can exploratory modeling of water scarcity vulnerabilities and robustness be scenario neutral? *Earth's Future* 8(11). https://doi.org/10.1029/2020EF001650 — Full
- [SD18] Gerst, M.D., Wang, P., Borsuk, M.E. (2013). Discovering plausible energy and economic futures under global change using multidimensional scenario discovery. *Environmental Modelling & Software* 44, 76–86. https://doi.org/10.1016/j.envsoft.2012.09.001 — Abstract
- [SD19] Arzamasov, V., Böhm, K. (2021). REDS: Rule Extraction for Discovering Scenarios. *SIGMOD '21*. https://doi.org/10.1145/3448016.3457301 — Partial
- [SD20] [Authors to confirm] (2026). Evaluating rule induction algorithms for scenario discovery. *Environmental Modelling & Software* 203, 107006. — Partial (preview)
- [SD21] Islam, T., Pruyt, E. (2016). Scenario generation using adaptive sampling: The case of resource scarcity. *Environmental Modelling & Software* 79, 285–299. — Abstract
- [SD22] Torres Lahoz, L., Lima Azevedo, C., Ancora, L., Morgado, P., Kotval, Z., Miranda, B., Camara Pereira, F. (2025). Scenario Discovery for Urban Planning: The Case of Green Urbanism and the Impact on Stress. arXiv:2504.02905. — Full (preprint)
- [SD23] Emmanouilidis, E. (2020). Scenario Discovery with Active Learning. Bachelor thesis, KIT. — Abstract
- [SD24] Bonham, N., Kasprzyk, J., Zagona, E. (2025). Taxonomy of purposes, methods, and recommendations for vulnerability analysis. *Environmental Modelling & Software* 183, 106269. https://doi.org/10.1016/j.envsoft.2024.106269 — Abstract
- [SD25] Auping, W.L., Pruyt, E., Kwakkel, J.H. (2014). Dealing with multiple models in system dynamics. *International Journal of System Dynamics Applications* 3(4), 17–35. https://doi.org/10.4018/ijsda.2014100102 — Abstract

### Subgroup discovery
- [SG1] van Leeuwen, M., Knobbe, A. (2012). Diverse subgroup set discovery. *Data Mining and Knowledge Discovery* 25. https://doi.org/10.1007/s10618-012-0273-y — Abstract
- [SG2] van Leeuwen, M., Ukkonen, A. (2013). Discovering skylines of subgroup sets. *ECML PKDD 2013*. https://doi.org/10.1007/978-3-642-40994-3_18 — Abstract
- [SG3] Lijffijt, J., Kang, B., Duivesteijn, W., Puolamäki, K., Oikarinen, E., De Bie, T. (2018). Subjectively interesting subgroup discovery on real-valued targets. *IEEE ICDE 2018*. https://doi.org/10.1109/ICDE.2018.00148 — Abstract

### Critical infrastructure
- [CI1] Ouyang, M. (2014). Review on modeling and simulation of interdependent critical infrastructure systems. *RESS* 121, 43–60. https://doi.org/10.1016/j.ress.2013.06.040 — Partial
- [CI2] Hosseini, S., Barker, K., Ramirez-Marquez, J.E. (2016). A review of definitions and measures of system resilience. *RESS* 145, 47–61. https://doi.org/10.1016/j.ress.2015.08.006 — Abstract
- [CI3] Rinaldi, S.M., Peerenboom, J.P., Kelly, T.K. (2001). Identifying, understanding, and analyzing critical infrastructure interdependencies. *IEEE Control Systems Magazine* 21(6), 11–25. https://doi.org/10.1109/37.969131 — Abstract
- [CI4] Reilly, A.C., Baroud, H., Flage, R., Gerst, M.D. (2021). Sources of uncertainty in interdependent infrastructure and their implications. *RESS* 213, 107756. — Partial
- [CI5] Mattsson, L.-G., Jenelius, E. (2015). Vulnerability and resilience of transport systems. *Transportation Research Part A* 81, 16–34. https://doi.org/10.1016/j.tra.2015.06.002 — Secondary
- [CI7] Jenelius, E., Mattsson, L.-G. (2012). Road network vulnerability analysis of area-covering disruptions. *Transportation Research Part A* 46(5), 746–760. — Abstract
- [CI8] Wang, D.Z.W., Liu, H., Szeto, W.Y., Chow, A.H.F. (year to confirm). Identification of critical combination of vulnerable links in transportation networks. *Transportmetrica A*. — Abstract
- [CI9] Xu, X., Chen, A., Yang, C., et al. (2018). Upper and lower bounds of transportation network vulnerability under simultaneous disruptions of multiple links. *Transportation Research Part C* 94, 338–353. https://doi.org/10.1016/j.trc.2017.08.015 — Abstract
- [CI10] Gu, Y., Chen, A., Xu, X. (2023). Measurement and ranking of important link combinations. *Transportation Research Part B* 167, 118–144. — Abstract
- [CI11] Vodák, R., Křivánková, Z., Bíl, M. (2022). Identification of road links with the gravest network impacts when blocked concurrently. *EJTIR* 22(1). https://doi.org/10.18757/ejtir.2022.22.1.5657 — Abstract
- [CI12] Kaiser, F., Strake, J., Witthaut, D. (2020). Collective effects of link failures in linear flow networks. *New Journal of Physics* 22(1). — Abstract
- [CI13] Church, R.L., Scaparra, M.P., Middleton, R.S. (2004). Identifying critical infrastructure: The median and covering facility interdiction problems. *Annals of the AAG* 94(3), 491–502. https://doi.org/10.1111/j.1467-8306.2004.00410.x — Abstract
- [CI14] Kuo, W., Zhu, X. (2012). *Importance Measures in Reliability, Risk, and Optimization.* Wiley. — Catalog record
- [CI15] Eppstein, M.J., Hines, P.D.H. (2012). A "Random Chemistry" algorithm for identifying collections of multiple contingencies that initiate cascading failure. *IEEE Transactions on Power Systems* 27(3), 1698–1705. — Partial
- [CI16] Rezaei, P., Hines, P.D.H., Eppstein, M.J. (2015). Estimating cascading failure risk with Random Chemistry. *IEEE Transactions on Power Systems* 30(5), 2726–2735. https://doi.org/10.1109/TPWRS.2014.2361735 — Abstract
- [CI17] Hines, P., Cotilla-Sanchez, E., Blumsack, S. (2010). Do topological models provide good information about vulnerability in electric power networks? *Chaos* 20, 033122. — Abstract
- [CI18] Ouyang, M., Zhao, L., Pan, Z., Hong, L. (2014). Comparisons of complex network based models and direct current power flow model to analyze power grid vulnerability under intentional attacks. *Physica A* 403, 45–53. — Abstract

### Reliability and simulation-based testing
- [R1] Echard, B., Gayton, N., Lemaire, M. (2011). AK-MCS: An active learning reliability method combining Kriging and Monte Carlo simulation. *Structural Safety* 33(2), 145–154. https://doi.org/10.1016/j.strusafe.2011.01.002 — Record
- [R2] Au, S.-K., Beck, J.L. (2001). Estimation of small failure probabilities in high dimensions by subset simulation. *Probabilistic Engineering Mechanics* 16(4), 263–277. — Abstract
- [R3] [Authors to confirm] (2021). Active learning for structural reliability: survey, general framework and benchmark. arXiv:2106.01713. — Abstract
- [R4] Mullins, G.E., Stankiewicz, P.G., Gupta, S.K. (2017). Automated generation of diverse and challenging scenarios for test and evaluation of autonomous vehicles. *IEEE ICRA 2017*. https://doi.org/10.1109/ICRA.2017.7989173 — Abstract
- [R5] Mullins, G.E., Stankiewicz, P.G., Hawthorne, R.C., Gupta, S.K. (2018). Adaptive generation of challenging scenarios for testing and evaluation of autonomous vehicles. *Journal of Systems and Software*. — Record
- [R6] Bryan, B., Schneider, J., Nichol, R.C., Miller, C.J., Genovese, C.R., Wasserman, L. (2005). Active learning for identifying function threshold boundaries. *NIPS 17*. — Secondary
- Lee, R., Mengshoel, O.J., Saksena, A., et al. (2019). Adaptive stress testing: Finding likely failure events with reinforcement learning. arXiv:1811.02188. — *Not yet verified*

### Modeler choices and assumptions
- [M1] Melsen, L.A., Teuling, A.J., Torfs, P.J.J.F., et al. (2019). Subjective modeling decisions can significantly impact the simulation of flood and drought events. *Journal of Hydrology* 568, 1093–1104. https://doi.org/10.1016/j.jhydrol.2018.11.046 — Abstract
- [M2] Holländer, H.M., Bormann, H., Blume, T., et al. (2014). Impact of modellers' decisions on hydrological a priori predictions. *HESS* 18(6), 2065–2085. https://doi.org/10.5194/hess-18-2065-2014 — Abstract
- [M3] Holländer, H.M., Blume, T., Bormann, H., et al. (2009). Comparative predictions of discharge from an artificial catchment (Chicken Creek) using sparse data. *HESS* 13(11), 2069–2094. https://doi.org/10.5194/hess-13-2069-2009 — Abstract
- [M4] Silberzahn, R., Uhlmann, E.L., Martin, D.P., et al. (2018). Many analysts, one data set. *Advances in Methods and Practices in Psychological Science* 1(3), 337–356. https://doi.org/10.1177/2515245917747646 — Record
- [M6] Law, A.M. (2019; 2022). How to build valid and credible simulation models. *Proc. Winter Simulation Conference*. — Partial
- [M7] Saltelli, A., Bammer, G., Bruno, I., et al. (2020). Five ways to ensure that models serve society: A manifesto. *Nature* 582, 482–484. https://doi.org/10.1038/d41586-020-01812-9 — Record
- [M8] Dewar, J.A. (2002). *Assumption-Based Planning.* Cambridge University Press. — Front matter
- [M9] Law, A.M., Kelton, W.D. (1982). *Simulation Modeling and Analysis.* McGraw-Hill. — Catalog record
- [E4] Chang, S., Comfort, L., Soga, K., Li, P., Wang, Y. (2026). Multiscale wildfire-evacuation modeling: Assessing differential access to safe egress in Marin County, CA. *Risk Analysis* 46(9), e70338. https://doi.org/10.1111/risa.70338 — Full

### LLM agents and simulation (added 2026-11-22; Snippet access, verify before citing)
- [L1] ChatScene: LLM-based agent generating safety-critical scenarios for autonomous vehicles in CARLA. https://github.com/javyduck/ChatScene ; paper via https://par.nsf.gov/servlets/purl/10524843 — Snippet
- [L2] Gao, Y., Piccinini, M., Moller, K., Betz, J. (2025). From Words to Collisions: LLM-Guided Evaluation and Adversarial Generation of Safety-Critical Driving Scenarios. arXiv:2502.02145. — Snippet
- [L3] Tian, Y., et al. (2025). Seeking to Collide: Online Safety-Critical Scenario Generation for Autonomous Driving with Retrieval Augmented Large Language Models. arXiv:2505.00972. — Snippet
- [L4] Xia, Y., Weyrich, M., Jazdi, N., Stümpfle, J., Sigel, J., Narla, A. (2026). LLM Agents Perform Controlled Experiments Using Simulation Models. arXiv:2608.23622. — Snippet
- [L5] GRACE: an Agentic AI for Particle Physics Experiment Design and Simulation (2026). arXiv:2602.15039. — Snippet
- [L6] Agentic Exploration of Physics Models (SciExplorer) (2025). arXiv:2509.24978. — Snippet
- [L7] Simulation Agent: A Framework for Integrating Simulation and Large Language Models for Enhanced Decision-Making (2025). arXiv:2505.13761. — Snippet
- [L8] An Experimental Design Approach to Evaluating Agentic AI's Autonomous Model Discovery (2026). arXiv:2607.06413. — Snippet

### Software (not checked in the literature review)
- Kwakkel, J.H. (2017). The Exploratory Modeling Workbench: An open source toolkit for exploratory modeling, scenario discovery, and (multi-objective) robust decision making. *Environmental Modelling & Software* 96, 239–250.
- Herman, J., Usher, W. (2017). SALib: An open-source Python library for sensitivity analysis. *Journal of Open Source Software* 2(9), 97.

### This project
- Foytik, P., et al. Discovering More Critical Scenarios in Critical Infrastructure Simulations Using Scenario Potential. *(in preparation)*

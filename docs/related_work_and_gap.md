# Related Work and Research Gap

## Overview

MS Harness sits at the intersection of exploratory modeling, scenario discovery, and AI-assisted analysis. This document surveys the existing landscape of M&S sensitivity and scenario analysis tools and identifies the specific gap that MS Harness is designed to fill.

---

## Existing Tools and Frameworks

### EMA Workbench

**Repository:** github.com/quakke/EMA-workbench  
**Origin:** Delft University of Technology — Policy Analysis and Decision Support group  
**Language:** Python

The EMA (Exploratory Modeling and Analysis) Workbench is the most mature open framework for scenario discovery in the M&S community. It supports Latin Hypercube Sampling, design-of-experiments, and includes a Python implementation of PRIM (Patient Rule Induction Method) for identifying critical scenario regions.

**What it does well:**
- Principled LHS sweep design
- PRIM-based scenario discovery
- Scenario visualization (feature scoring, dimensional stacking)
- Multi-model ensemble support

**Limitations relevant to our work:**
- Models must be Python-callable — no support for file-based or subprocess-driven tools without custom wrapping
- PRIM maximizes critical density (fraction of bad outcomes in box), not *surprise* — it will always find the obvious high-impact region, not the unexpected one
- No AI interpretation layer
- No adaptive sweep direction based on prior findings
- No concept of element potential or scenario potential

---

### SALib — Sensitivity Analysis Library

**Repository:** github.com/SALib/SALib  
**Language:** Python

SALib implements a suite of global sensitivity analysis methods: Sobol indices, Morris screening, FAST, RBD-FAST, Delta Moment-Independent Measure, and others. It is widely used in environmental modeling, hydrology, and systems engineering.

**What it does well:**
- Rigorous variance-based sensitivity decomposition
- Well-documented and widely cited
- Identifies which inputs explain the most output variance

**Limitations relevant to our work:**
- Variance decomposition ≠ scenario discovery — a parameter with low Sobol index can still participate in a critical scenario combination
- No concept of a "critical scenario region" or box
- No notion of surprise or low-potential failure
- No AI, no adaptive sampling, no findings interpretation

---

### Dakota — Design Analysis Kit for Optimization and Terascale Applications

**Origin:** Sandia National Laboratories  
**Language:** C++ with Python and input-file interfaces

Dakota is a heavyweight framework for uncertainty quantification, sensitivity analysis, and optimization in high-performance computing contexts. It supports a wide range of sampling methods and can call external executables through a file-based interface.

**What it does well:**
- File-based model coupling (closest to our adapter pattern among existing tools)
- Large-scale parallel execution
- Broad method library: LHS, quasi-Monte Carlo, Sobol, DACE, surrogate modeling

**Limitations relevant to our work:**
- No scenario discovery or PRIM-like region identification
- Configuration is complex and not SME-friendly
- No AI layer, no surprise score, no adaptive sweep guidance
- Designed for optimization and UQ, not for finding the unexpected critical region
- Steep learning curve; requires significant setup per new tool

---

### OpenMDAO

**Repository:** github.com/OpenMDAO/OpenMDAO  
**Origin:** NASA Glenn Research Center  
**Language:** Python

OpenMDAO is a framework for multidisciplinary design analysis and optimization, primarily used in aerospace. It supports derivative-based optimization, uncertainty propagation, and design-of-experiments.

**Limitations relevant to our work:**
- Requires models to be implemented as OpenMDAO Components — not a general adapter pattern
- No scenario discovery, no PRIM, no surprise scoring
- Domain-specific to engineering design optimization

---

### Rare Event Simulation and Adversarial Scenario Generation

A body of academic work addresses rare event simulation and safety-critical testing, particularly for autonomous systems. Methods include:

- **Importance Sampling** (Kroese, Rubinstein): reweights the probability distribution to oversample rare tail events. Effective when the rare event region is known in advance; less suited when the goal is *discovery* of an unknown surprising region.
- **Adaptive Stress Testing** (Lee et al., 2019): uses reinforcement learning to find failure scenarios for autonomous vehicles by learning adversarial input policies. Requires a differentiable or RL-compatible simulator.
- **CARLA-based adversarial testing** (various Waymo, Uber ATG, academic work): generates adversarial scenarios in driving simulation. Specific to autonomous vehicle simulation, not generalizable.
- **Falsification methods** (e.g., S-TaLiRo, Breach): search for inputs that violate a temporal logic specification. Require formal specification of the bad outcome and usually a smooth simulation response surface.

**Common limitations:**
- Domain-specific (autonomous vehicles, aerospace) or require formal specification
- Do not frame the problem as surprise-driven — they find any failure, not the *unexpected* failure
- No concept of scenario potential or element potential
- No AI-assisted interpretation of discovered regions

---

### PRIM — Patient Rule Induction Method

**Origin:** Friedman & Fisher (1999), *Data Mining and Knowledge Discovery*

The original PRIM algorithm peels the input space to find a hyper-box with elevated mean response. It is the methodological ancestor of PRIM and is implemented in EMA Workbench.

Standard PRIM maximizes the mean value of the critical outcome metric inside the box — it converges on the region of *highest impact*, which is typically the region domain experts already know about (set all high-impact inputs to their worst values).

Foytik et al. replace the PRIM objective with maximization of mean *surprise score* Z(x), which penalizes boxes populated by high-potential scenarios. This reorientation makes the algorithm specifically useful for discovering non-obvious critical scenarios — the blind spot of standard PRIM and all tools derived from it.

---

## The Gap MS Harness Fills

The table below maps capabilities to existing tools.

| Capability | EMA Workbench | SALib | Dakota | Rare Event / Adversarial | MS Harness |
|---|:---:|:---:|:---:|:---:|:---:|
| File-based / subprocess tool coupling | — | — | Partial | — | Yes |
| LHS sweep design | Yes | Yes | Yes | — | Yes |
| Scenario discovery (critical region) | PRIM | — | — | Partial | PRIM |
| Surprise-score objective (not just density) | — | — | — | — | Yes |
| Element potential (node importance) | — | — | — | — | Yes |
| Adaptive sweep (box → follow-up) | — | — | — | Partial | Yes |
| AI findings interpretation | — | — | — | — | Yes |
| AI onboarding (config generation) | — | — | — | — | Yes |
| AI adapter code generation | — | — | — | — | Yes |
| Tool-agnostic (any domain) | Partial | Yes | Partial | — | Yes |
| SME-friendly configuration | — | Partial | — | — | Yes |

**Three specific gaps addressed:**

1. **The surprise gap.** No existing scenario discovery tool distinguishes between *expected* critical scenarios (high-impact inputs in their worst state) and *surprising* ones (combinations of low-importance inputs that produce equally bad outcomes). PRIM's scenario potential formulation is the only published method targeting this distinction. MS Harness is the first harness built around it.

2. **The loose-coupling gap.** File-based M&S tools — the dominant form in defense, infrastructure, and operations research — have no supported path into existing Python-native frameworks without substantial custom integration work. Dakota's file interface is the closest precedent but provides none of the scenario discovery or AI capabilities. The three-file adapter pattern (input_processor / run_model.sh / output_processor) reduces this integration to a tractable 1–2 hour task for any file-based tool.

3. **The AI interpretation gap.** Even in tools that perform scenario discovery, the output is a hyper-box of parameter bounds. Converting those bounds into actionable operational insight requires the modeler to interpret them manually against their domain knowledge. MS Harness closes this loop by passing the PRIM findings and SME context directly to an LLM for grounded natural-language interpretation, targeted follow-up sweep proposals, and free-form Q&A about the results.

---

## References

- Friedman, J.H. & Fisher, N.I. (1999). Bump hunting in high-dimensional data. *Statistics and Computing*, 9(2), 123–143.
- Foytik, P. et al. Discovering More Critical Scenarios in Critical Infrastructure Simulations Using Scenario Potential. *(in preparation)*
- Kwakkel, J.H. (2017). The Exploratory Modeling Workbench: An open source toolkit for exploratory modeling, scenario discovery, and (multi-objective) robust decision making. *Environmental Modelling & Software*, 96, 239–250.
- Herman, J. & Usher, W. (2017). SALib: An open-source Python library for sensitivity analysis. *Journal of Open Source Software*, 2(9), 97.
- Lee, R., Mengshoel, O.J., Saksena, A., Gardner, R., Genin, D., Silbermann, J., Owen, M., & Kochenderfer, M. (2019). Adaptive stress testing: Finding likely failure events with reinforcement learning. *arXiv:1811.02188*.

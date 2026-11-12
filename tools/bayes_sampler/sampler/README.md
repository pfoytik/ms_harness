# Bayesian attack network sampler and network generator (copied)

These files were developed by Ross Gore and are bundled here so the `bayes_sampler` adapter is self-contained:

- Author: Ross Gore (co-author and colleague on this work)
- Source revision: `aaea92e69816ef8698a17b99c5014d34ce0c0b76`
- Changes from the source: the files were renamed and flattened into this folder (see the table). In comments, help text and one local parameter name (`readJson(attackLadderFile)` became `readJson(networkFile)` in `netGen.py`), "attack ladder" was changed to "attack network". There are no functional changes.

| File here | Original path | Used for |
|---|---|---|
| `headless_sampler.js` | `headless_js/headless_sampler.js` | Monte Carlo sampling of a Bayesian attack network. `run_model.sh` uses it when `adapter_config.sampler_path` is omitted or empty |
| `netGen.py` | `netGen/netGen/netGen.py` | Generating random attack networks (`--function createRandAG`) |
| `package.json` | (minimal, written for this copy) | Declares `"type": "module"`, which `headless_sampler.js` needs to load as an ES module. The original project declares this in its own `package.json`. |

Requirements: Node.js (v19.3 was used; the sampler has no npm dependencies) and, for netGen, Python with `networkx`, `numpy` and `matplotlib`.

`headless_sampler.js` at this commit takes six arguments: `<network.json> <n_samples> <fixedNodesFile|NA> <mitreGroupFile|NA> <samplesOut.json> <summaryOut.json>`. `run_model.sh` detects this signature and passes `NA NA`.

`netGen.py` does not seed its random generator, so it cannot regenerate `../nets/net_local_02.json` exactly. Use the archived network.

To generate a new network (from the repository root):

```bash
python tools/bayes_sampler/sampler/netGen.py --function createRandAG --filename tools/bayes_sampler/nets/my_net.json
```

The exit count is random. Screen generated networks for a small number of exits; with many exits, resilience is near 0% almost everywhere.
